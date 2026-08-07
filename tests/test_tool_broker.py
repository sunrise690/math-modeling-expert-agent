from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tool_broker import FileToolBroker, ToolBrokerError, call_file_tool_broker


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


if __name__ == "__main__":
    unittest.main()
