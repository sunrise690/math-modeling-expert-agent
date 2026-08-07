from __future__ import annotations

import argparse
import ipaddress
import json
import mimetypes
import re
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from agent_tools import MAX_UPLOAD_BYTES, ToolError
from quality_scoring import rubric_spec
from provider_config import ProviderConfigError, ProviderConfigStore, codex_cli_status
from provider_config import public_codex_status
from http_safety import safe_http_error, scrub_diagnostic, urlopen_no_redirect

from agent_backend import (
    MODES,
    ROOT,
    TERMINAL_STATUSES,
    AgentSettings,
    ApiError,
    RunManager,
    RunStore,
)


RUN_PATH = re.compile(r"^/api/runs/([a-f0-9]{32})$")
RUN_EVENTS_PATH = re.compile(r"^/api/runs/([a-f0-9]{32})/events$")
RUN_CANCEL_PATH = re.compile(r"^/api/runs/([a-f0-9]{32})/cancel$")
RUN_ARTIFACTS_PATH = re.compile(r"^/api/runs/([a-f0-9]{32})/artifacts$")
ARTIFACT_PATH = re.compile(r"^/api/artifacts/([a-f0-9]{32})/([^/]+)$")
UPLOAD_PATH = re.compile(r"^/api/uploads/([a-f0-9]{32})$")


class AgentHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], manager: RunManager) -> None:
        super().__init__(address, Handler)
        self.manager = manager
        self.provider_config = ProviderConfigStore(manager.root)


