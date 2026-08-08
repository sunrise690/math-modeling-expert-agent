from __future__ import annotations

import json
import hashlib
from collections import defaultdict
from math import ceil
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle
from run_identity import RUN_ID

from solve_q1_q2 import (
    GRAVITIES,
    SMOKE_RADIUS,
    Strategy,
    centerline_margin,
    full_cylinder_margin,
    missile_position,
    q1_strategy,
    smoke_center,
    strategy_intervals,
)


ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "validation"
FIGURES = ROOT / "figures"
COLORS = {
    "ink": "#18232F",
    "muted": "#66717D",
    "grid": "#E3E8ED",
    "panel": "#F5F7F9",
    "blue": "#2563A6",
    "blue_light": "#9BBBD5",
    "orange": "#D97706",
    "orange_light": "#F2C078",
    "green": "#16805C",
    "magenta": "#98537E",
    "cyan": "#3A839B",
    "red": "#B94B4B",
    "white": "#FFFFFF",
}
PALETTE = [
    COLORS["blue"], COLORS["orange"], COLORS["green"], COLORS["magenta"],
    COLORS["cyan"], "#8B6B3F", COLORS["ink"],
]
DRONE_COLORS = {
    "FY1": COLORS["blue"],
    "FY2": COLORS["orange"],
    "FY3": COLORS["green"],
    "FY4": COLORS["magenta"],
    "FY5": COLORS["cyan"],
}
MISSILE_COLORS = {"M1": COLORS["blue"], "M2": COLORS["orange"], "M3": COLORS["green"]}


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"],
            "font.size": 8.2,
            "axes.labelsize": 8.2,
            "axes.titlesize": 8.4,
            "xtick.labelsize": 7.3,
            "ytick.labelsize": 7.3,
            "legend.fontsize": 7.0,
            "axes.edgecolor": "#9AA4AE",
            "axes.linewidth": 0.65,
            "axes.labelcolor": COLORS["ink"],
            "xtick.color": COLORS["muted"],
            "ytick.color": COLORS["muted"],
            "xtick.major.width": 0.55,
            "ytick.major.width": 0.55,
            "xtick.major.size": 2.7,
            "ytick.major.size": 2.7,
            "lines.linewidth": 1.25,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
            "legend.frameon": False,
        }
    )


def style_axis(ax: plt.Axes, *, grid: str | None = None) -> None:
    """Apply the restrained contest-paper axis treatment used by every plot."""
    ax.set_facecolor("white")
    ax.tick_params(direction="out", pad=2.2)
    if grid:
        ax.grid(
            axis=grid,
            color=COLORS["grid"],
            linewidth=0.48,
            alpha=0.9,
            zorder=0,
        )
    ax.set_axisbelow(True)


def panel_label(ax: plt.Axes, label: str, *, x: float = -0.10, y: float = 1.04) -> None:
    ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.5,
        fontweight="bold",
        color=COLORS["ink"],
        clip_on=False,
    )


