from __future__ import annotations

import io
import tempfile
import unittest
import uuid
from pathlib import Path

from agent_tools import ToolError, ToolRegistry


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
        self.assertIn("A127（官网代码 A0127）已通过", exemplar_reference["content"])
        self.assertIn("只能称“组委会官方展示论文”", exemplar_reference["content"])
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

    def test_plot_tool_schema_matches_python_renderer(self) -> None:
        definitions = {
            item["function"]["name"]: item["function"]["parameters"]
            for item in self.registry._local_definitions()
            if item.get("type") == "function"
        }
        inline_types = set(definitions["create_plot"]["properties"]["chart_type"]["enum"])
        dataset_types = set(
            definitions["create_plot_from_dataset"]["properties"]["chart_type"]["enum"]
        )
        advanced = {"interval", "tornado", "contour", "pareto", "violin"}
        self.assertTrue(advanced <= inline_types)
        self.assertTrue(advanced <= dataset_types)
        self.assertIn("multi_panel", inline_types)
        self.assertNotIn("multi_panel", dataset_types)
        expected_templates = {
            "contest_paper",
            "root_event_zoom",
            "coverage_timeline",
            "optimization_landscape",
            "convergence_audit",
            "paired_sensitivity",
            "trajectory_geometry",
        }
        self.assertEqual(
            set(definitions["create_plot"]["properties"]["template"]["enum"]),
            expected_templates,
        )
        self.assertEqual(
            set(definitions["create_plot_from_dataset"]["properties"]["template"]["enum"]),
            expected_templates,
        )
        for field in (
            "figure_intent",
            "event_times",
            "threshold",
            "optimum",
            "summarize_intervals",
            "geometry_layers",
        ):
            self.assertIn(field, definitions["create_plot"]["properties"])
            self.assertIn(field, definitions["create_plot_from_dataset"]["properties"])

    def test_semantic_plot_template_returns_lint_and_exact_size(self) -> None:
        result = self.registry.execute(
            "create_plot",
            {
                "chart_type": "interval",
                "template": "coverage_timeline",
                "filename": "semantic-coverage",
                "formats": ["png"],
                "dpi": 300,
                "figsize": [6.0, 3.0],
                "x_label": "时间 (s)",
                "figure_intent": {
                    "claim": "多区间的并集包含重叠与空档",
                    "source": "连续事件求根",
                    "required_layers": ["union", "overlap", "gap"],
                    "strict": True,
                },
                "series": [
                    {"name": "事件 1", "intervals": [[0.0, 2.0]]},
                    {"name": "事件 2", "intervals": [[1.0, 3.0]]},
                    {"name": "事件 3", "intervals": [[4.0, 5.0]]},
                ],
            },
            self.run_id,
        )
        self.assertTrue(result["figureLint"]["ok"])
        self.assertEqual(result["template"], "coverage_timeline")
        self.assertAlmostEqual(result["semanticSummary"]["unionDuration"], 4.0)
        self.assertLessEqual(abs(result["actualSizeInches"]["width"] - 6.0) / 6.0, 0.05)
        self.assertLessEqual(abs(result["actualSizeInches"]["height"] - 3.0) / 3.0, 0.05)

    def test_creates_advanced_modeling_panels_with_editable_vector_text(self) -> None:
        result = self.registry.execute(
            "create_plot",
            {
                "chart_type": "multi_panel",
                "title": "竞赛建模证据图",
                "filename": "advanced-evidence-panels",
                "formats": ["png", "pdf", "svg"],
                "panels": [
                    {
                        "chart_type": "interval",
                        "title": "连续事件区间",
                        "x_label": "时间 (s)",
                        "series": [
                            {"name": "方案 A", "intervals": [[1.0, 2.4], [3.1, 4.0]]},
                            {"name": "方案 B", "intervals": [[1.5, 3.6]]},
                        ],
                    },
                    {
                        "chart_type": "tornado",
                        "title": "参数敏感性",
                        "x_label": "目标值",
                        "baseline": 10.0,
                        "series": [
                            {"name": "半径", "low": 8.2, "high": 12.7},
                            {"name": "速度", "low": 9.1, "high": 11.4},
                        ],
                    },
                    {
                        "chart_type": "contour",
                        "title": "目标响应面",
                        "x_label": "航向角 (°)",
                        "y_label": "速度 (m/s)",
                        "matrix": [[1.0, 1.8, 2.1], [1.4, 2.5, 2.2], [1.1, 1.9, 1.6]],
                        "x_values": [0.0, 5.0, 10.0],
                        "y_values": [80.0, 100.0, 120.0],
                        "colorbar_label": "遮蔽时长 (s)",
                    },
                    {
                        "chart_type": "pareto",
                        "title": "Pareto 前沿",
                        "x_label": "成本",
                        "y_label": "风险",
                        "series": [
                            {
                                "name": "可行方案",
                                "x": [1, 2, 3, 4, 5],
                                "y": [9, 6, 7, 4, 3],
                                "highlight_indices": [3],
                            }
                        ],
                    },
                    {
                        "chart_type": "violin",
                        "title": "多种子结果分布",
                        "y_label": "目标值",
                        "series": [
                            {"name": "算法 A", "values": [9.2, 9.7, 10.0, 10.3, 10.8]},
                            {"name": "算法 B", "values": [8.7, 9.0, 9.4, 9.8, 10.1]},
                        ],
                    },
                ],
            },
            self.run_id,
        )
        self.assertEqual(result["panelCount"], 5)
        names = {item["name"] for item in result["artifacts"]}
        self.assertEqual(
            names,
            {
                "advanced-evidence-panels.png",
                "advanced-evidence-panels.pdf",
                "advanced-evidence-panels.svg",
            },
        )
        svg = self.registry.artifact_path(self.run_id, "advanced-evidence-panels.svg")
        pdf = self.registry.artifact_path(self.run_id, "advanced-evidence-panels.pdf")
        svg_text = svg.read_text(encoding="utf-8")
        self.assertIn("<text", svg_text)
        self.assertTrue(all(line == line.rstrip() for line in svg_text.splitlines()))
        pdf_bytes = pdf.read_bytes()
        self.assertNotIn(b"/Subtype /Type3", pdf_bytes)
        self.assertTrue(b"/FontFile2" in pdf_bytes or b"/CIDFontType2" in pdf_bytes)

    def test_dataset_adapter_builds_advanced_plot_specs(self) -> None:
        csv = (
            "参数,x,y,z,low,high\n"
            "甲,0,0,1.0,8.0,12.0\n"
            "乙,1,0,1.8,9.0,11.0\n"
            "丙,0,1,1.4,7.0,13.0\n"
            "丁,1,1,2.5,6.0,14.0\n"
        )
        upload = self.registry.save_upload("advanced.csv", "text/csv", csv.encode("utf-8"))
        for chart_type, filename, x_column, y_columns, extra in (
            ("interval", "dataset-interval", "参数", ["low", "high"], {}),
            ("tornado", "dataset-tornado", "参数", ["low", "high"], {"baseline": 10.0}),
            ("contour", "dataset-contour", "x", ["y", "z"], {"colorbar_label": "目标值"}),
            ("pareto", "dataset-pareto", "x", ["z"], {"x_sense": "min", "y_sense": "max"}),
            ("violin", "dataset-violin", "", ["z", "low"], {}),
        ):
            with self.subTest(chart_type=chart_type):
                result = self.registry.execute(
                    "create_plot_from_dataset",
                    {
                        "upload_id": upload["id"],
                        "chart_type": chart_type,
                        "x_column": x_column,
                        "y_columns": y_columns,
                        "filename": filename,
                        "formats": ["png"],
                        **extra,
                    },
                    self.run_id,
                )
                self.assertIn(f"{filename}.png", {item["name"] for item in result["artifacts"]})

    def test_dataset_heatmap_rejects_unknown_or_empty_columns(self) -> None:
        upload = self.registry.save_upload(
            "columns.csv",
            "text/csv",
            b"x,y,z\n1,2,3\n2,3,4\n",
        )
        for y_columns in (["missing"], []):
            with self.subTest(y_columns=y_columns), self.assertRaises(ToolError):
                self.registry.execute(
                    "create_plot_from_dataset",
                    {
                        "upload_id": upload["id"],
                        "chart_type": "heatmap",
                        "y_columns": y_columns,
                        "filename": "must-not-fallback",
                    },
                    self.run_id,
                )

    def test_audits_actual_competition_manuscript_artifact(self) -> None:
        artifact_dir = self.registry._artifact_dir(self.run_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        abstract = (
            "问题一采用连续几何模型，得到时长 1.43 s；问题二采用全局搜索，得到时长 4.83 s；"
            "问题三按区间并集优化得到 6.42 s；问题四的三机协同结果为 15.74 s；"
            "问题五得到 53.08 s 的可行方案，最大约束违反量为 0 m。"
            "所有结果均由独立复算、步长收敛和敏感性检验支持，启发式结果不宣称全局最优。"
            * 3
        )
        sections = []
        numerals = ["一", "二", "三", "四", "五"]
        for index, numeral in enumerate(numerals, start=1):
            body = (
                "本问先明确目标、变量、单位和约束，再比较解析基线与主模型。"
                "模型由现实机制推导，算法报告参数、停止条件和可行性复算。"
                "图中给出结果、误差与基线，说明改进来自结构而非手工调参。"
                "本问还执行独立验证、敏感性检验、残差审计和边界讨论。"
                "最大残差为 1.0e-8 m，步长误差为 0.02 s。"
            ) * 18
            sections.append(
                f"\\section{{问题{numeral}：模型、结果与检验}}\n"
                f"{body}\n\\begin{{equation}}x_{index}= {index}\\end{{equation}}\n"
                f"\\begin{{figure}}\\caption{{问题{numeral}的专属结果与验证图}}"
                f"\\label{{fig:q{index}}}\\end{{figure}}\n"
                f"图\\ref{{fig:q{index}}}表明本问的误差随步长下降。\n"
            )
        extra_figures = "\n".join(
            [
                r"\begin{figure}\caption{问题二多种子稳定性检验}\end{figure}",
                r"\begin{figure}\caption{问题一至五的基线对比与敏感性分析}\end{figure}",
                r"\begin{figure}\caption{问题三组合搜索的数值收敛检验}\end{figure}",
            ]
        ) + "\n" + "\n".join(
            f"\\begin{{equation}}v_{index}= {index}\\end{{equation}}" for index in range(6, 9)
        )
        citations = " ".join(f"\\cite{{r{index}}}" for index in range(1, 7))
        bibliography = "\n".join(
            f"\\bibitem{{r{index}}} Author {index}. Verified reference {index}. 2024."
            for index in range(1, 7)
        )
        manuscript = (
            "\\documentclass{article}\n\\begin{document}\n"
            f"\\begin{{abstract}}{abstract}\\textbf{{关键词：}}优化；验证\\end{{abstract}}\n"
            "\\section{问题分析}五问共享统一模型链，并分别保留验证接口。\n"
            "\\section{模型假设与符号说明}模型假设均可检验，主要符号带单位。\n"
            + "\n".join(sections)
            + extra_figures
            + f"\n\\section{{结论}}量化结论与适用边界一致。{citations}\n"
            + f"\\begin{{thebibliography}}{{99}}{bibliography}\\end{{thebibliography}}\n"
            + "\\end{document}\n"
        )
        (artifact_dir / "submission.tex").write_text(manuscript, encoding="utf-8")
        result = self.registry.execute(
            "audit_competition_paper",
            {
                "artifact_name": "submission.tex",
                "expected_questions": 5,
                "full_paper": True,
            },
            self.run_id,
        )
        self.assertTrue(result["audit"]["passed"], result["audit"]["issues"])
        metrics = result["audit"]["metrics"]
        self.assertEqual(metrics["artifactName"], "submission.tex")
        self.assertEqual(len(metrics["artifactSha256"]), 64)
        self.assertTrue(metrics["fullPaper"])
        names = {item["name"] for item in result["artifacts"]}
        self.assertIn("paper-quality-audit.json", names)
        self.assertIn("paper-quality-audit.md", names)
        submission_record = next(item for item in result["artifacts"] if item["name"] == "submission.tex")
        self.assertEqual(submission_record["sha256"], metrics["artifactSha256"])

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
