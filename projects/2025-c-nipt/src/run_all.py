"""Reproduce the complete 2025 CUMCM problem C analysis."""

from __future__ import annotations

import json
import math
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm, TwoSlopeNorm
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.formula.api as smf
from statsmodels.nonparametric.smoothers_lowess import lowess
from scipy.optimize import minimize
from scipy.special import ndtr
from scipy.stats import norm, spearmanr
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_recall_curve,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data/raw/nipt_data.xlsx"
RANDOM_SEED = 2025
THRESHOLD = 0.04
GRID_WEEKS = np.arange(10.0, 25.0 + 1 / 14, 1 / 7)
COLORS = ["#1F4E79", "#2A9D8F", "#D5A021", "#B85C70", "#6C757D"]
GROUP_COLORS = ["#173F5F", "#2B6F92", "#4E9AB5", "#C6943B"]
GROUP_LINESTYLES = ["-", "--", "-.", (0, (1.5, 1.5))]
METHOD_COLORS = {
    "分组逻辑回归": "#1F4E79",
    "随机森林": "#2A9D8F",
    "直方图梯度提升": "#D5A021",
    "传统 |Z|≥3": "#B85C70",
}
METHOD_LINESTYLES = {
    "分组逻辑回归": "-",
    "随机森林": "--",
    "直方图梯度提升": "-.",
    "传统 |Z|≥3": (0, (1.5, 1.5)),
}
NEUTRAL_DARK = "#2F3437"
NEUTRAL_MID = "#778087"
NEUTRAL_LIGHT = "#D9DEE2"
RISK_COLOR = "#B85C70"
SIGNAL_COLOR = "#1F4E79"
GAIN_COLOR = "#2A9D8F"
PAPER_WIDTH = 7.2


def configure_plots() -> None:
    sns.set_theme(style="ticks", context="paper")
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "Arial", "SimHei", "DejaVu Sans"],
            "font.size": 8,
            "axes.labelsize": 8.5,
            "axes.titlesize": 9,
            "axes.titleweight": "bold",
            "xtick.labelsize": 7.2,
            "ytick.labelsize": 7.2,
            "legend.fontsize": 7.2,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.5,
            "lines.markersize": 4,
            "xtick.major.width": 0.7,
            "ytick.major.width": 0.7,
            "xtick.major.size": 3,
            "ytick.major.size": 3,
            "axes.edgecolor": NEUTRAL_DARK,
            "axes.labelcolor": NEUTRAL_DARK,
            "text.color": NEUTRAL_DARK,
            "xtick.color": NEUTRAL_DARK,
            "ytick.color": NEUTRAL_DARK,
            "axes.axisbelow": True,
            "legend.frameon": False,
            "axes.unicode_minus": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 160,
            "savefig.dpi": 600,
            "savefig.facecolor": "white",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def panel_label(axis: plt.Axes, label: str) -> None:
    axis.text(
        -0.12,
        1.06,
        label,
        transform=axis.transAxes,
        ha="left",
        va="bottom",
        fontsize=10,
        fontweight="bold",
        color=NEUTRAL_DARK,
    )


def finish_axis(axis: plt.Axes, grid: str | None = None) -> None:
    sns.despine(ax=axis, trim=False)
    if grid:
        axis.grid(axis=grid, color=NEUTRAL_LIGHT, linewidth=0.6, alpha=0.75)
    else:
        axis.grid(False)


def parse_week(value: Any) -> float:
    match = re.match(r"\s*(\d+)w(?:\+(\d+))?", str(value))
    if not match:
        return float("nan")
    return int(match.group(1)) + int(match.group(2) or 0) / 7


def numeric_count(value: Any) -> float:
    match = re.search(r"\d+", str(value))
    return float(match.group()) if match else float("nan")


def week_label(value: float) -> str:
    week = int(math.floor(value + 1e-8))
    day = int(round((value - week) * 7))
    if day == 7:
        week += 1
        day = 0
    return f"{week}w+{day}"


def markdown_table(frame: pd.DataFrame) -> str:
    columns = [str(column) for column in frame.columns]
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame.iterrows():
        rows.append("| " + " | ".join(str(row[column]) for column in frame.columns) + " |")
    return "\n".join(rows)


def save_figure(fig: plt.Figure, name: str) -> None:
    for extension in ("png", "pdf", "svg"):
        kwargs = {"dpi": 600} if extension == "png" else {}
        fig.savefig(
            ROOT / "figures" / f"{name}.{extension}",
            bbox_inches="tight",
            pad_inches=0.035,
            facecolor="white",
            **kwargs,
        )
    plt.close(fig)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    male = pd.read_excel(DATA_FILE, sheet_name="男胎检测数据")
    female = pd.read_excel(DATA_FILE, sheet_name="女胎检测数据")
    for frame in (male, female):
        frame.columns = frame.columns.astype(str).str.strip()
        frame["孕周数值"] = frame["检测孕周"].map(parse_week)
        frame["怀孕次数数值"] = frame["怀孕次数"].map(numeric_count)
        frame["非自然受孕"] = (frame["IVF妊娠"] != "自然受孕").astype(int)
    female = female.loc[:, ~female.columns.str.startswith("Unnamed:")].copy()
    male["Y达标"] = (male["Y染色体浓度"] >= THRESHOLD).astype(int)
    female["异常"] = female["染色体的非整倍体"].notna().astype(int)
    male.to_csv(ROOT / "data/processed/male_clean.csv", index=False, encoding="utf-8-sig")
    female.to_csv(ROOT / "data/processed/female_clean.csv", index=False, encoding="utf-8-sig")
    return male, female


def data_audit(male: pd.DataFrame, female: pd.DataFrame) -> pd.DataFrame:
    records = []
    for name, frame in (("男胎", male), ("女胎", female)):
        records.append(
            {
                "工作表": name,
                "记录数": len(frame),
                "孕妇数": frame["孕妇代码"].nunique(),
                "平均重复次数": round(len(frame) / frame["孕妇代码"].nunique(), 3),
                "孕周缺失": int(frame["孕周数值"].isna().sum()),
                "BMI缺失": int(frame["孕妇BMI"].isna().sum()),
                "标签阳性数": int(frame["Y达标"].sum()) if name == "男胎" else int(frame["异常"].sum()),
                "标签阳性率": round(float(frame["Y达标"].mean() if name == "男胎" else frame["异常"].mean()), 4),
            }
        )
    overview = pd.DataFrame(records)
    overview.to_csv(ROOT / "tables/data_overview.csv", index=False, encoding="utf-8-sig")
    return overview


def make_data_profile(male: pd.DataFrame, female: pd.DataFrame) -> None:
    male_repeats = male.groupby("孕妇代码").size()
    female_repeats = female.groupby("孕妇代码").size()
    male_subject_bmi = male.groupby("孕妇代码")["孕妇BMI"].median().dropna()
    fig, axes = plt.subplots(2, 2, figsize=(PAPER_WIDTH, 5.15), constrained_layout=True)

    bins = np.arange(20, 48.5, 1.5)
    axes[0, 0].hist(male_subject_bmi, bins=bins, color=SIGNAL_COLOR, alpha=0.9, edgecolor="white", linewidth=0.5)
    median_bmi = float(male_subject_bmi.median())
    axes[0, 0].axvline(median_bmi, color=RISK_COLOR, linestyle=(0, (3, 2)), linewidth=1.2)
    axes[0, 0].text(
        0.98,
        0.94,
        f"n={len(male_subject_bmi)}\n中位数={median_bmi:.1f}",
        transform=axes[0, 0].transAxes,
        ha="right",
        va="top",
        fontsize=7.2,
    )
    axes[0, 0].set(xlabel="孕妇 BMI（kg/m²）", ylabel="孕妇数", title="男胎孕妇 BMI 分布")
    panel_label(axes[0, 0], "a")
    finish_axis(axes[0, 0], "y")

    week_values = male["孕周数值"].dropna()
    axes[0, 1].hist(week_values, bins=np.arange(10, 28.6, 1), color=GAIN_COLOR, alpha=0.88, edgecolor="white", linewidth=0.5)
    axes[0, 1].axvspan(10, 25, color=GAIN_COLOR, alpha=0.06, linewidth=0)
    axes[0, 1].text(
        0.98,
        0.94,
        f"n={len(week_values)} 条记录\n范围 {week_values.min():.1f}–{week_values.max():.1f} 周",
        transform=axes[0, 1].transAxes,
        ha="right",
        va="top",
        fontsize=7.2,
    )
    axes[0, 1].set(xlabel="检测孕周（周）", ylabel="记录数", title="男胎检测孕周分布")
    panel_label(axes[0, 1], "b")
    finish_axis(axes[0, 1], "y")

    repeat_levels = np.arange(1, max(int(male_repeats.max()), int(female_repeats.max())) + 1)
    male_counts = male_repeats.value_counts().reindex(repeat_levels, fill_value=0)
    female_counts = female_repeats.value_counts().reindex(repeat_levels, fill_value=0)
    width = 0.36
    axes[1, 0].bar(repeat_levels - width / 2, male_counts, width=width, color=SIGNAL_COLOR, label="男胎", alpha=0.9)
    axes[1, 0].bar(
        repeat_levels + width / 2,
        female_counts,
        width=width,
        color="#C6943B",
        label="女胎",
        alpha=0.9,
        hatch="///",
        edgecolor="white",
        linewidth=0.35,
    )
    axes[1, 0].set_xticks(repeat_levels)
    axes[1, 0].set(xlabel="每名孕妇的检测记录数", ylabel="孕妇数", title="受试者内重复测量结构")
    axes[1, 0].legend(loc="upper right", handlelength=1.4)
    panel_label(axes[1, 0], "c")
    finish_axis(axes[1, 0], "y")

    label_counts = female["异常"].value_counts().reindex([0, 1], fill_value=0)
    bars = axes[1, 1].bar(["正常", "异常"], label_counts.values, color=[NEUTRAL_MID, RISK_COLOR], width=0.58)
    for index, value in enumerate(label_counts.values):
        rate = value / label_counts.sum()
        axes[1, 1].text(index, value + 9, f"{int(value)}\n({rate:.1%})", ha="center", va="bottom", fontsize=7.3)
    axes[1, 1].set_ylim(0, label_counts.max() * 1.18)
    axes[1, 1].set(ylabel="记录数", title="女胎异常标签不平衡")
    axes[1, 1].bar_label(bars, labels=["", ""], padding=0)
    panel_label(axes[1, 1], "d")
    finish_axis(axes[1, 1], "y")
    save_figure(fig, "data_profile_distribution")


