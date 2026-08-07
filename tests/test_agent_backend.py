from __future__ import annotations

import json
import io
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from agent_backend import (
    AgentSettings,
    ApiError,
    CodexCliProvider,
    OpenAICompatibleProvider,
    OpenAIResponsesProvider,
    ProviderError,
    ProviderToolEvent,
    RunManager,
    RunStore,
    build_prompt,
    build_system_prompt,
)


class FakeProvider:
    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings

    def stream(self, system_prompt, user_prompt, cancel_event, **kwargs):
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        yield "第一段"
        yield "，第二段。"


class SlowProvider:
    partial = "部分结果" * 20

    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings

    def stream(self, system_prompt, user_prompt, cancel_event, **kwargs):
        yield self.partial
        while not cancel_event.wait(0.01):
            pass


class QueueBlockingProvider:
    calls = 0
    started = threading.Event()
    release = threading.Event()
    lock = threading.Lock()

    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings

    @classmethod
    def reset(cls) -> None:
        cls.calls = 0
        cls.started = threading.Event()
        cls.release = threading.Event()

    def stream(self, system_prompt, user_prompt, cancel_event, **kwargs):
        with type(self).lock:
            type(self).calls += 1
        type(self).started.set()
        while not type(self).release.wait(0.01):
            if cancel_event.is_set():
                return
        yield "排队任务完成。"


class FakeModelHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for data in (
            '{"choices":[{"delta":{"content":"流式"}}]}',
            '{"choices":[{"delta":{"content":"结果"}}]}',
            "[DONE]",
        ):
            self.wfile.write(f"data: {data}\n\n".encode())
            self.wfile.flush()

    def log_message(self, format, *args):
        pass


class ToolCallingModelHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        has_tool_result = any(message.get("role") == "tool" for message in payload["messages"])
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        if has_tool_result:
            chunks = ['{"choices":[{"delta":{"content":"工具已使用"}}]}', "[DONE]"]
        else:
            chunks = [
                '{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"search_skills","arguments":"{\\"query\\":\\""}}]}}]}',
                '{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"优化\\"}"}}]}}]}',
                "[DONE]",
            ]
        for data in chunks:
            self.wfile.write(f"data: {data}\n\n".encode())
            self.wfile.flush()

    def log_message(self, format, *args):
        pass


class ResponsesToolCallingHandler(BaseHTTPRequestHandler):
    requests: list[dict] = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        type(self).requests.append(payload)
        has_tool_result = any(item.get("type") == "function_call_output" for item in payload.get("input", []))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        if has_tool_result:
            events = [
                {"type": "response.output_text.delta", "delta": "Responses 工具已使用"},
                {"type": "response.completed", "response": {"output": []}},
            ]
        else:
            function_call = {
                "type": "function_call",
                "id": "fc_1",
                "call_id": "call_1",
                "name": "search_skills",
                "arguments": '{"query":"优化"}',
            }
            events = [
                {"type": "response.output_item.done", "output_index": 0, "item": function_call},
                {"type": "response.completed", "response": {"output": [function_call]}},
            ]
        for event in events:
            self.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()

    def log_message(self, format, *args):
        pass


class SecretErrorHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.send_header("x-request-id", "req_safe_123")
        self.end_headers()
        self.wfile.write(b'{"error":"sk-never-expose-this-token /private/path"}')

    def log_message(self, format, *args):
        pass


class ImmediateCodexProcess:
    last_command: list[str] = []

    def __init__(self, command, **kwargs):
        type(self).last_command = list(command)
        self.stdin = io.StringIO()
        self.stdout = io.StringIO('{"type":"turn.completed"}\n')
        self.stderr = io.StringIO("")
        self.returncode = 0

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


class BlockingCodexStream:
    def __init__(self, stopped: threading.Event):
        self.stopped = stopped

    def __iter__(self):
        while not self.stopped.wait(0.01):
            pass
        return
        yield ""


class BlockingCodexProcess:
    def __init__(self, command, **kwargs):
        self.stopped = threading.Event()
        self.stdin = io.StringIO()
        self.stdout = BlockingCodexStream(self.stopped)
        self.stderr = io.StringIO("")
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -15
        self.stopped.set()

    def kill(self):
        self.returncode = -9
        self.stopped.set()

    def wait(self, timeout=None):
        if self.returncode is None and not self.stopped.wait(timeout):
            raise TimeoutError()
        return self.returncode


