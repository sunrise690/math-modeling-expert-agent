from __future__ import annotations

import argparse
import copy
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from string import ascii_uppercase
from typing import Any


PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#000000"]
LINE_STYLES = ["-", "--", "-.", ":"]
MARKERS = ["o", "s", "^", "D", "v", "P", "X"]
ALLOWED_TYPES = {
    "line",
    "scatter",
    "bar",
    "histogram",
    "box",
    "violin",
    "heatmap",
    "interval",
    "tornado",
    "contour",
    "pareto",
    "multi_panel",
}
ALLOWED_PANEL_TYPES = ALLOWED_TYPES - {"multi_panel"}
ALLOWED_FORMATS = {"png", "pdf", "svg"}
ALLOWED_TEMPLATES = {
    "contest_paper",
    "root_event_zoom",
    "coverage_timeline",
    "optimization_landscape",
    "convergence_audit",
    "paired_sensitivity",
    "trajectory_geometry",
}
TEMPLATE_DEFAULTS: dict[str, dict[str, Any]] = {
    "contest_paper": {},
    "root_event_zoom": {
        "figsize": [7.0, 3.35],
        "grid": True,
        "threshold": 0.0,
        "direct_labels": True,
    },
    "coverage_timeline": {
        "figsize": [7.2, 3.55],
        "summarize_intervals": True,
        "annotate_values": True,
    },
    "optimization_landscape": {
        "figsize": [6.45, 4.35],
        "filled": True,
        "levels": 15,
    },
    "convergence_audit": {
        "figsize": [7.0, 3.4],
        "grid": True,
        "direct_labels": True,
    },
    "paired_sensitivity": {
        "figsize": [7.0, 3.7],
        "grid": True,
        "direct_labels": True,
    },
    "trajectory_geometry": {
        "figsize": [6.5, 5.0],
        "equal_aspect": True,
        "direct_labels": True,
    },
}
TEMPLATE_CHART_TYPES: dict[str, set[str]] = {
    "root_event_zoom": {"line"},
    "coverage_timeline": {"interval"},
    "optimization_landscape": {"contour", "heatmap"},
    "convergence_audit": {"line"},
    "paired_sensitivity": {"line", "scatter"},
    "trajectory_geometry": {"line", "scatter"},
}


@dataclass(frozen=True)
class FigureIntent:
    """A compact, machine-checkable contract between a claim and its figure."""

    claim: str = ""
    caption_claim: str = ""
    source: str = ""
    x_unit: str = ""
    y_unit: str = ""
    value_unit: str = ""
    required_layers: tuple[str, ...] = ()
    strict: bool = False
    numerical_tolerance: float | None = None

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "FigureIntent":
        raw = spec.get("figure_intent", {})
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise ValueError("figure_intent 必须是对象")
        required = raw.get("required_layers", [])
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            raise ValueError("figure_intent.required_layers 必须是字符串数组")
        tolerance = raw.get("numerical_tolerance")
        if tolerance is not None:
            tolerance = float(tolerance)
            if not math.isfinite(tolerance) or tolerance < 0:
                raise ValueError("figure_intent.numerical_tolerance 必须是非负有限数")
        return cls(
            claim=str(raw.get("claim", "")).strip(),
            caption_claim=str(raw.get("caption_claim", "")).strip(),
            source=str(raw.get("source", "")).strip(),
            x_unit=str(raw.get("x_unit", "")).strip(),
            y_unit=str(raw.get("y_unit", "")).strip(),
            value_unit=str(raw.get("value_unit", "")).strip(),
            required_layers=tuple(item.strip().lower() for item in required if item.strip()),
            strict=bool(raw.get("strict", False)),
            numerical_tolerance=tolerance,
        )


def _safe_name(value: str, default: str = "figure") -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")
    return name[:80] or default


def _numbers(values: Any, label: str, *, allow_empty: bool = True) -> list[float]:
    if not isinstance(values, list) or len(values) > 50_000 or (not allow_empty and not values):
        suffix = "非空数组" if not allow_empty else "数组"
        raise ValueError(f"{label} 必须是长度不超过 50000 的{suffix}")
    result = [float(value) for value in values]
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"{label} 包含非有限数值")
    return result


def _optional_error(values: Any, count: int, label: str) -> list[float] | None:
    if values is None:
        return None
    result = _numbers(values, label)
    if len(result) != count or any(value < 0 for value in result):
        raise ValueError(f"{label} 必须与 y 等长且非负")
    return result


def _apply_template(spec: dict[str, Any]) -> dict[str, Any]:
    rendered = copy.deepcopy(spec)
    template = str(rendered.get("template", "contest_paper") or "contest_paper").strip().lower()
    if template not in ALLOWED_TEMPLATES:
        raise ValueError(f"不支持的绘图模板：{template}")
    chart_type = str(rendered.get("chart_type", "line")).lower()
    allowed = TEMPLATE_CHART_TYPES.get(template)
    if allowed is not None and chart_type not in allowed:
        readable = "、".join(sorted(allowed))
        raise ValueError(f"模板 {template} 仅支持：{readable}")
    rendered["template"] = template
    for key, value in TEMPLATE_DEFAULTS[template].items():
        rendered.setdefault(key, copy.deepcopy(value))
    intent = FigureIntent.from_spec(rendered)
    for label_key, unit in (("x_label", intent.x_unit), ("y_label", intent.y_unit)):
        label = str(rendered.get(label_key, "")).strip()
        if label and unit and not _has_unit(label, ""):
            rendered[label_key] = f"{label} ({unit})"
    colorbar_label = str(rendered.get("colorbar_label", "")).strip()
    if colorbar_label and intent.value_unit and not _has_unit(colorbar_label, ""):
        rendered["colorbar_label"] = f"{colorbar_label} ({intent.value_unit})"
    if chart_type == "multi_panel":
        rendered["panels"] = [
            _apply_template(panel) if isinstance(panel, dict) else panel
            for panel in rendered.get("panels", [])
        ]
    return rendered


def _issue(level: str, code: str, message: str, path: str = "$") -> dict[str, str]:
    return {"level": level, "code": code, "message": message, "path": path}