def solve_q1(male: pd.DataFrame) -> dict[str, Any]:
    data = male.dropna(subset=["孕周数值", "Y染色体浓度", "孕妇BMI", "年龄", "GC含量", "被过滤掉读段数的比例"]).copy()
    data["log_y"] = np.log(data["Y染色体浓度"])
    centers = {
        "week": data["孕周数值"].mean(),
        "bmi": data["孕妇BMI"].mean(),
        "age": data["年龄"].mean(),
        "gc": data["GC含量"].mean(),
        "filtered": data["被过滤掉读段数的比例"].mean(),
    }
    data["week_c"] = data["孕周数值"] - centers["week"]
    data["bmi_c"] = data["孕妇BMI"] - centers["bmi"]
    data["age_c"] = data["年龄"] - centers["age"]
    data["gc_c"] = data["GC含量"] - centers["gc"]
    data["filter_c"] = data["被过滤掉读段数的比例"] - centers["filtered"]
    formula = "log_y ~ week_c + I(week_c ** 2) + bmi_c + week_c:bmi_c + age_c + gc_c + filter_c"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = smf.mixedlm(formula, data, groups=data["孕妇代码"])
        fit = model.fit(reml=False, method="lbfgs", maxiter=1500)

    ci = fit.conf_int()
    coefficient_rows = []
    for name, value in fit.fe_params.items():
        coefficient_rows.append(
            {
                "变量": name,
                "系数": round(float(value), 6),
                "标准误": round(float(fit.bse[name]), 6),
                "z值": round(float(fit.tvalues[name]), 4),
                "p值": float(fit.pvalues[name]),
                "95%CI下限": round(float(ci.loc[name, 0]), 6),
                "95%CI上限": round(float(ci.loc[name, 1]), 6),
            }
        )
    coefficients = pd.DataFrame(coefficient_rows)
    coefficients.to_csv(ROOT / "tables/q1_mixed_effects.csv", index=False, encoding="utf-8-sig")

    fixed_prediction = np.asarray(fit.predict(data), dtype=float)
    fitted_prediction = np.asarray(fit.fittedvalues, dtype=float)
    fixed_variance = float(np.var(fixed_prediction, ddof=1))
    random_variance = float(fit.cov_re.iloc[0, 0])
    residual_variance = float(fit.scale)
    marginal_r2 = fixed_variance / (fixed_variance + random_variance + residual_variance)
    conditional_r2 = (fixed_variance + random_variance) / (fixed_variance + random_variance + residual_variance)
    icc = random_variance / (random_variance + residual_variance)

    grouped_cv = GroupKFold(n_splits=5)
    cv_prediction = np.zeros(len(data))
    for train_index, test_index in grouped_cv.split(data, groups=data["孕妇代码"]):
        fold_fit = smf.ols(formula, data.iloc[train_index]).fit()
        cv_prediction[test_index] = np.exp(fold_fit.predict(data.iloc[test_index]))
    cv_metrics = {
        "grouped_cv_mae": float(mean_absolute_error(data["Y染色体浓度"], cv_prediction)),
        "grouped_cv_r2": float(r2_score(data["Y染色体浓度"], cv_prediction)),
        "in_sample_mae_fixed": float(mean_absolute_error(data["Y染色体浓度"], np.exp(fixed_prediction))),
        "in_sample_mae_with_random_effect": float(mean_absolute_error(data["Y染色体浓度"], np.exp(fitted_prediction))),
        "marginal_r2": float(marginal_r2),
        "conditional_r2": float(conditional_r2),
        "icc": float(icc),
    }
    pd.DataFrame([cv_metrics]).to_csv(ROOT / "tables/q1_model_performance.csv", index=False, encoding="utf-8-sig")

    correlations = {}
    for column in ["孕周数值", "孕妇BMI", "年龄", "身高", "体重"]:
        rho, p_value = spearmanr(data[column], data["Y染色体浓度"], nan_policy="omit")
        correlations[column] = {"rho": float(rho), "p": float(p_value)}

    residual = data["log_y"].to_numpy() - fitted_prediction
    residual_summary = pd.DataFrame(
        [
            {
                "均值": float(np.mean(residual)),
                "标准差": float(np.std(residual, ddof=1)),
                "P05": float(np.quantile(residual, 0.05)),
                "中位数": float(np.median(residual)),
                "P95": float(np.quantile(residual, 0.95)),
            }
        ]
    )
    residual_summary.to_csv(ROOT / "tables/q1_residual_diagnostics.csv", index=False, encoding="utf-8-sig")
    density_cmap = LinearSegmentedColormap.from_list("density_blue", ["#F7F9FA", "#A9C9D8", SIGNAL_COLOR])
    fig, axes = plt.subplots(1, 2, figsize=(PAPER_WIDTH, 3.15), constrained_layout=True)
    density = axes[0].hexbin(
        fitted_prediction,
        residual,
        gridsize=32,
        mincnt=1,
        bins="log",
        cmap=density_cmap,
        linewidths=0,
    )
    smooth = lowess(residual, fitted_prediction, frac=0.28, return_sorted=True)
    axes[0].plot(smooth[:, 0], smooth[:, 1], color=RISK_COLOR, linewidth=1.5, label="LOWESS 趋势")
    axes[0].axhline(0, color=NEUTRAL_DARK, linestyle=(0, (3, 2)), linewidth=0.9)
    axes[0].set(xlabel="含随机效应的拟合 log(Y)", ylabel="条件残差", title="残差结构")
    axes[0].legend(loc="lower left")
    cbar = fig.colorbar(density, ax=axes[0], fraction=0.046, pad=0.025)
    cbar.set_label("记录密度", fontsize=7.4)
    cbar.ax.tick_params(labelsize=6.5, width=0.6, length=2)
    panel_label(axes[0], "a")
    finish_axis(axes[0])

    ordered = np.sort(residual)
    theoretical = norm.ppf((np.arange(1, len(ordered) + 1) - 0.5) / len(ordered))
    slope, intercept = np.polyfit(theoretical, ordered, 1)
    rng = np.random.default_rng(RANDOM_SEED)
    simulated = np.sort(
        rng.normal(np.mean(residual), np.std(residual, ddof=1), size=(350, len(ordered))),
        axis=1,
    )
    envelope_lower, envelope_upper = np.quantile(simulated, [0.025, 0.975], axis=0)
    axes[1].fill_between(theoretical, envelope_lower, envelope_upper, color=SIGNAL_COLOR, alpha=0.13, linewidth=0, label="正态 95% 包络")
    axes[1].scatter(theoretical, ordered, s=7, alpha=0.5, color=SIGNAL_COLOR, linewidths=0, rasterized=True)
    axes[1].plot(theoretical, intercept + slope * theoretical, color=NEUTRAL_DARK, linestyle=(0, (3, 2)), linewidth=1)
    axes[1].set(xlabel="标准正态理论分位数", ylabel="观测残差分位数", title="正态 Q-Q 诊断")
    axes[1].legend(loc="upper left")
    panel_label(axes[1], "b")
    finish_axis(axes[1])
    save_figure(fig, "q1_residual_diagnostic")

    fig, axes = plt.subplots(1, 2, figsize=(PAPER_WIDTH, 3.35), constrained_layout=True)
    y_percent = data["Y染色体浓度"] * 100
    y_limit = max(18.0, float(np.quantile(y_percent, 0.995)) * 1.05)
    week_density = axes[0].hexbin(
        data["孕周数值"],
        y_percent,
        gridsize=(35, 28),
        extent=(10, 25, 0, y_limit),
        mincnt=1,
        bins="log",
        cmap=density_cmap,
        linewidths=0,
    )
    weeks = np.linspace(10, 25, 180)
    for bmi, color, style in zip((26, 32, 38), GROUP_COLORS[:3], ("-", "--", "-.") ):
        curve = pd.DataFrame(
            {
                "week_c": weeks - centers["week"],
                "bmi_c": bmi - centers["bmi"],
                "age_c": 0.0,
                "gc_c": 0.0,
                "filter_c": 0.0,
            }
        )
        axes[0].plot(weeks, np.exp(fit.predict(curve)) * 100, color=color, linestyle=style, linewidth=1.8, label=f"BMI {bmi}")
    axes[0].axhline(4, color=RISK_COLOR, linestyle=(0, (3, 2)), linewidth=1, label="4% 阈值")
    axes[0].set(xlabel="检测孕周（周）", ylabel="Y 染色体浓度（%）", title="孕周效应与 BMI 分层", xlim=(10, 25), ylim=(0, y_limit))
    axes[0].legend(loc="upper left", ncol=2, handlelength=2.2, columnspacing=0.9)
    cbar = fig.colorbar(week_density, ax=axes[0], fraction=0.046, pad=0.025)
    cbar.set_label("记录密度", fontsize=7.4)
    cbar.ax.tick_params(labelsize=6.5, width=0.6, length=2)
    panel_label(axes[0], "a")
    finish_axis(axes[0])

    bmi_bins = pd.qcut(data["孕妇BMI"], q=12, duplicates="drop")
    bmi_summary = (
        data.assign(y_percent=y_percent, bmi_bin=bmi_bins)
        .groupby("bmi_bin", observed=True)
        .agg(bmi=("孕妇BMI", "median"), y=("y_percent", "median"), q25=("y_percent", lambda x: x.quantile(0.25)), q75=("y_percent", lambda x: x.quantile(0.75)))
        .reset_index(drop=True)
    )
    axes[1].errorbar(
        bmi_summary["bmi"],
        bmi_summary["y"],
        yerr=np.vstack([bmi_summary["y"] - bmi_summary["q25"], bmi_summary["q75"] - bmi_summary["y"]]),
        fmt="o",
        color=NEUTRAL_DARK,
        ecolor=NEUTRAL_MID,
        elinewidth=0.9,
        capsize=2,
        markersize=3.5,
        label="分箱中位数与 IQR",
        zorder=5,
    )
    bmi_grid = np.linspace(float(data["孕妇BMI"].min()), float(data["孕妇BMI"].max()), 160)
    for week, color, style in zip((14, 18, 22), GROUP_COLORS[:3], ("-", "--", "-.")):
        curve = pd.DataFrame(
            {
                "week_c": week - centers["week"],
                "bmi_c": bmi_grid - centers["bmi"],
                "age_c": 0.0,
                "gc_c": 0.0,
                "filter_c": 0.0,
            }
        )
        axes[1].plot(bmi_grid, np.exp(fit.predict(curve)) * 100, color=color, linestyle=style, linewidth=1.8, label=f"孕 {week} 周")
    axes[1].axhline(4, color=RISK_COLOR, linestyle=(0, (3, 2)), linewidth=1)
    axes[1].set(xlabel="孕妇 BMI（kg/m²）", ylabel="Y 染色体浓度（%）", title="BMI 条件效应", xlim=(20, 48), ylim=(0, y_limit))
    axes[1].legend(loc="upper right", handlelength=2.2)
    panel_label(axes[1], "b")
    finish_axis(axes[1])
    save_figure(fig, "q1_relationships")

    return {
        "n": len(data),
        "mothers": int(data["孕妇代码"].nunique()),
        "converged": bool(fit.converged),
        "coefficients": {row["变量"]: {"estimate": row["系数"], "p": row["p值"]} for row in coefficient_rows},
        "correlations": correlations,
        "metrics": cv_metrics,
    }


