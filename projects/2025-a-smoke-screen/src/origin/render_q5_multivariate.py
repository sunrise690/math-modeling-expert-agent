"""Render the Q5 multivariate evidence figure with OriginPro.

The script deliberately analyses only the 15 submitted smoke-bomb plans.  The
search diagnostics retain counts, not candidate-level features, so treating the
1,334 generated candidates as PCA observations would be irreproducible.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import importlib.metadata
import json
import locale
import math
import os
import platform
import subprocess
import struct
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np


FEATURE_KEYS = (
    "heading_cos",
    "heading_sin",
    "speed",
    "release_time",
    "fuse_delay",
    "coverage_centroid",
    "centerline_duration",
    "unique_contribution_ratio",
    "criterion_retention_ratio",
)
FEATURE_LABELS = ("cosT", "sinT", "v", "t_r", "tau", "t_c", "d", "u", "r")
FEATURE_UNITS = ("1", "1", "m/s", "s", "s", "s", "s", "1", "1")
FONT_NAME = "Arial"
HEATMAP_LIMIT = 2.5
HEATMAP_LEVELS = tuple(np.linspace(-HEATMAP_LIMIT, HEATMAP_LIMIT, 11))
GRAPH_CONTRACT = {
    "schema_version": 1,
    "page_definition": "script_defined_from_blank_origin_graph",
    "matrix_plot_type_id": 220,
    "matrix_plot_type": "Origin matrix image",
    "panel_geometry_percent": {
        "A": {"left": 8.0, "top": 8.0, "width": 43.5, "height": 82.0},
        "B": {"left": 68.0, "top": 8.0, "width": 28.0, "height": 37.0},
        "C": {"left": 68.0, "top": 53.0, "width": 28.0, "height": 37.0},
    },
    "matrix_scale": {
        "kind": "diverging",
        "center": 0.0,
        "limits": [-HEATMAP_LIMIT, HEATMAP_LIMIT],
        "levels": list(HEATMAP_LEVELS),
        "color_scale_required": True,
        "label": "weighted z",
    },
    "font": FONT_NAME,
    "exports": {
        "png": {"width_px": 2232, "dpi": 360},
        "pdf": {
            "font_mode": "outlined_compact",
            "truetype": False,
            "outline_mode": 0,
            "origin_tree": "tr2.PDF.Fonts",
        },
        "svg": {"text_mode": "editable_text", "size_factor_percent": 100},
        "opju": {"editable": True, "roundtrip_required": True},
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def union_length(intervals: Iterable[Iterable[float]]) -> float:
    ordered = sorted((float(a), float(b)) for a, b in intervals if float(b) > float(a))
    if not ordered:
        return 0.0
    start, end = ordered[0]
    total = 0.0
    for left, right in ordered[1:]:
        if left <= end:
            end = max(end, right)
        else:
            total += end - start
            start, end = left, right
    return total + end - start


def weighted_interval_centroid(intervals: list[list[float]]) -> float:
    duration = sum(float(right) - float(left) for left, right in intervals)
    if duration <= 0.0:
        raise ValueError("有效区间总长度必须为正")
    return sum(
        0.5 * (float(left) + float(right)) * (float(right) - float(left))
        for left, right in intervals
    ) / duration


def build_analysis(validation: dict[str, Any]) -> dict[str, Any]:
    q5 = validation["results"]["Q5"]
    plans = list(q5["plans"])
    full_durations = list(
        validation["full_cylinder_secondary_audit"]["Q5"]["individual_durations"]
    )
    if len(plans) != 15 or len(full_durations) != len(plans):
        raise ValueError("Q5 多维图只接受与结果表一致的 15 条计划及 15 条保守复核时长")

    per_missile_union = {
        missile: union_length(intervals)
        for missile, intervals in q5["exact_centerline_union"].items()
    }
    raw_rows: list[list[float]] = []
    row_metadata: list[dict[str, Any]] = []
    shot_count: dict[str, int] = {}
    for index, (plan, full_duration) in enumerate(zip(plans, full_durations, strict=True)):
        drone = str(plan["drone_id"])
        missile = str(plan["missile_id"])
        shot_count[drone] = shot_count.get(drone, 0) + 1
        shot = shot_count[drone]
        intervals = [[float(a), float(b)] for a, b in plan["exact_centerline_intervals"]]
        duration = float(plan["exact_centerline_duration"])
        without = [
            interval
            for other_index, other in enumerate(plans)
            if other_index != index and str(other["missile_id"]) == missile
            for interval in other["exact_centerline_intervals"]
        ]
        unique_ratio = (per_missile_union[missile] - union_length(without)) / duration
        theta = math.radians(float(plan["heading_deg"]))
        raw_rows.append(
            [
                math.cos(theta),
                math.sin(theta),
                float(plan["speed"]),
                float(plan["release_time"]),
                float(plan["fuse_delay"]),
                weighted_interval_centroid(intervals),
                duration,
                unique_ratio,
                float(full_duration) / duration,
            ]
        )
        row_metadata.append(
            {
                "row_id": f"{drone}-{shot}",
                "drone_id": drone,
                "shot_index": shot,
                "missile_id": missile,
            }
        )

    raw = np.asarray(raw_rows, dtype=float)
    means = raw.mean(axis=0)
    raw_stds = raw.std(axis=0, ddof=1)
    if np.any(raw_stds <= 0.0):
        raise ValueError("多维分析矩阵包含零方差特征")
    # cos(theta), sin(theta) jointly represent one circular variable.  Scale the
    # centered two-column block by one group norm so rotating the angular origin
    # cannot change pairwise distances or the PCA spectrum.  The block therefore
    # contributes exactly one unit of total sample variance.
    heading_covariance = np.cov(raw[:, :2], rowvar=False, ddof=1)
    heading_group_scale = math.sqrt(float(np.trace(heading_covariance)))
    if not math.isfinite(heading_group_scale) or heading_group_scale <= 0.0:
        raise ValueError("航向圆周变量组尺度无效")
    applied_scales = raw_stds.copy()
    applied_scales[:2] = heading_group_scale
    standardized = (raw - means) / applied_scales

    # Keep the submitted UAV/shot sequence.  Fifteen jointly selected plans are
    # not independent population samples, so a dendrogram-like ordering would
    # overstate evidence for natural clusters.
    row_order = np.arange(len(plans), dtype=int)
    u, singular, vt = np.linalg.svd(standardized, full_matrices=False)
    eigenvalues = singular**2 / (len(plans) - 1)
    explained = eigenvalues / eigenvalues.sum()
    # PCA axes have arbitrary sign.  Anchor PC1 to later coverage and PC2 to
    # higher speed so repeated builds keep the same orientation.
    for component, anchor_feature in ((0, 5), (1, 2)):
        if vt[component, anchor_feature] < 0.0:
            u[:, component] *= -1.0
            vt[component, :] *= -1.0
    standardized_scores = u[:, :2] * math.sqrt(len(plans) - 1)
    weighted_feature_stds = standardized.std(axis=0, ddof=1)
    correlation_loadings = (
        vt[:2, :].T * np.sqrt(eigenvalues[:2]) / weighted_feature_stds[:, None]
    )

    return {
        "raw": raw,
        "means": means,
        "raw_stds": raw_stds,
        "applied_scales": applied_scales,
        "heading_group_scale": heading_group_scale,
        "standardized": standardized,
        "row_order": row_order.astype(int),
        "scores": standardized_scores,
        "loadings": correlation_loadings,
        "explained": explained,
        "rows": row_metadata,
    }


def write_csv(path: Path, header: list[str], rows: Iterable[Iterable[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def interpolate_palette(hex_colors: list[str], count: int = 256) -> list[tuple[int, int, int]]:
    anchors = np.asarray(
        [[int(color[i : i + 2], 16) for i in (1, 3, 5)] for color in hex_colors],
        dtype=float,
    )
    source = np.linspace(0.0, 1.0, len(anchors))
    target = np.linspace(0.0, 1.0, count)
    channels = [np.interp(target, source, anchors[:, channel]) for channel in range(3)]
    rgb = np.column_stack(channels)
    return [tuple(int(round(value)) for value in row) for row in rgb]


def write_riff_palette(path: Path, colors: list[tuple[int, int, int]]) -> None:
    """Write a Windows RIFF PAL file accepted by Origin's colormap loader."""

    entries = b"".join(struct.pack("<BBBB", red, green, blue, 0) for red, green, blue in colors)
    data = struct.pack("<HH", 0x0300, len(colors)) + entries
    riff_payload = b"PAL " + b"data" + struct.pack("<I", len(data)) + data
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF" + struct.pack("<I", len(riff_payload)) + riff_payload)


