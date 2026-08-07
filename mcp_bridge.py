from __future__ import annotations

import asyncio
import atexit
import json
import os
import queue
import threading
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPBridgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    command: str
    args: tuple[str, ...] = ()
    cwd: str = ""
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    exposed_tools: frozenset[str] | None = None
    startup_timeout: float = 20.0
    call_timeout: float = 240.0


class MCPServerRuntime:
    def __init__(self, config: MCPServerConfig, log_dir: Path) -> None:
        self.config = config
        self.log_dir = log_dir
        self._requests: queue.Queue[tuple[str, dict[str, Any], Future[dict[str, Any]]] | None] = queue.Queue()
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._tools: list[dict[str, Any]] = []
        self._server_info: dict[str, Any] = {}
        self._state = "disabled" if not config.enabled else "idle"
        self._error = "" if config.enabled else "MCP Server 未安装或未启用"

    def start(self) -> None:
        if not self.config.enabled:
            return
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._ready.clear()
            self._state = "starting"
            self._error = ""
            self._thread = threading.Thread(
                target=self._thread_main,
                daemon=True,
                name=f"mcp-{self.config.name}",
            )
            self._thread.start()

    def list_tools(self) -> list[dict[str, Any]]:
        self.start()
        if not self.config.enabled:
            return []
        if not self._ready.wait(self.config.startup_timeout):
            raise MCPBridgeError(f"{self.config.name} MCP 初始化超时")
        if self._state != "ready":
            raise MCPBridgeError(self._error or f"{self.config.name} MCP 不可用")
        return list(self._tools)

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.list_tools()
        future: Future[dict[str, Any]] = Future()
        self._requests.put((name, arguments, future))
        try:
            return future.result(timeout=self.config.call_timeout + 5)
        except FutureTimeoutError as error:
            raise MCPBridgeError(f"{self.config.name}.{name} 调用超时") from error

    def status(self, probe: bool = False) -> dict[str, Any]:
        if probe and self.config.enabled and self._state != "ready":
            try:
                self.list_tools()
            except MCPBridgeError:
                pass
        return {
            "name": self.config.name,
            "enabled": self.config.enabled,
            "state": self._state,
            "available": self._state == "ready",
            "error": self._error,
            "server": self._server_info,
            "tools": [tool.get("name", "") for tool in self._tools],
        }

    def close(self) -> None:
        thread = self._thread
        if not thread or not thread.is_alive():
            return
        self._requests.put(None)
        thread.join(timeout=5)

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._serve())
        except Exception as error:
            self._mark_failed(error)

    async def _serve(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.log_dir / f"{self.config.name}.stderr.log"
        environment = os.environ.copy()
        environment.update(self.config.env)
        parameters = StdioServerParameters(
            command=self.config.command,
            args=list(self.config.args),
            env=environment,
            cwd=self.config.cwd or None,
        )
        with log_path.open("a", encoding="utf-8") as error_log:
            async with stdio_client(parameters, errlog=error_log) as streams:
                read_stream, write_stream = streams
                timeout = timedelta(seconds=self.config.call_timeout)
                async with ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timeout,
                ) as session:
                    initialized = await session.initialize()
                    listed = await session.list_tools()
                    tools = [tool.model_dump(by_alias=True, exclude_none=True) for tool in listed.tools]
                    if self.config.exposed_tools is not None:
                        tools = [tool for tool in tools if tool.get("name") in self.config.exposed_tools]
                    with self._lock:
                        self._tools = tools
                        self._server_info = initialized.serverInfo.model_dump(by_alias=True, exclude_none=True)
                        self._state = "ready"
                        self._error = ""
                        self._ready.set()

                    while True:
                        request = await asyncio.to_thread(self._requests.get)
                        if request is None:
                            break
                        name, arguments, future = request
                        if future.cancelled():
                            continue
                        try:
                            result = await session.call_tool(
                                name,
                                arguments,
                                read_timeout_seconds=timeout,
                            )
                            future.set_result(self._normalize_result(result))
                        except Exception as error:
                            future.set_exception(MCPBridgeError(str(error).strip() or "MCP 工具调用失败"))

    def _mark_failed(self, error: Exception) -> None:
        message = str(error).strip() or type(error).__name__
        with self._lock:
            self._state = "failed"
            self._error = message
            self._ready.set()
        while True:
            try:
                request = self._requests.get_nowait()
            except queue.Empty:
                break
            if request is not None:
                request[2].set_exception(MCPBridgeError(message))

    @staticmethod
    def _normalize_result(result: Any) -> dict[str, Any]:
        structured = getattr(result, "structuredContent", None)
        texts = [
            str(item.text)
            for item in getattr(result, "content", [])
            if getattr(item, "type", "") == "text" and getattr(item, "text", None)
        ]
        payload: dict[str, Any] = {
            "ok": not bool(getattr(result, "isError", False)),
            "content": "\n".join(texts).strip(),
        }
        if isinstance(structured, dict):
            payload["structured"] = structured
        elif structured is not None:
            payload["structured"] = json.loads(json.dumps(structured, ensure_ascii=False, default=str))
        if not payload["ok"]:
            payload["error"] = payload["content"] or "MCP 工具返回错误"
        return payload


class MCPToolManager:
    def __init__(self, configs: list[MCPServerConfig], log_dir: Path) -> None:
        self._runtimes = {config.name: MCPServerRuntime(config, log_dir) for config in configs}
        self._tool_routes: dict[str, tuple[str, str]] = {}
        atexit.register(self.close)

    def definitions(self) -> list[dict[str, Any]]:
        definitions: list[dict[str, Any]] = []
        routes: dict[str, tuple[str, str]] = {}
        used_names: set[str] = set()
        for server_name, runtime in self._runtimes.items():
            try:
                tools = runtime.list_tools()
            except MCPBridgeError:
                continue
            for tool in tools:
                original_name = str(tool.get("name", "")).strip()
                if not original_name:
                    continue
                public_name = original_name if original_name not in used_names else f"{server_name}_{original_name}"
                used_names.add(public_name)
                routes[public_name] = (server_name, original_name)
                definitions.append(
                    {
                        "type": "function",
                        "function": {
                            "name": public_name,
                            "description": f"[MCP:{server_name}] {tool.get('description', '')}".strip(),
                            "parameters": tool.get("inputSchema") or {"type": "object", "additionalProperties": False},
                        },
                    }
                )
        self._tool_routes = routes
        return definitions

    def call(self, public_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        route = self._tool_routes.get(public_name)
        if route is None:
            self.definitions()
            route = self._tool_routes.get(public_name)
        if route is None:
            raise MCPBridgeError(f"未知 MCP 工具：{public_name}")
        server_name, original_name = route
        result = self._runtimes[server_name].call(original_name, arguments)
        result["mcpServer"] = server_name
        result["mcpTool"] = original_name
        return result

    def call_server_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        runtime = self._runtimes.get(server_name)
        if runtime is None:
            raise MCPBridgeError(f"未知 MCP Server：{server_name}")
        result = runtime.call(tool_name, arguments)
        result["mcpServer"] = server_name
        result["mcpTool"] = tool_name
        return result

    def status(self, probe: bool = False) -> list[dict[str, Any]]:
        return [runtime.status(probe=probe) for runtime in self._runtimes.values()]

    def close(self) -> None:
        for runtime in self._runtimes.values():
            runtime.close()
