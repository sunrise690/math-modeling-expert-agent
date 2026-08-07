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
ALLOWED_TYPES = {"line", "scatter", "bar", "histogram", "box", "heatmap", "multi_panel"}
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
    if chart_type != "heatmap" and not isinstance(series, list):
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
    elif chart_type == "histogram":
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
    elif chart_type == "box":
        values = [
            _numbers(item.get("values", item.get("y", [])), f"series[{index}].values", allow_empty=False)
            for index, item in enumerate(series)
        ]
        labels = [str(item.get("name", f"Series {index + 1}")) for index, item in enumerate(series)]
        patch = ax.boxplot(values, tick_labels=labels, patch_artist=True, showmeans=True)
        for index, box in enumerate(patch["boxes"]):
            box.set_facecolor(PALETTE[index % len(PALETTE)])
            box.set_alpha(0.58)
        for index, samples in enumerate(values):
            if len(samples) <= 500:
                offsets = np.linspace(-0.07, 0.07, len(samples)) if len(samples) > 1 else np.array([0.0])
                ax.scatter(np.full(len(samples), index + 1) + offsets, samples, s=9, color="#252525", alpha=0.35, zorder=3)
    else:
        matrix = spec.get("matrix")
        if not isinstance(matrix, list) or not matrix:
            raise ValueError("热力图需要非空 matrix")
        rows = [_numbers(row, f"matrix[{index}]", allow_empty=False) for index, row in enumerate(matrix)]
        if len({len(row) for row in rows}) != 1:
            raise ValueError("matrix 每行长度必须一致")
        cmap = str(spec.get("cmap") or "viridis")
        center = spec.get("center")
        norm = None
        if center is not None:
            center_value = float(center)
            minimum = min(min(row) for row in rows)
            maximum = max(max(row) for row in rows)
            if minimum < center_value < maximum:
                norm = TwoSlopeNorm(vmin=minimum, vcenter=center_value, vmax=maximum)
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

    ax.set_title(str(spec.get("title", "")), pad=8, fontweight="bold")
    ax.set_xlabel(str(spec.get("x_label", "")))
    ax.set_ylabel(str(spec.get("y_label", "")))
    ax.tick_params(direction="out")
    if chart_type != "heatmap" and len(series) > 1:
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
