from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from tool_broker import (
    BROKER_TOOL_NAMES,
    FileToolBroker,
    ToolBrokerError,
    broker_tool_names,
    call_file_tool_broker,
)


class FakeRegistry:
    def __init__(self) -> None:
        self.calls = []

    def execute(self, name, arguments, run_id):
        self.calls.append((name, arguments, run_id))
        return {"ok": True, "name": name, "arguments": arguments}


class ToolBrokerTests(unittest.TestCase):
    def test_round_trip_keeps_run_id_and_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = FakeRegistry()
            broker = FileToolBroker(registry, "a" * 32, Path(temp_dir) / "broker").start()
            try:
                result = call_file_tool_broker(
                    broker.root,
                    broker.token,
                    "search_skills",
                    {"query": "优化"},
                    timeout=2,
                )
            finally:
                broker.stop()
            self.assertTrue(result["ok"])
            self.assertEqual(registry.calls, [("search_skills", {"query": "优化"}, "a" * 32)])

    def test_rejects_non_exposed_tool_before_writing_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ToolBrokerError, "白名单"):
                call_file_tool_broker(
                    Path(temp_dir) / "broker",
                    "token",
                    "internal_admin_tool",
                    {},
                    timeout=1,
                )

    def test_matlab_high_level_tools_are_exposed_but_raw_eval_is_not(self) -> None:
        self.assertTrue(
            {
                "matlab_status",
                "create_matlab_plot",
                "create_matlab_plot_from_dataset",
            }
            <= BROKER_TOOL_NAMES
        )
        self.assertNotIn("run_matlab", BROKER_TOOL_NAMES)
        self.assertIn("run_matlab", broker_tool_names(allow_unsandboxed_matlab=True))
        self.assertNotIn("evaluate_matlab_code", BROKER_TOOL_NAMES)

    def test_raw_matlab_requires_client_and_parent_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "broker"
            registry = FakeRegistry()
            broker = FileToolBroker(registry, "a" * 32, root).start()
            try:
                with self.assertRaisesRegex(ToolBrokerError, "白名单"):
                    call_file_tool_broker(
                        broker.root,
                        broker.token,
                        "run_matlab",
                        {"code": "disp(1);"},
                        timeout=1,
                        allow_unsandboxed_matlab=True,
                    )
            finally:
                broker.stop()
            self.assertEqual(registry.calls, [])

    def test_broker_stop_cancels_opted_in_raw_matlab(self) -> None:
        class CancellableRegistry:
            def __init__(self) -> None:
                self.started = threading.Event()
                self.cancelled = threading.Event()

            def execute(self, name, arguments, run_id):
                cancel_event = arguments.get("_broker_cancel_event")
                self.started.set()
                if cancel_event is None or not cancel_event.wait(2):
                    raise RuntimeError("未收到 broker 取消信号")
                self.cancelled.set()
                return {"ok": False, "cancelled": True}

        with tempfile.TemporaryDirectory() as temp_dir:
            registry = CancellableRegistry()
            broker = FileToolBroker(
                registry,
                "a" * 32,
                Path(temp_dir) / "broker",
                allow_unsandboxed_matlab=True,
            ).start()
            outcome: dict[str, object] = {}

            def invoke() -> None:
                try:
                    outcome["result"] = call_file_tool_broker(
                        broker.root,
                        broker.token,
                        "run_matlab",
                        {"code": "pause(60);"},
                        timeout=3,
                        allow_unsandboxed_matlab=True,
                    )
                except Exception as error:  # pragma: no cover - asserted below
                    outcome["error"] = error

            caller = threading.Thread(target=invoke)
            caller.start()
            self.assertTrue(registry.started.wait(1))
            broker.stop(timeout=1)
            caller.join(timeout=2)
            self.assertFalse(caller.is_alive())
            self.assertTrue(registry.cancelled.is_set())
            self.assertNotIn("error", outcome)


if __name__ == "__main__":
    unittest.main()
