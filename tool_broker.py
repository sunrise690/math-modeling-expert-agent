from __future__ import annotations

import json
import re
import secrets
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Protocol


MAX_BROKER_REQUEST_BYTES = 1_000_000
DEFAULT_BROKER_TIMEOUT = 190.0
BROKER_TOOL_NAMES = frozenset(
    {
        "search_materials",
        "read_material",
        "search_skills",
        "read_skill",
        "read_skill_reference",
        "inspect_dataset",
        "run_python",
        "solve_linear_program",
        "create_plot_from_dataset",
        "create_plot",
        "export_report",
    }
)


class RegistryProtocol(Protocol):
    def execute(self, name: str, arguments: dict[str, Any], run_id: str) -> dict[str, Any]: ...


class ToolBrokerError(RuntimeError):
    pass


def _validated_run_id(value: str) -> str:
    run_id = str(value).strip().lower()
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise ToolBrokerError("工具代理任务 ID 无效")
    return run_id


def _validated_broker_root(value: Path) -> Path:
    root = Path(value).resolve()
    if root.is_symlink():
        raise ToolBrokerError("工具代理目录不能是符号链接")
    root.mkdir(parents=True, exist_ok=True)
    for name in ("requests", "responses"):
        child = (root / name).resolve()
        if child.parent != root:
            raise ToolBrokerError("工具代理目录越界")
        child.mkdir(exist_ok=True)
    return root


class FileToolBroker:
    """Execute a fixed tool allowlist outside the nested Codex sandbox."""

    def __init__(self, registry: RegistryProtocol, run_id: str, broker_root: Path) -> None:
        self.registry = registry
        self.run_id = _validated_run_id(run_id)
        self.root = _validated_broker_root(broker_root)
        self.token = secrets.token_urlsafe(32)
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._serve,
            daemon=True,
            name=f"tool-broker-{self.run_id[:8]}",
        )

    def start(self) -> "FileToolBroker":
        self._thread.start()
        return self

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        self._thread.join(timeout=max(0.0, timeout))

    def _serve(self) -> None:
        request_root = self.root / "requests"
        while not self._stop.is_set():
            found = False
            for request_path in request_root.glob("*.json"):
                found = True
                self._process(request_path)
            if not found:
                self._stop.wait(0.02)

    def _process(self, request_path: Path) -> None:
        request_id = request_path.stem
        if not re.fullmatch(r"[a-f0-9]{32}", request_id):
            request_path.unlink(missing_ok=True)
            return
        response: dict[str, Any]
        try:
            if request_path.is_symlink() or request_path.stat().st_size > MAX_BROKER_REQUEST_BYTES:
                raise ToolBrokerError("工具代理请求无效")
            payload = json.loads(request_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or not secrets.compare_digest(str(payload.get("token", "")), self.token):
                raise ToolBrokerError("工具代理认证失败")
            name = str(payload.get("name", ""))
            arguments = payload.get("arguments")
            if name not in BROKER_TOOL_NAMES or not isinstance(arguments, dict):
                raise ToolBrokerError("工具不在代理白名单中")
            result = self.registry.execute(name, arguments, self.run_id)
            result.setdefault("ok", True)
            response = {"ok": True, "result": result}
        except Exception as error:
            response = {"ok": False, "error": str(error).strip()[:500] or "工具代理执行失败"}
        finally:
            request_path.unlink(missing_ok=True)
        target = self.root / "responses" / f"{request_id}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)


def call_file_tool_broker(
    broker_root: Path,
    token: str,
    name: str,
    arguments: dict[str, Any],
    *,
    timeout: float = DEFAULT_BROKER_TIMEOUT,
) -> dict[str, Any]:
    root = _validated_broker_root(broker_root)
    if name not in BROKER_TOOL_NAMES:
        raise ToolBrokerError("工具不在代理白名单中")
    if not token or not isinstance(arguments, dict):
        raise ToolBrokerError("工具代理参数无效")
    request_id = uuid.uuid4().hex
    payload = {"token": token, "name": name, "arguments": arguments}
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_BROKER_REQUEST_BYTES:
        raise ToolBrokerError("工具代理请求过大")
    target = root / "requests" / f"{request_id}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(encoded)
    temporary.replace(target)
    response_path = root / "responses" / f"{request_id}.json"
    deadline = time.monotonic() + max(1.0, float(timeout))
    while time.monotonic() < deadline:
        if response_path.is_file():
            try:
                response = json.loads(response_path.read_text(encoding="utf-8"))
            finally:
                response_path.unlink(missing_ok=True)
            if not isinstance(response, dict) or not response.get("ok"):
                raise ToolBrokerError(str(response.get("error", "工具代理执行失败"))[:500])
            result = response.get("result")
            if not isinstance(result, dict):
                raise ToolBrokerError("工具代理返回无效结果")
            return result
        time.sleep(0.02)
    target.unlink(missing_ok=True)
    raise ToolBrokerError("工具代理响应超时")
