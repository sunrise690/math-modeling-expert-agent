from __future__ import annotations

import argparse
import json
import math
import re
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


def _set_ticks(ax: Any, spec: dict[str, Any]) -> None:
    x_ticks = spec.get("x_ticks")
    y_ticks = spec.get("y_ticks")
    if isinstance(x_ticks, list) and x_ticks:
        ax.set_xticks(range(len(x_ticks)), [str(item) for item in x_ticks])
    if isinstance(y_ticks, list) and y_ticks:
        ax.set_yticks(range(len(y_ticks)), [str(item) for item in y_ticks])


def _draw_panel(fig: Any, ax: Any, spec: dict[str, Any]) -> None:
    import numpy as np
    from matplotlib.colors import TwoSlopeNorm

    chart_type = str(spec.get("chart_type", "line")).lower()
    if chart_type not in ALLOWED_PANEL_TYPES:
        raise ValueError(f"不支持的面板类型：{chart_type}")
    series = spec.get("series", [])
    if chart_type not in {"heatmap", "contour"} and not isinstance(series, list):
        raise ValueError("series 必须是数组")

    if chart_type in {"line", "scatter"}:
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

    ax.set_title(str(spec.get("title", "")), pad=8, fontweight="bold")
    ax.set_xlabel(str(spec.get("x_label", "")))
    ax.set_ylabel(str(spec.get("y_label", "")))
    ax.tick_params(direction="out")
    if chart_type not in {"heatmap", "contour", "interval", "tornado", "box", "violin"} and (
        len(series) > 1 or chart_type == "pareto"
    ):
        ax.legend(frameon=False)
    if bool(spec.get("grid", False)) and chart_type not in {"heatmap", "box"}:
        ax.grid(True, color="#D8D8D8", linewidth=0.55, alpha=0.55)


def create_figure(spec: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
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
            "axes.titlesize": 9,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.unicode_minus": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.7,
            "axes.grid": False,
            "savefig.facecolor": "white",
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
            fig.suptitle(str(spec["title"]), fontsize=10, fontweight="bold")
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
    for file_format in formats:
        target = output_dir / f"{filename}.{file_format}"
        fig.savefig(
            target,
            dpi=dpi if file_format == "png" else min(dpi, 300),
            bbox_inches="tight",
            pad_inches=0.06,
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
    plt.close(fig)

    if bool(spec.get("save_spec", False)):
        spec_target = output_dir / f"{filename}.figure.json"
        spec_target.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts.append(str(spec_target.resolve()))
    return {
        "ok": True,
        "chartType": chart_type,
        "panelCount": len(panels) if panels else 1,
        "palette": "Okabe-Ito",
        "dpi": dpi,
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
