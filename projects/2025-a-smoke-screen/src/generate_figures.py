from __future__ import annotations

import json
import hashlib
from math import ceil
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch
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
PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#000000"]


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"],
            "font.size": 8,
            "axes.labelsize": 9,
            "axes.titlesize": 10,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "savefig.facecolor": "white",
        }
    )


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
            bbox_inches="tight",
            pad_inches=0.06,
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
        ("题面与资料", "口径辨识\n约束提取"),
        ("统一机理", "解析轨迹\n有限视线"),
        ("连续事件", "括根定位\nBrent 精化"),
        ("组合优化", "候选航路\n区间并集"),
        ("证据审计", "约束回算\n双口径复核"),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 2.55), constrained_layout=True)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3)
    ax.axis("off")
    for index, (title, detail) in enumerate(columns):
        x = 0.25 + index * 1.95
        box = FancyBboxPatch(
            (x, 0.78), 1.55, 1.45,
            boxstyle="round,pad=0.08,rounding_size=0.08",
            facecolor=PALETTE[index % len(PALETTE)], edgecolor="white", alpha=0.90,
        )
        ax.add_patch(box)
        ax.text(x + 0.775, 1.77, title, ha="center", va="center", color="white", fontweight="bold", fontsize=8.5)
        ax.text(x + 0.775, 1.25, detail, ha="center", va="center", color="white", fontsize=7.5, linespacing=1.35)
        if index < len(columns) - 1:
            ax.annotate("", xy=(x + 1.87, 1.50), xytext=(x + 1.59, 1.50), arrowprops={"arrowstyle": "->", "lw": 1.2, "color": "#555555"})
    ax.text(0.25, 0.38, "Q1 复算", fontsize=7.2, color=PALETTE[0])
    ax.text(2.20, 0.38, "Q2 单弹连续优化", fontsize=7.2, color=PALETTE[1])
    ax.text(4.15, 0.38, "Q3–Q4 时间协同", fontsize=7.2, color=PALETTE[2])
    ax.text(6.10, 0.38, "Q5 航路—指派—排程", fontsize=7.2, color=PALETTE[3])
    ax.text(8.05, 0.38, "同一策略连续复算", fontsize=7.2, color=PALETTE[4])
    ax.set_title("五个子问题的统一建模与证据链", pad=4, fontweight="bold")
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

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.15), constrained_layout=True, gridspec_kw={"width_ratios": [1.35, 1]})
    ax = axes[0]
    ax.plot([missile[0], target[0]], [missile[2], target[2]], color="#333333", lw=1.2, label="导弹—目标有限视线")
    ax.scatter([missile[0]], [missile[2]], marker="^", s=42, color=PALETTE[1], label="M1")
    ax.scatter([target[0]], [target[2]], marker="s", s=28, color=PALETTE[2], label="真目标中心")
    ax.scatter([cloud[0]], [cloud[2]], s=38, color=PALETTE[0], label="烟幕球心")
    ax.plot([cloud[0], closest[0]], [cloud[2], closest[2]], "--", color=PALETTE[0], lw=1.0)
    ax.set_xlabel("x 坐标 (m)")
    ax.set_ylabel("z 坐标 (m)")
    ax.set_title("A  全局位置关系")
    ax.legend(frameon=False, fontsize=6.5)
    ax.grid(color="#D8D8D8", linewidth=0.5, alpha=0.55)

    ax = axes[1]
    ax.axhline(0, color="#333333", lw=1.1, label="有限视线")
    ax.add_patch(Circle((along, distance), SMOKE_RADIUS, facecolor=PALETTE[0], edgecolor=PALETTE[0], alpha=0.25))
    ax.scatter([along], [distance], color=PALETTE[0], s=25)
    ax.plot([along, along], [0, distance], "--", color=PALETTE[1], lw=1.0)
    ax.text(along + 1.0, distance / 2, f"$d={distance:.2f}$ m", va="center", fontsize=7)
    ax.set_xlim(along - 18, along + 18)
    ax.set_ylim(-13, 16)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("沿视线距离的局部坐标 (m)")
    ax.set_ylabel("垂直视线距离 (m)")
    ax.set_title(f"B  烟幕截面：裕度 $R-d={SMOKE_RADIUS-distance:.2f}$ m")
    ax.grid(color="#D8D8D8", linewidth=0.5, alpha=0.55)
    fig.suptitle("有限视线遮蔽判据的几何机理（Q1，$t=8.70$ s）", fontsize=10, fontweight="bold")
    return save(fig, "finite_sightline_geometry")


