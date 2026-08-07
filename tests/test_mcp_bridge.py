from __future__ import annotations

import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from agent_tools import ToolRegistry
from mcp_bridge import MCPServerConfig, MCPToolManager


ROOT = Path(__file__).resolve().parents[1]


class MCPBridgeTests(unittest.TestCase):
    def test_origin_mcp_lists_tools_and_returns_structured_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MCPToolManager(
                [
                    MCPServerConfig(
                        name="origin",
                        command=sys.executable,
                        args=(str(ROOT / "mcp_servers/origin_server.py"),),
                        cwd=str(ROOT),
                        startup_timeout=10,
                        exposed_tools=frozenset({"origin_status"}),
                    )
                ],
                Path(temp_dir) / "logs",
            )
            try:
                definitions = manager.definitions()
                self.assertEqual([item["function"]["name"] for item in definitions], ["origin_status"])
                result = manager.call("origin_status", {})
                self.assertTrue(result["ok"])
                self.assertEqual(result["mcpServer"], "origin")
                self.assertIn("originproInstalled", result["structured"])
                status = manager.status(probe=True)[0]
                self.assertEqual(status["state"], "ready")
                self.assertTrue(status["available"])
            finally:
                manager.close()

    def test_registry_exposes_high_level_mcp_plot_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = ToolRegistry(Path(temp_dir))
            try:
                names = {item["function"]["name"] for item in registry.definitions()}
                self.assertIn("create_origin_plot", names)
                self.assertIn("create_origin_plot_from_dataset", names)
                self.assertIn("origin_status", names)
            finally:
                registry.mcp.close()

    def test_matlab_plot_script_is_reproducible_and_exports_editable_figure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = ToolRegistry(Path(temp_dir))
            run_id = uuid.uuid4().hex
            output_dir = registry._artifact_dir(run_id)
            script = registry._matlab_plot_script(
                {
                    "chart_type": "line",
                    "filename": "trend.png",
                    "title": "趋势图",
                    "x_label": "时间",
                    "y_label": "指标",
                    "formats": ["png", "pdf", "svg"],
                    "series": [{"name": "方案A", "x": [1, 2, 3], "y": [2.0, 3.5, 5.0]}],
                },
                output_dir,
            )
            self.assertIn("exportgraphics", script)
            self.assertIn("'Resolution',300", script)
            self.assertIn("savefig", script)
            self.assertIn("trend.fig", script)


if __name__ == "__main__":
    unittest.main()