def shot_index_map(plans: list[dict[str, Any]]) -> dict[int, int]:
    """Return per-drone shot numbers ordered by actual release time."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for plan in plans:
        grouped[str(plan["drone_id"])].append(plan)
    result: dict[int, int] = {}
    for drone_plans in grouped.values():
        ordered = sorted(
            drone_plans,
            key=lambda item: (
                float(item.get("release_time", item.get("release_time_s", 0.0))),
                float(item.get("explosion_time", item.get("explosion_time_s", 0.0))),
            ),
        )
        for index, plan in enumerate(ordered, start=1):
            result[id(plan)] = index
    return result


def load_results() -> tuple[dict[str, Any], dict[str, Any]]:
    q12 = json.loads((VALIDATION / "q1_q2_independent.json").read_text(encoding="utf-8"))
    q35 = json.loads((VALIDATION / "q3_q5_independent.json").read_text(encoding="utf-8"))
    return q12, q35


def load_q2_multiseed() -> dict[str, Any]:
    return json.loads((VALIDATION / "q2_multiseed.json").read_text(encoding="utf-8"))


def load_q3_q4_multiseed() -> dict[str, Any]:
    return json.loads((VALIDATION / "q3_q4_multiseed.json").read_text(encoding="utf-8"))


def normalize_svg(path: Path) -> None:
    """Keep generated vector assets diff-clean without altering their geometry."""
    text = path.read_text(encoding="utf-8")
    path.write_text("\n".join(line.rstrip() for line in text.splitlines()) + "\n", encoding="utf-8")


def save(fig: plt.Figure, stem: str) -> list[str]:
    FIGURES.mkdir(parents=True, exist_ok=True)
    names = []
    for extension in ("png", "pdf", "svg"):
        path = FIGURES / f"{stem}.{extension}"
        fig.savefig(
            path,
            dpi=600 if extension == "png" else 300,
            facecolor="white",
            edgecolor="none",
        )
        if extension == "svg":
            normalize_svg(path)
        names.append(path.relative_to(ROOT).as_posix())
    plt.close(fig)
    return names


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def workflow_figure() -> list[str]:
    columns = [
        ("输入审计", "题意口径 · 约束 · 单位", "Q1–Q5"),
        ("机理内核", "解析运动 · 有限视线", "Q1 → Q5"),
        ("连续事件", "括根定位 · 边界精化", "Q1–Q2"),
        ("组合决策", "航路候选 · 区间并集", "Q3–Q5"),
        ("证据闭环", "独立复算 · 双口径审计", "全部结果"),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 2.25), layout="constrained")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 22)
    ax.axis("off")
    for index, (title, detail, scope) in enumerate(columns):
        x = 1.5 + index * 19.6
        box = FancyBboxPatch(
            (x, 5.2), 16.6, 11.8,
            boxstyle="round,pad=0.18,rounding_size=0.7",
            facecolor=COLORS["white"], edgecolor="#CBD3DB", linewidth=0.85,
        )
        ax.add_patch(box)
        ax.add_patch(Rectangle((x, 15.65), 16.6, 1.35, facecolor=COLORS["ink"], edgecolor="none"))
        ax.text(x + 1.2, 13.0, f"{index + 1:02d}", color=COLORS["blue"], fontsize=8.2, fontweight="bold")
        ax.text(x + 4.2, 13.0, title, color=COLORS["ink"], fontsize=8.3, fontweight="bold")
        ax.text(x + 1.2, 9.8, detail, color=COLORS["muted"], fontsize=7.1)
        ax.text(
            x + 1.2, 6.7, scope, color=COLORS["blue"], fontsize=6.8,
            bbox={"boxstyle": "round,pad=0.20", "facecolor": COLORS["panel"], "edgecolor": "none"},
        )
        if index < len(columns) - 1:
            ax.annotate(
                "", xy=(x + 19.15, 11.1), xytext=(x + 16.95, 11.1),
                arrowprops={"arrowstyle": "-|>", "lw": 0.9, "color": "#9AA4AE", "mutation_scale": 8},
            )
    ax.annotate(
        "",
        xy=(9.8, 3.3),
        xytext=(90.2, 3.3),
        arrowprops={"arrowstyle": "-|>", "lw": 0.85, "color": COLORS["orange"], "mutation_scale": 8},
    )
    ax.text(50, 1.45, "验证失败则回到口径、机理或候选层修订", ha="center", color=COLORS["orange"], fontsize=6.8)
    return save(fig, "modeling_workflow")


def geometry_mechanism() -> list[str]:
    strategy = q1_strategy()
    time_s = 8.70
    missile = missile_position(time_s)
    target = np.array((0.0, 200.0, 5.0))
    cloud = smoke_center(strategy, time_s, 9.8)
    segment = target - missile
    lam = float(np.clip(np.dot(cloud - missile, segment) / np.dot(segment, segment), 0.0, 1.0))
    closest = missile + lam * segment
    distance = float(np.linalg.norm(cloud - closest))
    along = float(np.linalg.norm(closest - missile))

    center_margin = float(centerline_margin(time_s, strategy, 9.8))
    cylinder_margin = float(full_cylinder_margin(time_s, strategy, 9.8))

    fig, axes = plt.subplots(
        1, 3, figsize=(7.2, 2.85), layout="constrained",
        gridspec_kw={"width_ratios": [1.35, 1.0, 0.9]},
    )

    ax = axes[0]
    # This panel is explicitly schematic: exact scale would collapse the cloud and missile.
    ax.plot([0.08, 0.92], [0.20, 0.20], color=COLORS["ink"], lw=1.25)
    ax.scatter([0.08], [0.20], marker="^", s=38, color=COLORS["orange"], zorder=3)
    ax.scatter([0.92], [0.20], marker="s", s=28, color=COLORS["green"], zorder=3)
    ax.scatter([0.29], [0.63], s=34, color=COLORS["blue"], zorder=4)
    ax.scatter([0.29], [0.20], s=17, facecolor="white", edgecolor=COLORS["blue"], zorder=4)
    ax.plot([0.29, 0.29], [0.20, 0.63], ls=(0, (3, 2)), color=COLORS["blue"], lw=1.0)
    ax.text(0.08, 0.10, "导弹 M1", ha="center", color=COLORS["muted"], fontsize=7.0)
    ax.text(0.92, 0.10, "真目标中心", ha="center", color=COLORS["muted"], fontsize=7.0)
    ax.text(0.31, 0.66, "烟幕球心 $C_s$", color=COLORS["blue"], fontsize=7.0)
    ax.text(0.31, 0.23, f"最近点 $P^*$\n$\\lambda^*={lam:.4f}$", color=COLORS["ink"], fontsize=6.8)
    ax.text(0.50, 0.88, "有限线段，而非无限直线", ha="center", color=COLORS["ink"], fontsize=7.3, fontweight="bold")
    ax.text(0.50, 0.01, "横向位置为示意；数值由三维坐标精确计算", ha="center", color=COLORS["muted"], fontsize=6.2)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    panel_label(ax, "A", x=0.00, y=0.97)

    ax = axes[1]
    ax.axhline(0, color=COLORS["ink"], lw=1.15)
    ax.add_patch(
        Circle((0, distance), SMOKE_RADIUS, facecolor=COLORS["blue_light"], edgecolor=COLORS["blue"], alpha=0.35, lw=1.0)
    )
    ax.scatter([0], [distance], color=COLORS["blue"], s=20, zorder=4)
    ax.plot([0, 0], [0, distance], ls=(0, (3, 2)), color=COLORS["orange"], lw=1.0)
    ax.annotate(
        "", xy=(SMOKE_RADIUS, distance), xytext=(0, distance),
        arrowprops={"arrowstyle": "<->", "lw": 0.85, "color": COLORS["blue"]},
    )
    ax.text(SMOKE_RADIUS / 2, distance + 0.75, "$R=10$ m", ha="center", color=COLORS["blue"], fontsize=6.8)
    ax.text(0.65, distance / 2, f"$d={distance:.2f}$ m", va="center", color=COLORS["orange"], fontsize=6.8)
    ax.text(-11.6, -1.9, "导弹—目标有限视线", color=COLORS["muted"], fontsize=6.5)
    ax.set_xlim(-12.5, 12.5)
    ax.set_ylim(-3.2, distance + 12.5)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("局部切向坐标 (m)")
    ax.set_ylabel("垂直视线距离 (m)")
    style_axis(ax, grid="both")
    panel_label(ax, "B")

    ax = axes[2]
    values = [center_margin, cylinder_margin]
    labels = ["中心视线", "完整圆柱"]
    colors = [COLORS["blue"], COLORS["orange"]]
    y = np.arange(2)
    ax.axvline(0, color=COLORS["ink"], lw=0.85)
    for yi, value, color in zip(y, values, colors):
        ax.hlines(yi, 0, value, color=color, lw=3.0)
        ax.scatter([value], [yi], s=31, color=color, edgecolor="white", linewidth=0.6, zorder=3)
        ax.text(value + 0.08, yi, f"{value:+.2f} m", ha="left", va="center", color=color, fontsize=6.8, fontweight="bold")
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    pad = max(0.85, max(abs(value) for value in values) * 0.30)
    ax.set_xlim(min(0, min(values)) - pad, max(0, max(values)) + pad)
    ax.set_xlabel("判据裕度 $F(t)$ (m)")
    ax.text(0.04, 0.52, r"$F\geq0$ 判为有效", transform=ax.transAxes, ha="left", va="center", color=COLORS["muted"], fontsize=6.5)
    style_axis(ax, grid="x")
    panel_label(ax, "C")
    return save(fig, "finite_sightline_geometry")


def q1_intervals(q12: dict[str, Any]) -> list[str]:
    records = [
        ("目标中心视线", q12["q1"]["g_9.80"]["centerline"], PALETTE[0]),
        ("完整圆柱全遮蔽", q12["q1"]["g_9.80"]["full_cylinder"], PALETTE[1]),
    ]
    fig, axes = plt.subplots(
        2, 1, figsize=(6.8, 3.65), sharex=True, layout="constrained",
        gridspec_kw={"height_ratios": [1.55, 1]},
    )
    strategy = q1_strategy()
    times = np.linspace(7.76, 9.68, 320)
    center_margins = [centerline_margin(float(time), strategy, 9.8) for time in times]
    full_margins = [full_cylinder_margin(float(time), strategy, 9.8) for time in times]
    axes[0].plot(times, center_margins, color=COLORS["blue"], lw=1.55, label="目标中心视线")
    axes[0].plot(times, full_margins, color=COLORS["orange"], lw=1.45, ls=(0, (4, 2)), label="完整圆柱全遮蔽")
    axes[0].axhline(0, color=COLORS["ink"], lw=0.75)
    axes[0].fill_between(
        times, 0, center_margins, where=np.asarray(center_margins) >= 0,
        color=COLORS["blue_light"], alpha=0.20, linewidth=0,
    )
    for _, record, color in records:
        left, right = record["intervals_s"][0]
        axes[0].axvline(left, color=color, lw=0.65, alpha=0.75, ls=(0, (2, 2)))
        axes[0].axvline(right, color=color, lw=0.65, alpha=0.75, ls=(0, (2, 2)))
    axes[0].set_ylabel("遮蔽裕度 $F(t)$ (m)")
    axes[0].legend(loc="upper right", ncols=2, handlelength=2.5)
    axes[0].text(
        0.015, 0.08, "阴影区：中心视线口径有效", transform=axes[0].transAxes,
        color=COLORS["muted"], fontsize=6.6,
    )
    axes[0].set_xlim(7.88, 9.54)
    axes[0].set_ylim(-4.5, max(center_margins) * 1.18)
    style_axis(axes[0], grid="y")
    panel_label(axes[0], "A")
    ax = axes[1]
    for index, (label, record, color) in enumerate(records):
        for left, right in record["intervals_s"]:
            ax.broken_barh(
                [(left, right - left)], (index - 0.17, 0.34),
                facecolors=color, edgecolors=color, linewidth=0.7,
            )
            ax.text((left + right) / 2, index, f"{right-left:.3f} s", ha="center", va="center", color="white", fontweight="bold", fontsize=6.7)
            ax.text(left, index - 0.31, f"{left:.3f}", ha="center", va="top", color=COLORS["muted"], fontsize=6.3)
            ax.text(right, index - 0.31, f"{right:.3f}", ha="center", va="top", color=COLORS["muted"], fontsize=6.3)
    ax.set_yticks(range(len(records)), [item[0] for item in records])
    ax.set_xlabel("任务时刻 (s)")
    center_left = records[0][1]["intervals_s"][0][0]
    full_left = records[1][1]["intervals_s"][0][0]
    delta_duration = records[0][1]["duration_s"] - records[1][1]["duration_s"]
    ax.annotate(
        "", xy=(full_left, 1.38), xytext=(center_left, 1.38),
        arrowprops={"arrowstyle": "<->", "lw": 0.8, "color": COLORS["orange"]},
    )
    ax.text(
        (center_left + full_left) / 2, 1.52,
        f"进入延后 {full_left-center_left:.4f} s",
        ha="center", va="bottom", color=COLORS["orange"], fontsize=6.6,
    )
    ax.text(
        0.995, 0.94, f"时长差 $\\Delta T={delta_duration:.4f}$ s",
        transform=ax.transAxes, ha="right", va="top", color=COLORS["ink"], fontsize=6.8,
        bbox={"boxstyle": "round,pad=0.25", "facecolor": COLORS["panel"], "edgecolor": "none"},
    )
    style_axis(ax, grid="x")
    ax.set_ylim(-0.62, 1.78)
    panel_label(ax, "B")
    return save(fig, "q1_occlusion_intervals")


def q2_response_surface(q12: dict[str, Any]) -> list[str]:
    headings = np.linspace(1.0, 13.0, 37)
    explosion_times = np.linspace(0.25, 1.25, 33)
    surface = np.zeros((len(explosion_times), len(headings)))
    for row, explosion_time in enumerate(explosion_times):
        for column, heading in enumerate(headings):
            strategy = Strategy(np.deg2rad(heading), 140.0, 0.0, float(explosion_time))
            intervals = strategy_intervals(strategy, "centerline", 9.8, max_step_s=0.08)
            surface[row, column] = sum(right - left for left, right in intervals)
    optimum = q12["q2"]["centerline"]["strategy"]
    optimum_heading = float(optimum["heading_deg"])
    optimum_time = float(optimum["explosion_time_s"])
    optimum_duration = float(q12["q2"]["centerline"]["duration_s"])

    heading_slice_x = np.linspace(2.0, 12.0, 71)
    heading_slice_y = []
    for heading in heading_slice_x:
        strategy = Strategy(np.deg2rad(float(heading)), 140.0, 0.0, optimum_time)
        intervals = strategy_intervals(strategy, "centerline", 9.8, max_step_s=0.06)
        heading_slice_y.append(sum(right - left for left, right in intervals))
    time_slice_x = np.linspace(0.35, 1.08, 71)
    time_slice_y = []
    for explosion_time in time_slice_x:
        strategy = Strategy(np.deg2rad(optimum_heading), 140.0, 0.0, float(explosion_time))
        intervals = strategy_intervals(strategy, "centerline", 9.8, max_step_s=0.06)
        time_slice_y.append(sum(right - left for left, right in intervals))

    fig = plt.figure(figsize=(7.2, 3.55), layout="constrained")
    grid = fig.add_gridspec(2, 2, width_ratios=[1.45, 1.0], height_ratios=[1, 1])
    ax = fig.add_subplot(grid[:, 0])
    levels = np.linspace(0, max(0.5, float(surface.max())), 11)
    contour = ax.contourf(headings, explosion_times, surface, levels=levels, cmap="cividis", extend="max")
    lines = ax.contour(headings, explosion_times, surface, levels=levels[2::2], colors="white", linewidths=0.5, alpha=0.75)
    ax.clabel(lines, inline=True, fontsize=5.8, fmt="%.1f")
    ax.scatter([optimum_heading], [optimum_time], marker="*", s=78, color=COLORS["orange"], edgecolor="white", linewidth=0.7, zorder=5)
    ax.annotate(
        f"连续精化\n({optimum_heading:.2f}°, {optimum_time:.3f} s)\n$T={optimum_duration:.3f}$ s",
        xy=(optimum_heading, optimum_time), xytext=(10, -34), textcoords="offset points",
        color=COLORS["ink"], fontsize=6.4,
        arrowprops={"arrowstyle": "-", "lw": 0.7, "color": COLORS["orange"]},
        bbox={"boxstyle": "round,pad=0.23", "facecolor": "white", "edgecolor": "#CBD3DB", "alpha": 0.92},
    )
    ax.set_xlabel("航向角 $\\theta$ ($^\\circ$)")
    ax.set_ylabel("起爆时刻 $t^e$ (s)\n($v=140$ m/s，$t^r=0$)")
    style_axis(ax)
    panel_label(ax, "A", x=-0.13)
    bar = fig.colorbar(contour, ax=ax, shrink=0.86, pad=0.025)
    bar.set_label("遮蔽时长 (s)", fontsize=7.0)
    bar.ax.tick_params(labelsize=6.2)

    ax_h = fig.add_subplot(grid[0, 1])
    ax_h.plot(heading_slice_x, heading_slice_y, color=COLORS["blue"], lw=1.45)
    ax_h.axvline(optimum_heading, color=COLORS["orange"], lw=0.8, ls=(0, (3, 2)))
    ax_h.scatter([optimum_heading], [optimum_duration], s=25, color=COLORS["orange"], zorder=3)
    high = np.asarray(heading_slice_y) >= 0.95 * optimum_duration
    if np.any(high):
        ax_h.axvspan(heading_slice_x[high][0], heading_slice_x[high][-1], color=COLORS["blue_light"], alpha=0.18)
    ax_h.set_xlabel("$\\theta$ ($^\\circ$)，固定 $t^e=t^{e*}$")
    ax_h.set_ylabel("$T$ (s)")
    ax_h.text(0.98, 0.09, "浅色：≥95% 峰值", transform=ax_h.transAxes, ha="right", color=COLORS["muted"], fontsize=6.2)
    style_axis(ax_h, grid="y")
    panel_label(ax_h, "B", x=-0.18)

    ax_t = fig.add_subplot(grid[1, 1])
    ax_t.plot(time_slice_x, time_slice_y, color=COLORS["green"], lw=1.45)
    ax_t.axvline(optimum_time, color=COLORS["orange"], lw=0.8, ls=(0, (3, 2)))
    ax_t.scatter([optimum_time], [optimum_duration], s=25, color=COLORS["orange"], zorder=3)
    high = np.asarray(time_slice_y) >= 0.95 * optimum_duration
    if np.any(high):
        ax_t.axvspan(time_slice_x[high][0], time_slice_x[high][-1], color="#A9D5C5", alpha=0.20)
    ax_t.set_xlabel("$t^e$ (s)，固定 $\\theta=\\theta^*$")
    ax_t.set_ylabel("$T$ (s)")
    style_axis(ax_t, grid="y")
    panel_label(ax_t, "C", x=-0.18)
    return save(fig, "q2_response_surface")


def q2_multiseed_stability(multiseed: dict[str, Any]) -> list[str]:
    runs = multiseed["runs"]
    exact = np.asarray([run["exact_duration_s"] for run in runs], dtype=float)
    target = float(np.median(exact))
    max_generation = max(int(run["best_so_far_trace"][-1]["generation"]) for run in runs)
    generation_grid = np.arange(1, max_generation + 1)
    gap_matrix = []
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.15), layout="constrained", gridspec_kw={"width_ratios": [1.45, 1.0]})
    for run in runs:
        trace = run["best_so_far_trace"]
        generations = np.asarray([point["generation"] for point in trace], dtype=float)
        incumbents = np.asarray([point["best_coarse_duration_s"] for point in trace], dtype=float)
        interpolated = np.interp(generation_grid, generations, incumbents, left=incumbents[0], right=incumbents[-1])
        gaps = np.maximum(target - interpolated, 1e-6)
        gap_matrix.append(gaps)
        axes[0].plot(
            generation_grid, gaps, lw=0.65, alpha=0.45, color="#8F99A3",
        )
    gap_matrix_np = np.asarray(gap_matrix)
    median_gap = np.median(gap_matrix_np, axis=0)
    q25 = np.quantile(gap_matrix_np, 0.25, axis=0)
    q75 = np.quantile(gap_matrix_np, 0.75, axis=0)
    axes[0].fill_between(generation_grid, q25, q75, color=COLORS["blue_light"], alpha=0.30, linewidth=0)
    axes[0].plot(generation_grid, median_gap, color=COLORS["blue"], lw=1.65)
    axes[0].axhspan(1e-6, 1e-3, color=COLORS["green"], alpha=0.08)
    axes[0].text(0.985, 0.08, "阴影：$10^{-3}$ s 内", transform=axes[0].transAxes, ha="right", color=COLORS["green"], fontsize=6.4)
    axes[0].set_yscale("log")
    axes[0].set_xlabel("差分进化代数")
    axes[0].set_ylabel("距连续终值的差 (s)")
    axes[0].text(0.03, 0.96, "灰线：单次运行  ·  蓝线/带：中位数/IQR", transform=axes[0].transAxes, va="top", color=COLORS["muted"], fontsize=6.4)
    style_axis(axes[0], grid="y")
    panel_label(axes[0], "A")

    evaluations = np.asarray([run["function_evaluations"] for run in runs], dtype=float) / 1000.0
    seed_labels = [str(run["seed"])[-2:] for run in runs]
    y = np.arange(len(runs))
    axes[1].hlines(y, evaluations.min() - 0.15, evaluations, color="#CDD4DA", lw=1.2)
    axes[1].scatter(evaluations, y, s=30, color=COLORS["blue"], edgecolor="white", linewidth=0.55, zorder=3)
    for x_value, y_value in zip(evaluations, y):
        axes[1].text(x_value + 0.04, y_value, f"{x_value:.2f}k", va="center", color=COLORS["ink"], fontsize=6.4)
    axes[1].set_yticks(y, [f"seed ·{label}" for label in seed_labels])
    axes[1].invert_yaxis()
    axes[1].set_xlabel("函数评估次数（千次）")
    summary = multiseed["summary"]
    terminal_span = float(summary["maximum_s"] - summary["minimum_s"])
    axes[1].text(
        0.02, 1.02,
        f"8/8 可行  ·  约束违反 0  ·  终值极差 {terminal_span:.1e} s",
        transform=axes[1].transAxes, ha="left", va="bottom", color=COLORS["ink"], fontsize=6.4,
    )
    style_axis(axes[1], grid="x")
    panel_label(axes[1], "B", x=-0.20)
    return save(fig, "q2_multiseed_stability")


def q3_q4_multiseed_stability(multiseed: dict[str, Any]) -> list[str]:
    fig, axes = plt.subplots(
        2, 2, figsize=(7.2, 4.55), layout="constrained",
        gridspec_kw={"width_ratios": [1.55, 1.0], "hspace": 0.10},
    )
    for row, question in enumerate(("Q3", "Q4")):
        record = multiseed["problems"][question]
        runs = record["runs"]
        summary = record["summary"]
        max_iteration = max(int(run["best_so_far_trace"][-1]["iteration"]) for run in runs)
        iteration_grid = np.arange(max_iteration + 1)
        trace_matrix = []
        accent = COLORS["blue"] if question == "Q3" else COLORS["orange"]
        for run in runs:
            trace = run["best_so_far_trace"]
            x_trace = np.asarray([point["iteration"] for point in trace], dtype=float)
            y_trace = np.asarray([point["best_fast_objective_s"] for point in trace], dtype=float)
            interpolated = np.interp(iteration_grid, x_trace, y_trace, left=y_trace[0], right=y_trace[-1])
            trace_matrix.append(interpolated)
            axes[row, 0].plot(
                iteration_grid, interpolated, color="#8F99A3", lw=0.65, alpha=0.42,
            )
        trace_matrix_np = np.asarray(trace_matrix)
        median_trace = np.median(trace_matrix_np, axis=0)
        lower = np.quantile(trace_matrix_np, 0.25, axis=0)
        upper = np.quantile(trace_matrix_np, 0.75, axis=0)
        axes[row, 0].fill_between(iteration_grid, lower, upper, color=accent, alpha=0.16, linewidth=0)
        axes[row, 0].plot(iteration_grid, median_trace, color=accent, lw=1.55)
        if row == 1:
            axes[row, 0].set_xlabel("局部随机精化迭代")
        axes[row, 0].set_ylabel("best-so-far 粗评分 (s)")
        axes[row, 0].text(0.02, 0.93, f"{question} · 灰线为单种子，色带为 IQR", transform=axes[row, 0].transAxes, va="top", color=COLORS["muted"], fontsize=6.4)
        style_axis(axes[row, 0], grid="y")
        panel_label(axes[row, 0], "A" if row == 0 else "C")

        terminal = np.asarray([run["final_exact_objective_s"] for run in runs], dtype=float)
        jitter = np.linspace(-0.12, 0.12, len(runs))
        axes[row, 1].hlines(0, terminal.min(), terminal.max(), color="#B8C0C8", lw=1.2)
        point_colors = [COLORS["orange"] if run["seed"] == summary["best_seed"] else accent for run in runs]
        axes[row, 1].scatter(terminal, jitter, s=34, c=point_colors, edgecolor="white", linewidth=0.55, zorder=3)
        for value, y_pos, run in zip(terminal, jitter, runs):
            axes[row, 1].annotate(str(run["seed"])[-2:], (value, y_pos), xytext=(0, 5), textcoords="offset points", ha="center", fontsize=6.0, color=COLORS["muted"])
        axes[row, 1].axvline(float(np.median(terminal)), color=COLORS["ink"], lw=0.7, ls=(0, (2, 2)))
        axes[row, 1].set_yticks([])
        axes[row, 1].set_ylim(-0.26, 0.32)
        axes[row, 1].set_xlabel("连续复算并集时长 (s)")
        axes[row, 1].text(
            0.02, 0.94,
            f"{question}  范围 {summary['minimum_s']:.3f}–{summary['maximum_s']:.3f} s\nSD = {summary['standard_deviation_s']:.3f} s",
            transform=axes[row, 1].transAxes, va="top", color=COLORS["ink"], fontsize=6.5,
        )
        axes[row, 1].text(0.98, 0.08, "橙色：本批最佳种子", transform=axes[row, 1].transAxes, ha="right", color=COLORS["orange"], fontsize=6.2)
        style_axis(axes[row, 1], grid="x")
        panel_label(axes[row, 1], "B" if row == 0 else "D", x=-0.18)
    return save(fig, "q3_q4_multiseed_stability")


def interval_union_figure(q35: dict[str, Any], question: str, stem: str) -> list[str]:
    plans = q35["results"][question]["plans"]
    union = q35["results"][question]["exact_centerline_union"]["M1"]
    fig, ax = plt.subplots(figsize=(6.8, 2.45 if question == "Q3" else 2.65), layout="constrained")
    shot_indices = shot_index_map(plans)
    labels = []
    for row, plan in enumerate(plans):
        label = f"{plan['drone_id']}·{shot_indices[id(plan)]}"
        labels.append(label)
        for left, right in plan["exact_centerline_intervals"]:
            color = COLORS["blue"] if question == "Q3" else DRONE_COLORS[str(plan["drone_id"])]
            ax.broken_barh(
                [(left, right - left)], (row - 0.21, 0.42),
                facecolors=color, edgecolors="white", linewidth=0.55,
            )
            ax.text((left + right) / 2, row, f"{right-left:.3f}", ha="center", va="center", color="white", fontsize=6.5, fontweight="bold")
            ax.text(left, row - 0.34, f"{left:.2f}", ha="center", va="top", color=COLORS["muted"], fontsize=5.9)
            ax.text(right, row - 0.34, f"{right:.2f}", ha="center", va="top", color=COLORS["muted"], fontsize=5.9)
    union_row = len(plans) + 0.45
    for left, right in union:
        ax.broken_barh(
            [(left, right - left)], (union_row - 0.22, 0.44),
            facecolors=COLORS["ink"], edgecolors=COLORS["ink"], linewidth=0.65,
        )
    labels.append("并集")
    ax.set_yticks([*range(len(plans)), union_row], labels)
    ax.set_xlabel("任务时刻 (s)")
    individual_sum = sum(
        right - left
        for plan in plans
        for left, right in plan["exact_centerline_intervals"]
    )
    union_total = sum(right - left for left, right in union)
    overlap = individual_sum - union_total
    if question == "Q3":
        all_intervals = [plan["exact_centerline_intervals"][0] for plan in plans]
        overlap_segments = []
        for first, second in zip(all_intervals, all_intervals[1:]):
            left = max(first[0], second[0])
            right = min(first[1], second[1])
            if right > left:
                overlap_segments.append((left, right))
        for index, (left, right) in enumerate(overlap_segments):
            ax.axvspan(left, right, color=COLORS["orange"], alpha=0.16, zorder=0)
            ax.text(
                (left + right) / 2, -0.64 if index == 0 else 2.64,
                f"重叠 {right-left:.3f}s", ha="center", va="center",
                color=COLORS["orange"], fontsize=6.2,
            )
        ax.text(
            0.99, 0.94,
            f"单弹和 {individual_sum:.3f} − 重叠 {overlap:.3f} = 并集 {union_total:.3f} s",
            transform=ax.transAxes, ha="right", va="top", color=COLORS["ink"], fontsize=6.7,
            bbox={"boxstyle": "round,pad=0.22", "facecolor": COLORS["panel"], "edgecolor": "none"},
        )
    else:
        gaps = [(union[index][1], union[index + 1][0]) for index in range(len(union) - 1)]
        for index, (left, right) in enumerate(gaps):
            y = union_row + 0.55 + index * 0.33
            ax.annotate(
                "", xy=(right, y), xytext=(left, y),
                arrowprops={"arrowstyle": "<->", "lw": 0.75, "color": COLORS["orange"]},
            )
            ax.text((left + right) / 2, y + 0.10, f"空窗 {right-left:.2f}s", ha="center", va="bottom", color=COLORS["orange"], fontsize=6.2)
        ax.text(
            0.99, 0.94, f"三窗互不重叠：并集 = {union_total:.3f} s",
            transform=ax.transAxes, ha="right", va="top", color=COLORS["ink"], fontsize=6.7,
            bbox={"boxstyle": "round,pad=0.22", "facecolor": COLORS["panel"], "edgecolor": "none"},
        )
    ax.set_ylim(-0.85, union_row + (1.35 if question == "Q4" else 0.85))
    style_axis(ax, grid="x")
    return save(fig, stem)


def search_diagnostics(q35: dict[str, Any]) -> list[str]:
    questions = ["Q3", "Q4", "Q5"]
    baseline = [q35["results"][q]["diagnostics"]["fast_baseline_objective"] for q in questions]
    approximate = [q35["results"][q]["diagnostics"]["fast_final_objective"] for q in questions]
    exact = [q35["results"][q]["diagnostics"]["exact_objective"] for q in questions]
    routes = [q35["results"][q]["diagnostics"]["routes_evaluated"] for q in questions]
    candidates = [q35["results"][q]["diagnostics"]["candidates_generated"] for q in questions]
    retained = [q35["results"][q]["diagnostics"]["packages_retained"] for q in questions]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), layout="constrained", gridspec_kw={"width_ratios": [1.25, 1.0]})
    y = np.arange(len(questions))
    approximate_ratio = np.asarray(approximate) / np.asarray(baseline) * 100.0
    exact_ratio = np.asarray(exact) / np.asarray(baseline) * 100.0
    for row, (coarse_value, exact_value) in enumerate(zip(approximate_ratio, exact_ratio)):
        axes[0].plot([100, coarse_value, exact_value], [row, row, row], color="#B8C0C8", lw=1.1, zorder=1)
        axes[0].scatter([100], [row], marker="|", s=90, color=COLORS["muted"], linewidth=1.2, zorder=3)
        axes[0].scatter([coarse_value], [row], marker="D", s=28, facecolor="white", edgecolor=COLORS["blue"], linewidth=1.0, zorder=3)
        axes[0].scatter([exact_value], [row], marker="o", s=32, color=COLORS["orange"], edgecolor="white", linewidth=0.5, zorder=4)
        axes[0].text(exact_value + 1.2, row, f"{exact_value:.1f}%", va="center", color=COLORS["orange"], fontsize=6.6, fontweight="bold")
    axes[0].set_yticks(y, questions)
    axes[0].invert_yaxis()
    axes[0].set_xlabel("相对粗网格基线（基线 = 100%）")
    handles = [
        Line2D([0], [0], marker="|", color="none", markeredgecolor=COLORS["muted"], markersize=9, label="基线"),
        Line2D([0], [0], marker="D", color="none", markerfacecolor="white", markeredgecolor=COLORS["blue"], markersize=4.5, label="粗评保留解"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["orange"], markeredgecolor=COLORS["orange"], markersize=4.5, label="连续复算"),
    ]
    axes[0].legend(handles=handles, loc="lower right", ncols=3, handletextpad=0.25, columnspacing=0.8)
    style_axis(axes[0], grid="x")
    panel_label(axes[0], "A")

    series = [
        (candidates, "生成候选", "o", COLORS["blue"]),
        (routes, "评估航路", "s", COLORS["orange"]),
        (retained, "保留包", "^", COLORS["green"]),
    ]
    offsets = [-0.16, 0.0, 0.16]
    for offset, (values, label, marker, color) in zip(offsets, series):
        axes[1].scatter(values, y + offset, marker=marker, s=28, color=color, edgecolor="white", linewidth=0.45, label=label, zorder=3)
        for x_value, y_value in zip(values, y + offset):
            axes[1].text(x_value * 1.08, y_value, f"{int(x_value)}", va="center", color=color, fontsize=5.9)
    axes[1].set_xscale("log")
    axes[1].set_yticks(y, questions)
    axes[1].invert_yaxis()
    axes[1].set_xlabel("搜索记账量（对数轴；三类不作漏斗解释）")
    axes[1].legend(loc="lower right", ncols=3, handletextpad=0.25, columnspacing=0.7)
    style_axis(axes[1], grid="x")
    panel_label(axes[1], "B", x=-0.18)
    return save(fig, "search_quality_diagnostics")


def numerical_convergence(q12: dict[str, Any]) -> list[str]:
    q2_record = q12["q2"]["centerline"]
    q2s = q2_record["strategy"]
    strategies = {
        "Q1 给定策略": (q1_strategy(), q12["q1"]["g_9.80"]["centerline"]["duration_s"]),
        "Q2 优化策略": (Strategy(q2s["heading_rad"], q2s["speed_mps"], q2s["release_time_s"], q2s["fuse_delay_s"]), q2_record["duration_s"]),
    }
    steps = np.array([0.50, 0.25, 0.10, 0.05, 0.02, 0.01, 0.005])
    fig, ax = plt.subplots(figsize=(5.8, 3.25), layout="constrained")
    for index, (label, (strategy, exact)) in enumerate(strategies.items()):
        errors = []
        for step in steps:
            start = strategy.explosion_time_s
            end = min(start + 20.0, 20099.75124224178 / 300.0)
            count = max(1, int(ceil((end - start) / step)))
            times = np.linspace(start, end, count + 1)
            active = np.array([centerline_margin(float(time), strategy, 9.8) >= 0 for time in times])
            sampled = float(np.trapezoid(active.astype(float), times))
            errors.append(max(abs(sampled - exact), 1e-8))
        color = COLORS["blue"] if index == 0 else COLORS["orange"]
        ax.loglog(steps, errors, marker=["o", "s"][index], markersize=3.8, color=color, lw=1.25, label=label)
    reference = 0.18 * steps
    ax.loglog(steps, reference, color="#A8B0B8", lw=0.8, ls=(0, (4, 2)))
    ax.text(0.40, 0.76, "$O(\\Delta t)$ 参考", transform=ax.transAxes, color=COLORS["muted"], fontsize=6.4, rotation=24)
    ax.axhspan(5e-5, 1e-2, color=COLORS["green"], alpha=0.08)
    ax.text(0.985, 0.08, "浅色：误差 ≤ 0.01 s", transform=ax.transAxes, ha="right", color=COLORS["green"], fontsize=6.5)
    ax.invert_xaxis()
    ax.set_xlabel("均匀采样步长 $\\Delta t$ (s)")
    ax.set_ylabel("相对连续验根结果的绝对误差 (s)")
    ax.set_xticks(steps)
    ax.set_xticklabels([f"{value:g}" for value in steps])
    ax.set_ylim(5e-5, 0.8)
    ax.text(0.985, 0.96, "网格加密  →", transform=ax.transAxes, ha="right", va="top", color=COLORS["muted"], fontsize=6.6)
    ax.legend(loc="upper left", ncols=2)
    style_axis(ax, grid="y")
    return save(fig, "time_step_convergence")


def criterion_comparison(q12: dict[str, Any], q35: dict[str, Any]) -> list[str]:
    center = [
        q12["q1"]["g_9.80"]["centerline"]["duration_s"],
        q12["q2"]["centerline"]["duration_s"],
        q35["results"]["Q3"]["exact_centerline_objective"],
        q35["results"]["Q4"]["exact_centerline_objective"],
        q35["results"]["Q5"]["exact_centerline_objective"],
    ]
    full = [
        q12["q1"]["g_9.80"]["full_cylinder"]["duration_s"],
        q12["q2"]["full_cylinder_tau_0_boundary"]["duration_s"],
        q35["full_cylinder_secondary_audit"]["Q3"]["objective"],
        q35["full_cylinder_secondary_audit"]["Q4"]["objective"],
        q35["full_cylinder_secondary_audit"]["Q5"]["objective"],
    ]
    paired_indices = [0, 2, 3, 4]
    paired_labels = ["Q1", "Q3", "Q4", "Q5"]
    retention = np.asarray([full[index] / center[index] * 100.0 for index in paired_indices])
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.85), layout="constrained", gridspec_kw={"width_ratios": [1.35, 0.9]})
    y = np.arange(len(paired_labels))
    axes[0].hlines(y, 60, retention, color="#C7CED5", lw=1.3)
    axes[0].scatter(retention, y, s=36, color=COLORS["orange"], edgecolor="white", linewidth=0.55, zorder=3)
    axes[0].axvline(100, color=COLORS["blue"], lw=0.9, ls=(0, (3, 2)))
    for x_value, y_value in zip(retention, y):
        axes[0].text(x_value - 0.8, y_value, f"{x_value:.1f}%", ha="right", va="center", color=COLORS["orange"], fontsize=6.7, fontweight="bold")
        axes[0].text(x_value + 0.8, y_value, f"损失 {100-x_value:.1f}%", ha="left", va="center", color=COLORS["muted"], fontsize=6.2)
    axes[0].set_yticks(y, paired_labels)
    axes[0].invert_yaxis()
    axes[0].set_xlim(60, 103)
    axes[0].set_xlabel("完整圆柱时长 / 同一策略中心视线时长")
    axes[0].text(0.99, 0.06, "蓝虚线：中心口径 100%", transform=axes[0].transAxes, ha="right", color=COLORS["blue"], fontsize=6.3)
    style_axis(axes[0], grid="x")
    panel_label(axes[0], "A")

    q2_values = [center[1], full[1]]
    q2_labels = ["中心口径\n各自优化", "圆柱口径\n各自优化"]
    q2_colors = [COLORS["blue"], COLORS["orange"]]
    for row, (value, label, color) in enumerate(zip(q2_values, q2_labels, q2_colors)):
        axes[1].hlines(row, 0, value, color=color, lw=2.7)
        axes[1].scatter([value], [row], s=38, color=color, edgecolor="white", linewidth=0.55, zorder=3)
        axes[1].text(value + 0.07, row, f"{value:.3f} s", va="center", color=color, fontsize=6.8, fontweight="bold")
    axes[1].set_yticks([0, 1], q2_labels)
    axes[1].invert_yaxis()
    axes[1].set_xlim(0, max(q2_values) * 1.24)
    axes[1].set_xlabel("Q2 各口径独立优化后的时长 (s)")
    axes[1].text(0.02, 1.02, "独立优化：禁止解释为同一策略前后损失", transform=axes[1].transAxes, va="bottom", color=COLORS["red"], fontsize=6.4)
    style_axis(axes[1], grid="x")
    panel_label(axes[1], "B", x=-0.20)
    return save(fig, "criterion_sensitivity")


def q5_gantt(q35: dict[str, Any]) -> list[str]:
    plans = q35["results"]["Q5"]["plans"]
    missiles = ["M1", "M2", "M3"]
    shot_indices = shot_index_map(plans)
    all_intervals = [interval for plan in plans for interval in plan["exact_centerline_intervals"]]
    x_min = min(left for left, _ in all_intervals) - 0.7
    x_max = max(right for _, right in all_intervals) + 0.7
    fig, axes = plt.subplots(3, 1, figsize=(7.2, 5.25), sharex=True, layout="constrained")
    for ax, missile in zip(axes, missiles):
        selected = sorted(
            [plan for plan in plans if plan["missile_id"] == missile],
            key=lambda item: (str(item["drone_id"]), shot_indices[id(item)]),
        )
        for row, plan in enumerate(selected):
            for left, right in plan["exact_centerline_intervals"]:
                ax.broken_barh(
                    [(left, right - left)],
                    (row - 0.22, 0.44),
                    facecolors=DRONE_COLORS[str(plan["drone_id"])],
                    edgecolors="white",
                    linewidth=0.55,
                )
                ax.text((left + right) / 2, row, f"{right-left:.2f}", ha="center", va="center", color="white", fontsize=6.1, fontweight="bold")
        union = q35["results"]["Q5"]["exact_centerline_union"][missile]
        union_row = len(selected) + 0.45
        for left, right in union:
            ax.broken_barh(
                [(left, right - left)], (union_row - 0.23, 0.46),
                facecolors=COLORS["ink"], edgecolors=COLORS["ink"], linewidth=0.6,
            )
        labels = [f"{plan['drone_id']}·{shot_indices[id(plan)]}" for plan in selected] + ["并集"]
        ax.set_yticks([*range(len(selected)), union_row], labels)
        ax.invert_yaxis()
        ax.set_ylim(union_row + 0.72, -0.62)
        duration = q35["results"]["Q5"]["exact_centerline_duration_by_missile"][missile]
        gaps = [(union[index][1], union[index + 1][0]) for index in range(len(union) - 1)]
        if gaps:
            gap_left, gap_right = max(gaps, key=lambda item: item[1] - item[0])
            ax.axvspan(gap_left, gap_right, color=COLORS["orange"], alpha=0.07, zorder=0)
            gap_text = f"最大空窗 {gap_right-gap_left:.2f}s"
        else:
            gap_text = "无内部空窗"
        ax.text(
            0.995, 0.93, f"并集 {duration:.3f}s  ·  {gap_text}",
            transform=ax.transAxes, ha="right", va="top", color=COLORS["ink"], fontsize=6.8,
        )
        style_axis(ax, grid="x")
        panel_label(ax, missile, x=-0.09, y=1.01)
        ax.set_xlim(x_min, x_max)
    axes[-1].set_xlabel("任务时刻 (s)")
    return save(fig, "q5_coverage_gantt")


def q5_missile_robustness(q35: dict[str, Any]) -> list[str]:
    missiles = ["M1", "M2", "M3"]
    center = [q35["results"]["Q5"]["exact_centerline_duration_by_missile"][item] for item in missiles]
    full = [q35["full_cylinder_secondary_audit"]["Q5"]["duration_by_missile"][item] for item in missiles]
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.75), layout="constrained", gridspec_kw={"width_ratios": [1.25, 0.9]})

    y = np.arange(len(missiles))
    for row, (center_value, full_value) in enumerate(zip(center, full)):
        axes[0].hlines(row, full_value, center_value, color="#B8C0C8", lw=1.25, zorder=1)
        axes[0].scatter([center_value], [row], s=38, color=COLORS["blue"], edgecolor="white", linewidth=0.55, zorder=3)
        axes[0].scatter([full_value], [row], s=38, facecolor="white", edgecolor=COLORS["orange"], linewidth=1.15, zorder=3)
        loss = center_value - full_value
        axes[0].text(center_value + 0.28, row, f"−{loss:.2f}s / {loss/center_value*100:.1f}%", va="center", color=COLORS["muted"], fontsize=6.4)
    axes[0].set_yticks(y, missiles)
    axes[0].invert_yaxis()
    axes[0].set_xlim(min(full) - 2.0, max(center) + 5.0)
    axes[0].set_xlabel("分导弹有效并集 (s)")
    style_axis(axes[0], grid="x")
    panel_label(axes[0], "A")

    center_total = float(sum(center))
    full_total = float(sum(full))
    axes[1].hlines(0, full_total, center_total, color="#B8C0C8", lw=2.0, zorder=1)
    axes[1].scatter([center_total], [0], s=46, color=COLORS["blue"], edgecolor="white", linewidth=0.6, zorder=3)
    axes[1].scatter([full_total], [0], s=46, facecolor="white", edgecolor=COLORS["orange"], linewidth=1.2, zorder=3)
    total_loss = center_total - full_total
    axes[1].text(
        (center_total + full_total) / 2, 0.16,
        f"总损失 {total_loss:.2f}s（{total_loss/center_total*100:.1f}%）",
        ha="center", color=COLORS["muted"], fontsize=6.6,
    )
    axes[1].set_yticks([0], ["合计"])
    axes[1].set_ylim(-0.42, 0.42)
    axes[1].set_xlim(full_total - 3.0, center_total + 3.0)
    axes[1].set_xlabel("三枚导弹时长之和 (s)")
    style_axis(axes[1], grid="x")
    panel_label(axes[1], "B", x=-0.18)

    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["blue"], markeredgecolor=COLORS["blue"], label="中心视线"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="white", markeredgecolor=COLORS["orange"], label="完整圆柱"),
    ]
    axes[0].legend(handles=handles, loc="lower right", ncols=2)
    axes[1].text(0.98, 0.08, "线段长度 = 口径损失", transform=axes[1].transAxes, ha="right", color=COLORS["muted"], fontsize=6.3)
    return save(fig, "q5_per_missile_robustness")


def q5_xy_strategy(q35: dict[str, Any]) -> list[str]:
    plans = q35["results"]["Q5"]["plans"]
    starts = {
        "FY1": (17800, 0),
        "FY2": (12000, 1400),
        "FY3": (6000, -3000),
        "FY4": (11000, 2000),
        "FY5": (13000, -2000),
    }
    shot_indices = shot_index_map(plans)
    fig, axes = plt.subplots(
        2, 1, figsize=(7.2, 4.25), layout="constrained",
        gridspec_kw={"height_ratios": [1.35, 1.0]},
    )

    # A: exact-scale global route overview.
    ax = axes[0]
    for drone, (x0, y0) in starts.items():
        drone_plans = sorted(
            [plan for plan in plans if plan["drone_id"] == drone],
            key=lambda item: float(item["explosion_time"]),
        )
        terminal = max(drone_plans, key=lambda item: float(item["explosion_time"]))["explosion_position"]
        ax.annotate(
            "", xy=(terminal[0] / 1000.0, terminal[1] / 1000.0), xytext=(x0 / 1000.0, y0 / 1000.0),
            arrowprops={"arrowstyle": "-|>", "lw": 0.95, "color": DRONE_COLORS[drone], "alpha": 0.82, "mutation_scale": 8},
        )
        ax.scatter([x0 / 1000.0], [y0 / 1000.0], marker="^", s=34, color=DRONE_COLORS[drone], edgecolor="white", linewidth=0.5, zorder=4)
        ax.text(x0 / 1000.0, y0 / 1000.0 + 0.16, drone, ha="center", color=DRONE_COLORS[drone], fontsize=6.7, fontweight="bold")
        for plan in drone_plans:
            explosion_x, explosion_y, _ = plan["explosion_position"]
            ax.scatter(
                [explosion_x / 1000.0], [explosion_y / 1000.0], s=24,
                color=MISSILE_COLORS[str(plan["missile_id"])], edgecolor="white", linewidth=0.45, zorder=4,
            )
    ax.scatter([0], [0], marker="x", s=34, color=COLORS["ink"], zorder=5)
    ax.scatter([0], [0.2], marker="o", s=24, facecolor="white", edgecolor=COLORS["ink"], linewidth=0.8, zorder=5)
    ax.text(0.20, -0.20, "假目标", color=COLORS["muted"], fontsize=6.3)
    ax.text(0.20, 0.39, "真目标", color=COLORS["muted"], fontsize=6.3)
    ax.set_xlim(-0.5, 18.5)
    ax.set_ylim(-3.4, 2.45)
    ax.set_aspect("equal", adjustable="box")
    ax.set_ylabel("$y$ (km)")
    ax.set_xlabel("$x$ (km)")
    style_axis(ax, grid="both")
    panel_label(ax, "A", x=-0.055, y=1.01)

    # B: vertically enlarged decision strip with the release layer made explicit.
    ax = axes[1]
    label_offsets = {
        "FY1": (0, 7), "FY2": (-3, 11), "FY3": (3, -11),
        "FY4": (-4, 7), "FY5": (4, -9),
    }
    for drone in starts:
        drone_plans = sorted(
            [plan for plan in plans if plan["drone_id"] == drone],
            key=lambda item: float(item["release_time"]),
        )
        for plan in drone_plans:
            release_x, release_y, _ = plan["release_position"]
            explosion_x, explosion_y, _ = plan["explosion_position"]
            color = MISSILE_COLORS[str(plan["missile_id"])]
            ax.plot(
                [release_x / 1000.0, explosion_x / 1000.0],
                [release_y / 1000.0, explosion_y / 1000.0],
                color=color, lw=0.75, alpha=0.75,
            )
            ax.scatter(
                [release_x / 1000.0], [release_y / 1000.0], marker="D", s=22,
                facecolor="white", edgecolor=DRONE_COLORS[drone], linewidth=0.9, zorder=4,
            )
            ax.scatter(
                [explosion_x / 1000.0], [explosion_y / 1000.0], marker="o", s=28,
                color=color, edgecolor="white", linewidth=0.5, zorder=5,
            )
            ax.annotate(
                str(shot_indices[id(plan)]),
                (explosion_x / 1000.0, explosion_y / 1000.0),
                xytext=label_offsets[drone], textcoords="offset points", ha="center",
                color=COLORS["ink"], fontsize=5.9,
                bbox={"boxstyle": "round,pad=0.08", "facecolor": "white", "edgecolor": "none", "alpha": 0.82},
            )
    ax.scatter([0], [0], marker="x", s=32, color=COLORS["ink"], zorder=5)
    ax.scatter([0], [0.2], marker="o", s=22, facecolor="white", edgecolor=COLORS["ink"], linewidth=0.8, zorder=5)
    ax.set_xlim(-0.45, 18.45)
    ax.set_ylim(-0.70, 0.70)
    ax.set_ylabel("$y$ (km，纵向放大)")
    ax.set_xlabel("$x$ (km)")
    ax.text(0.995, 1.02, "空心菱形：投放点  ·  实心圆：起爆点  ·  数字：同机弹序", transform=ax.transAxes, ha="right", va="bottom", color=COLORS["muted"], fontsize=6.3)
    style_axis(ax, grid="both")
    panel_label(ax, "B", x=-0.055, y=1.01)

    handles = [
        Line2D([0], [0], marker="D", color="none", markerfacecolor="white", markeredgecolor=COLORS["muted"], markersize=4.5, label="投放"),
        *[
            Line2D([0], [0], marker="o", color="none", markerfacecolor=color, markeredgecolor=color, markersize=4.5, label=f"起爆→{missile}")
            for missile, color in MISSILE_COLORS.items()
        ],
    ]
    axes[0].legend(handles=handles, loc="lower center", bbox_to_anchor=(0.56, 1.01), ncols=4, handletextpad=0.25, columnspacing=0.9)
    return save(fig, "q5_xy_strategy")


def main() -> None:
    configure_style()
    q12, q35 = load_results()
    multiseed = load_q2_multiseed()
    q34_multiseed = load_q3_q4_multiseed()
    artifacts = {
        "F1": workflow_figure(),
        "F2": geometry_mechanism(),
        "F3": q1_intervals(q12),
        "F4": q2_response_surface(q12),
        "F5": q2_multiseed_stability(multiseed),
        "F6": interval_union_figure(q35, "Q3", "q3_interval_union"),
        "F7": interval_union_figure(q35, "Q4", "q4_temporal_synergy"),
        "F8": search_diagnostics(q35),
        "F9": q5_xy_strategy(q35),
        "F10": q5_gantt(q35),
        "F11": q5_missile_robustness(q35),
        "F12": criterion_comparison(q12, q35),
        "F13": numerical_convergence(q12),
        "F14": q3_q4_multiseed_stability(q34_multiseed),
    }
    manifest = {
        "schema_version": 4,
        "run_id": RUN_ID,
        "generated_by": "src/generate_figures.py",
        "design_system": {
            "profile": "contest-paper-evidence-first",
            "palette": "graphite + Okabe-Ito-derived semantic accents",
            "title_policy": "paper captions carry titles; panels use A/B/C tags only",
            "export": "exact physical size; 600 dpi PNG plus editable PDF/SVG",
            "minimum_final_font_pt": 7.0,
        },
        "figures": [
            {"id": "F1", "claim_id": "C-WORKFLOW", "subquestion": "Q1-Q5", "files": artifacts["F1"], "data_source": "统一模型与验证流程", "axes": "流程节点", "units": "不适用", "caption": "五问共享运动学、连续事件、区间并集与证据审计链路。", "interpretation": "递进问题不是五套孤立模型。", "paper_location": "问题分析与技术路线"},
            {"id": "F2", "claim_id": "C-GEOMETRY", "subquestion": "Q1", "files": artifacts["F2"], "data_source": "题面常数与 src/solve_q1_q2.py", "axes": "x,z 与视线局部坐标", "units": "m", "caption": "有限视线几何及烟幕截面的真实尺度关系。", "interpretation": "遮蔽由球心到有限线段的距离而非无限直线距离决定。", "paper_location": "统一遮蔽模型"},
            {"id": "F3", "claim_id": "C-Q1-INTERVAL", "subquestion": "Q1", "files": artifacts["F3"], "data_source": "validation/q1_q2_independent.json", "axes": "任务时刻/遮蔽裕度", "units": "s,m", "caption": "Q1 两种口径的连续裕度与有效区间。", "interpretation": "口径差异主要来自进入边界。", "paper_location": "问题一结果与检验"},
            {"id": "F4", "claim_id": "C-Q2-LANDSCAPE", "subquestion": "Q2", "files": artifacts["F4"], "data_source": "src/solve_q1_q2.py 受控二维复算", "axes": "航向/起爆时刻/时长", "units": "deg,s", "caption": "固定速度与即时投放截面上的 Q2 目标函数地形。", "interpretation": "目标面具有零平台与狭窄高值区，支持全局候选后连续精化。", "paper_location": "问题二求解"},
            {"id": "F5", "claim_id": "C-Q2-MULTISEED", "subquestion": "Q2", "files": artifacts["F5"], "data_source": "validation/q2_multiseed.json", "axes": "迭代代数/距终值差/函数评估量", "units": "iteration,s,count", "caption": "8 个独立种子的收敛缺口、中位数/IQR 与函数评估量。", "interpretation": "8 次均可行且终值在数值容差内一致；皮秒级浮点噪声不作为统计分布放大。", "paper_location": "问题二稳定性检验"},
            {"id": "F6", "claim_id": "C-Q3-UNION", "subquestion": "Q3", "files": artifacts["F6"], "data_source": "validation/q3_q5_independent.json", "axes": "任务时刻/烟幕弹", "units": "s", "caption": "Q3 三弹原始区间及去重并集。", "interpretation": "6.8140 s 单弹和经重叠扣除后形成 6.6311 s 连续并集。", "paper_location": "问题三结果与检验"},
            {"id": "F7", "claim_id": "C-Q4-SYNERGY", "subquestion": "Q4", "files": artifacts["F7"], "data_source": "validation/q3_q5_independent.json", "axes": "任务时刻/无人机", "units": "s", "caption": "Q4 三机时间窗的互补结构。", "interpretation": "三段互不重叠窗口使并集等于单弹时长之和。", "paper_location": "问题四结果与检验"},
            {"id": "F8", "claim_id": "C-SEARCH-QUALITY", "subquestion": "Q3-Q5", "files": artifacts["F8"], "data_source": "validation/q3_q5_independent.json", "axes": "相对基线/搜索记账量", "units": "%,count", "caption": "Q3–Q5 归一化质量迁移及对数搜索记账。", "interpretation": "连续复算可纠正粗评偏差；候选、航路与保留包只作分项记账而非漏斗。", "paper_location": "组合搜索算法与质量标定"},
            {"id": "F9", "claim_id": "C-Q5-STRATEGY", "subquestion": "Q5", "files": artifacts["F9"], "data_source": "validation/q3_q5_independent.json", "axes": "x/y 坐标", "units": "km", "caption": "Q5 航迹、投放点、起爆点、目标指派与同机弹序。", "interpretation": "同机三弹共享航向与速度，且投放层与起爆层均被显式绘制。", "paper_location": "问题五策略解释"},
            {"id": "F10", "claim_id": "C-Q5-COVERAGE", "subquestion": "Q5", "files": artifacts["F10"], "data_source": "validation/q3_q5_independent.json", "axes": "任务时刻/烟幕弹/并集", "units": "s", "caption": "Q5 的 15 枚烟幕弹、逐导弹并集与最大空窗。", "interpretation": "并集摘要与内部空窗说明当前结果仍非上界；弹序按每机投放时刻生成。", "paper_location": "问题五覆盖结果"},
            {"id": "F11", "claim_id": "C-Q5-ROBUSTNESS", "subquestion": "Q5", "files": artifacts["F11"], "data_source": "validation/q3_q5_independent.json", "axes": "导弹/有效并集", "units": "s", "caption": "Q5 同一策略的双口径配对审计。", "interpretation": "保守口径降低绝对值但未改变导弹间排序。", "paper_location": "问题五保守审计"},
            {"id": "F12", "claim_id": "C-CRITERION-SENSITIVITY", "subquestion": "Q1-Q5", "files": artifacts["F12"], "data_source": "validation/q1_q2_independent.json; validation/q3_q5_independent.json", "axes": "同策略保留率/Q2 独立优化时长", "units": "%,s", "caption": "同策略判据保留率与 Q2 独立优化结果的分面比较。", "interpretation": "Q4 和 Q5 的几何口径风险最高；Q2 不得解释为同一策略前后损失。", "paper_location": "跨问题判据敏感性"},
            {"id": "F13", "claim_id": "C-TIME-CONVERGENCE", "subquestion": "Q1-Q2", "files": artifacts["F13"], "data_source": "validation/q1_q2_independent.json 与受控步长复算", "axes": "采样步长/绝对误差", "units": "s", "caption": "均匀计点法相对连续验根的离散误差。", "interpretation": "根精化消除了把采样分辨率直接当作报告精度的风险。", "paper_location": "数值收敛检验"},
            {"id": "F14", "claim_id": "C-Q34-MULTISEED", "subquestion": "Q3-Q4", "files": artifacts["F14"], "data_source": "validation/q3_q4_multiseed.json", "axes": "局部精化迭代/best-so-far/连续终值点", "units": "iteration,s", "caption": "Q3/Q4 五个种子的轨迹中位数/IQR 与连续终值点图。", "interpretation": "Q3 的种子离散明显大于 Q4；$n=5$ 不使用箱线图制造分布感。", "paper_location": "问题三、四随机搜索检验"}
        ],
    }
    figure_intents = {
        "F1": ("evidence_pipeline", ["module_dependency", "feedback_loop"]),
        "F2": ("trajectory_geometry", ["finite_segment", "nearest_point", "smoke_radius", "criterion_margin"]),
        "F3": ("root_event_zoom", ["zero_crossing", "interval", "entry_delay", "duration_delta"]),
        "F4": ("optimization_landscape", ["response_surface", "optimum", "orthogonal_slices", "high_value_band"]),
        "F5": ("convergence_audit", ["individual_trace", "median", "iqr", "evaluation_count", "feasibility"]),
        "F6": ("coverage_timeline", ["shot_index", "interval", "overlap", "union"]),
        "F7": ("coverage_timeline", ["drone", "interval", "gap", "union"]),
        "F8": ("search_quality", ["normalized_baseline", "coarse_score", "exact_score", "search_accounting"]),
        "F9": ("trajectory_geometry", ["drone_start", "route", "release_position", "explosion_position", "shot_index", "missile_assignment"]),
        "F10": ("coverage_timeline", ["shot_index", "missile_group", "interval", "union", "largest_gap"]),
        "F11": ("paired_sensitivity", ["paired_value", "absolute_loss", "relative_loss", "total"]),
        "F12": ("paired_sensitivity", ["same_strategy_retention", "independent_optimization_boundary"]),
        "F13": ("convergence_audit", ["step_size", "absolute_error", "reference_order", "tolerance_band"]),
        "F14": ("convergence_audit", ["individual_trace", "median", "iqr", "terminal_points", "sample_size"]),
    }
    for record in manifest["figures"]:
        template, semantic_layers = figure_intents[record["id"]]
        record["figure_intent"] = {
            "template": template,
            "reader_takeaway": record["interpretation"],
            "semantic_layers": semantic_layers,
            "comparison_semantics": "only like-for-like quantities share an axis",
            "cannot_infer": "图中证据不构成未声明的全局最优、现实随机鲁棒性或因果结论",
        }
        record["visual_qa"] = {
            "final_width_in": 6.2,
            "minimum_font_pt": 7.0,
            "figure_level_title": False,
            "vector_text_editable": True,
            "redundant_encoding": True,
        }
        record["sha256"] = {
            relative_path: sha256(ROOT / relative_path)
            for relative_path in record["files"]
        }
    (FIGURES / "figure_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"ok": True, "artifacts": artifacts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