def q1_intervals(q12: dict[str, Any]) -> list[str]:
    records = [
        ("目标中心视线", q12["q1"]["g_9.80"]["centerline"], PALETTE[0]),
        ("完整圆柱全遮蔽", q12["q1"]["g_9.80"]["full_cylinder"], PALETTE[1]),
    ]
    fig, axes = plt.subplots(2, 1, figsize=(6.2, 4.25), sharex=True, constrained_layout=True, gridspec_kw={"height_ratios": [1.35, 1]})
    strategy = q1_strategy()
    times = np.linspace(5.1, 10.2, 105)
    center_margins = [centerline_margin(float(time), strategy, 9.8) for time in times]
    full_margins = [full_cylinder_margin(float(time), strategy, 9.8) for time in times]
    axes[0].plot(times, center_margins, color=PALETTE[0], lw=1.6, label="目标中心视线")
    axes[0].plot(times, full_margins, color=PALETTE[1], lw=1.5, ls="--", label="完整圆柱全遮蔽")
    axes[0].axhline(0, color="#333333", lw=0.8)
    axes[0].fill_between(times, 0, center_margins, where=np.asarray(center_margins) >= 0, color=PALETTE[0], alpha=0.14)
    axes[0].set_ylabel("遮蔽裕度 $F(t)$ (m)")
    axes[0].set_title("A  连续几何裕度与零点")
    axes[0].legend(frameon=False)
    axes[0].grid(color="#D0D0D0", linewidth=0.5, alpha=0.5)
    ax = axes[1]
    for index, (label, record, color) in enumerate(records):
        for left, right in record["intervals_s"]:
            ax.broken_barh([(left, right - left)], (index - 0.22, 0.44), facecolors=color)
            ax.text(
                (left + right) / 2,
                index,
                f"{right-left:.6f} s",
                ha="center",
                va="center",
                color="white",
                fontweight="bold",
                fontsize=7,
            )
    ax.set_yticks(range(len(records)), [item[0] for item in records])
    ax.set_xlabel("任务时刻 (s)")
    ax.set_title("B  连续验根得到的有效时间区间")
    ax.grid(axis="x", color="#D0D0D0", linewidth=0.55, alpha=0.6)
    ax.set_ylim(-0.55, 1.55)
    fig.suptitle("问题 1：两种遮蔽口径的连续裕度与有效区间", fontsize=10, fontweight="bold")
    return save(fig, "q1_occlusion_intervals")


def q2_response_surface(q12: dict[str, Any]) -> list[str]:
    headings = np.linspace(1.0, 13.0, 25)
    explosion_times = np.linspace(0.25, 1.25, 23)
    surface = np.zeros((len(explosion_times), len(headings)))
    for row, explosion_time in enumerate(explosion_times):
        for column, heading in enumerate(headings):
            strategy = Strategy(np.deg2rad(heading), 140.0, 0.0, float(explosion_time))
            intervals = strategy_intervals(strategy, "centerline", 9.8, max_step_s=0.08)
            surface[row, column] = sum(right - left for left, right in intervals)
    optimum = q12["q2"]["centerline"]["strategy"]
    fig, ax = plt.subplots(figsize=(5.9, 4.0), constrained_layout=True)
    levels = np.linspace(0, max(0.5, float(surface.max())), 15)
    contour = ax.contourf(headings, explosion_times, surface, levels=levels, cmap="viridis")
    lines = ax.contour(headings, explosion_times, surface, levels=levels[::2], colors="white", linewidths=0.45, alpha=0.7)
    ax.clabel(lines, inline=True, fontsize=6, fmt="%.1f")
    ax.scatter([optimum["heading_deg"]], [optimum["explosion_time_s"]], marker="*", s=90, color=PALETTE[1], edgecolor="white", linewidth=0.6, label="连续精化方案")
    ax.set_xlabel("航向角 $\\theta$ ($^\\circ$)")
    ax.set_ylabel("起爆时刻 $t^e$ (s)；$v=140$ m/s，$t^r=0$")
    ax.set_title("问题 2：主口径目标函数的二维剖面")
    ax.legend(frameon=False)
    bar = fig.colorbar(contour, ax=ax)
    bar.set_label("有效遮蔽时长 (s)")
    return save(fig, "q2_response_surface")


