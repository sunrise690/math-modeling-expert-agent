from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


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
            "savefig.facecolor": "white",
        }
    )


def load_results() -> tuple[dict[str, Any], dict[str, Any]]:
    q12 = json.loads((VALIDATION / "q1_q2_independent.json").read_text(encoding="utf-8"))
    q35 = json.loads((VALIDATION / "q3_q5_independent.json").read_text(encoding="utf-8"))
    return q12, q35


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
        names.append(path.relative_to(ROOT).as_posix())
    plt.close(fig)
    return names


def q1_intervals(q12: dict[str, Any]) -> list[str]:
    records = [
        ("目标中心视线", q12["q1"]["g_9.80"]["centerline"], PALETTE[0]),
        ("完整圆柱全遮蔽", q12["q1"]["g_9.80"]["full_cylinder"], PALETTE[1]),
    ]
    fig, ax = plt.subplots(figsize=(5.2, 2.35), constrained_layout=True)
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
    ax.set_title("问题 1：两种有效遮蔽口径的连续时间区间")
    ax.grid(axis="x", color="#D0D0D0", linewidth=0.55, alpha=0.6)
    ax.set_ylim(-0.55, 1.55)
    return save(fig, "q1_occlusion_intervals")


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
    ax.legend(frameon=False, ncols=2)
    ax.grid(color="#D0D0D0", linewidth=0.5, alpha=0.45)
    return save(fig, "q5_xy_strategy")


def main() -> None:
    configure_style()
    q12, q35 = load_results()
    artifacts = {
        "F1": q1_intervals(q12),
        "F2": criterion_comparison(q12, q35),
        "F3": q5_gantt(q35),
        "F4": q5_missile_robustness(q35),
        "F5": q5_xy_strategy(q35),
    }
    manifest = {
        "schema_version": 1,
        "generated_by": "src/generate_figures.py",
        "figures": [
            {"id": "F1", "claim_id": "C-Q1-INTERVAL", "subquestion": "Q1", "files": artifacts["F1"], "data_source": "validation/q1_q2_independent.json", "axes": "任务时刻 (s) / 判据", "paper_location": "问题一结果与口径讨论"},
            {"id": "F2", "claim_id": "C-CRITERION-SENSITIVITY", "subquestion": "Q1-Q5", "files": artifacts["F2"], "data_source": "validation/q1_q2_independent.json; validation/q3_q5_independent.json", "axes": "问题 / 有效遮蔽时长 (s)", "paper_location": "模型检验与口径敏感性"},
            {"id": "F3", "claim_id": "C-Q5-COVERAGE", "subquestion": "Q5", "files": artifacts["F3"], "data_source": "validation/q3_q5_independent.json", "axes": "任务时刻 (s) / 烟幕弹", "paper_location": "问题五结果"},
            {"id": "F4", "claim_id": "C-Q5-ROBUSTNESS", "subquestion": "Q5", "files": artifacts["F4"], "data_source": "validation/q3_q5_independent.json", "axes": "导弹 / 有效遮蔽并集 (s)", "paper_location": "问题五保守审计"},
            {"id": "F5", "claim_id": "C-Q5-STRATEGY", "subquestion": "Q5", "files": artifacts["F5"], "data_source": "validation/q3_q5_independent.json", "axes": "x 坐标 (m) / y 坐标 (m)", "paper_location": "问题五策略解释"}
        ],
    }
    (FIGURES / "figure_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"ok": True, "artifacts": artifacts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