def _has_unit(label: str, explicit_unit: str) -> bool:
    normalized = label.strip()
    if not normalized:
        return False
    if explicit_unit:
        return True
    if re.search(r"(?:\([^)]{1,12}\)|（[^）]{1,12}）|\[[^\]]{1,12}\]|%|％|°|℃)", normalized):
        return True
    dimensionless = (
        "次数",
        "序号",
        "编号",
        "概率",
        "比例",
        "相关系数",
        "相对误差",
        "归一化",
        "迭代",
        "代数",
        "样本",
        "rank",
        "index",
        "probability",
    )
    return any(token.lower() in normalized.lower() for token in dimensionless)


def _interval_union(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    ordered = sorted(intervals)
    merged: list[tuple[float, float]] = []
    for left, right in ordered:
        if not merged or left > merged[-1][1]:
            merged.append((left, right))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
    return merged


def _interval_semantics(spec: dict[str, Any]) -> dict[str, Any]:
    all_intervals: list[tuple[float, float]] = []
    boundaries: list[tuple[float, int]] = []
    for item in spec.get("series", []):
        if not isinstance(item, dict):
            continue
        for raw in item.get("intervals", []):
            if not isinstance(raw, list) or len(raw) != 2:
                continue
            left, right = float(raw[0]), float(raw[1])
            all_intervals.append((left, right))
            boundaries.extend(((left, 1), (right, -1)))
    union = _interval_union(all_intervals)
    overlaps: list[tuple[float, float]] = []
    active = 0
    overlap_start: float | None = None
    for position, delta in sorted(boundaries, key=lambda pair: (pair[0], -pair[1])):
        previous = active
        active += delta
        if previous < 2 <= active:
            overlap_start = position
        elif previous >= 2 > active and overlap_start is not None and position > overlap_start:
            overlaps.append((overlap_start, position))
            overlap_start = None
    gaps = [
        (union[index][1], union[index + 1][0])
        for index in range(len(union) - 1)
        if union[index + 1][0] > union[index][1]
    ]
    def duration(rows: list[tuple[float, float]]) -> float:
        return sum(right - left for left, right in rows)
    return {
        "union": union,
        "overlap": _interval_union(overlaps),
        "gaps": gaps,
        "unionDuration": duration(union),
        "overlapDuration": duration(overlaps),
        "gapDuration": duration(gaps),
    }


def _inferred_layers(spec: dict[str, Any]) -> set[str]:
    template = str(spec.get("template", "contest_paper"))
    layers = {"data"}
    supplied = spec.get("layers", [])
    if isinstance(supplied, list):
        layers.update(str(item).strip().lower() for item in supplied if str(item).strip())
    if spec.get("event_times"):
        layers.add("events")
    if spec.get("threshold") is not None:
        layers.add("threshold")
    if spec.get("optimum"):
        layers.add("optimum")
    if template == "coverage_timeline" and bool(spec.get("summarize_intervals", True)):
        layers.update({"union", "overlap", "gap"})
    if template == "paired_sensitivity":
        layers.update({"baseline", "comparison", "delta"})
    if template == "trajectory_geometry":
        layers.add("geometry")
    for item in spec.get("series", []):
        if isinstance(item, dict) and item.get("ci_lower") is not None and item.get("ci_upper") is not None:
            layers.add("uncertainty")
    for panel in spec.get("panels", []):
        if isinstance(panel, dict):
            layers.update(_inferred_layers(panel))
    return layers


def figure_lint(spec: dict[str, Any]) -> dict[str, Any]:
    """Lint evidence semantics before rendering; errors are deliberately narrow."""

    template = str(spec.get("template", "contest_paper"))
    intent = FigureIntent.from_spec(spec)
    issues: list[dict[str, str]] = []
    is_multi_panel = str(spec.get("chart_type", "")).lower() == "multi_panel"
    panels = spec.get("panels", []) if is_multi_panel else [spec]
    inferred = _inferred_layers(spec)
    caption = intent.caption_claim
    caption_layers = {
        "并集": "union",
        "重叠": "overlap",
        "空档": "gap",
        "间断": "gap",
        "阈值": "threshold",
        "零点": "events",
        "事件根": "events",
        "最优": "optimum",
        "置信": "uncertainty",
        "几何": "geometry",
        "union": "union",
        "overlap": "overlap",
        "gap": "gap",
        "threshold": "threshold",
        "root": "events",
        "optimum": "optimum",
        "confidence": "uncertainty",
    }
    declared = set(intent.required_layers)
    declared.update(layer for token, layer in caption_layers.items() if token.lower() in caption.lower())
    for layer in sorted(declared - inferred):
        level = "error" if intent.strict or layer in intent.required_layers else "warning"
        issues.append(_issue(level, "missing_claimed_layer", f"图注或意图声明了 {layer} 图层，但绘图规格未提供。", "$.figure_intent"))

    if template != "contest_paper":
        if not intent.claim:
            issues.append(_issue("warning", "missing_figure_claim", "语义模板应在 figure_intent.claim 中写明要证明的结论。", "$.figure_intent.claim"))
        if not intent.source:
            issues.append(_issue("warning", "missing_data_source", "语义模板应记录数据或计算来源。", "$.figure_intent.source"))
    if template == "root_event_zoom" and "events" not in inferred:
        issues.append(_issue("warning", "event_roots_missing", "root_event_zoom 未提供精化后的 event_times。", "$.event_times"))
    if template == "optimization_landscape" and "optimum" not in inferred:
        issues.append(_issue("warning", "optimum_missing", "optimization_landscape 未标出最终采用的 optimum。", "$.optimum"))

    for index, panel in enumerate(panels):
        if not isinstance(panel, dict):
            continue
        path = f"$.panels[{index}]" if is_multi_panel else "$"
        panel_type = str(panel.get("chart_type", "line")).lower()
        panel_intent = FigureIntent.from_spec(panel) if panel.get("figure_intent") is not None else intent
        x_label = str(panel.get("x_label", ""))
        y_label = str(panel.get("y_label", ""))
        panel_template = str(panel.get("template", template))
        panel_layers = _inferred_layers(panel)
        if is_multi_panel and panel.get("figure_intent") is not None:
            panel_declared = set(panel_intent.required_layers)
            panel_declared.update(
                layer
                for token, layer in caption_layers.items()
                if token.lower() in panel_intent.caption_claim.lower()
            )
            for layer in sorted(panel_declared - panel_layers):
                level = "error" if panel_intent.strict or layer in panel_intent.required_layers else "warning"
                issues.append(
                    _issue(
                        level,
                        "missing_claimed_layer",
                        f"面板图注或意图声明了 {layer} 图层，但绘图规格未提供。",
                        f"{path}.figure_intent",
                    )
                )
        if is_multi_panel and panel_template != "contest_paper":
            if not panel_intent.claim:
                issues.append(_issue("warning", "missing_figure_claim", "语义面板应在 figure_intent.claim 中写明要证明的结论。", f"{path}.figure_intent.claim"))
            if not panel_intent.source:
                issues.append(_issue("warning", "missing_data_source", "语义面板应记录数据或计算来源。", f"{path}.figure_intent.source"))
            if panel_template == "root_event_zoom" and "events" not in panel_layers:
                issues.append(_issue("warning", "event_roots_missing", "root_event_zoom 未提供精化后的 event_times。", f"{path}.event_times"))
            if panel_template == "optimization_landscape" and "optimum" not in panel_layers:
                issues.append(_issue("warning", "optimum_missing", "optimization_landscape 未标出最终采用的 optimum。", f"{path}.optimum"))
        quantitative_x = panel_type not in {"box", "violin", "heatmap", "bar"}
        quantitative_y = panel_type not in {"interval", "heatmap", "tornado"} and panel_template != "paired_sensitivity"
        if quantitative_x and not _has_unit(x_label, panel_intent.x_unit):
            issues.append(_issue("warning", "missing_x_unit", "定量横轴缺少单位或无量纲说明。", f"{path}.x_label"))
        if quantitative_y and not _has_unit(y_label, panel_intent.y_unit):
            issues.append(_issue("warning", "missing_y_unit", "定量纵轴缺少单位或无量纲说明。", f"{path}.y_label"))
        if panel_type in {"heatmap", "contour"} and not _has_unit(
            str(panel.get("colorbar_label", "")), panel_intent.value_unit
        ):
            issues.append(_issue("warning", "missing_colorbar_unit", "颜色条缺少指标单位或无量纲说明。", f"{path}.colorbar_label"))

        if panel_type == "box":
            for series_index, item in enumerate(panel.get("series", [])):
                values = item.get("values", item.get("y", [])) if isinstance(item, dict) else []
                sample_count = len(values) if isinstance(values, list) else 0
                if sample_count < 5:
                    issues.append(_issue("error", "box_sample_too_small", "箱线图样本少于 5；应改用全部样本点或区间点图。", f"{path}.series[{series_index}]"))
                elif sample_count < 10:
                    issues.append(_issue("warning", "box_sample_small", "箱线图样本少于 10；建议显示全部样本点并弱化箱体。", f"{path}.series[{series_index}]"))

        if panel_type in {"box", "violin", "histogram"} and panel_intent.numerical_tolerance is not None:
            values = [
                float(value)
                for item in panel.get("series", [])
                if isinstance(item, dict)
                for value in item.get("values", item.get("y", []))
            ]
            if values and max(values) - min(values) <= panel_intent.numerical_tolerance:
                issues.append(_issue("error", "distribution_below_tolerance", "分布跨度不超过数值容差，禁止放大为分布差异。", path))

        if panel_type == "interval" and len(panel.get("series", [])) > 1:
            summary = bool(panel.get("summarize_intervals", spec.get("summarize_intervals", False)))
            if not summary:
                issues.append(_issue("warning", "interval_summary_missing", "多组区间缺少并集、重叠和空档摘要。", path))

    if template == "coverage_timeline" and not bool(spec.get("summarize_intervals", True)):
        issues.append(_issue("error", "coverage_summary_disabled", "coverage_timeline 模板不能关闭区间摘要。"))
    errors = [item for item in issues if item["level"] == "error"]
    return {
        "ok": not errors,
        "template": template,
        "intent": {
            "claim": intent.claim,
            "source": intent.source,
            "requiredLayers": list(intent.required_layers),
        },
        "layers": sorted(inferred),
        "issues": issues,
        "errorCount": len(errors),
        "warningCount": len(issues) - len(errors),
    }


def _set_ticks(ax: Any, spec: dict[str, Any]) -> None:
    x_ticks = spec.get("x_ticks")
    y_ticks = spec.get("y_ticks")
    if isinstance(x_ticks, list) and x_ticks:
        ax.set_xticks(range(len(x_ticks)), [str(item) for item in x_ticks])
    if isinstance(y_ticks, list) and y_ticks:
        ax.set_yticks(range(len(y_ticks)), [str(item) for item in y_ticks])


def _draw_paired_sensitivity(ax: Any, spec: dict[str, Any]) -> None:
    import numpy as np

    series = spec.get("series", [])
    if not isinstance(series, list) or len(series) != 2:
        raise ValueError("paired_sensitivity 模板需要恰好两个 series")
    baseline = _numbers(series[0].get("y", []), "series[0].y", allow_empty=False)
    comparison = _numbers(series[1].get("y", []), "series[1].y", allow_empty=False)
    if len(baseline) != len(comparison):
        raise ValueError("paired_sensitivity 两个 series 的 y 必须等长")
    labels = series[0].get("x") or spec.get("y_ticks") or [f"参数 {index + 1}" for index in range(len(baseline))]
    if len(labels) != len(baseline):
        raise ValueError("paired_sensitivity 的类别标签必须与 y 等长")
    positions = np.arange(len(baseline))
    for index, (left, right) in enumerate(zip(baseline, comparison)):
        ax.plot([left, right], [index, index], color="#B7C0C8", linewidth=1.3, zorder=1)
        delta = right - left
        ax.text(
            max(left, right),
            index - 0.18,
            f"{delta:+.3g}",
            ha="right" if delta < 0 else "left",
            va="center",
            fontsize=6.4,
            color="#4B5563",
        )
    ax.scatter(baseline, positions, s=24, color=PALETTE[0], marker="o", label=str(series[0].get("name", "基线")), zorder=3)
    ax.scatter(comparison, positions, s=28, color=PALETTE[1], marker="D", label=str(series[1].get("name", "扰动")), zorder=3)
    ax.set_yticks(positions, [str(item) for item in labels])
    ax.invert_yaxis()


def _draw_geometry_layers(ax: Any, spec: dict[str, Any]) -> None:
    from matplotlib.patches import Circle, Polygon

    layers = spec.get("geometry_layers", [])
    if layers is None:
        return
    if not isinstance(layers, list):
        raise ValueError("geometry_layers 必须是数组")
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict):
            raise ValueError(f"geometry_layers[{index}] 必须是对象")
        kind = str(layer.get("kind", "point")).lower()
        label = str(layer.get("label", ""))
        color = str(layer.get("color", "#4B5563"))
        if kind == "circle":
            center = _numbers(layer.get("center", []), f"geometry_layers[{index}].center", allow_empty=False)
            radius = float(layer.get("radius", 0))
            if len(center) != 2 or not math.isfinite(radius) or radius <= 0:
                raise ValueError("circle 图层需要二维 center 和正 radius")
            patch = Circle(center, radius, facecolor=color, edgecolor=color, alpha=0.12, linewidth=0.9)
            ax.add_patch(patch)
            if label:
                ax.text(center[0], center[1] + radius, label, ha="center", va="bottom", fontsize=6.5, color=color)
        elif kind == "segment":
            points = layer.get("points", [])
            if not isinstance(points, list) or len(points) != 2:
                raise ValueError("segment 图层需要两个 points")
            start = _numbers(points[0], f"geometry_layers[{index}].points[0]", allow_empty=False)
            end = _numbers(points[1], f"geometry_layers[{index}].points[1]", allow_empty=False)
            if len(start) != 2 or len(end) != 2:
                raise ValueError("segment 图层的点必须为二维坐标")
            ax.plot([start[0], end[0]], [start[1], end[1]], color=color, linewidth=1.0, linestyle=str(layer.get("linestyle", "--")))
            if label:
                ax.text((start[0] + end[0]) / 2, (start[1] + end[1]) / 2, label, fontsize=6.5, color=color)
        elif kind == "polygon":
            points = layer.get("points", [])
            parsed = [_numbers(point, f"geometry_layers[{index}].points", allow_empty=False) for point in points]
            if len(parsed) < 3 or any(len(point) != 2 for point in parsed):
                raise ValueError("polygon 图层至少需要三个二维 points")
            patch = Polygon(parsed, closed=True, facecolor=color, edgecolor=color, alpha=0.12, linewidth=0.9)
            ax.add_patch(patch)
            if label:
                ax.text(sum(point[0] for point in parsed) / len(parsed), sum(point[1] for point in parsed) / len(parsed), label, fontsize=6.5, color=color)
        elif kind == "point":
            point = _numbers(layer.get("point", []), f"geometry_layers[{index}].point", allow_empty=False)
            if len(point) != 2:
                raise ValueError("point 图层需要二维 point")
            ax.scatter([point[0]], [point[1]], s=32, marker=str(layer.get("marker", "o")), color=color, zorder=5)
            if label:
                ax.annotate(label, point, xytext=(4, 4), textcoords="offset points", fontsize=6.5, color=color)
        else:
            raise ValueError(f"不支持的 geometry layer kind：{kind}")