def q2_multiseed_stability(multiseed: dict[str, Any]) -> list[str]:
    runs = multiseed["runs"]
    exact = np.asarray([run["exact_duration_s"] for run in runs], dtype=float)
    exact_delta_ps = (exact - np.median(exact)) * 1e12
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.25), constrained_layout=True)
    for index, run in enumerate(runs):
        trace = run["best_so_far_trace"]
        generations = [point["generation"] for point in trace]
        incumbents = [point["best_coarse_duration_s"] for point in trace]
        axes[0].plot(
            generations,
            incumbents,
            lw=0.9,
            alpha=0.72,
            color=PALETTE[index % 6],
            label=f"种子 {str(run['seed'])[-2:]}",
        )
    axes[0].set_xlabel("差分进化代数")
    axes[0].set_ylabel("best-so-far 粗评分 (s)")
    axes[0].set_title("A  八个独立种子的逐代收敛轨迹")
    axes[0].legend(frameon=False, fontsize=5.8, ncols=2)
    axes[0].grid(color="#D0D0D0", linewidth=0.5, alpha=0.5)

    positions = np.linspace(-0.16, 0.16, len(runs))
    axes[1].boxplot(
        exact_delta_ps,
        orientation="vertical",
        widths=0.34,
        patch_artist=True,
        showfliers=False,
        boxprops={"facecolor": PALETTE[0], "alpha": 0.22, "edgecolor": PALETTE[0]},
        medianprops={"color": "#222222", "linewidth": 1.2},
        whiskerprops={"color": PALETTE[0]},
        capprops={"color": PALETTE[0]},
    )
    axes[1].scatter(1 + positions, exact_delta_ps, s=25, color=PALETTE[1], edgecolor="white", linewidth=0.45, zorder=3)
    for x_pos, value, run in zip(1 + positions, exact_delta_ps, runs):
        axes[1].annotate(str(run["seed"])[-2:], (x_pos, value), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=5.8)
    axes[1].axhline(0, color="#333333", lw=0.75)
    axes[1].set_xticks([1], ["连续精化终值"])
    axes[1].set_ylabel("相对中位数偏差 (ps)")
    axes[1].set_title("B  连续复算终值分布（$n=8$）")
    axes[1].grid(axis="y", color="#D0D0D0", linewidth=0.5, alpha=0.5)
    summary = multiseed["summary"]
    fig.suptitle(
        "问题 2 随机搜索审计：全部成功，连续终值标准差 "
        f"{summary['standard_deviation_s']:.2e} s，最大约束违反量 {summary['max_constraint_violation']:.0f}",
        fontsize=9.5,
        fontweight="bold",
    )
    return save(fig, "q2_multiseed_stability")