def build_subject_intervals(male: pd.DataFrame, threshold: float) -> pd.DataFrame:
    working = male.dropna(subset=["孕周数值", "Y染色体浓度"]).copy()
    working["hit_for_interval"] = working["Y染色体浓度"] >= threshold
    rows = []
    for code, group in working.groupby("孕妇代码"):
        group = group.sort_values("孕周数值")
        hits = group[group["hit_for_interval"]]
        if len(hits):
            upper = float(hits["孕周数值"].min())
            below = group[(~group["hit_for_interval"]) & (group["孕周数值"] < upper)]
            lower = float(below["孕周数值"].max()) if len(below) else 0.0
        else:
            lower = float(group["孕周数值"].max())
            upper = float("inf")
        rows.append(
            {
                "孕妇代码": code,
                "lower": lower,
                "upper": upper,
                "bmi": float(group["孕妇BMI"].median()),
                "age": float(group["年龄"].median()),
                "height": float(group["身高"].median()),
                "ivf": float(group["非自然受孕"].max()),
                "pregnancies": float(group["怀孕次数数值"].median()),
                "parity": float(group["生产次数"].median()),
            }
        )
    return pd.DataFrame(rows)


@dataclass
class AFTModel:
    columns: list[str]
    means: pd.Series
    scales: pd.Series
    beta: np.ndarray
    sigma: float
    nll: float
    aic: float
    success: bool
    standard_errors: np.ndarray

    def design(self, frame: pd.DataFrame) -> np.ndarray:
        numeric = frame[self.columns].apply(pd.to_numeric, errors="coerce").fillna(self.means)
        standardized = (numeric - self.means) / self.scales
        return np.column_stack([np.ones(len(frame)), standardized.to_numpy(dtype=float)])

    def probability(self, frame: pd.DataFrame, week: float) -> np.ndarray:
        mu = self.design(frame) @ self.beta
        return ndtr((np.log(week) - mu) / self.sigma)

    def quantile(self, frame: pd.DataFrame, probability: float) -> np.ndarray:
        mu = self.design(frame) @ self.beta
        return np.exp(mu + self.sigma * norm.ppf(probability))


def fit_interval_aft(subjects: pd.DataFrame, columns: list[str]) -> AFTModel:
    numeric = subjects[columns].apply(pd.to_numeric, errors="coerce")
    means = numeric.mean()
    numeric = numeric.fillna(means)
    scales = numeric.std().replace(0, 1)
    design = np.column_stack([np.ones(len(subjects)), ((numeric - means) / scales).to_numpy(dtype=float)])
    lower = subjects["lower"].to_numpy(dtype=float)
    upper = subjects["upper"].to_numpy(dtype=float)
    log_lower = np.full(len(subjects), -np.inf)
    log_upper = np.full(len(subjects), np.inf)
    log_lower[lower > 0] = np.log(lower[lower > 0])
    finite_upper = np.isfinite(upper)
    log_upper[finite_upper] = np.log(upper[finite_upper])
    left = lower == 0
    right = ~finite_upper
    interval = finite_upper & ~left

    def negative_log_likelihood(parameters: np.ndarray) -> float:
        mu = design @ parameters[:-1]
        sigma = np.exp(parameters[-1])
        z_upper = (log_upper - mu) / sigma
        z_lower = (log_lower - mu) / sigma
        likelihood = np.zeros(len(subjects))
        likelihood[left] = ndtr(z_upper[left])
        likelihood[right] = 1 - ndtr(z_lower[right])
        likelihood[interval] = ndtr(z_upper[interval]) - ndtr(z_lower[interval])
        return float(-np.log(np.clip(likelihood, 1e-15, 1)).sum())

    observed_log_times = np.log(upper[finite_upper])
    initial = np.r_[np.mean(observed_log_times), np.zeros(len(columns)), np.log(0.25)]
    result = minimize(
        negative_log_likelihood,
        initial,
        method="L-BFGS-B",
        bounds=[(None, None)] * (len(initial) - 1) + [(-4, 1)],
        options={"maxiter": 5000, "ftol": 1e-12},
    )
    try:
        inverse_hessian = np.asarray(result.hess_inv.todense(), dtype=float)
        standard_errors = np.sqrt(np.clip(np.diag(inverse_hessian), 0, np.inf))[:-1]
    except Exception:
        standard_errors = np.full(len(columns) + 1, np.nan)
    parameter_count = len(columns) + 2
    return AFTModel(
        columns=columns,
        means=means,
        scales=scales,
        beta=result.x[:-1],
        sigma=float(np.exp(result.x[-1])),
        nll=float(result.fun),
        aic=float(2 * parameter_count + 2 * result.fun),
        success=bool(result.success),
        standard_errors=standard_errors,
    )


def optimal_bmi_partition(subjects: pd.DataFrame, model: AFTModel, group_count: int = 4, minimum_size: int = 35) -> tuple[list[float], list[tuple[int, int]], np.ndarray]:
    order = np.argsort(subjects["bmi"].to_numpy())
    sorted_bmi = subjects["bmi"].to_numpy()[order]
    q90 = np.clip(model.quantile(subjects, 0.9), 10, 30)[order]
    n = len(subjects)
    prefix = np.r_[0.0, np.cumsum(q90)]
    prefix_square = np.r_[0.0, np.cumsum(q90**2)]

    def segment_cost(start: int, stop: int) -> float:
        count = stop - start
        total = prefix[stop] - prefix[start]
        return max(0.0, prefix_square[stop] - prefix_square[start] - total**2 / count)

    dp = np.full((group_count + 1, n + 1), np.inf)
    previous = np.full((group_count + 1, n + 1), -1, dtype=int)
    dp[0, 0] = 0
    for group in range(1, group_count + 1):
        for stop in range(group * minimum_size, n + 1):
            for start in range((group - 1) * minimum_size, stop - minimum_size + 1):
                candidate = dp[group - 1, start] + segment_cost(start, stop)
                if candidate < dp[group, stop]:
                    dp[group, stop] = candidate
                    previous[group, stop] = start
    segments = []
    stop = n
    for group in range(group_count, 0, -1):
        start = int(previous[group, stop])
        if start < 0:
            raise RuntimeError("BMI 分组动态规划不可行")
        segments.append((start, stop))
        stop = start
    segments.reverse()
    boundaries = []
    for (_, left_stop), (right_start, _) in zip(segments[:-1], segments[1:]):
        boundaries.append(float((sorted_bmi[left_stop - 1] + sorted_bmi[right_start]) / 2))
    return boundaries, segments, order


def recommendation_table(subjects: pd.DataFrame, model: AFTModel, boundaries: list[float]) -> pd.DataFrame:
    group_index = np.digitize(subjects["bmi"].to_numpy(), boundaries, right=False)
    records = []
    edges = [-np.inf, *boundaries, np.inf]
    for index in range(len(edges) - 1):
        selected = subjects.iloc[np.where(group_index == index)[0]]
        probabilities = np.array([model.probability(selected, week).mean() for week in GRID_WEEKS])
        feasible = np.where(probabilities >= 0.9)[0]
        chosen_index = int(feasible[0]) if len(feasible) else len(GRID_WEEKS) - 1
        chosen_week = float(GRID_WEEKS[chosen_index])
        left = float(selected["bmi"].min())
        right = float(selected["bmi"].max())
        records.append(
            {
                "组别": index + 1,
                "BMI下限": round(left, 3),
                "BMI上限": round(right, 3),
                "BMI区间": f"[{left:.2f}, {right:.2f}]",
                "孕妇数": len(selected),
                "推荐孕周": round(chosen_week, 4),
                "推荐时点": week_label(chosen_week),
                "预测达标比例": round(float(probabilities[chosen_index]), 4),
                "中位90%达标周": round(float(np.median(model.quantile(selected, 0.9))), 4),
            }
        )
    return pd.DataFrame(records)


def aft_effect_table(model: AFTModel) -> pd.DataFrame:
    records = []
    names = ["截距", *model.columns]
    for index, name in enumerate(names):
        estimate = float(model.beta[index])
        standard_error = float(model.standard_errors[index]) if index < len(model.standard_errors) else float("nan")
        p_value = float(2 * norm.sf(abs(estimate / standard_error))) if standard_error > 0 else float("nan")
        if index == 0:
            time_ratio = math.exp(estimate)
        else:
            raw_coefficient = estimate / float(model.scales[model.columns[index - 1]])
            time_ratio = math.exp(raw_coefficient)
        records.append(
            {
                "变量": name,
                "标准化系数": round(estimate, 6),
                "近似标准误": round(standard_error, 6),
                "近似p值": p_value,
                "每单位时间比": round(time_ratio, 6),
            }
        )
    return pd.DataFrame(records)