class Handler(BaseHTTPRequestHandler):
    server_version = "MathModelingAgent/0.8"
    server: AgentHTTPServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            self.require_same_origin()
            if parsed.path == "/api/health":
                settings = AgentSettings.load(self.server.manager.root)
                tool_definitions = self.server.manager.tools.definitions()
                self.send_json(
                    {
                        "ok": True,
                        "service": "math-modeling-agent",
                        "version": "0.8",
                        "configured": settings.configured,
                        "tools": len(tool_definitions),
                        "mcp": self.server.manager.tools.mcp_status(),
                        "knowledge": self.server.manager.tools.knowledge_status(),
                        "runtime": self.server.manager.runtime_status(),
                        "quality": {
                            "enabled": settings.quality_enabled,
                            "threshold": settings.quality_threshold,
                            "maxRevisions": settings.max_revisions,
                        },
                    }
                )
                return
            if parsed.path == "/api/config":
                settings = AgentSettings.load(self.server.manager.root)
                self.send_json(self.server.provider_config.public_config(settings.public_dict()))
                return
            if parsed.path == "/api/modes":
                self.send_json({"modes": MODES})
                return
            if parsed.path == "/api/rubric":
                self.send_json(rubric_spec())
                return
            if parsed.path == "/api/tools":
                self.send_json(
                    {
                        "tools": [
                            {
                                "name": item["function"]["name"],
                                "description": item["function"]["description"],
                            }
                            for item in self.server.manager.tools.definitions()
                        ]
                    }
                )
                return
            if parsed.path == "/api/mcp":
                self.send_json({"servers": self.server.manager.tools.mcp_status(probe=True)})
                return
            if parsed.path == "/api/runtime":
                self.send_json(self.server.manager.runtime_status())
                return
            if parsed.path in {"/api/knowledge", "/api/knowledge/status"}:
                self.send_json(self.server.manager.tools.knowledge_status())
                return
            if parsed.path == "/api/knowledge/search":
                search_query = query.get("q", [""])[0]
                limit = self._query_int(query, "limit", 5)
                extensions = query.get("extension", [])
                self.send_json(
                    self.server.manager.tools.search_knowledge(
                        search_query,
                        limit,
                        extensions or None,
                    )
                )
                return
            if parsed.path == "/api/runs":
                limit = self._query_int(query, "limit", 20)
                self.send_json({"runs": self.server.manager.store.list(limit)})
                return
            match = RUN_EVENTS_PATH.fullmatch(parsed.path)
            if match:
                after = self._query_int(query, "after", 0)
                last_event_id = self.headers.get("Last-Event-ID", "").strip()
                if last_event_id.isdigit():
                    after = max(after, int(last_event_id))
                self.stream_events(match.group(1), after)
                return
            match = RUN_ARTIFACTS_PATH.fullmatch(parsed.path)
            if match:
                self.server.manager.store.get(match.group(1))
                self.send_json({"artifacts": self.server.manager.tools.list_artifacts(match.group(1))})
                return
            match = ARTIFACT_PATH.fullmatch(parsed.path)
            if match:
                target = self.server.manager.tools.artifact_path(match.group(1), unquote(match.group(2)))
                self.serve_file(target, cache="private, max-age=3600")
                return
            match = UPLOAD_PATH.fullmatch(parsed.path)
            if match:
                self.send_json({"upload": self.server.manager.tools.get_upload(match.group(1))})
                return
            match = RUN_PATH.fullmatch(parsed.path)
            if match:
                self.send_json({"run": self.server.manager.store.get(match.group(1))})
                return
            if parsed.path == "/favicon.ico":
                self.send_response(204)
                self.send_cors_headers()
                self.end_headers()
                return

            self.serve_static(parsed.path)
        except ApiError as error:
            self.send_error_json(error.status, error.message)
        except ToolError as error:
            self.send_error_json(404, str(error))
        except (ValueError, TypeError):
            self.send_error_json(400, "请求参数无效")
        except Exception as error:
            self.log_error("GET failed: %s", error)
            self.send_error_json(500, "服务器错误")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            self.require_same_origin()
            if parsed.path == "/api/config":
                payload = self.read_json()
                self.server.provider_config.save(payload)
                settings = AgentSettings.load(self.server.manager.root)
                self.send_json({"config": self.server.provider_config.public_config(settings.public_dict())})
                return
            if parsed.path == "/api/config/test":
                payload = self.read_json()
                values = self.server.provider_config.preview_values(payload)
                settings = AgentSettings.load(self.server.manager.root, overrides=values)
                self.send_json({"test": self.test_provider_connection(settings)})
                return
            if parsed.path in {"/api/knowledge/reindex", "/api/knowledge/index"}:
                self.send_json(
                    {"job": self.server.manager.tools.start_knowledge_reindex()},
                    status=202,
                )
                return
            if parsed.path == "/api/uploads":
                filename = unquote(self.headers.get("X-Filename", "")).strip()
                if not filename:
                    raise ApiError(400, "缺少文件名")
                upload = self.server.manager.tools.save_upload(
                    filename,
                    self.headers.get("Content-Type", "application/octet-stream"),
                    self.read_bytes(MAX_UPLOAD_BYTES),
                )
                try:
                    inspection = self.server.manager.tools.execute(
                        "inspect_dataset",
                        {"upload_id": upload["id"], "sample_rows": 3},
                        "0" * 32,
                    )
                except Exception as error:
                    self.server.manager.tools.delete_upload(upload["id"])
                    raise ApiError(422, str(error).strip() or "无法读取数据文件") from error
                self.send_json({"upload": upload, "inspection": inspection}, status=201)
                return
            if parsed.path == "/api/prompt":
                self.send_json(self.server.manager.prepare(self.read_json()))
                return
            if parsed.path == "/api/runs":
                run = self.server.manager.create(self.read_json())
                self.send_json({"run": run}, status=202)
                return
            match = RUN_CANCEL_PATH.fullmatch(parsed.path)
            if match:
                run = self.server.manager.cancel(match.group(1))
                self.send_json({"run": run}, status=202)
                return
            self.send_error_json(404, "接口不存在")
        except ApiError as error:
            self.send_error_json(error.status, error.message)
        except json.JSONDecodeError:
            self.send_error_json(400, "JSON 无效")
        except UnicodeDecodeError:
            self.send_error_json(400, "请求必须使用 UTF-8")
        except ToolError as error:
            self.send_error_json(400, str(error))
        except ProviderConfigError as error:
            self.send_error_json(400, str(error))
        except Exception as error:
            self.log_error("POST failed: %s", error)
            self.send_error_json(500, "服务器错误")

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        try:
            self.require_same_origin()
            upload_match = UPLOAD_PATH.fullmatch(parsed.path)
            if upload_match:
                self.server.manager.tools.delete_upload(upload_match.group(1))
                self.send_response(204)
                self.send_cors_headers()
                self.end_headers()
                return
            match = RUN_PATH.fullmatch(parsed.path)
            if not match:
                self.send_error_json(404, "接口不存在")
                return
            run = self.server.manager.store.get(match.group(1))
            self.server.manager.store.delete(match.group(1))
            self.server.manager.tools.delete_artifacts(match.group(1))
            for upload in run.get("meta", {}).get("uploads", []):
                try:
                    self.server.manager.tools.delete_upload(str(upload.get("id", "")))
                except ToolError:
                    pass
            self.send_response(204)
            self.send_cors_headers()
            self.end_headers()
        except ApiError as error:
            self.send_error_json(error.status, error.message)
        except ToolError as error:
            self.send_error_json(404, str(error))

    def do_OPTIONS(self) -> None:
        try:
            self.require_same_origin()
            self.send_response(204)
            self.send_cors_headers()
            self.end_headers()
        except ApiError as error:
            self.send_error_json(error.status, error.message)

    def stream_events(self, run_id: str, after: int) -> None:
        self.server.manager.store.get(run_id)
        self.send_response(200)
        self.send_cors_headers()
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        self.close_connection = True

        cursor = after
        try:
            while True:
                events = self.server.manager.store.events_after(run_id, cursor)
                for event in events:
                    cursor = event["seq"]
                    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                    message = f"id: {cursor}\nevent: agent\ndata: {data}\n\n".encode("utf-8")
                    self.wfile.write(message)
                if events:
                    self.wfile.flush()

                run = self.server.manager.store.get(run_id)
                if run["status"] in TERMINAL_STATUSES:
                    break

                if not events:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                self.server.manager.wait_for_change(run_id, timeout=10.0)
        except (BrokenPipeError, ConnectionResetError):
            return

    def read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as error:
            raise ApiError(400, "Content-Length 无效") from error
        if length < 0 or length > 1_000_000:
            raise ApiError(413, "请求过大")
        body = self.rfile.read(length)
        data = json.loads(body.decode("utf-8") if body else "{}")
        if not isinstance(data, dict):
            raise ApiError(400, "JSON 必须是对象")
        return data

    def read_bytes(self, maximum: int) -> bytes:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as error:
            raise ApiError(400, "Content-Length 无效") from error
        if length <= 0:
            raise ApiError(400, "上传文件为空")
        if length > maximum:
            raise ApiError(413, "单个附件不能超过 25 MB")
        content = self.rfile.read(length)
        if len(content) != length:
            raise ApiError(400, "上传内容不完整")
        return content

    def test_provider_connection(self, settings: AgentSettings) -> dict[str, Any]:
        started = time.monotonic()
        if settings.provider == "codex-cli":
            status = codex_cli_status(settings.codex_cli_path, force=True)
            models = status.get("models", []) if isinstance(status.get("models"), list) else []
            model_ids = {str(item.get("id", "")) for item in models if isinstance(item, dict)}
            available = bool(status.get("authenticated")) and bool(status.get("invokable"))
            reason = str(status.get("reason", ""))
            if available and settings.model and model_ids and settings.model not in model_ids:
                available = False
                reason = f"当前 Codex 账号不提供模型：{settings.model}"
            default_model = next(
                (str(item.get("id", "")) for item in models if isinstance(item, dict) and item.get("isDefault")),
                "gpt-5.6-sol",
            )
            return {
                "ok": available,
                "latencyMs": round((time.monotonic() - started) * 1000),
                "reason": reason,
                "codexLogin": public_codex_status(status),
                "models": models,
                "defaultModel": default_model,
            }

        if not settings.base_url:
            return {"ok": False, "latencyMs": 0, "reason": "基础 URL 不能为空", "models": []}
        endpoint = settings.base_url if settings.base_url.endswith("/models") else f"{settings.base_url}/models"
        headers = {"Accept": "application/json", "User-Agent": "MathModelingAgent/0.8"}
        if settings.api_key:
            headers["Authorization"] = f"Bearer {settings.api_key}"
        request = urllib.request.Request(endpoint, headers=headers, method="GET")
        try:
            with urlopen_no_redirect(request, timeout=min(20.0, settings.timeout)) as response:
                raw = response.read(1_000_000)
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            raw_models = payload.get("data", payload.get("models", [])) if isinstance(payload, dict) else []
            models = []
            for item in raw_models if isinstance(raw_models, list) else []:
                if isinstance(item, dict):
                    model_id = str(item.get("id", item.get("name", ""))).strip()
                else:
                    model_id = str(item).strip()
                if model_id:
                    models.append({"id": model_id, "displayName": model_id})
            reason = ""
            if settings.model and models and settings.model not in {item["id"] for item in models}:
                reason = f"接口可连接，但模型列表中未找到 {settings.model}"
            return {
                "ok": True,
                "latencyMs": round((time.monotonic() - started) * 1000),
                "reason": reason,
                "models": models[:500],
                "defaultModel": settings.model or (models[0]["id"] if models else ""),
            }
        except urllib.error.HTTPError as error:
            error.close()
            return {
                "ok": False,
                "latencyMs": round((time.monotonic() - started) * 1000),
                "reason": safe_http_error(error, "模型接口"),
                "models": [],
            }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            return {
                "ok": False,
                "latencyMs": round((time.monotonic() - started) * 1000),
                "reason": f"无法验证模型接口：{scrub_diagnostic(str(error), settings.api_key, limit=180) or type(error).__name__}",
                "models": [],
            }

    def serve_static(self, request_path: str) -> None:
        path = unquote(request_path)
        if path in {"", "/"}:
            path = "/index.html"
        if path != "/index.html":
            raise ApiError(404, "文件不存在")
        target = self.server.manager.root / "index.html"
        self.serve_file(target)

    def serve_file(self, target: Path, cache: str = "no-store") -> None:
        mime_type, _ = mimetypes.guess_type(str(target))
        content = target.read_bytes()
        self.send_response(200)
        self.send_cors_headers()
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, data: Any, status: int = 200) -> None:
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def send_error_json(self, status: int, message: str) -> None:
        self.send_json({"ok": False, "error": message}, status=status)

    def send_cors_headers(self) -> None:
        origin = self.headers.get("Origin", "").strip()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Last-Event-ID, X-Filename")

    def require_same_origin(self) -> None:
        request_host = self.headers.get("Host", "").strip()
        host_parts = urlparse(f"//{request_host}")
        hostname = host_parts.hostname or ""
        try:
            loopback = hostname.casefold() == "localhost" or ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            loopback = False
        if not loopback:
            raise ApiError(403, "仅允许通过本机回环地址访问")
        origin = self.headers.get("Origin", "").strip()
        if not origin:
            return
        origin_parts = urlparse(origin)
        if origin_parts.scheme not in {"http", "https"} or origin_parts.netloc.casefold() != request_host.casefold():
            raise ApiError(403, "仅允许同源本地请求")

    @staticmethod
    def _query_int(query: dict[str, list[str]], key: str, default: int) -> int:
        raw = query.get(key, [str(default)])[0]
        value = int(raw)
        return max(0, value)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")


def create_server(host: str, port: int, database: Path | None = None) -> AgentHTTPServer:
    try:
        loopback = host.casefold() == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if not loopback:
        raise ValueError("为保护模型密钥与本地资料，服务只能监听回环地址")
    store = RunStore(database or ROOT / ".agent-data/runs.db")
    manager = RunManager(store, ROOT)
    return AgentHTTPServer((host, port), manager)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local math modeling agent backend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--database", type=Path, default=ROOT / ".agent-data/runs.db")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = create_server(args.host, args.port, args.database)
    print(f"Math modeling agent: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.manager.close()
        server.server_close()


if __name__ == "__main__":
    main()