def q3_q4_multiseed_stability(multiseed: dict[str, Any]) -> list[str]:
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.45), constrained_layout=True)
    for row, question in enumerate(("Q3", "Q4")):
        record = multiseed["problems"][question]
        runs = record["runs"]
        summary = record["summary"]
        for index, run in enumerate(runs):
            trace = run["best_so_far_trace"]
            axes[row, 0].plot(
                [point["iteration"] for point in trace],
                [point["best_fast_objective_s"] for point in trace],
                color=PALETTE[index],
                lw=1.0,
                alpha=0.78,
                label=f"种子 {str(run['seed'])[-2:]}",
            )
        axes[row, 0].set_xlabel("局部随机精化迭代")
        axes[row, 0].set_ylabel("best-so-far 粗评分 (s)")
        axes[row, 0].set_title(f"{'A' if row == 0 else 'C'}  {question} 局部精化轨迹")
        axes[row, 0].grid(color="#D0D0D0", linewidth=0.5, alpha=0.5)
        axes[row, 0].legend(frameon=False, fontsize=5.8, ncols=2)

        terminal = np.asarray([run["final_exact_objective_s"] for run in runs], dtype=float)
        x_positions = 1 + np.linspace(-0.16, 0.16, len(runs))
        axes[row, 1].boxplot(
            terminal,
            orientation="vertical",
            widths=0.34,
            patch_artist=True,
            showfliers=False,
            boxprops={"facecolor": PALETTE[row], "alpha": 0.20, "edgecolor": PALETTE[row]},
            medianprops={"color": "#222222", "linewidth": 1.2},
            whiskerprops={"color": PALETTE[row]},
            capprops={"color": PALETTE[row]},
        )
        point_colors = [PALETTE[1] if run["seed"] == summary["best_seed"] else PALETTE[2] for run in runs]
        axes[row, 1].scatter(x_positions, terminal, s=28, c=point_colors, edgecolor="white", linewidth=0.45, zorder=3)
        for x_pos, value, run in zip(x_positions, terminal, runs):
            axes[row, 1].annotate(str(run["seed"])[-2:], (x_pos, value), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=5.8)
        axes[row, 1].set_xticks([1], [f"{question} 连续终值"])
        axes[row, 1].set_ylabel("连续复算并集时长 (s)")
        axes[row, 1].set_title(
            f"{'B' if row == 0 else 'D'}  五种子终值："
            f"{summary['minimum_s']:.3f}–{summary['maximum_s']:.3f} s"
        )
        axes[row, 1].grid(axis="y", color="#D0D0D0", linewidth=0.5, alpha=0.5)
    fig.suptitle(
        "问题 3–4 随机局部精化审计：五个种子均可行，橙色点为本批最好终值",
        fontsize=9.5,
        fontweight="bold",
    )
    return save(fig, "q3_q4_multiseed_stability")


def interval_union_figure(q35: dict[str, Any], question: str, stem: str) -> list[str]:
    plans = q35["results"][question]["plans"]
    union = q35["results"][question]["exact_centerline_union"]["M1"]
    fig, ax = plt.subplots(figsize=(6.4, 2.9 if question == "Q3" else 3.2), constrained_layout=True)
    labels = []
    for row, plan in enumerate(plans):
        label = f"{plan['drone_id']}-{row + 1}"
        labels.append(label)
        for left, right in plan["exact_centerline_intervals"]:
            ax.broken_barh([(left, right - left)], (row - 0.31, 0.62), facecolors=PALETTE[row % len(PALETTE)], edgecolors="white")
    union_row = len(plans) + 0.35
    for left, right in union:
        ax.broken_barh([(left, right - left)], (union_row - 0.34, 0.68), facecolors="#222222")
    labels.append("并集计分")
    ax.set_yticks([*range(len(plans)), union_row], labels)
    ax.set_xlabel("任务时刻 (s)")
    ax.set_title(f"问题 {question[1:]}：单弹有效区间与去重后的并集")
    ax.grid(axis="x", color="#D0D0D0", linewidth=0.5, alpha=0.55)
    return save(fig, stem)