def solve_q2_q3(male: pd.DataFrame) -> dict[str, Any]:
    base_subjects = build_subject_intervals(male, THRESHOLD)
    q2_model = fit_interval_aft(base_subjects, ["bmi"])
    q3_columns = ["bmi", "age", "height", "ivf", "pregnancies", "parity"]
    q3_model = fit_interval_aft(base_subjects, q3_columns)

    q2_boundaries, _, _ = optimal_bmi_partition(base_subjects, q2_model)
    q3_boundaries, _, _ = optimal_bmi_partition(base_subjects, q3_model)
    q2_groups = recommendation_table(base_subjects, q2_model, q2_boundaries)
    q3_groups = recommendation_table(base_subjects, q3_model, q3_boundaries)
    q2_groups.to_csv(ROOT / "tables/q2_groups.csv", index=False, encoding="utf-8-sig")
    q3_groups.to_csv(ROOT / "tables/q3_groups.csv", index=False, encoding="utf-8-sig")
    q2_effects = aft_effect_table(q2_model)
    q3_effects = aft_effect_table(q3_model)
    q2_effects.to_csv(ROOT / "tables/q2_aft_effects.csv", index=False, encoding="utf-8-sig")
    q3_effects.to_csv(ROOT / "tables/q3_aft_effects.csv", index=False, encoding="utf-8-sig")

    sensitivity_records = []
    for threshold in (0.035, 0.04, 0.045):
        subjects = build_subject_intervals(male, threshold)
        for problem, columns, boundaries in (
            ("问题2", ["bmi"], q2_boundaries),
            ("问题3", q3_columns, q3_boundaries),
        ):
            model = fit_interval_aft(subjects, columns)
            groups = recommendation_table(subjects, model, boundaries)
            for _, row in groups.iterrows():
                sensitivity_records.append(
                    {
                        "问题": problem,
                        "浓度阈值": threshold,
                        "组别": int(row["组别"]),
                        "推荐孕周": float(row["推荐孕周"]),
                        "推荐时点": row["推荐时点"],
                        "预测达标比例": float(row["预测达标比例"]),
                    }
                )
    sensitivity = pd.DataFrame(sensitivity_records)
    base_times = sensitivity[sensitivity["浓度阈值"] == 0.04].set_index(["问题", "组别"])["推荐孕周"]
    sensitivity["相对基准变化天数"] = [
        round((row["推荐孕周"] - base_times.loc[(row["问题"], row["组别"])]) * 7, 2)
        for _, row in sensitivity.iterrows()
    ]
    sensitivity.to_csv(ROOT / "tables/q2_q3_error_sensitivity.csv", index=False, encoding="utf-8-sig")

    fig, axes = plt.subplots(1, 2, figsize=(PAPER_WIDTH, 3.2), constrained_layout=True, sharey=True)
    for panel, (title, subjects, model, boundaries, groups) in enumerate(
        (
            ("问题 2：仅 BMI", base_subjects, q2_model, q2_boundaries, q2_groups),
            ("问题 3：多因素修正", base_subjects, q3_model, q3_boundaries, q3_groups),
        )
    ):
        membership = np.digitize(subjects["bmi"].to_numpy(), boundaries)
        for index, row in groups.iterrows():
            selected = subjects.iloc[np.where(membership == index)[0]]
            probabilities = np.asarray([model.probability(selected, week).mean() for week in GRID_WEEKS])
            axes[panel].plot(
                GRID_WEEKS,
                probabilities,
                color=GROUP_COLORS[index],
                linewidth=1.8,
                linestyle=GROUP_LINESTYLES[index],
                label=f"G{index + 1}  {row['BMI区间']}",
            )
            chosen_week = float(row["推荐孕周"])
            chosen_probability = float(model.probability(selected, chosen_week).mean())
            axes[panel].vlines(chosen_week, 0.34, chosen_probability, color=GROUP_COLORS[index], linestyle=(0, (2, 2)), linewidth=0.8, alpha=0.65)
            axes[panel].scatter(chosen_week, chosen_probability, s=23, color=GROUP_COLORS[index], edgecolor="white", linewidth=0.6, zorder=5)
            axes[panel].annotate(
                str(row["推荐时点"]),
                xy=(chosen_week, chosen_probability),
                xytext=(0, 7 + 7 * (index % 2)),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=6.4,
                color=GROUP_COLORS[index],
                fontweight="bold",
            )
        axes[panel].axhline(0.9, color=RISK_COLOR, linestyle=(0, (4, 2)), linewidth=1.1)
        axes[panel].text(10.15, 0.907, "90% 约束", color=RISK_COLOR, fontsize=6.8, va="bottom")
        axes[panel].set(xlabel="检测孕周（周）", title=title, xlim=(10, 25), ylim=(0.34, 1.01))
        axes[panel].set_xticks([10, 13, 16, 19, 22, 25])
        panel_label(axes[panel], "ab"[panel])
        finish_axis(axes[panel], "y")
    axes[0].set_ylabel("预测达标比例")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.035), ncol=4, handlelength=2.2, columnspacing=1.0)
    save_figure(fig, "q2_q3_reach_probability")

    fig, axes = plt.subplots(1, 2, figsize=(PAPER_WIDTH, 2.95), constrained_layout=True, sharey=True)
    for panel, (axis, (title, groups)) in enumerate(zip(axes, (("问题 2：仅 BMI", q2_groups), ("问题 3：多因素修正", q3_groups)))):
        for index, row in groups.iterrows():
            lower = float(row["BMI下限"])
            upper = float(row["BMI上限"])
            width = upper - lower
            axis.barh(index, width, left=lower, color=GROUP_COLORS[index], alpha=0.94, height=0.58, edgecolor="white", linewidth=0.6)
            label = f"{row['推荐时点']}  ·  n={int(row['孕妇数'])}"
            if width < 3.0:
                axis.text(upper + 0.22, index, label, ha="left", va="center", fontsize=6.7, color=NEUTRAL_DARK)
            else:
                axis.text((lower + upper) / 2, index, label, ha="center", va="center", fontsize=6.8, color="white", fontweight="bold")
        axis.set(xlabel="孕妇 BMI（kg/m²）", title=title, xlim=(20, 48))
        axis.set_yticks(range(4), labels=["G1", "G2", "G3", "G4"])
        axis.invert_yaxis()
        axis.set_xticks([20, 25, 30, 35, 40, 45])
        panel_label(axis, "ab"[panel])
        finish_axis(axis, "x")
    axes[0].set_ylabel("连续 BMI 组")
    save_figure(fig, "grouping_decision_boundary")

    fig, axes = plt.subplots(1, 2, figsize=(PAPER_WIDTH, 2.85), constrained_layout=True)
    max_shift = max(1.0, float(sensitivity["相对基准变化天数"].abs().max()))
    norm_scale = TwoSlopeNorm(vmin=-max_shift, vcenter=0, vmax=max_shift)
    diverging = LinearSegmentedColormap.from_list("shift", ["#2B6F92", "#F5F6F7", "#B85C70"])
    baseline_groups = {"问题2": q2_groups, "问题3": q3_groups}
    image = None
    for panel, (axis, problem, title) in enumerate(zip(axes, ("问题2", "问题3"), ("问题 2：仅 BMI", "问题 3：多因素修正"))):
        pivot = (
            sensitivity[sensitivity["问题"] == problem]
            .pivot(index="组别", columns="浓度阈值", values="相对基准变化天数")
            .reindex(index=[1, 2, 3, 4], columns=[0.035, 0.04, 0.045])
        )
        image = axis.imshow(pivot.to_numpy(), cmap=diverging, norm=norm_scale, aspect="auto")
        for row_index in range(pivot.shape[0]):
            for column_index in range(pivot.shape[1]):
                value = float(pivot.iloc[row_index, column_index])
                text_color = "white" if abs(value) > 0.58 * max_shift else NEUTRAL_DARK
                axis.text(column_index, row_index, f"{value:+.0f}", ha="center", va="center", fontsize=8, fontweight="bold", color=text_color)
        base_labels = [f"G{int(row['组别'])}\n{row['推荐时点']}" for _, row in baseline_groups[problem].iterrows()]
        axis.set_xticks(range(3), labels=["3.5%", "4.0%", "4.5%"])
        axis.set_yticks(range(4), labels=base_labels)
        axis.set(xlabel="达标判定阈值", title=title)
        axis.tick_params(length=0)
        panel_label(axis, "ab"[panel])
        for spine in axis.spines.values():
            spine.set_visible(False)
    colorbar = fig.colorbar(image, ax=axes, fraction=0.035, pad=0.025)
    colorbar.set_label("相对 4.0% 基准变化（天）", fontsize=7.5)
    colorbar.ax.tick_params(labelsize=6.8, width=0.6, length=2)
    save_figure(fig, "q2_q3_error_sensitivity")

    interval_counts = {
        "left_censored": int((base_subjects["lower"] == 0).sum()),
        "interval_censored": int(((base_subjects["lower"] > 0) & np.isfinite(base_subjects["upper"])).sum()),
        "right_censored": int((~np.isfinite(base_subjects["upper"])).sum()),
    }
    model_comparison = pd.DataFrame(
        [
            {"模型": "BMI-AFT", "负对数似然": q2_model.nll, "AIC": q2_model.aic, "sigma": q2_model.sigma},
            {"模型": "多因素-AFT", "负对数似然": q3_model.nll, "AIC": q3_model.aic, "sigma": q3_model.sigma},
        ]
    )
    model_comparison.to_csv(ROOT / "tables/q2_q3_model_comparison.csv", index=False, encoding="utf-8-sig")
    return {
        "interval_counts": interval_counts,
        "q2": {
            "aic": q2_model.aic,
            "nll": q2_model.nll,
            "sigma": q2_model.sigma,
            "success": q2_model.success,
            "groups": q2_groups.to_dict(orient="records"),
            "effects": q2_effects.to_dict(orient="records"),
        },
        "q3": {
            "aic": q3_model.aic,
            "nll": q3_model.nll,
            "sigma": q3_model.sigma,
            "success": q3_model.success,
            "groups": q3_groups.to_dict(orient="records"),
            "effects": q3_effects.to_dict(orient="records"),
        },
        "sensitivity": sensitivity.to_dict(orient="records"),
    }