def set_data_label(
    label: Any,
    x: float,
    y: float,
    *,
    size: float,
    color: str,
    font_index: int,
    rotate: float = 0.0,
) -> None:
    label.set_int("attach", 2)
    label.set_float("x1", x)
    label.set_float("y1", y)
    label.set_float("fsize", size)
    label.set_int("font", font_index)
    label.color = color
    if rotate:
        label.set_float("rotate", rotate)


def add_data_label(
    layer: Any,
    text: str,
    x: float,
    y: float,
    *,
    size: float,
    color: str,
    font_index: int,
    rotate: float = 0.0,
) -> Any:
    label = layer.add_label(text, x, y)
    set_data_label(
        label,
        x,
        y,
        size=size,
        color=color,
        font_index=font_index,
        rotate=rotate,
    )
    return label


def style_axis_title(
    layer: Any, name: str, *, size: float, color: str, font_index: int
) -> None:
    label = layer.label(name)
    if label is not None:
        label.set_float("fsize", size)
        label.set_int("font", font_index)
        label.color = color


def remove_template_labels(layer: Any, names: Iterable[str]) -> None:
    """Remove stock-template labels without relying on localized object text."""

    for name in names:
        label = layer.label(name)
        if label is not None:
            label.remove()


def style_layer_canvas(op: Any, layer: Any, *, paper: str) -> None:
    """Force an explicit white layer background for stable headless export."""

    layer.set_int("color", op.ocolor(paper))


def style_numeric_axes(
    op: Any, layer: Any, *, ink: str, grid: str, font_index: int
) -> None:
    """Apply readable neutral axes to the two PCA support panels."""

    ink_color = op.ocolor(ink)
    grid_color = op.ocolor(grid)
    for axis_name in ("x", "y"):
        layer.set_int(f"{axis_name}.color", ink_color)
        layer.set_int(f"{axis_name}.label.color", ink_color)
        layer.set_float(f"{axis_name}.label.fsize", 11.0)
        layer.set_int(f"{axis_name}.label.font", font_index)
        layer.set_int(f"{axis_name}.grid.color", grid_color)
        layer.set_float(f"{axis_name}.grid.width", 0.55)
        layer.set_int(f"{axis_name}.showgrids", 1)
        layer.set_int(f"{axis_name}.opposite", 1)


def tick_indexed_strings(layer: Any, axis_name: str, labels: Iterable[str]) -> None:
    """Use Origin's tick-indexed string mode without a locale-dependent template."""

    layer.set_int(f"{axis_name}.label.type", 10)
    layer.set_str(f"{axis_name}.label.string", " ".join(f'\"{label}\"' for label in labels))


def origin_process_ids() -> set[int]:
    """Return Origin64 process IDs without disturbing an existing GUI session."""

    if os.name != "nt":
        return set()
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Origin64.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False),
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"无法读取 Origin 进程快照：{result.stderr.strip()}")
    pids: set[int] = set()
    for row in csv.reader(result.stdout.splitlines()):
        if len(row) < 2 or row[0].lower() != "origin64.exe":
            continue
        try:
            pids.add(int(row[1].replace(",", "")))
        except ValueError as error:
            raise RuntimeError(f"Origin 进程快照包含无效 PID：{row[1]}") from error
    return pids