def search_diagnostics(q35: dict[str, Any]) -> list[str]:
    questions = ["Q3", "Q4", "Q5"]
    baseline = [q35["results"][q]["diagnostics"]["fast_baseline_objective"] for q in questions]
    approximate = [q35["results"][q]["diagnostics"]["fast_final_objective"] for q in questions]
    exact = [q35["results"][q]["diagnostics"]["exact_objective"] for q in questions]
    routes = [q35["results"][q]["diagnostics"]["routes_evaluated"] for q in questions]
    candidates = [q35["results"][q]["diagnostics"]["candidates_generated"] for q in questions]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.25), constrained_layout=True)
    x = np.arange(3)
    width = 0.25
    for offset, values, label, color in (
        (-width, baseline, "粗网格基线", PALETTE[2]),
        (0, approximate, "粗网格保留解", PALETTE[0]),
        (width, exact, "连续复算", PALETTE[1]),
    ):
        bars = axes[0].bar(x + offset, values, width, label=label, color=color)
        axes[0].bar_label(bars, fmt="%.2f", padding=2, fontsize=6)
    axes[0].set_xticks(x, questions)
    axes[0].set_ylabel("目标函数 (s)")
    axes[0].set_title("A  基线、近似评分与连续复算")
    axes[0].legend(frameon=False, fontsize=6.5)
    axes[0].grid(axis="y", color="#D0D0D0", linewidth=0.5, alpha=0.5)
    axes[1].bar(x - 0.18, routes, 0.36, label="评估航路数", color=PALETTE[0])
    axes[1].bar(x + 0.18, candidates, 0.36, label="生成候选数", color=PALETTE[4])
    axes[1].set_xticks(x, questions)
    axes[1].set_ylabel("计数")
    axes[1].set_title("B  确定性搜索规模")
    axes[1].legend(frameon=False, fontsize=6.5)
    axes[1].grid(axis="y", color="#D0D0D0", linewidth=0.5, alpha=0.5)
    fig.suptitle("问题 3–5：组合搜索的质量标定与计算规模", fontsize=10, fontweight="bold")
    return save(fig, "search_quality_diagnostics")


def numerical_convergence(q12: dict[str, Any]) -> list[str]:
    q2_record = q12["q2"]["centerline"]
    q2s = q2_record["strategy"]
    strategies = {
        "Q1 给定策略": (q1_strategy(), q12["q1"]["g_9.80"]["centerline"]["duration_s"]),
        "Q2 优化策略": (Strategy(q2s["heading_rad"], q2s["speed_mps"], q2s["release_time_s"], q2s["fuse_delay_s"]), q2_record["duration_s"]),
    }
    steps = np.array([0.50, 0.25, 0.10, 0.05, 0.02, 0.01, 0.005])
    fig, ax = plt.subplots(figsize=(5.3, 3.45), constrained_layout=True)
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
        ax.loglog(steps, errors, marker=["o", "s"][index], color=PALETTE[index], lw=1.5, label=label)
    ax.invert_xaxis()
    ax.set_xlabel("均匀采样步长 $\\Delta t$ (s)")
    ax.set_ylabel("相对连续验根结果的绝对误差 (s)")
    ax.set_title("均匀计点法的离散误差与连续验根基准")
    ax.grid(which="both", color="#D0D0D0", linewidth=0.5, alpha=0.55)
    ax.legend(frameon=False)
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
    labels = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    x = np.arange(len(labels))
    width = 0.36
    fig, ax = plt.subplots(figsize=(6.0, 3.35), constrained_layout=True)
    left = ax.bar(x - width / 2, center, width, label="中心视线主评分", color=PALETTE[0])
    right = ax.bar(x + width / 2, full, width, label="完整圆柱保守审计", color=PALETTE[1])
    ax.bar_label(left, fmt="%.2f", padding=2, fontsize=6)
    ax.bar_label(right, fmt="%.2f", padding=2, fontsize=6)
    ax.set_xticks(x, labels)
    ax.set_ylabel("有效遮蔽时长或分导弹时长之和 (s)")
    ax.set_title("五问结果对遮蔽判据的敏感性")
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#D0D0D0", linewidth=0.55, alpha=0.55)
    ax.set_ylim(bottom=0)
    return save(fig, "criterion_sensitivity")


