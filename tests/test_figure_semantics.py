from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.plot_figure import ALLOWED_TEMPLATES, _apply_template, create_figure, figure_lint


class FigureSemanticTests(unittest.TestCase):
    def test_all_semantic_templates_apply_distinct_defaults(self) -> None:
        base_types = {
            "contest_paper": "line",
            "root_event_zoom": "line",
            "coverage_timeline": "interval",
            "optimization_landscape": "contour",
            "convergence_audit": "line",
            "paired_sensitivity": "line",
            "trajectory_geometry": "line",
        }
        self.assertEqual(set(base_types), ALLOWED_TEMPLATES)
        for template, chart_type in base_types.items():
            with self.subTest(template=template):
                rendered = _apply_template({"template": template, "chart_type": chart_type})
                self.assertEqual(rendered["template"], template)
                if template != "contest_paper":
                    self.assertIn("figsize", rendered)

    def test_coverage_template_adds_union_overlap_and_gap_and_preserves_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = create_figure(
                {
                    "chart_type": "interval",
                    "template": "coverage_timeline",
                    "filename": "coverage",
                    "formats": ["png", "pdf", "svg"],
                    "dpi": 300,
                    "figsize": [6.4, 3.2],
                    "x_label": "时间 (s)",
                    "figure_intent": {
                        "claim": "三段区间形成一个并集，且存在重叠和内部空档",
                        "caption_claim": "并集、重叠与空档摘要",
                        "x_unit": "s",
                        "required_layers": ["union", "overlap", "gap"],
                        "strict": True,
                    },
                    "series": [
                        {"name": "烟幕 1", "intervals": [[0.0, 2.0]]},
                        {"name": "烟幕 2", "intervals": [[1.5, 3.0]]},
                        {"name": "烟幕 3", "intervals": [[4.0, 5.0]]},
                    ],
                },
                Path(directory),
            )
            svg_text = (Path(directory) / "coverage.svg").read_text(encoding="utf-8")
        self.assertTrue(result["figureLint"]["ok"])
        self.assertEqual(result["figureLint"]["layers"], ["data", "gap", "overlap", "union"])
        self.assertAlmostEqual(result["semanticSummary"]["unionDuration"], 4.0)
        self.assertAlmostEqual(result["semanticSummary"]["overlapDuration"], 0.5)
        self.assertAlmostEqual(result["semanticSummary"]["gapDuration"], 1.0)
        self.assertIn("烟幕 1", svg_text)
        self.assertIn("∪ 并集", svg_text)
        for artifact in result["artifactSizes"]:
            self.assertLessEqual(abs(artifact["widthInches"] - 6.4) / 6.4, 0.05)
            self.assertLessEqual(abs(artifact["heightInches"] - 3.2) / 3.2, 0.05)

    def test_paired_sensitivity_uses_semantic_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = create_figure(
                {
                    "chart_type": "line",
                    "template": "paired_sensitivity",
                    "filename": "paired",
                    "formats": ["png"],
                    "x_label": "目标值 (s)",
                    "series": [
                        {"name": "基线", "x": ["风速", "半径", "延迟"], "y": [10.0, 10.0, 10.0]},
                        {"name": "扰动", "y": [9.2, 10.6, 8.8]},
                    ],
                },
                Path(directory),
            )
        self.assertEqual(result["template"], "paired_sensitivity")
        self.assertTrue({"baseline", "comparison", "delta"} <= set(result["figureLint"]["layers"]))

    def test_event_landscape_convergence_and_geometry_layers_render(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = create_figure(
                {
                    "chart_type": "multi_panel",
                    "template": "contest_paper",
                    "filename": "semantic-panels",
                    "formats": ["png"],
                    "dpi": 300,
                    "panels": [
                        {
                            "chart_type": "line",
                            "template": "root_event_zoom",
                            "x_label": "时间 (s)",
                            "y_label": "判别裕量 (m)",
                            "event_times": [0.5, 1.5],
                            "figure_intent": {"claim": "两个连续事件根限定有效区间", "source": "高精度根求解", "required_layers": ["events", "threshold"]},
                            "series": [{"name": "裕量", "x": [0, 0.5, 1, 1.5, 2], "y": [-1, 0, 1, 0, -1]}],
                        },
                        {
                            "chart_type": "contour",
                            "template": "optimization_landscape",
                            "x_label": "航向角 (°)",
                            "y_label": "速度 (m/s)",
                            "colorbar_label": "目标值 (s)",
                            "matrix": [[1.0, 1.4, 1.2], [1.3, 2.0, 1.5], [1.1, 1.6, 1.3]],
                            "x_values": [0, 5, 10],
                            "y_values": [80, 100, 120],
                            "optimum": {"x": 5, "y": 100, "label": "采用解"},
                            "figure_intent": {"claim": "采用解位于响应峰附近", "source": "局部响应面", "required_layers": ["optimum"]},
                        },
                        {
                            "chart_type": "line",
                            "template": "convergence_audit",
                            "x_label": "网格层级 (次数)",
                            "y_label": "绝对误差 (s)",
                            "y_scale": "log",
                            "threshold": 0.01,
                            "threshold_label": "验收线",
                            "figure_intent": {"claim": "离散误差下降至验收线以下", "source": "步长折半复算", "required_layers": ["threshold"]},
                            "series": [{"name": "误差", "x": [1, 2, 3, 4], "y": [0.4, 0.11, 0.025, 0.006]}],
                        },
                        {
                            "chart_type": "line",
                            "template": "trajectory_geometry",
                            "x_label": "东向坐标 (m)",
                            "y_label": "北向坐标 (m)",
                            "figure_intent": {"claim": "轨迹避开禁入圆并抵达目标", "source": "运动学积分", "required_layers": ["geometry"]},
                            "series": [{"name": "轨迹", "x": [0, 1, 2, 3], "y": [0, 0.4, 1.2, 2.0]}],
                            "geometry_layers": [
                                {"kind": "circle", "center": [1.5, 1.5], "radius": 0.35, "label": "禁入区"},
                                {"kind": "point", "point": [3, 2], "label": "目标"},
                            ],
                        },
                    ],
                },
                Path(directory),
            )
        layers = set(result["figureLint"]["layers"])
        self.assertTrue({"events", "threshold", "optimum", "geometry"} <= layers)
        self.assertEqual(result["panelCount"], 4)

    def test_small_boxplot_and_sub_tolerance_distribution_are_rejected(self) -> None:
        small_box = {
            "chart_type": "box",
            "filename": "small-box",
            "formats": ["png"],
            "series": [{"name": "种子", "values": [1.0, 1.1, 0.9, 1.05]}],
        }
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, "箱线图样本少于 5"):
            create_figure(small_box, Path(directory))

        tiny_distribution = {
            "chart_type": "violin",
            "filename": "tiny",
            "formats": ["png"],
            "figure_intent": {"numerical_tolerance": 1e-6},
            "series": [{"name": "重复计算", "values": [1.0, 1.0000002, 0.9999999, 1.0000001, 1.0]}],
        }
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, "禁止放大为分布差异"):
            create_figure(tiny_distribution, Path(directory))

    def test_units_and_caption_layers_are_linted(self) -> None:
        materialized_units = _apply_template(
            {
                "chart_type": "line",
                "x_label": "时间",
                "y_label": "距离",
                "colorbar_label": "目标值",
                "figure_intent": {"x_unit": "s", "y_unit": "m", "value_unit": "s"},
            }
        )
        self.assertEqual(materialized_units["x_label"], "时间 (s)")
        self.assertEqual(materialized_units["y_label"], "距离 (m)")
        self.assertEqual(materialized_units["colorbar_label"], "目标值 (s)")

        missing_units = figure_lint(
            _apply_template(
                {
                    "chart_type": "line",
                    "filename": "unit-warning",
                    "x_label": "时间",
                    "y_label": "距离",
                    "series": [{"x": [0, 1], "y": [2, 3]}],
                }
            )
        )
        codes = {item["code"] for item in missing_units["issues"]}
        self.assertTrue({"missing_x_unit", "missing_y_unit"} <= codes)

        missing_layer = figure_lint(
            _apply_template(
                {
                    "chart_type": "line",
                    "filename": "missing-layer",
                    "x_label": "时间 (s)",
                    "y_label": "裕量 (m)",
                    "figure_intent": {
                        "caption_claim": "曲线穿过阈值",
                        "required_layers": ["threshold"],
                        "strict": True,
                    },
                    "series": [{"x": [0, 1], "y": [-1, 1]}],
                }
            )
        )
        self.assertFalse(missing_layer["ok"])
        self.assertIn("missing_claimed_layer", {item["code"] for item in missing_layer["issues"]})

        missing_panel_layer = figure_lint(
            _apply_template(
                {
                    "chart_type": "multi_panel",
                    "panels": [
                        {
                            "chart_type": "line",
                            "x_label": "时间 (s)",
                            "y_label": "误差 (m)",
                            "figure_intent": {"required_layers": ["threshold"], "strict": True},
                            "series": [{"x": [0, 1], "y": [1, 0.5]}],
                        }
                    ],
                }
            )
        )
        self.assertFalse(missing_panel_layer["ok"])
        self.assertTrue(any(item["path"].startswith("$.panels[0]") for item in missing_panel_layer["issues"] if item["level"] == "error"))


if __name__ == "__main__":
    unittest.main()