def _apply_semantic_layers(ax: Any, spec: dict[str, Any], series: list[Any]) -> None:
    template = str(spec.get("template", "contest_paper"))
    threshold = spec.get("threshold")
    if threshold is not None:
        threshold_value = float(threshold)
        if not math.isfinite(threshold_value):
            raise ValueError("threshold 必须是有限数值")
        ax.axhline(threshold_value, color="#5F6B76", linewidth=0.9, linestyle="--", zorder=0)
        label = str(spec.get("threshold_label", "阈值"))
        ax.annotate(label, (1.0, threshold_value), xycoords=("axes fraction", "data"), xytext=(-3, 3), textcoords="offset points", ha="right", fontsize=6.3, color="#5F6B76")

    event_times = spec.get("event_times", [])
    if event_times is not None:
        event_values = _numbers(event_times, "event_times")
        for index, value in enumerate(event_values):
            ax.axvline(value, color=PALETTE[1], linewidth=0.8, linestyle=(0, (3, 2)), alpha=0.85, zorder=0)
            ax.annotate(f"t={value:.3g}", (value, 1.0), xycoords=("data", "axes fraction"), xytext=(2, -4 - 8 * (index % 2)), textcoords="offset points", va="top", fontsize=6.2, color=PALETTE[1])

    optimum = spec.get("optimum")
    if optimum is not None:
        if not isinstance(optimum, dict):
            raise ValueError("optimum 必须是对象")
        try:
            x_value = float(optimum.get("x"))
            y_value = float(optimum.get("y"))
        except (TypeError, ValueError) as error:
            raise ValueError("optimum.x/y 必须是有限数值") from error
        if not math.isfinite(x_value) or not math.isfinite(y_value):
            raise ValueError("optimum.x/y 必须是有限数值")
        ax.scatter([x_value], [y_value], marker="*", s=78, color="#F0E442", edgecolor="#1F2933", linewidth=0.7, zorder=7)
        ax.annotate(str(optimum.get("label", "最优解")), (x_value, y_value), xytext=(5, 5), textcoords="offset points", fontsize=6.5, color="#1F2933")

    if template == "trajectory_geometry":
        _draw_geometry_layers(ax, spec)

    if bool(spec.get("direct_labels", False)) and template not in {"paired_sensitivity"}:
        ax.margins(x=0.08)
        for index, item in enumerate(series):
            if not isinstance(item, dict) or not item.get("y"):
                continue
            y_values = _numbers(item["y"], f"series[{index}].y", allow_empty=False)
            x_values = item.get("x") or list(range(len(y_values)))
            if len(x_values) != len(y_values):
                continue
            try:
                x_value = float(x_values[-1])
            except (TypeError, ValueError):
                continue
            ax.annotate(
                str(item.get("name", f"Series {index + 1}")),
                (x_value, y_values[-1]),
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
                fontsize=6.4,
                color=PALETTE[index % len(PALETTE)],
            )

    if bool(spec.get("equal_aspect", False)):
        ax.set_aspect("equal", adjustable="datalim")