def q5_gantt(q35: dict[str, Any]) -> list[str]:
    plans = q35["results"]["Q5"]["plans"]
    missiles = ["M1", "M2", "M3"]
    # The title, five-item legend and first panel need independent vertical bands.
    # A manual top margin avoids the overlap that constrained_layout can create
    # when the exported bounding box is tightened.
    fig, axes = plt.subplots(3, 1, figsize=(7.2, 5.4), sharex=True, constrained_layout=False)
    drone_colors = {f"FY{index + 1}": PALETTE[index] for index in range(5)}
    for ax, missile in zip(axes, missiles):
        selected = [plan for plan in plans if plan["missile_id"] == missile]
        for row, plan in enumerate(selected):
            for left, right in plan["exact_centerline_intervals"]:
                ax.broken_barh(
                    [(left, right - left)],
                    (row - 0.34, 0.68),
                    facecolors=drone_colors[plan["drone_id"]],
                    edgecolors="white",
                    linewidth=0.5,
                )
        ax.set_yticks(range(len(selected)), [f"{p['drone_id']}-{index + 1}" for index, p in enumerate(selected)])
        ax.set_ylabel(missile)
        duration = q35["results"]["Q5"]["exact_centerline_duration_by_missile"][missile]
        ax.set_title(f"{missile}：并集 {duration:.3f} s", loc="left", fontsize=8, fontweight="bold")
        ax.grid(axis="x", color="#D0D0D0", linewidth=0.5, alpha=0.5)
    axes[-1].set_xlabel("任务时刻 (s)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=drone_colors[name]) for name in drone_colors]
    fig.suptitle("问题 5：15 枚烟幕弹的中心视线有效区间", y=0.985, fontsize=10, fontweight="bold")
    fig.legend(
        handles,
        list(drone_colors),
        loc="upper center",
        bbox_to_anchor=(0.5, 0.945),
        ncols=5,
        frameon=False,
    )
    fig.subplots_adjust(left=0.10, right=0.985, bottom=0.09, top=0.84, hspace=0.43)
    return save(fig, "q5_coverage_gantt")


def q5_missile_robustness(q35: dict[str, Any]) -> list[str]:
    missiles = ["M1", "M2", "M3"]
    center = [q35["results"]["Q5"]["exact_centerline_duration_by_missile"][item] for item in missiles]
    full = [q35["full_cylinder_secondary_audit"]["Q5"]["duration_by_missile"][item] for item in missiles]
    x = np.arange(3)
    width = 0.36
    fig, ax = plt.subplots(figsize=(4.8, 3.1), constrained_layout=True)
    left = ax.bar(x - width / 2, center, width, label="中心视线", color=PALETTE[0])
    right = ax.bar(x + width / 2, full, width, label="完整圆柱", color=PALETTE[1])
    ax.bar_label(left, fmt="%.2f", padding=2, fontsize=7)
    ax.bar_label(right, fmt="%.2f", padding=2, fontsize=7)
    ax.set_xticks(x, missiles)
    ax.set_ylabel("有效遮蔽并集 (s)")
    ax.set_title("问题 5：分导弹覆盖及保守审计")
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#D0D0D0", linewidth=0.55, alpha=0.55)
    ax.set_ylim(bottom=0)
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
    missile_colors = {"M1": PALETTE[0], "M2": PALETTE[1], "M3": PALETTE[2]}
    fig, ax = plt.subplots(figsize=(6.3, 4.0), constrained_layout=True)
    for drone, (x0, y0) in starts.items():
        drone_plans = [plan for plan in plans if plan["drone_id"] == drone]
        heading = np.deg2rad(drone_plans[0]["heading_deg"])
        ax.scatter([x0], [y0], marker="^", s=42, color="#222222", zorder=4)
        ax.text(x0, y0 + 130, drone, ha="center", fontsize=7)
        ax.arrow(x0, y0, 900 * np.cos(heading), 900 * np.sin(heading), width=18, color="#666666", alpha=0.75)
        for plan in drone_plans:
            x, y, _z = plan["explosion_position"]
            ax.scatter(x, y, s=30, color=missile_colors[plan["missile_id"]], edgecolor="white", linewidth=0.5)
    ax.scatter([0], [0], marker="x", s=48, color="#000000", label="假目标")
    target = plt.Circle((0, 200), 7, facecolor="none", edgecolor="#555555", linewidth=1.0)
    ax.add_patch(target)
    # The true target is only 14 m wide on an 18 km canvas, so retain the
    # physically scaled circle and add a visible centre marker for readers.
    ax.scatter([0], [200], marker="o", s=14, facecolor="white", edgecolor="#555555", label="真目标中心")
    for missile, color in missile_colors.items():
        ax.scatter([], [], s=30, color=color, label=f"指派给 {missile}")
    ax.set_xlabel("x 坐标 (m)")
    ax.set_ylabel("y 坐标 (m)")
    ax.set_title("问题 5：无人机航向与烟幕弹起爆点平面投影")
    ax.set_aspect("equal", adjustable="box")
    ax.legend(frameon=False, ncols=2)
    ax.grid(color="#D0D0D0", linewidth=0.5, alpha=0.45)
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
        "schema_version": 3,
        "run_id": RUN_ID,
        "generated_by": "src/generate_figures.py",
        "figures": [
            {"id": "F1", "claim_id": "C-WORKFLOW", "subquestion": "Q1-Q5", "files": artifacts["F1"], "data_source": "统一模型与验证流程", "axes": "流程节点", "units": "不适用", "caption": "五问共享运动学、连续事件、区间并集与证据审计链路。", "interpretation": "递进问题不是五套孤立模型。", "paper_location": "问题分析与技术路线"},
            {"id": "F2", "claim_id": "C-GEOMETRY", "subquestion": "Q1", "files": artifacts["F2"], "data_source": "题面常数与 src/solve_q1_q2.py", "axes": "x,z 与视线局部坐标", "units": "m", "caption": "有限视线几何及烟幕截面的真实尺度关系。", "interpretation": "遮蔽由球心到有限线段的距离而非无限直线距离决定。", "paper_location": "统一遮蔽模型"},
            {"id": "F3", "claim_id": "C-Q1-INTERVAL", "subquestion": "Q1", "files": artifacts["F3"], "data_source": "validation/q1_q2_independent.json", "axes": "任务时刻/遮蔽裕度", "units": "s,m", "caption": "Q1 两种口径的连续裕度与有效区间。", "interpretation": "口径差异主要来自进入边界。", "paper_location": "问题一结果与检验"},
            {"id": "F4", "claim_id": "C-Q2-LANDSCAPE", "subquestion": "Q2", "files": artifacts["F4"], "data_source": "src/solve_q1_q2.py 受控二维复算", "axes": "航向/起爆时刻/时长", "units": "deg,s", "caption": "固定速度与即时投放截面上的 Q2 目标函数地形。", "interpretation": "目标面具有零平台与狭窄高值区，支持全局候选后连续精化。", "paper_location": "问题二求解"},
            {"id": "F5", "claim_id": "C-Q2-MULTISEED", "subquestion": "Q2", "files": artifacts["F5"], "data_source": "validation/q2_multiseed.json", "axes": "迭代代数/best-so-far/连续终值偏差", "units": "iteration,s,ps", "caption": "8 个独立种子的逐代收敛轨迹与连续复算终值分布。", "interpretation": "不同全局搜索起点均穿越零平台，连续精化终值在当前参数化下高度一致。", "paper_location": "问题二稳定性检验"},
            {"id": "F6", "claim_id": "C-Q3-UNION", "subquestion": "Q3", "files": artifacts["F6"], "data_source": "validation/q3_q5_independent.json", "axes": "任务时刻/烟幕弹", "units": "s", "caption": "Q3 三弹原始区间及去重并集。", "interpretation": "6.8140 s 单弹和经重叠扣除后形成 6.6311 s 连续并集。", "paper_location": "问题三结果与检验"},
            {"id": "F7", "claim_id": "C-Q4-SYNERGY", "subquestion": "Q4", "files": artifacts["F7"], "data_source": "validation/q3_q5_independent.json", "axes": "任务时刻/无人机", "units": "s", "caption": "Q4 三机时间窗的互补结构。", "interpretation": "三段互不重叠窗口使并集等于单弹时长之和。", "paper_location": "问题四结果与检验"},
            {"id": "F8", "claim_id": "C-SEARCH-QUALITY", "subquestion": "Q3-Q5", "files": artifacts["F8"], "data_source": "validation/q3_q5_independent.json", "axes": "问题/目标值/候选规模", "units": "s,count", "caption": "Q3–Q5 基线、粗评、连续复算及搜索规模。", "interpretation": "连续复算可纠正粗网格乐观偏差，且 Q3/Q5 相对基线取得提升。", "paper_location": "组合搜索算法与质量标定"},
            {"id": "F9", "claim_id": "C-Q5-STRATEGY", "subquestion": "Q5", "files": artifacts["F9"], "data_source": "validation/q3_q5_independent.json", "axes": "x/y 坐标", "units": "m", "caption": "Q5 无人机航向与起爆点平面投影。", "interpretation": "同机三弹共享航向与速度。", "paper_location": "问题五策略解释"},
            {"id": "F10", "claim_id": "C-Q5-COVERAGE", "subquestion": "Q5", "files": artifacts["F10"], "data_source": "validation/q3_q5_independent.json", "axes": "任务时刻/烟幕弹", "units": "s", "caption": "Q5 的 15 枚烟幕弹有效区间排程。", "interpretation": "M2、M3 仍有可利用空档，当前结果不构成上界。", "paper_location": "问题五覆盖结果"},
            {"id": "F11", "claim_id": "C-Q5-ROBUSTNESS", "subquestion": "Q5", "files": artifacts["F11"], "data_source": "validation/q3_q5_independent.json", "axes": "导弹/有效并集", "units": "s", "caption": "Q5 同一策略的双口径配对审计。", "interpretation": "保守口径降低绝对值但未改变导弹间排序。", "paper_location": "问题五保守审计"},
            {"id": "F12", "claim_id": "C-CRITERION-SENSITIVITY", "subquestion": "Q1-Q5", "files": artifacts["F12"], "data_source": "validation/q1_q2_independent.json; validation/q3_q5_independent.json", "axes": "问题/有效时长", "units": "s", "caption": "五问对遮蔽判据的敏感性。", "interpretation": "Q4 和 Q5 的几何口径风险最高。", "paper_location": "跨问题判据敏感性"},
            {"id": "F13", "claim_id": "C-TIME-CONVERGENCE", "subquestion": "Q1-Q2", "files": artifacts["F13"], "data_source": "validation/q1_q2_independent.json 与受控步长复算", "axes": "采样步长/绝对误差", "units": "s", "caption": "均匀计点法相对连续验根的离散误差。", "interpretation": "根精化消除了把采样分辨率直接当作报告精度的风险。", "paper_location": "数值收敛检验"},
            {"id": "F14", "claim_id": "C-Q34-MULTISEED", "subquestion": "Q3-Q4", "files": artifacts["F14"], "data_source": "validation/q3_q4_multiseed.json", "axes": "局部精化迭代/best-so-far/连续终值", "units": "iteration,s", "caption": "Q3/Q4 五个独立种子的局部精化轨迹与连续复算终值分布。", "interpretation": "Q3 的种子离散明显大于 Q4，说明固定种子可复现不等于随机搜索稳定；本批最好可行值应被回写并重新核验。", "paper_location": "问题三、四随机搜索检验"}
        ],
    }
    for record in manifest["figures"]:
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