def origin_status_snapshot() -> dict[str, Any]:
    """Perform the non-launching portion of the agent's ``origin_status`` check."""

    candidates: list[Path] = []
    configured = os.environ.get("ORIGIN_EXE", "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.append(Path(r"D:\Origin2024\Origin64.exe"))
    for variable in ("ProgramFiles", "ProgramW6432"):
        base = os.environ.get(variable, "").strip()
        if base:
            candidates.extend(Path(base).glob("OriginLab/Origin*/Origin64.exe"))
    executables = sorted(
        {str(path.resolve()) for path in candidates if path.is_file()},
        key=os.path.normcase,
    )
    try:
        originpro_version = importlib.metadata.version("originpro")
    except importlib.metadata.PackageNotFoundError:
        originpro_version = ""
    return {
        "check": "origin_status",
        "platform": sys.platform,
        "originpro_installed": bool(originpro_version),
        "originpro_version": originpro_version,
        "detected_executables": executables,
        "available": os.name == "nt" and bool(originpro_version) and bool(executables),
    }


def wait_for_origin_exit(before_pids: set[int], *, timeout_s: float = 15.0) -> tuple[set[int], set[int]]:
    """Wait until every Origin process launched by this run has exited."""

    deadline = time.monotonic() + timeout_s
    current = origin_process_ids()
    while current - before_pids and time.monotonic() < deadline:
        time.sleep(0.25)
        current = origin_process_ids()
    return current, current - before_pids


def export_graph_strict(page: Any, op: Any, target: Path, file_format: str) -> Path:
    """Export into an empty run directory and reject Origin's empty-string failure."""

    if target.exists():
        raise RuntimeError(f"临时导出目标意外存在：{target}")
    page.activate()
    if file_format == "pdf":
        op.set_lt_str("__LASTEXP", "")
        command = (
            'expgraph -sw type:=pdf overwrite:=replace '
            f'filename:="{target.name}" path:="{target.parent}" '
            "sysopts:=0 tr2.PDF.Fonts.Embed:=2 "
            "tr2.PDF.Fonts.OutLineMode:=0"
        )
        if not op.lt_exec(command):
            raise RuntimeError("Origin PDF 导出命令执行失败")
        generated = op.get_lt_str("__LASTEXP")
    else:
        generated = page.save_fig(
            str(target),
            type=file_format,
            replace=False,
            width=int(GRAPH_CONTRACT["exports"]["png"]["width_px"])
            if file_format == "png"
            else 0,
            ratio=int(GRAPH_CONTRACT["exports"]["svg"]["size_factor_percent"])
            if file_format == "svg"
            else 0,
        )
    if not generated:
        raise RuntimeError(f"Origin 返回空导出路径：{target.name}")
    generated_path = Path(generated).resolve()
    if generated_path != target.resolve():
        raise RuntimeError(
            f"Origin 导出路径不匹配：期望 {target.resolve()}，实际 {generated_path}"
        )
    if not generated_path.is_file() or generated_path.stat().st_size == 0:
        raise RuntimeError(f"Origin 未生成 {target.name}")
    if file_format == "svg":
        # Origin appends an extra blank line after the closing tag.  Keep the
        # exported vector content byte-for-byte otherwise, but canonicalize the
        # file ending so repository whitespace checks remain deterministic.
        svg_bytes = generated_path.read_bytes()
        generated_path.write_bytes(svg_bytes.rstrip(b" \t\r\n") + b"\n")
    return generated_path


def validate_saved_origin_project(
    op: Any, project: Path, analysis: dict[str, Any]
) -> dict[str, Any]:
    """Reopen the saved OPJU and verify its editable pages and linked data."""

    if not op.open(str(project), readonly=True, asksave=False):
        raise RuntimeError("Origin 无法重开刚保存的 OPJU 工程")
    graphs = [
        graph
        for graph in op.graph_list("p")
        if graph.lname == "Q5 nine-dimensional plan structure"
    ]
    if len(graphs) != 1:
        raise RuntimeError("OPJU 重开后目标图页缺失或重复")
    graph = graphs[0]
    plot_counts = [len(layer.plot_list()) for layer in graph]
    if len(graph) != 3 or plot_counts != [1, 3, 0]:
        raise RuntimeError(
            "OPJU 重开后的图层/绘图对象结构不符合合同："
            f"layers={len(graph)}, plots={plot_counts}"
        )

    matrix_books = [
        book for book in op.pages("m") if book.lname == "Q5 standardized features"
    ]
    if len(matrix_books) != 1:
        raise RuntimeError("OPJU 重开后九维矩阵工作簿缺失或重复")
    reopened_matrix = np.asarray(matrix_books[0][0].to_np2d(), dtype=float)
    expected_matrix = analysis["standardized"][analysis["row_order"], :][::-1, :]
    if reopened_matrix.shape != (15, 9) or not np.allclose(
        reopened_matrix, expected_matrix, rtol=1.0e-12, atol=1.0e-12
    ):
        raise RuntimeError("OPJU 重开后的九维矩阵与本轮规范矩阵不一致")

    score_books = [book for book in op.pages("w") if book.lname == "PCA scores"]
    loading_books = [book for book in op.pages("w") if book.lname == "PCA loadings"]
    if len(score_books) != 1 or len(loading_books) != 1:
        raise RuntimeError("OPJU 重开后 PCA 得分或载荷工作簿缺失")
    score_sheet = score_books[0][0]
    loading_sheet = loading_books[0][0]
    reopened_scores = np.column_stack(
        (score_sheet.to_list(0)[:15], score_sheet.to_list(1)[:15])
    ).astype(float)
    reopened_loadings = np.column_stack(
        (loading_sheet.to_list(0)[:9], loading_sheet.to_list(1)[:9])
    ).astype(float)
    if reopened_scores.shape != (15, 2) or not np.allclose(
        reopened_scores, analysis["scores"], rtol=1.0e-12, atol=1.0e-12
    ):
        raise RuntimeError("OPJU 重开后的 PCA 得分与本轮派生数据不一致")
    if reopened_loadings.shape != (9, 2) or not np.allclose(
        reopened_loadings, analysis["loadings"], rtol=1.0e-12, atol=1.0e-12
    ):
        raise RuntimeError("OPJU 重开后的 PCA 载荷与本轮派生数据不一致")
    return {
        "graph_pages": 1,
        "graph_layers": 3,
        "layer_plot_counts": plot_counts,
        "matrix_shape": [15, 9],
        "score_shape": [15, 2],
        "loading_shape": [9, 2],
    }


def configure_origin_figure(
    op: Any,
    analysis: dict[str, Any],
    output_stem: Path,
    palette_path: Path,
    palette: dict[str, Any],
) -> tuple[list[Path], str, dict[str, Any]]:
    paper = palette["roles"]["paper"]
    ink = palette["roles"]["ink"]
    muted = palette["roles"]["muted"]
    secondary = palette["roles"]["secondary"]
    grid = palette["roles"]["grid"]
    primary = palette["roles"]["primary"]

    if not op.oext:
        raise RuntimeError("This renderer requires an isolated external Origin automation session")
    op.set_show(False)
    op.new(asksave=False)
    origin_version = f"{op.lt_float('@V'):.6f}"
    font_index = int(op.lt_float(f"font({FONT_NAME})"))
    if font_index <= 0:
        raise RuntimeError(f"Origin 无法解析字体 {FONT_NAME}")
    if not op.lt_exec(
        f'system.font.default$="{FONT_NAME}";'
        f'system.font.labelName$="{FONT_NAME}";'
        f'system.font.greekName$="{FONT_NAME}";'
        "@EMRD=0;"
    ):
        raise RuntimeError("Origin 字体与 PDF 嵌入设置失败")

    # ----- Data books -----
    matrix = analysis["standardized"][analysis["row_order"], :][::-1, :]
    matrix_sheet = op.new_sheet(type="m", lname="Q5 standardized features", hidden=True)
    matrix_sheet.from_np(matrix)
    matrix_sheet.xymap = (1.0, float(matrix.shape[1]), 1.0, float(matrix.shape[0]))

    ordered_rows = [analysis["rows"][int(index)] for index in analysis["row_order"]]
    row_labels = [f"{row['row_id']}/{row['missile_id']}" for row in ordered_rows][::-1]

    score_sheet = op.new_sheet(type="w", lname="PCA scores", hidden=True)
    score_sheet.from_list(0, analysis["scores"][:, 0].tolist(), lname="PC1", axis="X")
    score_sheet.from_list(1, analysis["scores"][:, 1].tolist(), lname="PC2", axis="Y")
    score_sheet.from_list(2, [row["missile_id"] for row in analysis["rows"]], lname="missile", axis="L")
    score_sheet.from_list(3, [row["row_id"] for row in analysis["rows"]], lname="plan", axis="L")

    loading_sheet = op.new_sheet(type="w", lname="PCA loadings", hidden=True)
    loading_sheet.from_list(0, analysis["loadings"][:, 0].tolist(), lname="PC1 correlation", axis="X")
    loading_sheet.from_list(1, analysis["loadings"][:, 1].tolist(), lname="PC2 correlation", axis="Y")
    loading_sheet.from_list(2, list(FEATURE_LABELS), lname="feature", axis="L")

    # ----- Page and panel A: full 15 x 9 feature matrix -----
    # Start from the blank Origin graph and specify the matrix-image plot type
    # explicitly.  No named heatmap template or user-folder theme participates
    # in the rendering contract.
    page = op.new_graph(lname="Q5 multivariate structure", hidden=True)
    page.set_float("width", 6900.0)
    page.set_float("height", 5050.0)
    page.set_int("aa", 1)
    page.set_int("BaseColor", op.ocolor(paper))
    heat = page[0]
    for prop, value in (("left", 8.0), ("top", 8.0), ("width", 43.5), ("height", 82.0)):
        heat.set_float(prop, value)
    heat_plot = heat.add_mplot(matrix_sheet, z=0, type=220)
    if heat_plot is None:
        raise RuntimeError("Origin 无法创建显式 type=220 矩阵图")
    heat_plot.colormap = str(palette_path)
    heat_plot.zlevels = {"minors": 0, "levels": list(HEATMAP_LEVELS)}
    configured_levels = np.asarray(heat_plot.zlevels["levels"], dtype=float)
    if configured_levels.shape != (len(HEATMAP_LEVELS),) or not np.allclose(
        configured_levels,
        np.asarray(HEATMAP_LEVELS),
        atol=1.0e-10,
        rtol=0.0,
    ):
        raise RuntimeError(
            "Origin 未接受固定发散色阶："
            f"期望 {list(HEATMAP_LEVELS)}，实际 {configured_levels.tolist()}"
        )
    heat.set_int("cmap.colorBelow", op.ocolor(palette["diverging_standardized"][0]))
    heat.set_int("cmap.colorAbove", op.ocolor(palette["diverging_standardized"][-1]))
    heat.set_int("cmap.colorMiss", op.ocolor(paper))
    heat.set_xlim(0.5, 9.5, 1.0)
    heat.set_ylim(0.5, 15.5, 1.0)
    style_layer_canvas(op, heat, paper=paper)
    style_numeric_axes(op, heat, ink=ink, grid=grid, font_index=font_index)
    tick_indexed_strings(heat, "x", FEATURE_LABELS)
    tick_indexed_strings(heat, "y", row_labels)
    heat.set_float("x.label.fsize", 10.5)
    heat.set_float("y.label.fsize", 10.5)
    heat.set_float("x.label.rotate", 0.0)
    heat.set_int("x.showgrids", 0)
    heat.set_int("y.showgrids", 0)
    heat.set_int("x.opposite", 1)
    heat.set_int("y.opposite", 1)
    heat.axis("x").title = "Weighted standardized feature (fixed semantic order)"
    heat.axis("y").title = "Selected shot / target (fixed UAV-shot order)"
    style_axis_title(heat, "xb", size=12.0, color=ink, font_index=font_index)
    style_axis_title(heat, "yl", size=12.0, color=ink, font_index=font_index)
    remove_template_labels(heat, ("Legend", "_202", "LTEXT", "XT", "YR"))
    heat.lt_exec("spectrum;")
    op.wait()
    color_scale = heat.label("SPECTRUM1")
    if color_scale is None:
        raise RuntimeError("Origin 色标对象缺失")
    color_scale.set_int("attach", 0)
    for prop, value in (
        ("left", 3750.0),
        ("top", 1450.0),
        ("width", 170.0),
        ("height", 1800.0),
        ("barthick", 80.0),
        ("lgap", 18.0),
    ):
        color_scale.set_float(prop, value)
    heat.lt_exec(
        "Spectrum1.levels.major=3; Spectrum1.levels.from=-2.5; "
        "Spectrum1.levels.to=2.5; Spectrum1.levels.type=1; "
        'Spectrum1.levels.inc=1; Spectrum1.levels.inc$="1.25"; '
        "Spectrum1.levels.minorticks=0; Spectrum1.labels.autodisp=0; "
        "Spectrum1.labels.numdisp=6; Spectrum1.labels.cusfmt$=\"*3\"; "
        f"Spectrum1.labels.font={font_index}; Spectrum1.labels.fsize=10; "
        "Spectrum1.revorder=0;"
    )
    scale_title = heat.add_label("weighted z")
    scale_title.set_int("attach", 0)
    scale_title.set_float("left", 3680.0)
    scale_title.set_float("top", 1210.0)
    scale_title.set_float("fsize", 10.0)
    scale_title.set_int("font", font_index)
    scale_title.color = muted
    add_data_label(
        heat,
        "A  Nine-feature signature",
        0.55,
        15.92,
        size=15.0,
        color=ink,
        font_index=font_index,
    )

    # ----- Panel B: normalized PCA scores -----
    score = page.add_layer(0)
    for prop, value in (("left", 68.0), ("top", 8.0), ("width", 28.0), ("height", 37.0)):
        score.set_float(prop, value)
    style_layer_canvas(op, score, paper=paper)
    style_numeric_axes(op, score, ink=ink, grid=grid, font_index=font_index)
    score.set_xlim(-1.85, 1.95, 1.0)
    score.set_ylim(-1.75, 1.75, 1.0)
    score.axis("x").title = f"PC1 standardized score ({100.0 * analysis['explained'][0]:.1f}%)"
    score.axis("y").title = f"PC2 standardized score ({100.0 * analysis['explained'][1]:.1f}%)"
    score.set_int("x.showgrids", 1)
    score.set_int("y.showgrids", 1)
    score.set_int("x.opposite", 1)
    score.set_int("y.opposite", 1)
    style_axis_title(score, "xb", size=13.0, color=ink, font_index=font_index)
    style_axis_title(score, "yl", size=13.0, color=ink, font_index=font_index)
    remove_template_labels(score, ("XT", "YR", "LTEXT", "SPECTRUM1"))
    horizontal = score.add_line(-1.85, 0.0, 1.95, 0.0)
    horizontal.color = grid
    horizontal.width = 0.7
    vertical = score.add_line(0.0, -1.75, 0.0, 1.75)
    vertical.color = grid
    vertical.width = 0.7

    score_xy = analysis["scores"]
    rows = analysis["rows"]
    drones = sorted({str(row["drone_id"]) for row in rows})
    route_line_types = (1, 2, 3, 4, 5)
    for drone, line_type in zip(drones, route_line_types, strict=True):
        indices = [index for index, row in enumerate(rows) if row["drone_id"] == drone]
        indices.sort(key=lambda index: int(rows[index]["shot_index"]))
        for left_index, right_index in zip(indices[:-1], indices[1:], strict=True):
            route = score.add_line(
                float(score_xy[left_index, 0]),
                float(score_xy[left_index, 1]),
                float(score_xy[right_index, 0]),
                float(score_xy[right_index, 1]),
            )
            route.color = secondary
            route.width = 1.2
            route.type = line_type
        center = score_xy[indices, :].mean(axis=0)
        offsets = {
            "FY1": (-0.16, 0.16),
            "FY2": (-0.30, 0.20),
            "FY3": (0.02, 0.15),
            "FY4": (0.02, -0.18),
            "FY5": (0.08, -0.20),
        }
        dx, dy = offsets[drone]
        add_data_label(
            score,
            drone,
            float(center[0] + dx),
            float(center[1] + dy),
            size=12.0,
            color=ink,
            font_index=font_index,
        )

    missile_styles = {
        "M1": (3, "#365D7D"),
        "M2": (2, primary),
        "M3": (1, "#94AEC4"),
    }
    for missile, (symbol, color) in missile_styles.items():
        indices = [index for index, row in enumerate(rows) if row["missile_id"] == missile]
        x_col = score_sheet.cols
        score_sheet.cols = x_col + 2
        score_sheet.from_list(x_col, score_xy[indices, 0].tolist(), lname=f"{missile} PC1", axis="X")
        score_sheet.from_list(x_col + 1, score_xy[indices, 1].tolist(), lname=missile, axis="Y")
        scatter = score.add_plot(score_sheet, coly=x_col + 1, colx=x_col, type="s")
        scatter.color = color
        scatter.symbol_kind = symbol
        scatter.symbol_interior = 1 if missile != "M3" else 2
        scatter.symbol_size = 11.0
        scatter.set_cmd("-kh 24")
    score.lt_exec("legend -r;")
    score_legend = score.label("Legend")
    if score_legend is not None:
        score_legend.text = r"\l(1) M1   \l(2) M2   \l(3) M3"
        score_legend.set_int("showframe", 0)
        set_data_label(
            score_legend,
            0.64,
            0.58,
            size=12.0,
            color=ink,
            font_index=font_index,
        )
    add_data_label(
        score,
        "B  PCA score map",
        -1.80,
        1.88,
        size=18.0,
        color=ink,
        font_index=font_index,
    )

    # ----- Panel C: variable-PC correlation loadings -----
    loading = page.add_layer(0)
    for prop, value in (("left", 68.0), ("top", 53.0), ("width", 28.0), ("height", 37.0)):
        loading.set_float(prop, value)
    style_layer_canvas(op, loading, paper=paper)
    style_numeric_axes(op, loading, ink=ink, grid=grid, font_index=font_index)
    loading.set_xlim(-1.08, 1.08, 0.5)
    loading.set_ylim(-1.08, 1.08, 0.5)
    loading.axis("x").title = "Feature-PC1 correlation"
    loading.axis("y").title = "Feature-PC2 correlation"
    loading.set_int("x.showgrids", 1)
    loading.set_int("y.showgrids", 1)
    loading.set_int("x.opposite", 1)
    loading.set_int("y.opposite", 1)
    style_axis_title(loading, "xb", size=13.0, color=ink, font_index=font_index)
    style_axis_title(loading, "yl", size=13.0, color=ink, font_index=font_index)
    circle_angle = np.linspace(0.0, 2.0 * math.pi, 97)
    for left_angle, right_angle in zip(circle_angle[:-1], circle_angle[1:], strict=True):
        segment = loading.add_line(
            float(math.cos(left_angle)),
            float(math.sin(left_angle)),
            float(math.cos(right_angle)),
            float(math.sin(right_angle)),
        )
        segment.color = grid
        segment.width = 0.8
    remove_template_labels(loading, ("Legend", "LTEXT", "SPECTRUM1", "_202", "XT", "YR"))
    xzero = loading.add_line(-1.08, 0.0, 1.08, 0.0)
    xzero.color = grid
    xzero.width = 0.7
    yzero = loading.add_line(0.0, -1.08, 0.0, 1.08)
    yzero.color = grid
    yzero.width = 0.7
    loading_offsets = {
        "cosT": (-0.16, 0.03),
        "sinT": (0.03, 0.05),
        "v": (0.04, -0.07),
        "t_r": (0.03, -0.05),
        "tau": (0.03, 0.03),
        "t_c": (0.03, 0.04),
        "d": (0.03, -0.07),
        "u": (0.03, 0.03),
        "r": (-0.12, 0.04),
    }
    for label_text, (x_value, y_value) in zip(FEATURE_LABELS, analysis["loadings"], strict=True):
        arrow = loading.add_line(0.0, 0.0, float(x_value), float(y_value))
        arrow.color = primary
        arrow.width = 1.0
        arrow.set_int("arrowendshape", 2)
        dx, dy = loading_offsets[label_text]
        add_data_label(
            loading,
            label_text,
            float(x_value + dx),
            float(y_value + dy),
            size=12.0,
            color=ink,
            font_index=font_index,
        )
    add_data_label(
        loading,
        "C  Correlation loadings",
        -1.05,
        1.18,
        size=18.0,
        color=ink,
        font_index=font_index,
    )
    add_data_label(
        loading,
        f"PC1+PC2 = {100.0 * analysis['explained'][:2].sum():.1f}%  |  PC1-PC3 = {100.0 * analysis['explained'][:3].sum():.1f}%",
        -1.02,
        0.91,
        size=10.0,
        color=muted,
        font_index=font_index,
    )

    page.lname = "Q5 nine-dimensional plan structure"
    op.wait()
    remove_template_labels(heat, ("Legend", "_202", "LTEXT", "XT", "YR"))
    # Origin may recreate legends lazily after a plot is added.  Delete only the
    # loading-panel scatter legend; the matrix color scale is required evidence.
    loading.lt_exec("legend -d;")
    remove_template_labels(loading, ("Legend", "_202", "SPECTRUM1", "XT", "YR"))
    op.wait()

    # Spectrum redraws can reset its anchor.  Apply physical page coordinates
    # only after the final update so the scale stays inside the inter-panel gap.
    color_scale.obj.PutLeft(3600)
    color_scale.obj.PutTop(1450)
    color_scale.obj.PutWidth(170)
    color_scale.obj.PutHeight(1800)
    scale_title.obj.PutLeft(3500)
    scale_title.obj.PutTop(1210)

    output_stem.parent.mkdir(parents=True, exist_ok=True)
    artifacts: list[Path] = []
    for suffix in ("png", "pdf", "svg"):
        target = output_stem.with_suffix(f".{suffix}")
        artifacts.append(export_graph_strict(page, op, target, suffix))

    project = output_stem.with_suffix(".opju")
    if project.exists():
        raise RuntimeError(f"临时 OPJU 目标意外存在：{project}")
    if not op.save(str(project)):
        raise RuntimeError("Origin 保存 OPJU 返回失败")
    if not project.is_file() or project.stat().st_size == 0:
        raise RuntimeError("Origin 未生成可编辑 OPJU 工程")
    roundtrip_summary = validate_saved_origin_project(op, project, analysis)
    artifacts.append(project.resolve())
    return artifacts, origin_version, roundtrip_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the Q5 multivariate Origin figure")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="2025 A project root",
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    validation_path = root / "validation" / "q3_q5_independent.json"
    palette_spec_path = root / "src" / "matlab" / "palette_spec.json"
    support_dir = root / "support" / "multivariate"
    source_path = Path(__file__).resolve()
    output_stem = support_dir / "q5_multivariate_structure"
    palette_path = support_dir / "editorial_standardized_diverging.pal"
    contract_path = support_dir / "q5_multivariate_figure_contract.json"
    capability_path = support_dir / "origin_capability_snapshot.json"
    provenance_path = support_dir / "q5_multivariate_provenance.json"
    run_log_path = support_dir / "q5_multivariate_run.json"
    support_dir.mkdir(parents=True, exist_ok=True)

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    palette = json.loads(palette_spec_path.read_text(encoding="utf-8"))
    analysis = build_analysis(validation)
    status_snapshot = origin_status_snapshot()
    if not status_snapshot["available"]:
        raise RuntimeError(
            "origin_status 未通过：需要 Windows、OriginPro 可执行文件和官方 originpro 包"
        )

    run_id = f"origin-{time.time_ns()}"
    run_started_ns = time.time_ns()
    final_data_paths: list[Path] = []
    final_artifacts: list[Path] = []
    origin_version = ""
    origin_executable = Path()
    origin_executable_hash = ""
    originpro_version = importlib.metadata.version("originpro")
    originext_version = importlib.metadata.version("OriginExt")
    project_roundtrip: dict[str, Any] = {}
    before_pids = origin_process_ids()
    launched_pids: set[int] = set()
    after_pids: set[int] = set()

    with tempfile.TemporaryDirectory(prefix=".origin-run-", dir=support_dir) as temporary:
        run_dir = Path(temporary).resolve()
        temporary_output_stem = run_dir / output_stem.name
        temporary_palette = run_dir / palette_path.name
        temporary_contract = run_dir / contract_path.name
        temporary_capability = run_dir / capability_path.name
        temporary_raw_csv = run_dir / "q5_multivariate_features.csv"
        temporary_scaling_csv = run_dir / "q5_multivariate_standardization.csv"
        temporary_weighted_z_csv = run_dir / "q5_multivariate_weighted_z.csv"
        temporary_score_csv = run_dir / "q5_pca_scores.csv"
        temporary_loading_csv = run_dir / "q5_pca_loadings.csv"

        write_riff_palette(
            temporary_palette,
            interpolate_palette(list(palette["diverging_standardized"])),
        )
        temporary_contract.write_text(
            json.dumps(GRAPH_CONTRACT, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        raw_rows = [
            [
                metadata["row_id"],
                metadata["drone_id"],
                metadata["shot_index"],
                metadata["missile_id"],
                *values,
            ]
            for metadata, values in zip(analysis["rows"], analysis["raw"], strict=True)
        ]
        write_csv(
            temporary_raw_csv,
            ["row_id", "drone_id", "shot_index", "missile_id", *FEATURE_KEYS],
            raw_rows,
        )
        write_csv(
            temporary_scaling_csv,
            [
                "feature",
                "unit",
                "sample_mean",
                "raw_sample_std_ddof1",
                "applied_scale",
                "semantic_group",
                "group_total_sample_variance",
            ],
            [
                [
                    feature,
                    unit,
                    mean,
                    raw_std,
                    applied_scale,
                    "heading_direction" if index < 2 else feature,
                    1.0,
                ]
                for index, (feature, unit, mean, raw_std, applied_scale) in enumerate(
                    zip(
                        FEATURE_KEYS,
                        FEATURE_UNITS,
                        analysis["means"],
                        analysis["raw_stds"],
                        analysis["applied_scales"],
                        strict=True,
                    )
                )
            ],
        )
        write_csv(
            temporary_weighted_z_csv,
            [
                "row_id",
                "drone_id",
                "shot_index",
                "missile_id",
                *[f"weighted_z_{key}" for key in FEATURE_KEYS],
            ],
            [
                [
                    row["row_id"],
                    row["drone_id"],
                    row["shot_index"],
                    row["missile_id"],
                    *values,
                ]
                for row, values in zip(
                    analysis["rows"], analysis["standardized"], strict=True
                )
            ],
        )
        write_csv(
            temporary_score_csv,
            [
                "row_id",
                "drone_id",
                "shot_index",
                "missile_id",
                "pc1_standardized_score",
                "pc2_standardized_score",
            ],
            [
                [
                    row["row_id"],
                    row["drone_id"],
                    row["shot_index"],
                    row["missile_id"],
                    *score,
                ]
                for row, score in zip(analysis["rows"], analysis["scores"], strict=True)
            ],
        )
        write_csv(
            temporary_loading_csv,
            ["feature", "unit", "pc1_correlation", "pc2_correlation"],
            [
                [feature, unit, *values]
                for feature, unit, values in zip(
                    FEATURE_KEYS, FEATURE_UNITS, analysis["loadings"], strict=True
                )
            ],
        )

        try:
            import originpro as op
        except ImportError as error:
            raise RuntimeError("缺少 OriginLab 官方 originpro Python 包") from error

        temporary_artifacts: list[Path] = []
        render_error: Exception | None = None
        exit_error: Exception | None = None
        exit_requested = False
        try:
            temporary_artifacts, origin_version, project_roundtrip = configure_origin_figure(
                op,
                analysis,
                temporary_output_stem,
                temporary_palette,
                palette,
            )
            origin_program_dir = Path(op.path("e")).resolve()
            origin_executable = origin_program_dir / "Origin64.exe"
            if not origin_executable.is_file():
                raise RuntimeError(f"Origin 可执行文件路径无效：{origin_executable}")
            origin_executable_hash = sha256(origin_executable)
            during_pids = origin_process_ids()
            launched_pids = during_pids - before_pids
            if not launched_pids:
                raise RuntimeError("外部自动化未创建独立 Origin 进程")
        except Exception as error:
            render_error = error
        finally:
            gc.collect()
            try:
                if getattr(op, "oext", False):
                    op.exit()
                    exit_requested = True
            except Exception as error:
                exit_error = error
            gc.collect()
            try:
                after_pids, remaining_new_pids = wait_for_origin_exit(before_pids)
            except Exception as error:
                if exit_error is None:
                    exit_error = error
                after_pids = origin_process_ids()
                remaining_new_pids = after_pids - before_pids

        if render_error is not None:
            raise RuntimeError(f"Origin 渲染失败：{render_error}") from render_error
        if exit_error is not None:
            raise RuntimeError(f"Origin 正常退出失败：{exit_error}") from exit_error
        if not exit_requested or remaining_new_pids:
            raise RuntimeError(
                "Origin 自动化退出门禁失败；仍有新增进程："
                + ", ".join(str(pid) for pid in sorted(remaining_new_pids))
            )

        # Origin exports the requested pixels but may omit the physical DPI tag.
        # Re-save only PNG container metadata while it is still in the run directory.
        from PIL import Image

        temporary_png = temporary_output_stem.with_suffix(".png")
        with Image.open(temporary_png) as image:
            pixels = image.copy()
        pixels.save(
            temporary_png,
            dpi=(
                int(GRAPH_CONTRACT["exports"]["png"]["dpi"]),
                int(GRAPH_CONTRACT["exports"]["png"]["dpi"]),
            ),
        )

        capability = {
            "schema_version": 2,
            "run_id": run_id,
            "status": "pass",
            "origin_status": status_snapshot,
            "renderer": f"OriginPro {origin_version}",
            "origin_version": origin_version,
            "origin_executable": str(origin_executable),
            "origin_executable_sha256": origin_executable_hash,
            "originpro_version": originpro_version,
            "originext_version": originext_version,
            "python": platform.python_version(),
            "external_automation": True,
            "hidden_session": True,
            "license_session_verified_by_render": True,
            "scripted_page_verified": True,
            "required_exports_completed": ["png", "pdf", "svg", "opju"],
            "project_save_verified": True,
            "project_roundtrip_verified": True,
            "project_roundtrip": project_roundtrip,
            "modal_dialog_blocked": False,
            "origin_exit_requested": exit_requested,
            "origin_exit_verified": True,
            "origin_pids_before": sorted(before_pids),
            "origin_pids_launched": sorted(launched_pids),
            "origin_pids_after": sorted(after_pids),
            "remaining_new_origin_pids": [],
        }
        temporary_capability.write_text(
            json.dumps(capability, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        temporary_data_paths = [
            temporary_raw_csv,
            temporary_scaling_csv,
            temporary_weighted_z_csv,
            temporary_score_csv,
            temporary_loading_csv,
            temporary_palette,
            temporary_contract,
            temporary_capability,
        ]
        expected_temporary_artifacts = [
            temporary_output_stem.with_suffix(suffix)
            for suffix in (".png", ".pdf", ".svg", ".opju")
        ]
        if {path.resolve() for path in temporary_artifacts} != {
            path.resolve() for path in expected_temporary_artifacts
        }:
            raise RuntimeError("Origin 四格式产物集合与渲染合约不一致")
        for temporary_path in [*temporary_data_paths, *expected_temporary_artifacts]:
            if not temporary_path.is_file() or temporary_path.stat().st_size == 0:
                raise RuntimeError(f"本轮闭包产物缺失：{temporary_path.name}")

        # Only a complete, exited run may replace the previous accepted closure.
        final_data_paths = [support_dir / path.name for path in temporary_data_paths]
        final_artifacts = [support_dir / path.name for path in expected_temporary_artifacts]
        for temporary_path, final_path in zip(
            [*temporary_data_paths, *expected_temporary_artifacts],
            [*final_data_paths, *final_artifacts],
            strict=True,
        ):
            os.replace(temporary_path, final_path)

    run_completed_ns = time.time_ns()
    provenance = {
        "schema_version": 2,
        "run_id": run_id,
        "command": ["python", "-B", "src/origin/render_q5_multivariate.py"],
        "renderer_backend": "originpro",
        "origin_version": origin_version,
        "origin_executable": str(origin_executable),
        "origin_executable_sha256": origin_executable_hash,
        "originpro_version": originpro_version,
        "originext_version": originext_version,
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "source": source_path.relative_to(root).as_posix(),
        "source_sha256": sha256(source_path),
        "input": validation_path.relative_to(root).as_posix(),
        "input_sha256": sha256(validation_path),
        "palette_spec": palette_spec_path.relative_to(root).as_posix(),
        "palette_spec_sha256": sha256(palette_spec_path),
        "graph_contract": {
            "path": contract_path.relative_to(root).as_posix(),
            "sha256": sha256(contract_path),
            "mode": "scripted_page",
            "base_template": "blank origin graph",
        },
        "capability_snapshot": {
            "path": capability_path.relative_to(root).as_posix(),
            "sha256": sha256(capability_path),
        },
        "derived_data": {
            path.relative_to(root).as_posix(): sha256(path)
            for path in final_data_paths
            if path not in {contract_path, capability_path}
        },
        "preprocessing": {
            "observations": 15,
            "features": list(FEATURE_KEYS),
            "standardization": "sample z-score (ddof=1) for scalar features",
            "circular_heading_group": ["heading_cos", "heading_sin"],
            "circular_heading_scaling": "centered cos/sin block divided by sqrt(trace(sample covariance)); total group sample variance = 1",
            "heading_group_scale": float(analysis["heading_group_scale"]),
            "row_order": "fixed UAV identifier and within-UAV shot sequence; no clustering",
            "pca": "SVD of the same weighted standardized matrix; deterministic sign anchors",
            "loading_definition": "Pearson correlation between each weighted feature and each standardized PC score",
        },
        "execution": {
            "run_started_ns": run_started_ns,
            "run_completed_ns": run_completed_ns,
            "external_automation": True,
            "hidden_session": True,
            "origin_exit_requested": True,
            "origin_exit_verified": True,
            "project_roundtrip_verified": True,
            "remaining_new_origin_pids": [],
            "required_exports_completed": ["png", "pdf", "svg", "opju"],
        },
        "export_parameters": GRAPH_CONTRACT["exports"],
        "explained_variance_ratio": analysis["explained"].tolist(),
        "row_order": [analysis["rows"][int(index)]["row_id"] for index in analysis["row_order"]],
        "artifacts": {
            path.relative_to(root).as_posix(): sha256(path) for path in final_artifacts
        },
        "limitations": [
            "descriptive analysis of 15 jointly selected final plans, not independent replicates",
            "PC1 and PC2 do not retain all nine-dimensional variation",
            "PCA point separation is descriptive and must not be interpreted as natural clustering",
            "does not establish global optimality, multi-seed stability or real-world robustness",
        ],
    }
    provenance_path.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    run_log_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": run_id,
                "status": "pass",
                "renderer": f"OriginPro {origin_version}",
                "originpro_version": originpro_version,
                "originext_version": originext_version,
                "external_automation": True,
                "hidden_session": True,
                "origin_exit_verified": True,
                "project_roundtrip_verified": True,
                "remaining_new_origin_pids": [],
                "export_formats": ["png", "pdf", "svg", "opju"],
                "capability_snapshot": capability_path.relative_to(root).as_posix(),
                "capability_snapshot_sha256": sha256(capability_path),
                "provenance": provenance_path.relative_to(root).as_posix(),
                "provenance_sha256": sha256(provenance_path),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": True,
                "renderer": f"OriginPro {origin_version}",
                "run_id": run_id,
                "artifacts": [str(path) for path in final_artifacts],
                "pc12": float(analysis["explained"][:2].sum()),
                "pc123": float(analysis["explained"][:3].sum()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