def _draw_panel(fig: Any, ax: Any, spec: dict[str, Any]) -> None:
    import numpy as np
    from matplotlib.colors import TwoSlopeNorm

    chart_type = str(spec.get("chart_type", "line")).lower()
    if chart_type not in ALLOWED_PANEL_TYPES:
        raise ValueError(f"不支持的面板类型：{chart_type}")
    series = spec.get("series", [])
    if chart_type not in {"heatmap", "contour"} and not isinstance(series, list):
        raise ValueError("series 必须是数组")
    x_scale = str(spec.get("x_scale", "linear"))
    y_scale = str(spec.get("y_scale", "linear"))
    if x_scale not in {"linear", "log", "symlog"} or y_scale not in {"linear", "log", "symlog"}:
        raise ValueError("x_scale/y_scale 只能是 linear、log 或 symlog")
    ax.set_xscale(x_scale)
    ax.set_yscale(y_scale)

    semantic_handled = str(spec.get("template", "")) == "paired_sensitivity"
    if semantic_handled:
        _draw_paired_sensitivity(ax, spec)
    elif chart_type in {"line", "scatter"}:
        for index, item in enumerate(series):
            if not isinstance(item, dict):
                raise ValueError(f"series[{index}] 必须是对象")
            y_values = _numbers(item.get("y", []), f"series[{index}].y", allow_empty=False)
            raw_x = item.get("x")
            x_values = list(range(len(y_values))) if raw_x is None else list(raw_x)
            if len(x_values) != len(y_values):
                raise ValueError("x 与 y 长度必须一致")
            color = PALETTE[index % len(PALETTE)]
            label = str(item.get("name", f"Series {index + 1}"))
            marker = str(item.get("marker") or MARKERS[index % len(MARKERS)])[:8]
            linestyle = str(item.get("linestyle") or LINE_STYLES[index % len(LINE_STYLES)])
            y_error = _optional_error(item.get("y_error"), len(y_values), f"series[{index}].y_error")
            if chart_type == "line":
                if y_error is not None:
                    ax.errorbar(
                        x_values,
                        y_values,
                        yerr=y_error,
                        label=label,
                        color=color,
                        linestyle=linestyle,
                        marker=marker,
                        linewidth=1.6,
                        markersize=4,
                        capsize=2.5,
                    )
                else:
                    ax.plot(
                        x_values,
                        y_values,
                        label=label,
                        color=color,
                        linestyle=linestyle,
                        marker=marker,
                        linewidth=1.6,
                        markersize=4,
                    )
            elif y_error is not None:
                ax.errorbar(
                    x_values,
                    y_values,
                    yerr=y_error,
                    fmt=marker,
                    label=label,
                    color=color,
                    markersize=4.5,
                    capsize=2.5,
                    linestyle="none",
                )
            else:
                ax.scatter(x_values, y_values, s=28, alpha=0.82, label=label, color=color, marker=marker)

            lower = item.get("ci_lower")
            upper = item.get("ci_upper")
            if lower is not None or upper is not None:
                lower_values = _numbers(lower, f"series[{index}].ci_lower")
                upper_values = _numbers(upper, f"series[{index}].ci_upper")
                if len(lower_values) != len(y_values) or len(upper_values) != len(y_values):
                    raise ValueError("置信区间上下界必须与 y 等长")
                try:
                    numeric_x = [float(value) for value in x_values]
                except (TypeError, ValueError) as error:
                    raise ValueError("置信带要求数值型 x") from error
                ax.fill_between(numeric_x, lower_values, upper_values, color=color, alpha=0.16, linewidth=0)
    elif chart_type == "bar":
        if not series:
            raise ValueError("柱状图至少需要一个 series")
        count = len(_numbers(series[0].get("y", []), "series[0].y", allow_empty=False))
        labels = series[0].get("x") or list(range(count))
        positions = np.arange(count)
        bar_width = 0.8 / max(1, len(series))
        for index, item in enumerate(series):
            values = _numbers(item.get("y", []), f"series[{index}].y", allow_empty=False)
            if len(values) != count:
                raise ValueError("所有柱状图 series 长度必须一致")
            y_error = _optional_error(item.get("y_error"), count, f"series[{index}].y_error")
            offset = (index - (len(series) - 1) / 2) * bar_width
            ax.bar(
                positions + offset,
                values,
                width=bar_width,
                yerr=y_error,
                capsize=2.5 if y_error is not None else 0,
                label=str(item.get("name", f"Series {index + 1}")),
                color=PALETTE[index % len(PALETTE)],
                edgecolor="white",
                linewidth=0.5,
            )
        ax.set_xticks(positions, [str(item) for item in labels])
        if all(value >= 0 for item in series for value in _numbers(item.get("y", []), "bar.y")):
            ax.set_ylim(bottom=0)
    elif chart_type == "interval":
        if not series:
            raise ValueError("区间图至少需要一个 series")
        labels: list[str] = []
        for index, item in enumerate(series):
            if not isinstance(item, dict):
                raise ValueError(f"series[{index}] 必须是对象")
            raw_intervals = item.get("intervals")
            if not isinstance(raw_intervals, list) or not raw_intervals:
                raise ValueError(f"series[{index}].intervals 必须是非空区间数组")
            intervals: list[tuple[float, float]] = []
            for interval_index, raw_interval in enumerate(raw_intervals):
                values = _numbers(
                    raw_interval,
                    f"series[{index}].intervals[{interval_index}]",
                    allow_empty=False,
                )
                if len(values) != 2 or values[1] < values[0]:
                    raise ValueError("每个区间必须是满足 right >= left 的 [left, right]")
                intervals.append((values[0], values[1] - values[0]))
            label = str(item.get("name", f"Series {index + 1}"))
            labels.append(label)
            color = PALETTE[index % len(PALETTE)]
            ax.broken_barh(
                intervals,
                (index - 0.31, 0.62),
                facecolors=color,
                edgecolors="white",
                linewidth=0.5,
            )
            if bool(spec.get("annotate_values", False)):
                for left, width in intervals:
                    ax.text(
                        left + width / 2,
                        index,
                        f"{width:.3g}",
                        ha="center",
                        va="center",
                        fontsize=6,
                        color="white",
                        fontweight="bold",
                    )
        if bool(spec.get("summarize_intervals", False)):
            summary = _interval_semantics(spec)
            summary_rows = (
                ("∪ 并集", summary["union"], "#334155", 0.92),
                ("∩ 重叠", summary["overlap"], PALETTE[1], 0.74),
                ("空档", summary["gaps"], "#94A3B8", 0.62),
            )
            for label, rows, color, alpha in summary_rows:
                row_index = len(labels)
                labels.append(label)
                widths = [(left, right - left) for left, right in rows]
                if widths:
                    ax.broken_barh(
                        widths,
                        (row_index - 0.25, 0.5),
                        facecolors=color,
                        edgecolors="white",
                        linewidth=0.4,
                        alpha=alpha,
                    )
                else:
                    ax.text(
                        0.01,
                        row_index,
                        "无",
                        transform=ax.get_yaxis_transform(),
                        ha="left",
                        va="center",
                        fontsize=6.2,
                        color="#64748B",
                    )
            ax.text(
                1.0,
                1.015,
                f"并集 {summary['unionDuration']:.3g} · 重叠 {summary['overlapDuration']:.3g} · 空档 {summary['gapDuration']:.3g}",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=6.3,
                color="#475569",
            )
            ax.axhline(len(series) - 0.5, color="#CBD5E1", linewidth=0.7)
        ax.set_yticks(range(len(labels)), labels)
        ax.invert_yaxis()
    elif chart_type == "tornado":
        if not series:
            raise ValueError("龙卷风图至少需要一个 series")
        baseline = float(spec.get("baseline", 0.0))
        if not math.isfinite(baseline):
            raise ValueError("baseline 必须是有限数值")
        records: list[tuple[str, float, float]] = []
        for index, item in enumerate(series):
            if not isinstance(item, dict):
                raise ValueError(f"series[{index}] 必须是对象")
            if item.get("low") is None or item.get("high") is None:
                raw_values = _numbers(
                    item.get("values", []),
                    f"series[{index}].values",
                    allow_empty=False,
                )
                if len(raw_values) != 2:
                    raise ValueError("龙卷风图 series 需要 low/high 或恰好两个 values")
                low, high = raw_values
            else:
                low = float(item["low"])
                high = float(item["high"])
            if not math.isfinite(low) or not math.isfinite(high) or not low <= baseline <= high:
                raise ValueError("龙卷风图要求有限数值且 low <= baseline <= high")
            records.append((str(item.get("name", f"Series {index + 1}")), low, high))
        if bool(spec.get("sort_effects", True)):
            records.sort(key=lambda record: max(baseline - record[1], record[2] - baseline))
        low_label = str(spec.get("low_label", "低情景"))
        high_label = str(spec.get("high_label", "高情景"))
        for index, (label, low, high) in enumerate(records):
            ax.barh(
                index,
                baseline - low,
                left=low,
                color=PALETTE[0],
                alpha=0.84,
                label=low_label if index == 0 else "_nolegend_",
            )
            ax.barh(
                index,
                high - baseline,
                left=baseline,
                color=PALETTE[1],
                alpha=0.84,
                label=high_label if index == 0 else "_nolegend_",
            )
            if bool(spec.get("annotate_values", True)):
                ax.text(low, index, f" {low:.3g}", ha="right", va="center", fontsize=6)
                ax.text(high, index, f" {high:.3g}", ha="left", va="center", fontsize=6)
        ax.axvline(baseline, color="#333333", linewidth=0.9, linestyle="--")
        ax.set_yticks(range(len(records)), [record[0] for record in records])
        ax.legend(frameon=False)
    elif chart_type == "histogram":
        if not series:
            raise ValueError("直方图至少需要一个 series")
        for index, item in enumerate(series):
            values = _numbers(item.get("values", item.get("y", [])), f"series[{index}].values", allow_empty=False)
            ax.hist(
                values,
                bins=max(5, min(100, int(item.get("bins", 20)))),
                alpha=0.52,
                label=str(item.get("name", f"Series {index + 1}")),
                color=PALETTE[index % len(PALETTE)],
                edgecolor="white",
                linewidth=0.5,
            )
    elif chart_type in {"box", "violin"}:
        if not series:
            raise ValueError("箱线图或小提琴图至少需要一个 series")
        values = [
            _numbers(item.get("values", item.get("y", [])), f"series[{index}].values", allow_empty=False)
            for index, item in enumerate(series)
        ]
        labels = [str(item.get("name", f"Series {index + 1}")) for index, item in enumerate(series)]
        if chart_type == "box":
            patch = ax.boxplot(values, tick_labels=labels, patch_artist=True, showmeans=True)
            for index, box in enumerate(patch["boxes"]):
                box.set_facecolor(PALETTE[index % len(PALETTE)])
                box.set_alpha(0.58)
        else:
            positions = np.arange(1, len(values) + 1)
            patch = ax.violinplot(
                values,
                positions=positions,
                showmeans=False,
                showmedians=True,
                showextrema=True,
            )
            for index, body in enumerate(patch["bodies"]):
                body.set_facecolor(PALETTE[index % len(PALETTE)])
                body.set_edgecolor("#333333")
                body.set_linewidth(0.55)
                body.set_alpha(0.58)
            for key in ("cbars", "cmins", "cmaxes", "cmedians"):
                if key in patch:
                    patch[key].set_color("#333333")
                    patch[key].set_linewidth(0.75)
            ax.set_xticks(positions, labels)
        for index, samples in enumerate(values):
            if len(samples) <= 500:
                offsets = np.linspace(-0.07, 0.07, len(samples)) if len(samples) > 1 else np.array([0.0])
                ax.scatter(np.full(len(samples), index + 1) + offsets, samples, s=9, color="#252525", alpha=0.35, zorder=3)
    elif chart_type == "pareto":
        if not series:
            raise ValueError("Pareto 图至少需要一个 series")
        x_sense = str(spec.get("x_sense", "min")).lower()
        y_sense = str(spec.get("y_sense", "min")).lower()
        if x_sense not in {"min", "max"} or y_sense not in {"min", "max"}:
            raise ValueError("Pareto 图的 x_sense/y_sense 只能是 min 或 max")
        x_multiplier = 1.0 if x_sense == "min" else -1.0
        y_multiplier = 1.0 if y_sense == "min" else -1.0
        for index, item in enumerate(series):
            if not isinstance(item, dict):
                raise ValueError(f"series[{index}] 必须是对象")
            x_values = _numbers(item.get("x", []), f"series[{index}].x", allow_empty=False)
            y_values = _numbers(item.get("y", []), f"series[{index}].y", allow_empty=False)
            if len(x_values) != len(y_values):
                raise ValueError("Pareto 图的 x 与 y 长度必须一致")
            transformed = np.column_stack(
                (np.asarray(x_values) * x_multiplier, np.asarray(y_values) * y_multiplier)
            )
            front_mask = np.zeros(len(transformed), dtype=bool)
            order = np.lexsort((transformed[:, 1], transformed[:, 0]))
            best_y = math.inf
            position = 0
            while position < len(order):
                group_end = position + 1
                x_value = transformed[order[position], 0]
                while group_end < len(order) and transformed[order[group_end], 0] == x_value:
                    group_end += 1
                group_indices = order[position:group_end]
                group_minimum = float(np.min(transformed[group_indices, 1]))
                if group_minimum < best_y:
                    minimum_indices = group_indices[
                        transformed[group_indices, 1] == group_minimum
                    ]
                    front_mask[minimum_indices] = True
                    best_y = group_minimum
                position = group_end
            color = PALETTE[index % len(PALETTE)]
            ax.scatter(x_values, y_values, s=22, alpha=0.28, color=color, label="_nolegend_")
            front_indices = np.flatnonzero(front_mask)
            front_indices = front_indices[np.argsort(np.asarray(x_values)[front_indices])]
            ax.plot(
                np.asarray(x_values)[front_indices],
                np.asarray(y_values)[front_indices],
                color=color,
                marker=MARKERS[index % len(MARKERS)],
                linewidth=1.5,
                markersize=4.5,
                label=str(item.get("name", f"Series {index + 1}")),
            )
            highlight_indices = item.get("highlight_indices", [])
            if not isinstance(highlight_indices, list):
                raise ValueError("highlight_indices 必须是整数数组")
            for highlight_index in highlight_indices:
                if not isinstance(highlight_index, int) or not 0 <= highlight_index < len(x_values):
                    raise ValueError("highlight_indices 包含越界索引")
                ax.scatter(
                    [x_values[highlight_index]],
                    [y_values[highlight_index]],
                    s=72,
                    marker="*",
                    color=color,
                    edgecolor="#111111",
                    linewidth=0.7,
                    zorder=4,
                )
    elif chart_type in {"heatmap", "contour"}:
        matrix = spec.get("matrix")
        if not isinstance(matrix, list) or not matrix:
            raise ValueError("热力图或等高线图需要非空 matrix")
        rows = [_numbers(row, f"matrix[{index}]", allow_empty=False) for index, row in enumerate(matrix)]
        if len({len(row) for row in rows}) != 1:
            raise ValueError("matrix 每行长度必须一致")
        cmap = str(spec.get("cmap") or "viridis")
        center = spec.get("center")
        norm = None
        minimum = min(min(row) for row in rows)
        maximum = max(max(row) for row in rows)
        if center is not None:
            center_value = float(center)
            if minimum < center_value < maximum:
                norm = TwoSlopeNorm(vmin=minimum, vcenter=center_value, vmax=maximum)
        if chart_type == "heatmap":
            image = ax.imshow(rows, cmap=cmap, norm=norm, aspect="auto")
            colorbar = fig.colorbar(image, ax=ax, shrink=0.84)
            colorbar.ax.tick_params(labelsize=7)
            _set_ticks(ax, spec)
            if bool(spec.get("annotate_heatmap")) and len(rows) * len(rows[0]) <= 400:
                for row_index, row in enumerate(rows):
                    for column_index, value in enumerate(row):
                        red, green, blue, _alpha = image.cmap(image.norm(value))
                        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
                        ax.text(
                            column_index,
                            row_index,
                            f"{value:.3g}",
                            ha="center",
                            va="center",
                            fontsize=6,
                            color="white" if luminance < 0.48 else "black",
                        )
        else:
            if len(rows) < 2 or len(rows[0]) < 2:
                raise ValueError("等高线图至少需要 2x2 matrix")
            x_values = _numbers(
                spec.get("x_values", list(range(len(rows[0])))),
                "x_values",
                allow_empty=False,
            )
            y_values = _numbers(
                spec.get("y_values", list(range(len(rows)))),
                "y_values",
                allow_empty=False,
            )
            if len(x_values) != len(rows[0]) or len(y_values) != len(rows):
                raise ValueError("等高线图 x_values/y_values 必须与 matrix 维度一致")
            if minimum == maximum:
                raise ValueError("等高线图 matrix 不能为常数")
            levels = max(3, min(50, int(spec.get("levels", 12))))
            x_grid, y_grid = np.meshgrid(x_values, y_values)
            if bool(spec.get("filled", True)):
                contour = ax.contourf(x_grid, y_grid, rows, levels=levels, cmap=cmap, norm=norm)
                contour_lines = ax.contour(
                    x_grid,
                    y_grid,
                    rows,
                    levels=levels,
                    colors="#333333",
                    linewidths=0.35,
                    alpha=0.5,
                )
            else:
                contour = ax.contour(x_grid, y_grid, rows, levels=levels, cmap=cmap, norm=norm)
                contour_lines = contour
            if bool(spec.get("annotate_values", False)):
                ax.clabel(contour_lines, inline=True, fontsize=6, fmt="%.3g")
            colorbar = fig.colorbar(contour, ax=ax, shrink=0.84)
            colorbar.ax.tick_params(labelsize=7)
            if spec.get("colorbar_label"):
                colorbar.set_label(str(spec["colorbar_label"]))

    _apply_semantic_layers(ax, spec, series if isinstance(series, list) else [])
    ax.set_title(str(spec.get("title", "")), pad=6, fontweight="normal", loc="left")
    ax.set_xlabel(str(spec.get("x_label", "")))
    ax.set_ylabel(str(spec.get("y_label", "")))
    ax.tick_params(direction="out")
    if str(spec.get("template", "")) == "paired_sensitivity":
        ax.legend(frameon=False, ncol=2, loc="best")
    elif not bool(spec.get("direct_labels", False)) and chart_type not in {"heatmap", "contour", "interval", "tornado", "box", "violin"} and (
        len(series) > 1 or chart_type == "pareto"
    ):
        ax.legend(frameon=False)
    if bool(spec.get("grid", False)) and chart_type not in {"heatmap", "box"}:
        ax.grid(True, axis="y", color="#DCE2E7", linewidth=0.45, alpha=0.72)