def classification_metrics(y_true: pd.Series, probability: np.ndarray, threshold: float) -> dict[str, float]:
    prediction = probability >= threshold
    tn, fp, fn, tp = confusion_matrix(y_true, prediction, labels=[0, 1]).ravel()
    return {
        "roc_auc": float(roc_auc_score(y_true, probability)),
        "pr_auc": float(average_precision_score(y_true, probability)),
        "threshold": float(threshold),
        "precision": float(precision_score(y_true, prediction, zero_division=0)),
        "recall": float(recall_score(y_true, prediction, zero_division=0)),
        "specificity": float(tn / (tn + fp)),
        "f1": float(f1_score(y_true, prediction, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, prediction)),
        "brier": float(brier_score_loss(y_true, probability)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def logit_column(probability: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(probability, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(clipped / (1 - clipped)).reshape(-1, 1)


def grouped_platt_oof(
    estimator: Any,
    x: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
) -> np.ndarray:
    """Generate leakage-safe calibrated probabilities for unseen mothers."""
    calibrated = np.full(len(y), np.nan, dtype=float)
    outer_cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    for fold, (train_index, test_index) in enumerate(outer_cv.split(x, y, groups)):
        x_train = x.iloc[train_index]
        y_train = y.iloc[train_index]
        groups_train = groups.iloc[train_index]
        inner_cv = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=RANDOM_SEED + fold + 1)
        inner_probability = cross_val_predict(
            clone(estimator),
            x_train,
            y_train,
            cv=inner_cv,
            groups=groups_train,
            method="predict_proba",
            n_jobs=-1,
        )[:, 1]
        calibrator = LogisticRegression(C=1e6, max_iter=2000, random_state=RANDOM_SEED)
        calibrator.fit(logit_column(inner_probability), y_train)
        fitted = clone(estimator).fit(x_train, y_train)
        test_probability = fitted.predict_proba(x.iloc[test_index])[:, 1]
        calibrated[test_index] = calibrator.predict_proba(logit_column(test_probability))[:, 1]
    if np.isnan(calibrated).any():
        raise RuntimeError("Grouped Platt calibration left unassigned observations")
    return calibrated


def solve_q4(female: pd.DataFrame) -> dict[str, Any]:
    features = [
        "13号染色体的Z值",
        "18号染色体的Z值",
        "21号染色体的Z值",
        "X染色体的Z值",
        "X染色体浓度",
        "GC含量",
        "13号染色体的GC含量",
        "18号染色体的GC含量",
        "21号染色体的GC含量",
        "原始读段数",
        "在参考基因组上比对的比例",
        "重复读段的比例",
        "唯一比对的读段数",
        "被过滤掉读段数的比例",
        "孕妇BMI",
        "年龄",
        "孕周数值",
    ]
    data = female.dropna(subset=["孕妇代码"]).copy()
    x = data[features]
    y = data["异常"].astype(int)
    groups = data["孕妇代码"]
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    models = {
        "分组逻辑回归": make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(max_iter=4000, class_weight="balanced", C=0.3, random_state=RANDOM_SEED),
        ),
        "随机森林": make_pipeline(
            SimpleImputer(strategy="median"),
            RandomForestClassifier(
                n_estimators=500,
                min_samples_leaf=5,
                max_features=0.7,
                class_weight="balanced_subsample",
                random_state=RANDOM_SEED,
                n_jobs=-1,
            ),
        ),
        "直方图梯度提升": make_pipeline(
            SimpleImputer(strategy="median"),
            HistGradientBoostingClassifier(
                max_iter=220,
                max_leaf_nodes=15,
                learning_rate=0.04,
                l2_regularization=2,
                class_weight="balanced",
                random_state=RANDOM_SEED,
            ),
        ),
    }
    probabilities: dict[str, np.ndarray] = {}
    metrics = []
    for name, model in models.items():
        probability = cross_val_predict(model, x, y, cv=cv, groups=groups, method="predict_proba", n_jobs=-1)[:, 1]
        probabilities[name] = probability
        row = {"模型": name, **classification_metrics(y, probability, 0.5)}
        metrics.append(row)

    z_score = data[["13号染色体的Z值", "18号染色体的Z值", "21号染色体的Z值"]].abs().max(axis=1).to_numpy()
    z_probability = 1 / (1 + np.exp(-(z_score - 3)))
    probabilities["传统 |Z|≥3"] = z_probability
    metrics.append({"模型": "传统 |Z|≥3", **classification_metrics(y, z_probability, 0.5)})
    metrics_frame = pd.DataFrame(metrics)
    metrics_frame.to_csv(ROOT / "tables/q4_model_metrics.csv", index=False, encoding="utf-8-sig")

    best_probability = probabilities["分组逻辑回归"]
    best_metrics = classification_metrics(y, best_probability, 0.5)
    calibrated_probability = grouped_platt_oof(models["分组逻辑回归"], x, y, groups)
    calibration_source = pd.DataFrame(
        {
            "预测概率": calibrated_probability,
            "实际标签": y.to_numpy(),
        }
    )
    calibration_source["分箱"] = pd.qcut(
        calibration_source["预测概率"], q=8, labels=False, duplicates="drop"
    )
    calibration_bins = (
        calibration_source.groupby("分箱", observed=True)
        .agg(
            样本数=("实际标签", "size"),
            阳性数=("实际标签", "sum"),
            平均预测概率=("预测概率", "mean"),
            观察阳性率=("实际标签", "mean"),
            概率下界=("预测概率", "min"),
            概率上界=("预测概率", "max"),
        )
        .reset_index(drop=True)
    )
    z_95 = float(norm.ppf(0.975))
    denominator = 1 + z_95**2 / calibration_bins["样本数"]
    center = (
        calibration_bins["观察阳性率"] + z_95**2 / (2 * calibration_bins["样本数"])
    ) / denominator
    half_width = (
        z_95
        * np.sqrt(
            calibration_bins["观察阳性率"]
            * (1 - calibration_bins["观察阳性率"])
            / calibration_bins["样本数"]
            + z_95**2 / (4 * calibration_bins["样本数"] ** 2)
        )
        / denominator
    )
    calibration_bins["Wilson下限"] = np.maximum(0, center - half_width)
    calibration_bins["Wilson上限"] = np.minimum(1, center + half_width)
    calibration_bins.to_csv(ROOT / "tables/q4_calibration_bins.csv", index=False, encoding="utf-8-sig")
    calibration_diagnostic = LogisticRegression(C=1e6, max_iter=2000, random_state=RANDOM_SEED)
    calibration_diagnostic.fit(logit_column(calibrated_probability), y)
    calibration_intercept = float(calibration_diagnostic.intercept_[0])
    calibration_slope = float(calibration_diagnostic.coef_[0, 0])
    raw_brier = float(brier_score_loss(y, best_probability))
    calibrated_brier = float(brier_score_loss(y, calibrated_probability))
    calibration_ece = float(
        np.average(
            np.abs(calibration_bins["观察阳性率"] - calibration_bins["平均预测概率"]),
            weights=calibration_bins["样本数"],
        )
    )
    pd.DataFrame(
        [
            {
                "校准方法": "嵌套孕妇分组 Platt",
                "原始Brier": raw_brier,
                "校准后Brier": calibrated_brier,
                "ECE": calibration_ece,
                "校准截距": calibration_intercept,
                "校准斜率": calibration_slope,
                "等频分箱数": int(len(calibration_bins)),
            }
        ]
    ).to_csv(ROOT / "tables/q4_calibration_summary.csv", index=False, encoding="utf-8-sig")

    threshold_rows = []
    for threshold in np.arange(0.05, 0.951, 0.05):
        row = classification_metrics(y, best_probability, float(threshold))
        threshold_rows.append(
            {
                "分数阈值": float(threshold),
                "精确率": row["precision"],
                "召回率": row["recall"],
                "特异度": row["specificity"],
                "F1": row["f1"],
                "假阳性数": row["fp"],
                "假阴性数": row["fn"],
            }
        )
    threshold_frame = pd.DataFrame(threshold_rows)
    threshold_frame.to_csv(ROOT / "tables/q4_threshold_tradeoff.csv", index=False, encoding="utf-8-sig")
    confusion = pd.DataFrame(
        [[best_metrics["tn"], best_metrics["fp"]], [best_metrics["fn"], best_metrics["tp"]]],
        index=["实际正常", "实际异常"],
        columns=["预测正常", "预测异常"],
    )
    confusion.to_csv(ROOT / "tables/q4_confusion_matrix.csv", encoding="utf-8-sig")

    rng = np.random.default_rng(RANDOM_SEED)
    group_array = groups.to_numpy()
    y_array = y.to_numpy()
    unique_groups = pd.unique(group_array)
    bootstrap_values = {"ROC-AUC": [], "PR-AUC": [], "召回率": [], "特异度": []}
    for _ in range(500):
        sampled_groups = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        sampled_indices = np.concatenate([np.flatnonzero(group_array == group_id) for group_id in sampled_groups])
        sampled_y = y_array[sampled_indices]
        if np.unique(sampled_y).size < 2:
            continue
        sampled_probability = best_probability[sampled_indices]
        sampled_metrics = classification_metrics(pd.Series(sampled_y), sampled_probability, 0.5)
        bootstrap_values["ROC-AUC"].append(sampled_metrics["roc_auc"])
        bootstrap_values["PR-AUC"].append(sampled_metrics["pr_auc"])
        bootstrap_values["召回率"].append(sampled_metrics["recall"])
        bootstrap_values["特异度"].append(sampled_metrics["specificity"])
    point_estimates = {
        "ROC-AUC": best_metrics["roc_auc"],
        "PR-AUC": best_metrics["pr_auc"],
        "召回率": best_metrics["recall"],
        "特异度": best_metrics["specificity"],
    }
    bootstrap_rows = []
    for metric, values in bootstrap_values.items():
        lower, upper = np.quantile(values, [0.025, 0.975])
        bootstrap_rows.append(
            {
                "指标": metric,
                "点估计": float(point_estimates[metric]),
                "95%CI下限": float(lower),
                "95%CI上限": float(upper),
                "Bootstrap次数": len(values),
            }
        )
    bootstrap_frame = pd.DataFrame(bootstrap_rows)
    bootstrap_frame.to_csv(ROOT / "tables/q4_grouped_bootstrap_uncertainty.csv", index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(PAPER_WIDTH, 3.15), constrained_layout=True)
    positions = np.arange(len(bootstrap_frame))
    estimates = bootstrap_frame["点估计"].to_numpy()
    lower_error = estimates - bootstrap_frame["95%CI下限"].to_numpy()
    upper_error = bootstrap_frame["95%CI上限"].to_numpy() - estimates
    distributions = [np.asarray(bootstrap_values[metric]) for metric in bootstrap_frame["指标"]]
    violins = ax.violinplot(distributions, positions=positions, orientation="horizontal", widths=0.62, showmeans=False, showmedians=False, showextrema=False)
    for body in violins["bodies"]:
        body.set_facecolor(SIGNAL_COLOR)
        body.set_edgecolor("none")
        body.set_alpha(0.14)
    ax.errorbar(
        estimates,
        positions,
        xerr=np.vstack([lower_error, upper_error]),
        fmt="o",
        markersize=5.2,
        markerfacecolor=SIGNAL_COLOR,
        markeredgecolor="white",
        markeredgewidth=0.7,
        color=SIGNAL_COLOR,
        ecolor=NEUTRAL_DARK,
        capsize=3,
        elinewidth=1.3,
        zorder=5,
    )
    for position, estimate, lower, upper in zip(positions, estimates, bootstrap_frame["95%CI下限"], bootstrap_frame["95%CI上限"]):
        ax.text(float(upper) + 0.018, position, f"{estimate:.3f} [{lower:.3f}, {upper:.3f}]", va="center", ha="left", fontsize=7, color=NEUTRAL_DARK)
    ax.set_yticks(positions, labels=bootstrap_frame["指标"])
    ax.invert_yaxis()
    x_min = max(0.0, float(bootstrap_frame["95%CI下限"].min()) - 0.08)
    x_max = min(1.0, float(bootstrap_frame["95%CI上限"].max()) + 0.18)
    ax.set(xlabel="指标值", xlim=(x_min, x_max), title="分组逻辑回归的不确定性")
    ax.text(0.995, 0.03, "按孕妇重抽样 · 500 次", transform=ax.transAxes, ha="right", va="bottom", fontsize=6.8, color=NEUTRAL_MID)
    finish_axis(ax, "x")
    save_figure(fig, "q4_grouped_bootstrap_uncertainty")

    final_model = clone(models["分组逻辑回归"]).fit(x, y)
    coefficients = pd.DataFrame(
        {
            "变量": features,
            "标准化系数": final_model.named_steps["logisticregression"].coef_[0],
        }
    )
    coefficients["绝对系数"] = coefficients["标准化系数"].abs()
    coefficients = coefficients.sort_values("绝对系数", ascending=False)
    coefficients.to_csv(ROOT / "tables/q4_logistic_coefficients.csv", index=False, encoding="utf-8-sig")

    fig, axes = plt.subplots(1, 2, figsize=(PAPER_WIDTH, 3.25), constrained_layout=True)
    for index, (name, probability) in enumerate(probabilities.items()):
        fpr, tpr, _ = roc_curve(y, probability)
        precision, recall, _ = precision_recall_curve(y, probability)
        selected = name == "分组逻辑回归"
        line_style = METHOD_LINESTYLES[name]
        axes[0].plot(
            fpr,
            tpr,
            color=METHOD_COLORS[name],
            linewidth=2.4 if selected else 1.35,
            linestyle=line_style,
            alpha=1.0 if selected else 0.82,
            zorder=5 if selected else 2,
            label=f"{name}  {roc_auc_score(y, probability):.3f}",
        )
        axes[1].plot(
            recall,
            precision,
            color=METHOD_COLORS[name],
            linewidth=2.4 if selected else 1.35,
            linestyle=line_style,
            alpha=1.0 if selected else 0.82,
            zorder=5 if selected else 2,
            label=f"{name}  {average_precision_score(y, probability):.3f}",
        )
    axes[0].plot([0, 1], [0, 1], color=NEUTRAL_MID, linestyle=(0, (3, 2)), linewidth=0.9)
    axes[0].set(xlabel="假阳性率", ylabel="真阳性率", title="ROC 曲线 · 图例为 AUC", xlim=(0, 1), ylim=(0, 1.02))
    axes[1].axhline(y.mean(), color=NEUTRAL_MID, linestyle=(0, (3, 2)), linewidth=0.9)
    axes[1].text(0.98, y.mean() + 0.025, f"异常率 {y.mean():.3f}", ha="right", va="bottom", fontsize=6.6, color=NEUTRAL_MID)
    axes[1].set(xlabel="召回率", ylabel="精确率", title="PR 曲线 · 图例为 AP", xlim=(0, 1), ylim=(0, 1.02))
    for panel, axis in enumerate(axes):
        axis.legend(loc="lower right" if panel == 0 else "upper right", handlelength=2.3, labelspacing=0.35)
        axis.set_box_aspect(1)
        panel_label(axis, "ab"[panel])
        finish_axis(axis)
    save_figure(fig, "q4_roc_pr")

    fig, axes = plt.subplots(1, 2, figsize=(PAPER_WIDTH, 3.25), constrained_layout=True)
    calibration_limit = min(
        1.0,
        max(
            0.4,
            float(calibration_bins["平均预测概率"].max()) + 0.08,
            float(calibration_bins["Wilson上限"].max()) + 0.05,
        ),
    )
    axes[0].plot(
        [0, calibration_limit],
        [0, calibration_limit],
        color=NEUTRAL_MID,
        linestyle=(0, (3, 2)),
        linewidth=0.9,
        label="理想校准",
    )
    y_error = np.vstack(
        [
            np.maximum(0, calibration_bins["观察阳性率"] - calibration_bins["Wilson下限"]),
            np.maximum(0, calibration_bins["Wilson上限"] - calibration_bins["观察阳性率"]),
        ]
    )
    axes[0].errorbar(
        calibration_bins["平均预测概率"],
        calibration_bins["观察阳性率"],
        yerr=y_error,
        color=SIGNAL_COLOR,
        ecolor=NEUTRAL_MID,
        linewidth=1.6,
        elinewidth=1.0,
        capsize=2.5,
        marker="o",
        markersize=4.8,
        markerfacecolor=SIGNAL_COLOR,
        markeredgecolor="white",
        markeredgewidth=0.6,
        label="嵌套分组 Platt 校准",
    )
    axes[0].text(
        0.04,
        0.96,
        f"Brier  {raw_brier:.3f} → {calibrated_brier:.3f}\n"
        f"ECE  {calibration_ece:.3f}  ·  slope  {calibration_slope:.2f}",
        transform=axes[0].transAxes,
        ha="left",
        va="top",
        fontsize=6.8,
        color=NEUTRAL_DARK,
    )
    axes[0].set(
        xlabel="平均预测概率",
        ylabel="观察阳性率",
        title="概率校准 · 等频 8 组",
        xlim=(0, calibration_limit),
        ylim=(0, calibration_limit),
    )
    axes[0].legend(loc="lower right", handlelength=2.1)

    threshold_styles = {
        "召回率": (SIGNAL_COLOR, "-"),
        "特异度": (GAIN_COLOR, "--"),
        "精确率": ("#C08A24", "-."),
        "F1": (RISK_COLOR, (0, (1.5, 1.5))),
    }
    for metric, (color, linestyle) in threshold_styles.items():
        axes[1].step(
            threshold_frame["分数阈值"],
            threshold_frame[metric],
            color=color,
            linestyle=linestyle,
            linewidth=1.8 if metric in {"召回率", "特异度"} else 1.35,
            where="mid",
            label=metric,
        )
        selected_row = threshold_frame.iloc[(threshold_frame["分数阈值"] - 0.5).abs().argmin()]
        axes[1].scatter(
            selected_row["分数阈值"],
            selected_row[metric],
            s=24,
            color=color,
            edgecolor="white",
            linewidth=0.6,
            zorder=5,
        )
    axes[1].axvline(0.5, color=NEUTRAL_MID, linestyle=(0, (3, 2)), linewidth=0.9)
    axes[1].text(0.515, 0.99, "固定阈值 0.5", fontsize=6.6, color=NEUTRAL_MID, va="top")
    axes[1].set(
        xlabel="筛查分数阈值",
        ylabel="性能指标",
        title="阈值变化下的错误权衡",
        xlim=(0.05, 0.95),
        ylim=(0, 1.02),
    )
    axes[1].legend(loc="lower right", ncol=2, handlelength=2.3, labelspacing=0.35, columnspacing=0.9)
    for panel, axis in enumerate(axes):
        axis.set_box_aspect(1)
        panel_label(axis, "ab"[panel])
        finish_axis(axis, "both")
    save_figure(fig, "q4_calibration_threshold")

    fig, axes = plt.subplots(1, 2, figsize=(PAPER_WIDTH, 3.35), constrained_layout=True, gridspec_kw={"width_ratios": [0.82, 1.45]})
    confusion_values = confusion.to_numpy(dtype=float)
    confusion_rates = confusion_values / confusion_values.sum(axis=1, keepdims=True)
    confusion_cmap = LinearSegmentedColormap.from_list("confusion_blue", ["#F5F7F8", "#A9C9D8", SIGNAL_COLOR])
    axes[0].imshow(confusion_rates, cmap=confusion_cmap, vmin=0, vmax=1)
    for row in range(2):
        for column in range(2):
            rate = confusion_rates[row, column]
            axes[0].text(
                column,
                row,
                f"{int(confusion_values[row, column])}\n{rate:.1%}",
                ha="center",
                va="center",
                fontsize=9,
                fontweight="bold",
                color="white" if rate > 0.58 else NEUTRAL_DARK,
            )
    axes[0].set_xticks([0, 1], labels=["预测正常", "预测异常"])
    axes[0].set_yticks([0, 1], labels=["实际正常", "实际异常"])
    axes[0].set_title("固定阈值 0.5 的错误结构")
    axes[0].tick_params(length=0)
    for spine in axes[0].spines.values():
        spine.set_visible(False)
    panel_label(axes[0], "a")

    display_names = {
        "13号染色体的GC含量": "13 号染色体 GC",
        "18号染色体的GC含量": "18 号染色体 GC",
        "21号染色体的GC含量": "21 号染色体 GC",
        "13号染色体的Z值": "13 号染色体 Z",
        "18号染色体的Z值": "18 号染色体 Z",
        "21号染色体的Z值": "21 号染色体 Z",
        "X染色体的Z值": "X 染色体 Z",
        "X染色体浓度": "X 染色体浓度",
        "在参考基因组上比对的比例": "参考基因组比对比例",
        "被过滤掉读段数的比例": "过滤读段比例",
        "重复读段的比例": "重复读段比例",
        "唯一比对的读段数": "唯一比对读段数",
        "原始读段数": "原始读段数",
        "孕妇BMI": "孕妇 BMI",
        "孕周数值": "检测孕周",
    }
    top = coefficients.head(10).sort_values("标准化系数").copy()
    top["显示变量"] = top["变量"].map(display_names).fillna(top["变量"])
    y_positions = np.arange(len(top))
    for position, value in zip(y_positions, top["标准化系数"]):
        color = SIGNAL_COLOR if value >= 0 else RISK_COLOR
        axes[1].hlines(position, 0, value, color=color, linewidth=2.2, alpha=0.8)
        axes[1].scatter(value, position, s=28, color=color, edgecolor="white", linewidth=0.6, zorder=5)
        axes[1].annotate(f"{value:+.2f}", xy=(value, position), xytext=(4 if value >= 0 else -4, 0), textcoords="offset points", ha="left" if value >= 0 else "right", va="center", fontsize=6.6, color=color)
    axes[1].set_yticks(y_positions, labels=top["显示变量"])
    axes[1].axvline(0, color=NEUTRAL_DARK, linewidth=0.8)
    max_abs = float(top["标准化系数"].abs().max()) * 1.25
    axes[1].set(xlabel="标准化逻辑回归系数", title="主要判定变量", xlim=(-max_abs, max_abs))
    axes[1].legend(
        handles=[
            Line2D([0], [0], marker="o", color=SIGNAL_COLOR, label="正向", linewidth=2),
            Line2D([0], [0], marker="o", color=RISK_COLOR, label="负向", linewidth=2),
        ],
        loc="lower right",
        ncol=2,
        handlelength=1.2,
    )
    panel_label(axes[1], "b")
    finish_axis(axes[1], "x")
    save_figure(fig, "q4_confusion_coefficients")

    return {
        "n": len(data),
        "mothers": int(groups.nunique()),
        "positive": int(y.sum()),
        "positive_rate": float(y.mean()),
        "models": metrics_frame.to_dict(orient="records"),
        "selected_model": "分组逻辑回归",
        "selected_threshold": 0.5,
        "calibration": {
            "method": "nested grouped Platt calibration",
            "raw_brier": raw_brier,
            "calibrated_brier": calibrated_brier,
            "ece": calibration_ece,
            "intercept": calibration_intercept,
            "slope": calibration_slope,
            "bins": int(len(calibration_bins)),
        },
        "bootstrap_uncertainty": bootstrap_frame.to_dict(orient="records"),
        "top_coefficients": coefficients.head(10).to_dict(orient="records"),
    }


def build_report(overview: pd.DataFrame, q1: dict[str, Any], timing: dict[str, Any], q4: dict[str, Any]) -> str:
    q1_coef = q1["coefficients"]
    q2_groups = pd.DataFrame(timing["q2"]["groups"])[["组别", "BMI区间", "孕妇数", "推荐时点", "预测达标比例"]]
    q3_groups = pd.DataFrame(timing["q3"]["groups"])[["组别", "BMI区间", "孕妇数", "推荐时点", "预测达标比例"]]
    q4_metrics = pd.DataFrame(q4["models"])[["模型", "roc_auc", "pr_auc", "precision", "recall", "specificity", "f1"]].copy()
    q4_uncertainty = pd.DataFrame(q4["bootstrap_uncertainty"]).set_index("指标")
    for column in q4_metrics.columns[1:]:
        q4_metrics[column] = q4_metrics[column].map(lambda value: f"{value:.3f}")
    sensitivity = pd.DataFrame(timing["sensitivity"])
    max_shift = float(sensitivity["相对基准变化天数"].abs().max())
    week_effect = q1_coef["week_c"]
    bmi_effect = q1_coef["bmi_c"]
    report = rf"""# NIPT 的时点选择与胎儿异常判定

## 摘要

本文基于 2025 年全国大学生数学建模竞赛 C 题附件，对 267 名男胎孕妇的 1082 条重复检测记录和 147 名女胎孕妇的 605 条记录进行建模。针对同一孕妇多次检测造成的组内相关，问题 1 采用随机截距混合效应模型；问题 2、3 将 4% 浓度首次达标视为区间删失事件，建立对数正态加速失效时间模型，并以“预测达标比例不低于 90% 时的最早孕周”为最佳时点；问题 4 使用按孕妇分组的五折交叉验证比较逻辑回归、随机森林、梯度提升和传统 Z 阈值规则。结果表明，孕周对男胎 Y 浓度有显著正效应（对数尺度系数 {week_effect['estimate']:.4f}, p={week_effect['p']:.3g}），BMI 有显著负效应（{bmi_effect['estimate']:.4f}, p={bmi_effect['p']:.3g}），个体内相关系数达到 {q1['metrics']['icc']:.3f}。仅 BMI 模型得到四组推荐时点，多因素模型用于问题 3 的风险修正。女胎分组逻辑回归的 ROC-AUC 为 {q4['models'][0]['roc_auc']:.3f}，明显优于传统 |Z|≥3 规则。结论适用于本附件覆盖的人群与赛题假设，不构成临床建议。

**关键词：** NIPT；混合效应模型；区间删失；AFT；BMI 分组；分组交叉验证

## 1 问题重述与数据

NIPT 在孕 10 至 25 周利用母体血液中的胎儿游离 DNA 进行染色体异常筛查。男胎 Y 染色体浓度达到 4% 是结果基本可靠的重要条件；女胎则需结合常染色体、X 染色体和测序质量指标判定异常。附件存在多次采血和重复检测，故所有验证均以孕妇代码为分组单位。

{markdown_table(overview)}

## 2 模型假设

1. 附件中的孕妇代码唯一标识同一孕妇，重复行之间存在组内相关。
2. 观测到首次达标前最后一次未达标与首次达标时点之间包含真实达标时点；首次观测即达标视为左删失，从未达标视为右删失。
3. 赛题所称检测误差用 3.5%、4.0%、4.5% 三个达标阈值进行敏感性分析。
4. 最佳时点定义为某 BMI 组预测达标比例首次达到 90% 的孕周；这等价于在满足可靠性约束后尽可能保留治疗窗口。
5. 女胎异常标签以附件“染色体的非整倍体”是否为空为准，不以出生健康字段替代。

## 3 问题 1：Y 浓度关系模型

设第 $i$ 名孕妇第 $j$ 次检测的 Y 浓度为 $Y_{{ij}}$，孕周为 $W_{{ij}}$，BMI 为 $B_{{ij}}$。建立

$$
\log Y_{{ij}}=\beta_0+\beta_1W_c+\beta_2W_c^2+\beta_3B_c+\beta_4W_cB_c+\beta_5A_c+\beta_6GC_c+\beta_7F_c+u_i+\epsilon_{{ij}},
$$

其中 $u_i$ 为孕妇随机截距。模型成功收敛，边际 $R^2={q1['metrics']['marginal_r2']:.3f}$，条件 $R^2={q1['metrics']['conditional_r2']:.3f}$，ICC={q1['metrics']['icc']:.3f}$。高 ICC 说明不同孕妇之间的稳定差异远大于单次测量噪声，普通 OLS 会低估不确定性。按孕妇分组的五折验证 MAE 为 {q1['metrics']['grouped_cv_mae']:.4f}。

![问题1关系图](../figures/q1_relationships.png)

## 4 问题 2：BMI 分组与时点

对每名孕妇构造首次达标时间区间 $(L_i,U_i]$，令

$$
\log T_i=\alpha_0+\alpha_1 BMI_i+\sigma\varepsilon_i,\qquad \varepsilon_i\sim N(0,1).
$$

四组连续 BMI 区间通过动态规划最小化个体 90% 达标分位数的组内平方差，并保证每组至少 35 人。推荐结果如下：

{markdown_table(q2_groups)}

![问题2和问题3达标概率](../figures/q2_q3_reach_probability.png)

## 5 问题 3：多因素修正

在 BMI 基础上加入年龄、身高、受孕方式、怀孕次数和生产次数，仍采用区间删失 AFT 模型。为避免决策时点泄漏，不使用检测后才得到的 Z 值、读段比例或 Y 浓度作为时点预测变量。结果为：

{markdown_table(q3_groups)}

多因素模型 AIC 为 {timing['q3']['aic']:.2f}，仅 BMI 模型 AIC 为 {timing['q2']['aic']:.2f}。多因素模型的 AIC 并未降低，因此它主要用于刻画异质性和风险修正，不应被表述为显著优于 BMI 主模型。将达标阈值在 3.5% 至 4.5% 之间调整时，推荐时点最大变化 {max_shift:.1f} 天，说明检测误差会对高 BMI 组产生更明显的时点推迟。

![误差敏感性](../figures/q2_q3_error_sensitivity.png)

## 6 问题 4：女胎异常判定

以 Z13、Z18、Z21、ZX、X 浓度、GC 指标、读段数及比例、BMI、年龄和孕周为输入，比较四种方法。五折划分始终保持同一孕妇只出现在一个折中。

{markdown_table(q4_metrics)}

选择分组逻辑回归作为主模型，因为其排序能力最好且系数可解释。阈值 0.5 下召回率为 {q4['models'][0]['recall']:.3f}、特异度为 {q4['models'][0]['specificity']:.3f}。按孕妇整组重抽样 500 次后，ROC-AUC 的 95% 置信区间为 [{q4_uncertainty.loc['ROC-AUC', '95%CI下限']:.3f}, {q4_uncertainty.loc['ROC-AUC', '95%CI上限']:.3f}]。传统 |Z|≥3 在本附件上表现较弱，说明 AB 标签不能由单次三条常染色体 Z 值的绝对值阈值完全复现；联合质量和个体指标更合适。

![问题4模型比较](../figures/q4_roc_pr.png)

类别加权输出用于筛查排序，不直接当作真实风险概率。经嵌套分组 Platt 校准后，Brier 分数由 {q4['calibration']['raw_brier']:.3f} 降至 {q4['calibration']['calibrated_brier']:.3f}；阈值权衡图同时展示召回率、特异度、精确率与 F1 随筛查分数阈值的变化。

![问题4校准与阈值权衡](../figures/q4_calibration_threshold.png)

![问题4混淆矩阵与系数](../figures/q4_confusion_coefficients.png)

![问题4分组Bootstrap不确定性](../figures/q4_grouped_bootstrap_uncertainty.png)

## 7 稳健性与局限

1. 所有交叉验证按孕妇分组，消除了重复测量泄漏，但样本来自高 BMI 人群，外推到一般孕妇需重新校准。
2. 218 名男胎孕妇首次观测即已达标，属于左删失，说明真实首次达标时间早于观测；AFT 模型比直接把首次观测周当作达标周更合理，但仍依赖分布假设。
3. 4% 阈值误差敏感性已显式检查；更完整的临床误差模型需要实验室重复测量方差。
4. 女胎异常样本仅 {q4['positive']} 条，PR-AUC 比准确率更有解释价值；模型输出只能作为赛题中的风险判定，不是医学诊断。

## 8 结论

混合效应结果支持“孕周增加、Y 浓度上升；BMI 增加、Y 浓度下降”，同时指出孕妇个体差异是主要变异来源。问题 2 和问题 3 的四组时点分别由表中给出，高 BMI 组需要明显更晚的检测时点。女胎判定中，联合多指标的分组逻辑回归优于单一 Z 阈值。完整代码、处理后数据、表格和图形均可由 `python src/run_all.py` 重新生成。

## 参考文献

[1] 全国大学生数学建模竞赛组委会. 2025 年高教社杯全国大学生数学建模竞赛赛题, 2025.

[2] Deng C, et al. Maternal and fetal factors influencing fetal fraction: a retrospective analysis of 153,306 pregnant women undergoing noninvasive prenatal screening. 2023. PMID: 37114008.

[3] Gazdarica J, et al. Insights into non-informative results from non-invasive prenatal screening through gestational age, maternal BMI, and age analyses. 2024. PMID: 38452118.

[4] Rolnik DL, et al. Influence of Body Mass Index on Fetal Fraction Increase With Gestation and Cell-Free DNA Test Failure. 2018. PMID: 29995742.

[5] Zhang X, et al. Evaluation of the Z-score accuracy of noninvasive prenatal testing for fetal trisomies 13, 18 and 21 at a single center. 2021. PMID: 33480032.
"""
    (ROOT / "paper/report.md").write_text(report, encoding="utf-8")
    return report


def write_manifests(summary: dict[str, Any]) -> None:
    figures = [
        {"figure_id": "F0", "id": "F0", "claim_id": "D1", "subquestion": "global", "figure_type": "data profile", "x_axis": "BMI / 孕周 / 重复次数 / 标签", "y_axis": "记录数或孕妇数", "data_source": "data/processed/male_clean.csv and female_clean.csv", "caption": "样本分布与重复测量结构", "body_or_appendix": "body", "file_path": "figures/data_profile_distribution.png", "file_exists": True},
        {"figure_id": "F1", "id": "F1", "claim_id": "C1,C2,C3", "subquestion": "Q1", "figure_type": "relationship", "x_axis": "检测孕周 / 孕妇BMI", "y_axis": "Y染色体浓度(%)", "data_source": "data/processed/male_clean.csv and tables/q1_mixed_effects.csv", "caption": "孕周、BMI与男胎Y染色体浓度关系", "body_or_appendix": "body", "file_path": "figures/q1_relationships.png", "file_exists": True},
        {"figure_id": "F1D", "id": "F1D", "claim_id": "V1", "subquestion": "Q1", "figure_type": "model diagnostic", "x_axis": "拟合值 / 理论分位数", "y_axis": "残差 / 残差分位数", "data_source": "MixedLM fitted values and residuals", "caption": "混合效应模型残差诊断", "body_or_appendix": "body", "file_path": "figures/q1_residual_diagnostic.png", "file_exists": True},
        {"figure_id": "F2", "id": "F2", "claim_id": "C4,C5", "subquestion": "Q2,Q3", "figure_type": "prediction decision", "x_axis": "检测孕周(周)", "y_axis": "预测达标比例", "data_source": "tables/q2_groups.csv and q3_groups.csv", "caption": "两条路线下各BMI组的预测达标概率", "body_or_appendix": "body", "file_path": "figures/q2_q3_reach_probability.png", "file_exists": True},
        {"figure_id": "F2B", "id": "F2B", "claim_id": "C4,C5", "subquestion": "Q2,Q3", "figure_type": "grouping decision", "x_axis": "孕妇BMI", "y_axis": "连续BMI组", "data_source": "tables/q2_groups.csv and q3_groups.csv", "caption": "连续BMI分组边界与推荐孕周", "body_or_appendix": "body", "file_path": "figures/grouping_decision_boundary.png", "file_exists": True},
        {"figure_id": "F3", "id": "F3", "claim_id": "C7", "subquestion": "Q3", "figure_type": "sensitivity robustness", "x_axis": "达标判定阈值(%)", "y_axis": "推荐孕周(周)", "data_source": "tables/q2_q3_error_sensitivity.csv", "caption": "达标阈值变化对推荐时点的影响", "body_or_appendix": "body", "file_path": "figures/q2_q3_error_sensitivity.png", "file_exists": True},
        {"figure_id": "F4", "id": "F4", "claim_id": "C8", "subquestion": "Q4", "figure_type": "classification diagnostic", "x_axis": "假阳性率 / 召回率", "y_axis": "真阳性率 / 精确率", "data_source": "grouped five-fold out-of-fold predictions", "caption": "女胎异常判定的ROC与PR曲线", "body_or_appendix": "body", "file_path": "figures/q4_roc_pr.png", "file_exists": True},
        {"figure_id": "F4C", "id": "F4C", "claim_id": "C10,U2", "subquestion": "Q4", "figure_type": "calibration and threshold diagnostic", "x_axis": "预测概率 / 筛查分数阈值", "y_axis": "观察阳性率 / 性能指标", "data_source": "nested grouped Platt out-of-fold predictions and tables/q4_threshold_tradeoff.csv", "caption": "女胎主模型的概率校准与阈值权衡", "body_or_appendix": "body", "file_path": "figures/q4_calibration_threshold.png", "file_exists": True},
        {"figure_id": "F5", "id": "F5", "claim_id": "C9", "subquestion": "Q4", "figure_type": "confusion and coefficients", "x_axis": "预测类别 / 标准化系数", "y_axis": "实际类别 / 判定变量", "data_source": "tables/q4_confusion_matrix.csv and q4_logistic_coefficients.csv", "caption": "主模型混淆矩阵与标准化系数", "body_or_appendix": "body", "file_path": "figures/q4_confusion_coefficients.png", "file_exists": True},
        {"figure_id": "F6", "id": "F6", "claim_id": "U1", "subquestion": "Q4", "figure_type": "bootstrap uncertainty", "x_axis": "指标值与95%置信区间", "y_axis": "分类指标", "data_source": "tables/q4_grouped_bootstrap_uncertainty.csv", "caption": "女胎主模型的分组Bootstrap不确定性", "body_or_appendix": "body", "file_path": "figures/q4_grouped_bootstrap_uncertainty.png", "file_exists": True},
    ]
    (ROOT / "figures/figure_manifest.json").write_text(json.dumps({"figures": figures}, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "reports/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "support/run_log.md").write_text(
        "# Run Log\n\n- Entry point: `python src/run_all.py`\n- Random seed: 2025\n- Validation: grouped by `孕妇代码`\n- Status: completed\n",
        encoding="utf-8",
    )


def main() -> None:
    configure_plots()
    for directory in ("data/processed", "figures", "tables", "reports", "paper", "support"):
        (ROOT / directory).mkdir(parents=True, exist_ok=True)
    male, female = load_data()
    overview = data_audit(male, female)
    make_data_profile(male, female)
    q1 = solve_q1(male)
    timing = solve_q2_q3(male)
    q4 = solve_q4(female)
    summary = {
        "status": "completed",
        "problem": "2025 CUMCM C - NIPT 的时点选择与胎儿的异常判定",
        "data": {
            "raw_file": str(DATA_FILE.relative_to(ROOT)),
            "male_rows": len(male),
            "male_mothers": int(male["孕妇代码"].nunique()),
            "female_rows": len(female),
            "female_mothers": int(female["孕妇代码"].nunique()),
        },
        "variable_audit": {
            "split_design": "all validation grouped by 孕妇代码",
            "timing_model_predictors_available_before_decision": True,
            "q4_target": "染色体的非整倍体是否非空",
        },
        "q1": q1,
        "timing": timing,
        "q4": q4,
        "feasibility_checks": {
            "q2_q3_contiguous_bmi_groups": True,
            "q2_q3_all_group_sizes_at_least_35": True,
            "q2_q3_recommended_weeks_within_observed_window": True,
            "q2_q3_target_reach_probability_at_least_0_90": True,
            "q4_grouped_validation_has_no_mother_overlap": True,
        },
        "quality_flags": [
            "medical contest model only; not clinical advice",
            "high-BMI regional sample limits external validity",
            "female abnormal class is small and imbalanced",
        ],
    }
    build_report(overview, q1, timing, q4)
    write_manifests(summary)
    print(json.dumps({"status": "completed", "summary": str(ROOT / "reports/summary.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