class FakeToolRegistry:
    def definitions(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_skills",
                    "description": "search",
                    "parameters": {"type": "object"},
                },
            }
        ]

    def execute(self, name, arguments, run_id):
        return {"ok": True, "skills": ["pymoo"], "query": arguments["query"]}


class AgentBackendTests(unittest.TestCase):
    def test_system_prompt_loads_project_expert_contract(self) -> None:
        prompt = build_system_prompt("solver")
        self.assertIn("<expert_skill>", prompt)
        self.assertIn("题目—模型—计算—证据—结论", prompt)

    def test_settings_loads_scheduler_limits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text(
                "AGENT_MAX_CONCURRENT_RUNS=3\nAGENT_MAX_QUEUED_RUNS=7\n",
                encoding="utf-8",
            )
            settings = AgentSettings.load(root)
            self.assertEqual(settings.max_concurrent_runs, 3)
            self.assertEqual(settings.max_queued_runs, 7)
            self.assertEqual(settings.public_dict()["maxConcurrentRuns"], 3)

    def test_build_prompt_validates_and_deduplicates(self) -> None:
        result = build_prompt(
            {
                "mode": "solver",
                "content": "分析这道题",
                "depth": "详细",
                "requirements": ["代码实现", "代码实现", "未知要求"],
            }
        )
        self.assertEqual(result["mode"], "solver")
        self.assertEqual(result["meta"]["requirements"], ["代码实现"])
        self.assertIn("分析这道题", result["prompt"])

        with self.assertRaises(ApiError):
            build_prompt({"mode": "solver", "content": ""})

    def test_build_prompt_accepts_resolved_upload_without_text(self) -> None:
        result = build_prompt(
            {
                "mode": "solver",
                "content": "",
                "_uploads": [
                    {
                        "id": "a" * 32,
                        "name": "data.csv",
                        "size": 128,
                        "mimeType": "text/csv",
                    }
                ],
            }
        )
        self.assertEqual(result["meta"]["dataState"], "有数据文件")
        self.assertEqual(result["meta"]["uploads"][0]["name"], "data.csv")
        self.assertIn("inspect_dataset", result["prompt"])

    def test_settings_never_exposes_api_key(self) -> None:
        settings = AgentSettings(
            provider="openai-compatible",
            base_url="https://example.com/v1",
            api_key="secret",
            model="test-model",
        )
        public = settings.public_dict()
        self.assertTrue(public["configured"])
        self.assertNotIn("api_key", public)
        self.assertNotIn("secret", str(public))

    def test_stream_chunk_parser(self) -> None:
        payload = {"choices": [{"delta": {"content": "结果"}}]}
        self.assertEqual(OpenAICompatibleProvider._extract_text(payload), "结果")

    def test_provider_reads_openai_compatible_stream(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeModelHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            settings = AgentSettings(
                "test",
                f"http://127.0.0.1:{server.server_port}/v1",
                "",
                "fake-model",
            )
            provider = OpenAICompatibleProvider(settings)
            result = "".join(provider.stream("system", "user", threading.Event()))
            self.assertEqual(result, "流式结果")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_provider_does_not_expose_remote_error_body(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), SecretErrorHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            settings = AgentSettings(
                "test",
                f"http://127.0.0.1:{server.server_port}/v1",
                "local-test-key",
                "fake-model",
            )
            provider = OpenAICompatibleProvider(settings)
            with self.assertRaises(ProviderError) as raised:
                list(provider.stream("system", "user", threading.Event()))
            public_error = str(raised.exception)
            self.assertIn("HTTP 401", public_error)
            self.assertIn("req_safe_123", public_error)
            self.assertNotIn("never-expose", public_error)
            self.assertNotIn("private/path", public_error)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_codex_specialist_mcp_respects_tools_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = AgentSettings(
                provider="codex-cli",
                base_url="",
                api_key="",
                model="gpt-test",
                tools_enabled=False,
                codex_available=True,
                codex_logged_in=True,
                project_root=str(root),
                codex_fast_http=False,
            )
            provider = CodexCliProvider(settings)
            with patch.object(provider, "_resolve_executable", return_value="C:\\safe\\codex.exe"), patch(
                "agent_backend.subprocess.Popen",
                side_effect=ImmediateCodexProcess,
            ):
                self.assertEqual(
                    list(
                        provider.stream(
                            "system",
                            "user",
                            threading.Event(),
                            tool_registry=FakeToolRegistry(),
                            run_id="a" * 32,
                        )
                    ),
                    [],
                )
            command_text = "\n".join(ImmediateCodexProcess.last_command)
            self.assertNotIn("mcp_servers.math_modeling", command_text)

    def test_codex_total_timeout_terminates_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = AgentSettings(
                provider="codex-cli",
                base_url="",
                api_key="",
                model="gpt-test",
                timeout=0.05,
                tools_enabled=False,
                codex_available=True,
                codex_logged_in=True,
                project_root=temp_dir,
                codex_fast_http=False,
            )
            provider = CodexCliProvider(settings)
            with patch.object(provider, "_resolve_executable", return_value="C:\\safe\\codex.exe"), patch(
                "agent_backend.subprocess.Popen",
                side_effect=BlockingCodexProcess,
            ):
                with self.assertRaisesRegex(ProviderError, "响应超时"):
                    list(provider.stream("system", "user", threading.Event(), run_id="b" * 32))

    def test_provider_executes_streamed_tool_call(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), ToolCallingModelHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            settings = AgentSettings("test", f"http://127.0.0.1:{server.server_port}/v1", "", "fake-model")
            provider = OpenAICompatibleProvider(settings)
            events = list(
                provider.stream(
                    "system",
                    "user",
                    threading.Event(),
                    tool_registry=FakeToolRegistry(),
                    run_id="a" * 32,
                )
            )
            tool_events = [event for event in events if isinstance(event, ProviderToolEvent)]
            text = "".join(event for event in events if isinstance(event, str))
            self.assertEqual([event.phase for event in tool_events], ["started", "finished"])
            self.assertEqual(tool_events[-1].result["skills"], ["pymoo"])
            self.assertEqual(text, "工具已使用")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_responses_provider_uses_flat_tools_and_continues_function_call(self) -> None:
        ResponsesToolCallingHandler.requests = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), ResponsesToolCallingHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            settings = AgentSettings(
                "openai-responses",
                f"http://127.0.0.1:{server.server_port}/v1",
                "",
                "fake-model",
            )
            provider = OpenAIResponsesProvider(settings)
            events = list(
                provider.stream(
                    "system",
                    "user",
                    threading.Event(),
                    tool_registry=FakeToolRegistry(),
                    run_id="a" * 32,
                )
            )
            text = "".join(item for item in events if isinstance(item, str))
            tool_events = [item for item in events if isinstance(item, ProviderToolEvent)]
            self.assertEqual(text, "Responses 工具已使用")
            self.assertEqual([item.phase for item in tool_events], ["started", "finished"])
            first_request, second_request = ResponsesToolCallingHandler.requests
            self.assertEqual(first_request["tools"][0]["type"], "function")
            self.assertEqual(first_request["tools"][0]["name"], "search_skills")
            self.assertNotIn("function", first_request["tools"][0])
            self.assertTrue(any(item.get("type") == "function_call_output" for item in second_request["input"]))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_run_lifecycle_persists_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = RunStore(root / "runs.db")
            settings = AgentSettings(
                provider="test",
                base_url="http://127.0.0.1:1/v1",
                api_key="",
                model="fake-model",
            )
            manager = RunManager(
                store,
                root,
                settings_loader=lambda: settings,
                provider_factory=FakeProvider,
            )
            run = manager.create({"mode": "paper", "content": "润色摘要"})

            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                current = store.get(run["id"])
                if current["status"] == "completed":
                    break
                time.sleep(0.01)
            else:
                self.fail("run did not complete")

            self.assertEqual(current["output"], "第一段，第二段。")
            event_types = [event["type"] for event in store.events_after(run["id"], 0)]
            self.assertEqual(event_types[0], "RUN_QUEUED")
            self.assertIn("TEXT_MESSAGE_CONTENT", event_types)
            self.assertEqual(event_types[-1], "RUN_FINISHED")

    def test_run_resolves_uploaded_dataset_into_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = RunStore(root / "runs.db")
            settings = AgentSettings("test", "http://127.0.0.1:1/v1", "", "fake-model")
            manager = RunManager(
                store,
                root,
                settings_loader=lambda: settings,
                provider_factory=FakeProvider,
            )
            upload = manager.tools.save_upload("data.csv", "text/csv", b"x,y\n1,2\n")
            run = manager.create({"mode": "solver", "content": "", "uploads": [upload["id"]]})

            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                current = store.get(run["id"])
                if current["status"] == "completed":
                    break
                time.sleep(0.01)
            else:
                self.fail("run did not complete")

            self.assertEqual(current["meta"]["uploads"][0]["id"], upload["id"])
            self.assertEqual(current["meta"]["dataState"], "有数据文件")

    def test_run_can_be_cancelled_without_losing_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = RunStore(root / "runs.db")
            settings = AgentSettings("test", "http://127.0.0.1:1/v1", "", "fake-model")
            manager = RunManager(
                store,
                root,
                settings_loader=lambda: settings,
                provider_factory=SlowProvider,
            )
            run = manager.create({"mode": "solver", "content": "测试取消"})

            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                current = store.get(run["id"])
                if current["output"]:
                    break
                time.sleep(0.01)
            manager.cancel(run["id"])

            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                current = store.get(run["id"])
                if current["status"] == "cancelled":
                    break
                time.sleep(0.01)
            self.assertEqual(current["status"], "cancelled")
            self.assertEqual(current["output"], SlowProvider.partial)

    def test_bounded_scheduler_rejects_overload_and_cancels_queued_run(self) -> None:
        QueueBlockingProvider.reset()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = RunStore(root / "runs.db")
            settings = AgentSettings(
                "test",
                "http://127.0.0.1:1/v1",
                "",
                "fake-model",
                quality_enabled=False,
            )
            manager = RunManager(
                store,
                root,
                settings_loader=lambda: settings,
                provider_factory=QueueBlockingProvider,
                max_workers=1,
                max_queued_runs=1,
            )
            try:
                first = manager.create({"mode": "solver", "content": "第一个任务"})
                self.assertTrue(QueueBlockingProvider.started.wait(1))
                second = manager.create({"mode": "solver", "content": "第二个任务"})

                runtime = manager.runtime_status()
                self.assertEqual(runtime["activeCount"], 1)
                self.assertEqual(runtime["queuedCount"], 1)
                self.assertEqual(runtime["availableSlots"], 0)
                with self.assertRaises(ApiError) as raised:
                    manager.create({"mode": "solver", "content": "第三个任务"})
                self.assertEqual(raised.exception.status, 429)

                cancelled = manager.cancel(second["id"])
                self.assertEqual(cancelled["status"], "cancelled")
                self.assertEqual(manager.runtime_status()["queuedCount"], 0)
                self.assertEqual(QueueBlockingProvider.calls, 1)
                event = store.events_after(second["id"], 0)[-1]
                self.assertEqual(event["type"], "RUN_CANCELLED")
                self.assertEqual(event["stage"], "queued")

                QueueBlockingProvider.release.set()
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    if store.get(first["id"])["status"] == "completed":
                        break
                    time.sleep(0.01)
                self.assertEqual(store.get(first["id"])["status"], "completed")
                self.assertEqual(manager.runtime_status()["availableSlots"], 2)
            finally:
                QueueBlockingProvider.release.set()
                manager.close()

    def test_scheduler_close_cancels_active_and_queued_runs(self) -> None:
        QueueBlockingProvider.reset()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = RunStore(root / "runs.db")
            settings = AgentSettings(
                "test",
                "http://127.0.0.1:1/v1",
                "",
                "fake-model",
                quality_enabled=False,
            )
            manager = RunManager(
                store,
                root,
                settings_loader=lambda: settings,
                provider_factory=QueueBlockingProvider,
                max_workers=1,
                max_queued_runs=1,
            )
            active = manager.create({"mode": "solver", "content": "运行中任务"})
            self.assertTrue(QueueBlockingProvider.started.wait(1))
            queued = manager.create({"mode": "solver", "content": "排队任务"})
            manager.close(timeout=2)

            self.assertEqual(store.get(active["id"])["status"], "cancelled")
            self.assertEqual(store.get(queued["id"])["status"], "cancelled")
            runtime = manager.runtime_status()
            self.assertFalse(runtime["accepting"])
            self.assertEqual(runtime["activeCount"], 0)
            self.assertEqual(runtime["queuedCount"], 0)


if __name__ == "__main__":
    unittest.main()