def _artifact_dimensions(target: Path, file_format: str, dpi: int) -> dict[str, Any]:
    if file_format == "png":
        from PIL import Image

        with Image.open(target) as image:
            pixel_width, pixel_height = image.size
        return {
            "widthPixels": pixel_width,
            "heightPixels": pixel_height,
            "widthInches": pixel_width / dpi,
            "heightInches": pixel_height / dpi,
        }
    if file_format == "svg":
        text = target.read_text(encoding="utf-8")[:4096]
        width_match = re.search(r'\bwidth="([0-9.]+)(pt|px|in)?"', text)
        height_match = re.search(r'\bheight="([0-9.]+)(pt|px|in)?"', text)
        if width_match and height_match:
            def inches(match: re.Match[str]) -> float:
                value = float(match.group(1))
                unit = match.group(2) or "px"
                return value if unit == "in" else value / (72.0 if unit == "pt" else 96.0)

            return {"widthInches": inches(width_match), "heightInches": inches(height_match)}
    if file_format == "pdf":
        payload = target.read_bytes()[:100_000]
        match = re.search(rb"/MediaBox\s*\[\s*[-0-9.]+\s+[-0-9.]+\s+([0-9.]+)\s+([0-9.]+)\s*\]", payload)
        if match:
            return {
                "widthInches": float(match.group(1)) / 72.0,
                "heightInches": float(match.group(2)) / 72.0,
            }
    return {}


