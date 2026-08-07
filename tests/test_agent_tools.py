from __future__ import annotations

import io
import tempfile
import unittest
import uuid
from pathlib import Path

from agent_tools import ToolRegistry


class AgentToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.registry = ToolRegistry(self.root)
        self.run_id = uuid.uuid4().hex

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_searches_installed_modeling_skills(self) -> None:
        result = self.registry.execute("search_skills", {"query": "多目标优化", "limit": 3}, self.run_id)
        names = [item["name"] for item in result["skills"]]
        self.assertIn("pymoo", names)

    def test_searches_project_expert_skill(self) -> None:
        result = self.registry.execute("search_skills", {"query": "数模全流程验证", "limit": 3}, self.run_id)
        names = [item["name"] for item in result["skills"]]
        self.assertEqual(names[0], "cumcm-expert-agent")
        skill = self.registry.execute("read_skill", {"name": "cumcm-expert-agent"}, self.run_id)
        self.assertIn("题目—模型—计算—证据—结论", skill["content"])
        reference = self.registry.execute(
            "read_skill_reference",
            {"name": "cumcm-expert-agent", "relative_path": "references/figure-standards.md"},
            self.run_id,
        )
        self.assertIn("先写图的主张", reference["content"])
        geometry = self.registry.execute(
            "search_skills",
            {"query": "轨迹遮蔽连续事件", "limit": 2},
            self.run_id,
        )
        self.assertEqual(geometry["skills"][0]["name"], "cumcm-expert-agent")
        geometry_reference = self.registry.execute(
            "read_skill_reference",
            {"name": "cumcm-expert-agent", "relative_path": "references/geometry-continuous-events.md"},
            self.run_id,
        )
        self.assertIn("连续事件求解", geometry_reference["content"])
        exemplars = self.registry.execute(
            "search_skills",
            {"query": "国赛一等奖优秀论文复盘", "limit": 2},
            self.run_id,
        )
        self.assertEqual(exemplars["skills"][0]["name"], "cumcm-expert-agent")
        exemplar_reference = self.registry.execute(
            "read_skill_reference",
            {
                "name": "cumcm-expert-agent",
                "relative_path": "references/first-prize-paper-patterns.md",
            },
            self.run_id,
        )
        self.assertIn("跨问支配门", exemplar_reference["content"])
        self.assertIn("不能把具体奖项等级当作已独立核验事实", exemplar_reference["content"])
        with self.assertRaisesRegex(Exception, "references"):
            self.registry.execute(
                "read_skill_reference",
                {"name": "cumcm-expert-agent", "relative_path": "../README.md"},
                self.run_id,
            )

    def test_summarizes_inline_data(self) -> None:
        result = self.registry.execute(
            "summarize_data",
            {"columns": {"x": [1, 2, 3], "y": [2, 4, 6], "group": ["a", "a", "b"]}},
            self.run_id,
        )
        self.assertEqual(result["rows"], 3)
        self.assertEqual(result["numericSummary"]["x"]["mean"], 2.0)
        self.assertEqual(result["correlations"]["x"]["y"], 1.0)

    def test_uploads_and_inspects_csv_dataset(self) -> None:
        upload = self.registry.save_upload(
            "sample.csv",
            "text/csv",
            "城市,年份,需求\n甲,2024,10\n乙,2025,15\n乙,2026,20\n".encode("utf-8"),
        )
        result = self.registry.execute(
            "inspect_dataset",
            {"upload_id": upload["id"], "sample_rows": 2},
            self.run_id,
        )
        self.assertEqual(result["rows"], 3)
        self.assertEqual(result["columns"], ["城市", "年份", "需求"])
        self.assertEqual(result["sample"][0]["城市"], "甲")
        self.registry.delete_upload(upload["id"])
        self.assertFalse((self.root / ".agent-data/uploads" / upload["id"]).exists())

    def test_inspects_xlsx_and_plots_selected_columns(self) -> None:
        import pandas as pd

        workbook = io.BytesIO()
        with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
            pd.DataFrame({"月份": [1, 2, 3], "销量": [8, 13, 21]}).to_excel(
                writer,
                sheet_name="趋势",
                index=False,
            )
        upload = self.registry.save_upload(
            "sales.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            workbook.getvalue(),
        )
        inspection = self.registry.execute(
            "inspect_dataset",
            {"upload_id": upload["id"], "sheet_name": "趋势"},
            self.run_id,
        )
        self.assertEqual(inspection["sheets"], ["趋势"])
        result = self.registry.execute(
            "create_plot_from_dataset",
            {
                "upload_id": upload["id"],
                "sheet_name": "趋势",
                "chart_type": "line",
                "x_column": "月份",
                "y_columns": ["销量"],
                "filename": "sales-trend",
                "formats": ["png"],
            },
            self.run_id,
        )
        self.assertIn("sales-trend.png", {item["name"] for item in result["artifacts"]})

    def test_solves_linear_program(self) -> None:
        result = self.registry.execute(
            "solve_linear_program",
            {
                "objective": [3, 2],
                "sense": "max",
                "A_ub": [[1, 1], [1, 0], [0, 1]],
                "b_ub": [4, 2, 3],
                "bounds": [[0, None], [0, None]],
            },
            self.run_id,
        )
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["objective"], 10.0)
        self.assertEqual(result["variables"], [2.0, 2.0])

    def test_runs_python_with_upload_and_collects_outputs(self) -> None:
        upload = self.registry.save_upload(
            "input.csv",
            "text/csv",
            b"x,y\n1,2\n3,4\n",
        )
        result = self.registry.execute(
            "run_python",
            {
                "input_upload_ids": [upload["id"]],
                "timeout_seconds": 20,
                "code": (
                    "from pathlib import Path\n"
                    "import pandas as pd\n"
                    "frame = pd.read_csv('inputs/input.csv')\n"
                    "Path('outputs').mkdir(exist_ok=True)\n"
                    "frame.assign(total=frame.x + frame.y).to_csv('outputs/result.csv', index=False)\n"
                    "print(int(frame.y.sum()))\n"
                ),
            },
            self.run_id,
        )
        self.assertTrue(result["ok"], result.get("stderr"))
        self.assertEqual(result["stdout"].strip(), "6")
        self.assertEqual(result["inputs"][0]["relativePath"], "inputs/input.csv")
        self.assertIn("result.csv", {item["name"] for item in result["artifacts"]})

    def test_python_runner_blocks_external_file_reads(self) -> None:
        secret = self.root / "outside-secret.txt"
        secret.write_text("do-not-read", encoding="utf-8")
        result = self.registry.execute(
            "run_python",
            {"code": f"print(open({str(secret)!r}, encoding='utf-8').read())"},
            self.run_id,
        )
        self.assertFalse(result["ok"])
        self.assertIn("禁止读取外部路径", result["stderr"])

    def test_python_runner_times_out(self) -> None:
        result = self.registry.execute(
            "run_python",
            {"code": "while True:\n    pass\n", "timeout_seconds": 1},
            self.run_id,
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result["timedOut"])

    def test_creates_figure_artifacts(self) -> None:
        result = self.registry.execute(
            "create_plot",
            {
                "chart_type": "line",
                "title": "趋势",
                "x_label": "时间",
                "y_label": "值",
                "filename": "trend",
                "formats": ["png", "svg"],
                "series": [{"name": "方案 A", "x": [1, 2, 3], "y": [2, 3, 5]}],
            },
            self.run_id,
        )
        names = {item["name"] for item in result["artifacts"]}
        self.assertEqual(names, {"trend.png", "trend.svg"})
        self.assertTrue(all(item["url"].startswith(f"/api/artifacts/{self.run_id}/") for item in result["artifacts"]))
        self.registry.delete_artifacts(self.run_id)
        self.assertEqual(self.registry.list_artifacts(self.run_id), [])

    def test_creates_reproducible_multi_panel_figure_with_uncertainty(self) -> None:
        result = self.registry.execute(
            "create_plot",
            {
                "chart_type": "multi_panel",
                "title": "模型诊断",
                "filename": "model-diagnostics",
                "formats": ["png", "pdf", "svg"],
                "dpi": 600,
                "save_spec": True,
                "panels": [
                    {
                        "chart_type": "line",
                        "title": "预测区间",
                        "x_label": "时间 (s)",
                        "y_label": "响应值",
                        "series": [
                            {
                                "name": "模型",
                                "x": [0, 1, 2],
                                "y": [1.0, 1.8, 2.5],
                                "ci_lower": [0.8, 1.5, 2.1],
                                "ci_upper": [1.2, 2.1, 2.9],
                            }
                        ],
                    },
                    {
                        "chart_type": "heatmap",
                        "title": "相关矩阵",
                        "matrix": [[1.0, -0.4], [-0.4, 1.0]],
                        "x_ticks": ["x", "y"],
                        "y_ticks": ["x", "y"],
                        "cmap": "PuOr",
                        "center": 0,
                        "annotate_heatmap": True,
                    },
                ],
            },
            self.run_id,
        )
        names = {item["name"] for item in result["artifacts"]}
        self.assertEqual(
            names,
            {
                "model-diagnostics.png",
                "model-diagnostics.pdf",
                "model-diagnostics.svg",
                "model-diagnostics.figure.json",
            },
        )
        self.assertEqual(result["panelCount"], 2)
        self.assertEqual(result["palette"], "Okabe-Ito")

    def test_exports_markdown_and_docx(self) -> None:
        result = self.registry.execute(
            "export_report",
            {
                "title": "测试报告",
                "filename": "report",
                "formats": ["md", "docx"],
                "markdown": "# 测试报告\n\n## 结果\n\n模型运行正常。",
            },
            self.run_id,
        )
        names = {item["name"] for item in result["artifacts"]}
        self.assertEqual(names, {"report.md", "report.docx"})


if __name__ == "__main__":
    unittest.main()