def create_figure(spec: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    spec = _apply_template(spec)
    lint = figure_lint(spec)
    if not lint["ok"]:
        messages = "；".join(item["message"] for item in lint["issues"] if item["level"] == "error")
        raise ValueError(f"图形语义质检未通过：{messages}")
    chart_type = str(spec.get("chart_type", "line")).lower()
    if chart_type not in ALLOWED_TYPES:
        raise ValueError(f"不支持的图表类型：{chart_type}")
    output_dir.mkdir(parents=True, exist_ok=True)

    panels = spec.get("panels", []) if chart_type == "multi_panel" else []
    if chart_type == "multi_panel" and (not isinstance(panels, list) or not 1 <= len(panels) <= 6):
        raise ValueError("multi_panel 需要 1 至 6 个 panels")
    default_size = [7.2, max(3.2, math.ceil(len(panels) / 2) * 2.8)] if panels else [7.2, 4.6]
    figsize = spec.get("figsize") or default_size
    if not isinstance(figsize, list) or len(figsize) != 2:
        figsize = default_size
    width, height = (max(3.0, min(16.0, float(value))) for value in figsize)

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "font.size": 8,
            "axes.labelsize": 9,
            "axes.titlesize": 8.5,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.unicode_minus": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.7,
            "axes.grid": False,
            "savefig.facecolor": "white",
            "savefig.bbox": None,
        }
    )

    if panels:
        columns = min(2, len(panels))
        rows = math.ceil(len(panels) / columns)
        fig, axes = plt.subplots(rows, columns, figsize=(width, height), constrained_layout=True, squeeze=False)
        flat_axes = list(axes.flat)
        for index, panel in enumerate(panels):
            if not isinstance(panel, dict):
                raise ValueError(f"panels[{index}] 必须是对象")
            _draw_panel(fig, flat_axes[index], panel)
            if bool(spec.get("panel_labels", True)):
                flat_axes[index].text(
                    -0.12,
                    1.06,
                    ascii_uppercase[index],
                    transform=flat_axes[index].transAxes,
                    fontsize=10,
                    fontweight="bold",
                    va="top",
                )
        for ax in flat_axes[len(panels) :]:
            ax.set_visible(False)
        if spec.get("title"):
            fig.suptitle(str(spec["title"]), fontsize=9.2, fontweight="normal", x=0.02, ha="left")
    else:
        fig, ax = plt.subplots(figsize=(width, height), constrained_layout=True)
        _draw_panel(fig, ax, spec)

    formats = spec.get("formats", ["png", "pdf", "svg"])
    if not isinstance(formats, list):
        formats = ["png"]
    formats = list(dict.fromkeys(str(item).lower() for item in formats if str(item).lower() in ALLOWED_FORMATS))
    if not formats:
        formats = ["png"]
    filename = _safe_name(str(spec.get("filename", "figure")))
    dpi = max(300, min(1200, int(spec.get("dpi", 600))))
    artifacts: list[str] = []
    artifact_sizes: list[dict[str, Any]] = []
    for file_format in formats:
        target = output_dir / f"{filename}.{file_format}"
        export_dpi = dpi if file_format == "png" else min(dpi, 300)
        fig.savefig(
            target,
            dpi=export_dpi,
            bbox_inches=None,
            pad_inches=0,
            facecolor="white",
            edgecolor="none",
        )
        if file_format == "svg":
            svg_text = target.read_text(encoding="utf-8")
            target.write_text(
                "\n".join(line.rstrip() for line in svg_text.splitlines()) + "\n",
                encoding="utf-8",
            )
        artifacts.append(str(target.resolve()))
        artifact_sizes.append(
            {
                "path": str(target.resolve()),
                "format": file_format,
                **_artifact_dimensions(target, file_format, export_dpi),
            }
        )
    actual_width, actual_height = (float(value) for value in fig.get_size_inches())
    plt.close(fig)

    if bool(spec.get("save_spec", False)):
        spec_target = output_dir / f"{filename}.figure.json"
        spec_target.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts.append(str(spec_target.resolve()))
    return {
        "ok": True,
        "chartType": chart_type,
        "template": spec["template"],
        "panelCount": len(panels) if panels else 1,
        "palette": "Okabe-Ito",
        "dpi": dpi,
        "requestedSizeInches": {"width": width, "height": height},
        "actualSizeInches": {"width": actual_width, "height": actual_height},
        "artifactSizes": artifact_sizes,
        "figureLint": lint,
        "semanticSummary": _interval_semantics(spec) if chart_type == "interval" else None,
        "artifacts": artifacts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a publication-ready figure from JSON.")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8-sig"))
    if not isinstance(spec, dict):
        raise ValueError("spec 必须是 JSON 对象")
    print(json.dumps(create_figure(spec, args.output_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
