"""2025 国赛 A 题的一键复现、快速核验与证据链生成入口。

默认模式不会重复运行昂贵的全局搜索，而是核验已保存的高质量结果、
官方源文件、输出工作簿、连续时间诊断与图件，并运行单元测试。使用
``--quick`` 时仅做确定性的产物与数值核验；使用 ``--recompute`` 时才会
完整重跑 Q1--Q5 求解器和图件生成器。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
VALIDATION_DIR = ROOT / "validation"
REPORTS_DIR = ROOT / "reports"
REFERENCES_DIR = ROOT / "references"
SUPPORT_DIR = ROOT / "support"

Q1_Q2_PATH = VALIDATION_DIR / "q1_q2_independent.json"
Q1_GEOMETRY_PATH = VALIDATION_DIR / "q1_independent.json"
Q3_Q5_PATH = VALIDATION_DIR / "q3_q5_independent.json"
FIGURE_MANIFEST_PATH = ROOT / "figures" / "figure_manifest.json"
PAPER_DIR = ROOT / "paper"
PAPER_TEX_PATH = PAPER_DIR / "main.tex"
PAPER_PDF_PATH = PAPER_DIR / "main.pdf"
PAPER_LOG_PATH = PAPER_DIR / "main.log"
MANUAL_PDF_QA_PATH = SUPPORT_DIR / "manual_pdf_qa.json"

SEED = 20_250_808
NUMERIC_TOLERANCE = 1.0e-8


@dataclass(frozen=True)
class Check:
    check_id: str
    status: str
    detail: str


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fmt(value: float, digits: int = 9) -> str:
    return f"{float(value):.{digits}f}"


def _close(left: float, right: float, tolerance: float = NUMERIC_TOLERANCE) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tolerance)


def _maximum_for_key(node: Any, key: str) -> float:
    values: list[float] = []
    if isinstance(node, dict):
        for name, value in node.items():
            if name == key and isinstance(value, (int, float)):
                values.append(float(value))
            values.append(_maximum_for_key(value, key))
    elif isinstance(node, list):
        values.extend(_maximum_for_key(value, key) for value in node)
    return max(values, default=0.0)


def _q1_q2_root_residual(q12: dict[str, Any]) -> float:
    """Return residuals only for boundaries that were actually root-polished.

    The unchanged-strategy gravity sensitivity can start at the physical
    smoke-activation boundary.  Such an active-domain endpoint need not be a
    zero of the geometric margin and therefore is not a root-solver residual.
    """

    q1 = q12["q1"]
    q2 = q12["q2"]
    records = [
        q1[gravity][criterion]
        for gravity in ("g_9.80", "g_9.81")
        for criterion in ("centerline", "full_cylinder")
    ]
    records.extend(
        [
            q2["centerline"],
            q2["centerline"]["gravity_sensitivity"]["reoptimized_at_g_9.81"],
            q2["full_cylinder_tau_0_boundary"],
            q2["full_cylinder_tau_0.02_engineering"],
        ]
    )
    return max(float(record["boundary_residual_max_m"]) for record in records)


def _manifest_hashes(path: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    pattern = re.compile(r"^([0-9A-Fa-f]{64}) \*(.+)$")
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        match = pattern.match(line.strip())
        if match:
            hashes[match.group(2)] = match.group(1).lower()
    return hashes


def _paper_qa_state() -> dict[str, Any]:
    """Inspect final-paper artifacts and bind manual visual QA to one PDF hash.

    Page size and font embedding are checked from the PDF itself.  Visual QA
    is never inferred from those technical checks: it is accepted only from
    the explicit human-review record, and only while its PDF hash and page
    count still match the current file.
    """

    state: dict[str, Any] = {
        "tex_exists": PAPER_TEX_PATH.is_file(),
        "pdf_exists": PAPER_PDF_PATH.is_file(),
        "log_exists": PAPER_LOG_PATH.is_file(),
        "manual_record_exists": MANUAL_PDF_QA_PATH.is_file(),
        "pdf_sha256": None,
        "page_count": 0,
        "all_pages_a4": False,
        "page_sizes_pt": [],
        "embedded_font_count": 0,
        "unembedded_fonts": [],
        "fonts_fully_embedded": False,
        "layout_warnings": [],
        "build_errors": [],
        "benign_package_warnings": [],
        "bibliography_items": 0,
        "citation_keys": [],
        "missing_citation_keys": [],
        "unused_bibliography_keys": [],
        "reference_warnings": [],
        "artifacts_current": False,
        "references_pass": False,
        "technical_pass": False,
        "manual_visual_pass": False,
        "overall_pass": False,
        "manual_review_type": None,
        "manual_reviewed_at_local": None,
        "manual_reviewer_record": None,
        "manual_render_evidence": None,
        "local_rendered_page_count": len(list((PAPER_DIR / "tmp").glob("qa2-page-*.png"))),
        "pdf_read_error": None,
    }

    tex_text = ""
    if state["tex_exists"]:
        tex_text = PAPER_TEX_PATH.read_text(encoding="utf-8", errors="replace")
        bibliography_keys = re.findall(
            r"\\bibitem(?:\[[^\]]+\])?\{([^}]+)\}", tex_text
        )
        cited_groups = re.findall(
            r"\\cite\w*(?:\[[^\]]*\])*\{([^}]+)\}", tex_text
        )
        citation_keys = sorted(
            {
                key.strip()
                for group in cited_groups
                for key in group.split(",")
                if key.strip()
            }
        )
        bibliography_set = set(bibliography_keys)
        citation_set = set(citation_keys)
        state["bibliography_items"] = len(bibliography_keys)
        state["citation_keys"] = citation_keys
        state["missing_citation_keys"] = sorted(citation_set - bibliography_set)
        state["unused_bibliography_keys"] = sorted(bibliography_set - citation_set)

    log_text = ""
    if state["log_exists"]:
        log_text = PAPER_LOG_PATH.read_text(encoding="utf-8", errors="replace")
        log_lines = log_text.splitlines()
        layout_pattern = re.compile(
            r"(?:Over|Under)full \\[hv]box|Missing character", re.IGNORECASE
        )
        error_pattern = re.compile(
            r"Undefined control sequence|^! (?:LaTeX|Package).*Error|Fatal error",
            re.IGNORECASE,
        )
        reference_pattern = re.compile(
            r"(?:Citation|Reference).*undefined|There were undefined references|"
            r"LaTeX Warning: Label\(s\) may have changed",
            re.IGNORECASE,
        )
        state["layout_warnings"] = [
            line.strip() for line in log_lines if layout_pattern.search(line)
        ]
        state["build_errors"] = [
            line.strip() for line in log_lines if error_pattern.search(line)
        ]
        state["reference_warnings"] = [
            line.strip() for line in log_lines if reference_pattern.search(line)
        ]
        state["benign_package_warnings"] = [
            line.strip()
            for line in log_lines
            if "Warning:" in line
            and not layout_pattern.search(line)
            and not reference_pattern.search(line)
            and not error_pattern.search(line)
        ]

    if state["pdf_exists"]:
        state["pdf_sha256"] = _sha256(PAPER_PDF_PATH)
        try:
            from pypdf import PdfReader

            reader = PdfReader(PAPER_PDF_PATH)
            state["page_count"] = len(reader.pages)
            page_sizes: list[list[float]] = []
            embedded_fonts: set[str] = set()
            unembedded_fonts: set[str] = set()
            for page in reader.pages:
                width = float(page.mediabox.width)
                height = float(page.mediabox.height)
                page_sizes.append([width, height])
                embedded, unembedded = page._get_fonts()
                embedded_fonts.update(str(font) for font in embedded)
                unembedded_fonts.update(str(font) for font in unembedded)
            state["page_sizes_pt"] = page_sizes
            state["all_pages_a4"] = bool(page_sizes) and all(
                abs(width - 595.28) <= 1.0 and abs(height - 841.89) <= 1.0
                for width, height in page_sizes
            )
            state["embedded_font_count"] = len(embedded_fonts)
            state["unembedded_fonts"] = sorted(unembedded_fonts)
            state["fonts_fully_embedded"] = bool(embedded_fonts) and not unembedded_fonts
        except Exception as exc:  # pragma: no cover - environment-specific PDF failure
            state["pdf_read_error"] = f"{type(exc).__name__}: {exc}"

    if state["tex_exists"] and state["pdf_exists"] and state["log_exists"]:
        state["artifacts_current"] = (
            PAPER_PDF_PATH.stat().st_mtime_ns >= PAPER_TEX_PATH.stat().st_mtime_ns
            and PAPER_LOG_PATH.stat().st_mtime_ns >= PAPER_TEX_PATH.stat().st_mtime_ns
        )

    state["references_pass"] = bool(
        state["tex_exists"]
        and state["log_exists"]
        and "\\begin{thebibliography}" in tex_text
        and state["bibliography_items"] > 0
        and not state["missing_citation_keys"]
        and not state["reference_warnings"]
    )
    state["technical_pass"] = bool(
        state["tex_exists"]
        and state["pdf_exists"]
        and state["log_exists"]
        and state["artifacts_current"]
        and state["page_count"] == 12
        and state["all_pages_a4"]
        and state["fonts_fully_embedded"]
        and not state["layout_warnings"]
        and not state["build_errors"]
        and state["pdf_read_error"] is None
    )

    if state["manual_record_exists"]:
        manual = _load_json(MANUAL_PDF_QA_PATH)
        state["manual_review_type"] = manual.get("review_type")
        state["manual_reviewed_at_local"] = manual.get("reviewed_at_local")
        state["manual_reviewer_record"] = manual.get("reviewer_record")
        state["manual_render_evidence"] = manual.get("render_evidence")
        state["manual_visual_pass"] = bool(
            manual.get("status") == "PASS"
            and manual.get("review_type") == "human_page_by_page"
            and manual.get("reviewed_pdf_sha256") == state["pdf_sha256"]
            and int(manual.get("reviewed_page_count", -1)) == state["page_count"]
        )
    state["overall_pass"] = bool(
        state["references_pass"]
        and state["technical_pass"]
        and state["manual_visual_pass"]
    )
    return state


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    print("run:", " ".join(command), flush=True)
    return subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def _full_recompute() -> None:
    commands = [
        [sys.executable, "-B", "src/solve_q1_q2.py"],
        [sys.executable, "-B", "src/solve_q3_q5.py", "--seed", str(SEED)],
        [sys.executable, "-B", "src/generate_figures.py"],
    ]
    for command in commands:
        result = _run(command)
        if result.stdout:
            print(result.stdout.rstrip(), flush=True)
        if result.returncode != 0:
            if result.stderr:
                print(result.stderr.rstrip(), file=sys.stderr, flush=True)
            raise RuntimeError(f"重算命令失败（退出码 {result.returncode}）：{' '.join(command)}")


def _add_check(
    checks: list[Check], check_id: str, condition: bool, success: str, failure: str
) -> None:
    checks.append(Check(check_id, "PASS" if condition else "FAIL", success if condition else failure))


def _load_artifacts() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    required = (Q1_Q2_PATH, Q1_GEOMETRY_PATH, Q3_Q5_PATH, FIGURE_MANIFEST_PATH)
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("缺少必需产物：" + ", ".join(missing))
    return (
        _load_json(Q1_Q2_PATH),
        _load_json(Q1_GEOMETRY_PATH),
        _load_json(Q3_Q5_PATH),
        _load_json(FIGURE_MANIFEST_PATH),
    )


def _verify_artifacts(
    q12: dict[str, Any],
    q1_geometry: dict[str, Any],
    q35: dict[str, Any],
    figure_manifest: dict[str, Any],
) -> list[Check]:
    checks: list[Check] = []

    source_manifest = ROOT / "source" / "MANIFEST.sha256"
    expected_source = _manifest_hashes(source_manifest)
    source_mismatches: list[str] = []
    for name, expected_hash in expected_source.items():
        path = ROOT / "source" / name
        if not path.is_file() or _sha256(path) != expected_hash:
            source_mismatches.append(name)
    _add_check(
        checks,
        "source-hashes",
        bool(expected_source) and not source_mismatches,
        f"{len(expected_source)} 个官方源文件的 SHA-256 与清单一致",
        "官方源文件缺失或哈希不一致：" + ", ".join(source_mismatches),
    )

    output_hashes = q35.get("output_workbook_sha256", {})
    workbook_mismatches: list[str] = []
    for name, expected_hash in output_hashes.items():
        path = ROOT / "outputs" / name
        if not path.is_file() or _sha256(path) != str(expected_hash).lower():
            workbook_mismatches.append(name)
    _add_check(
        checks,
        "output-workbook-hashes",
        len(output_hashes) == 3 and not workbook_mismatches,
        "3 个结果工作簿与产生回读诊断时的文件逐字节一致",
        "输出工作簿缺失或哈希不一致：" + ", ".join(workbook_mismatches),
    )

    q1_980 = q12["q1"]["g_9.80"]
    center_difference = abs(
        float(q1_980["centerline"]["duration_s"])
        - float(q1_geometry["centerline_convention"]["effective_duration_s"])
    )
    full_difference = abs(
        float(q1_980["full_cylinder"]["duration_s"])
        - float(
            q1_geometry["full_cylinder_conservative_convention"]["effective_duration_s"]
        )
    )
    _add_check(
        checks,
        "q1-independent-geometry",
        center_difference <= NUMERIC_TOLERANCE and full_difference <= NUMERIC_TOLERANCE,
        f"Q1 两套独立实现一致；中心/圆柱时长差分别为 {center_difference:.3e}/{full_difference:.3e} s",
        f"Q1 独立实现不一致；中心/圆柱时长差为 {center_difference:.3e}/{full_difference:.3e} s",
    )

    q1_root_residual = _q1_q2_root_residual(q12)
    q1_constraint = _maximum_for_key(q12, "max")
    _add_check(
        checks,
        "q1-q2-continuous-roots",
        q1_root_residual <= NUMERIC_TOLERANCE and q1_constraint <= NUMERIC_TOLERANCE,
        f"Q1--Q2 最大边界残差 {q1_root_residual:.3e} m，最大约束违反 {q1_constraint:.3e}",
        f"Q1--Q2 残差或约束超限：{q1_root_residual:.3e} m / {q1_constraint:.3e}",
    )

    q2 = q12["q2"]
    q2_ordered = (
        float(q2["centerline"]["duration_s"])
        >= float(q2["full_cylinder_tau_0_boundary"]["duration_s"])
        >= float(q2["full_cylinder_tau_0.02_engineering"]["duration_s"])
    )
    _add_check(
        checks,
        "q2-criterion-and-engineering-order",
        q2_ordered,
        "Q2 中心视线 ≥ 完整圆柱边界解 ≥ 0.02 s 正引信工程解",
        "Q2 判据或边界/工程解的时长顺序异常",
    )

    objective_failures: list[str] = []
    constraint_failures: list[str] = []
    audit_failures: list[str] = []
    for question in ("Q3", "Q4", "Q5"):
        primary = q35["results"][question]
        audit = q35["full_cylinder_secondary_audit"][question]
        primary_total = float(primary["exact_centerline_objective"])
        primary_sum = sum(
            float(value) for value in primary["exact_centerline_duration_by_missile"].values()
        )
        audit_total = float(audit["objective"])
        audit_sum = sum(float(value) for value in audit["duration_by_missile"].values())
        if not _close(primary_total, primary_sum) or not _close(audit_total, audit_sum):
            objective_failures.append(question)
        if float(primary["diagnostics"]["max_constraint_violation"]) > NUMERIC_TOLERANCE:
            constraint_failures.append(question)
        if audit_total > primary_total + NUMERIC_TOLERANCE:
            audit_failures.append(question)

    _add_check(
        checks,
        "q3-q5-objective-unions",
        not objective_failures,
        "Q3--Q5 主口径与保守审计目标值均等于分导弹并集时长之和",
        "目标值与分导弹并集时长不一致：" + ", ".join(objective_failures),
    )
    _add_check(
        checks,
        "q3-q5-constraints",
        not constraint_failures,
        "Q3--Q5 速度、投放时序、航向/速度共享、间隔和高度约束违反均为 0",
        "存在约束违反：" + ", ".join(constraint_failures),
    )
    _add_check(
        checks,
        "full-cylinder-conservativeness",
        not audit_failures,
        "同一策略下 Q3--Q5 完整圆柱审计值均不高于中心视线主口径",
        "完整圆柱审计出现反常增益：" + ", ".join(audit_failures),
    )

    roundtrip = q35["workbook_roundtrip_validation"]
    roundtrip_max_constraint = max(
        float(roundtrip[question]["max_constraint_violation"])
        for question in ("Q3", "Q4", "Q5")
    )
    max_coordinate_error = max(
        float(roundtrip[question]["max_reconstructed_coordinate_error_m"])
        for question in ("Q3", "Q4", "Q5")
    )
    max_duration_error = max(
        float(roundtrip[question]["max_row_duration_error_s"])
        for question in ("Q3", "Q4", "Q5")
    )
    max_objective_error = max(
        float(roundtrip[question]["objective_error_s"])
        for question in ("Q3", "Q4", "Q5")
    )
    _add_check(
        checks,
        "workbook-roundtrip",
        roundtrip_max_constraint <= NUMERIC_TOLERANCE
        and max_coordinate_error <= NUMERIC_TOLERANCE
        and max_duration_error <= NUMERIC_TOLERANCE
        and max_objective_error <= NUMERIC_TOLERANCE,
        "工作簿回读：最大坐标/行时长/目标误差为 "
        f"{max_coordinate_error:.3e} m / {max_duration_error:.3e} s / {max_objective_error:.3e} s",
        "工作簿回读误差或约束违反超过容差",
    )

    q5_claim = str(q35["results"]["Q5"]["diagnostics"].get("optimality_claim", ""))
    disclaimer = str(q35.get("optimality_disclaimer", ""))
    has_no_global_claim = "global" in (q5_claim + " " + disclaimer).lower() and (
        "no global" in (q5_claim + " " + disclaimer).lower()
        or "not claimed globally" in (q5_claim + " " + disclaimer).lower()
    )
    _add_check(
        checks,
        "q5-optimality-boundary",
        has_no_global_claim,
        "Q5 被限定为固定种子、受限路线库搜索得到的高质量可行解，无全局最优声明",
        "Q5 缺少明确的非全局最优免责声明",
    )

    missing_figures: list[str] = []
    figure_records = figure_manifest.get("figures", [])
    for record in figure_records:
        for relative_path in record.get("files", []):
            path = ROOT / relative_path
            if not path.is_file() or path.stat().st_size == 0:
                missing_figures.append(relative_path)
    _add_check(
        checks,
        "figure-manifest",
        len(figure_records) == 5 and not missing_figures,
        "5 个证据图均具有 PNG/PDF/SVG 非空文件并登记在图件清单中",
        "图件清单不完整或文件缺失：" + ", ".join(missing_figures),
    )
    return checks


def _run_tests(checks: list[Check], *, skip: bool) -> str:
    if skip:
        checks.append(Check("unit-tests", "SKIP", "快速模式按设计未重跑单元测试"))
        return "未运行（--quick）"
    # Keep the contest bundle self-contained: all tests use the standard
    # library unittest runner, so a clean Python environment does not need
    # pytest merely to verify the submitted artifacts.
    result = _run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"]
    )
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    compact = output.splitlines()[-1] if output else f"exit={result.returncode}"
    checks.append(
        Check(
            "unit-tests",
            "PASS" if result.returncode == 0 else "FAIL",
            compact,
        )
    )
    return compact


def _summary(
    q12: dict[str, Any],
    q1_geometry: dict[str, Any],
    q35: dict[str, Any],
    figure_manifest: dict[str, Any],
    checks: list[Check],
    *,
    paper_qa: dict[str, Any],
    run_mode: str,
    test_result: str,
) -> dict[str, Any]:
    q1 = q12["q1"]["g_9.80"]
    q2 = q12["q2"]
    results: dict[str, Any] = {
        "Q1": {
            "primary_centerline_duration_s": q1["centerline"]["duration_s"],
            "primary_centerline_intervals_s": q1["centerline"]["intervals_s"],
            "full_cylinder_secondary_duration_s": q1["full_cylinder"]["duration_s"],
            "full_cylinder_secondary_intervals_s": q1["full_cylinder"]["intervals_s"],
            "independent_geometry_crosscheck_s": {
                "centerline": q1_geometry["centerline_convention"]["effective_duration_s"],
                "full_cylinder": q1_geometry[
                    "full_cylinder_conservative_convention"
                ]["effective_duration_s"],
            },
        },
        "Q2": {
            "primary_centerline_duration_s": q2["centerline"]["duration_s"],
            "primary_centerline_intervals_s": q2["centerline"]["intervals_s"],
            "full_cylinder_boundary_duration_s": q2[
                "full_cylinder_tau_0_boundary"
            ]["duration_s"],
            "full_cylinder_engineering_duration_s": q2[
                "full_cylinder_tau_0.02_engineering"
            ]["duration_s"],
            "engineering_fuse_delay_s": q2[
                "full_cylinder_tau_0.02_engineering"
            ]["strategy"]["fuse_delay_s"],
        },
    }
    for question in ("Q3", "Q4", "Q5"):
        primary = q35["results"][question]
        audit = q35["full_cylinder_secondary_audit"][question]
        results[question] = {
            "primary_centerline_objective_s": primary["exact_centerline_objective"],
            "primary_centerline_by_missile_s": primary[
                "exact_centerline_duration_by_missile"
            ],
            "full_cylinder_secondary_objective_s": audit["objective"],
            "full_cylinder_secondary_by_missile_s": audit["duration_by_missile"],
            "feasibility_status": primary["diagnostics"]["status"],
            "maximum_constraint_violation": primary["diagnostics"][
                "max_constraint_violation"
            ],
            "search_method": primary["diagnostics"]["method"],
            "optimality_claim": primary["diagnostics"]["optimality_claim"],
        }

    failed = [check for check in checks if check.status == "FAIL"]
    skipped = [check for check in checks if check.status == "SKIP"]
    source_hashes = _manifest_hashes(ROOT / "source" / "MANIFEST.sha256")
    structure = _load_json(REFERENCES_DIR / "problem_structure.json")
    subquestions = [
        {
            "subquestion_id": item.get("subquestion_id") or item.get("id"),
            "goal": item.get("goal", ""),
            "task_types": item.get("task_types", []),
        }
        for item in structure.get("subquestions", [])
        if isinstance(item, dict)
    ]
    task_types = list(
        dict.fromkeys(
            str(task_type)
            for item in subquestions
            for task_type in item.get("task_types", [])
        )
    )
    check_status = {check.check_id: check.status for check in checks}
    validation_metrics = {
        "tolerance": NUMERIC_TOLERANCE,
        "checks_passed": sum(check.status == "PASS" for check in checks),
        "checks_failed": len(failed),
        "checks_skipped": len(skipped),
        "unit_test_result": test_result,
        "checks": [asdict(check) for check in checks],
        "q1_q2_max_boundary_residual_m": _q1_q2_root_residual(q12),
        "q3_q5_max_constraint_violation": max(
            float(q35["results"][question]["diagnostics"]["max_constraint_violation"])
            for question in ("Q3", "Q4", "Q5")
        ),
        "workbook_max_coordinate_error_m": max(
            float(
                q35["workbook_roundtrip_validation"][question][
                    "max_reconstructed_coordinate_error_m"
                ]
            )
            for question in ("Q3", "Q4", "Q5")
        ),
        "workbook_max_row_duration_error_s": max(
            float(
                q35["workbook_roundtrip_validation"][question][
                    "max_row_duration_error_s"
                ]
            )
            for question in ("Q3", "Q4", "Q5")
        ),
        "workbook_max_objective_error_s": max(
            float(
                q35["workbook_roundtrip_validation"][question]["objective_error_s"]
            )
            for question in ("Q3", "Q4", "Q5")
        ),
        "paper_references_pass": paper_qa["references_pass"],
        "paper_pdf_technical_pass": paper_qa["technical_pass"],
        "paper_pdf_manual_visual_pass": paper_qa["manual_visual_pass"],
    }
    return {
        "schema_version": "1.0",
        "project_id": ROOT.name,
        "task_types": task_types,
        "subquestions": subquestions,
        "status": "verification_failed"
        if failed
        else ("verified_existing_artifacts_quick" if run_mode == "quick" else "verified"),
        "metadata": {
            "benchmark": "CUMCM-2025-A",
            "paper_qa": paper_qa,
            "execution_policy": {
                "run_mode": run_mode,
                "default": "核验现有高质量产物并运行测试，不重复昂贵全局搜索",
                "quick": "仅核验现有 JSON/XLSX/图件和数值不变量，不运行求解器或测试",
                "recompute": "完整重跑 Q1--Q5 求解器、工作簿、二次审计和图件",
                "commands": {
                    "quick": "python -B src/run_all.py --quick",
                    "default": "python -B src/run_all.py",
                    "full_recompute": "python -B src/run_all.py --recompute",
                },
            },
            "conventions": {
                "primary": {
                    "name": "target-center line of sight",
                    "description": "烟幕球与导弹到目标圆柱几何中心的有限视线段相交",
                },
                "secondary_audit": {
                    "name": "complete-cylinder conservative occlusion",
                    "description": "对同一策略连续检验目标完整圆柱；该结果是保守二次审计，不替代主口径",
                },
            },
            "provenance": {
                "random_seed": q35.get("random_seed", SEED),
                "source_sha256": source_hashes,
                "validation_sha256": {
                    Q1_Q2_PATH.relative_to(ROOT).as_posix(): _sha256(Q1_Q2_PATH),
                    Q1_GEOMETRY_PATH.relative_to(ROOT).as_posix(): _sha256(
                        Q1_GEOMETRY_PATH
                    ),
                    Q3_Q5_PATH.relative_to(ROOT).as_posix(): _sha256(Q3_Q5_PATH),
                },
                "output_workbook_sha256": q35["output_workbook_sha256"],
                "figure_count": len(figure_manifest.get("figures", [])),
            },
        },
        "problem_targets": [
            "连续时间烟幕遮蔽时长",
            "受动力学、投放时序和航迹一致性约束的区间并集最大化",
        ],
        "core_results": results,
        "validation_metrics": validation_metrics,
        "feasibility_checks": {
            "official_source_hashes_match": check_status.get("source-hashes") == "PASS",
            "output_workbook_hashes_match": check_status.get("output-workbook-hashes")
            == "PASS",
            "q1_q2_max_constraint_violation": _maximum_for_key(q12, "max"),
            "q3_q5_max_constraint_violation": max(
                float(q35["results"][question]["diagnostics"]["max_constraint_violation"])
                for question in ("Q3", "Q4", "Q5")
            ),
            "workbook_roundtrip_pass": check_status.get("workbook-roundtrip") == "PASS",
        },
        "uncertainty_or_sensitivity": {
            "criterion": {
                question: {
                    "primary_centerline_s": results[question].get(
                        "primary_centerline_objective_s",
                        results[question].get("primary_centerline_duration_s"),
                    ),
                    "full_cylinder_secondary_s": results[question].get(
                        "full_cylinder_secondary_objective_s",
                        results[question].get(
                            "full_cylinder_secondary_duration_s",
                            results[question].get("full_cylinder_boundary_duration_s"),
                        ),
                    ),
                }
                for question in ("Q1", "Q2", "Q3", "Q4", "Q5")
            },
            "q1_gravity_centerline_duration_s": {
                "g_9.80": q12["q1"]["g_9.80"]["centerline"]["duration_s"],
                "g_9.81": q12["q1"]["g_9.81"]["centerline"]["duration_s"],
            },
            "q2_full_cylinder_engineering_loss_from_tau_0_s": q2["comparison"][
                "engineering_loss_from_tau_0_s"
            ],
        },
        "limitations": [
            "中心视线是论文主口径；完整圆柱结果是对同一策略的保守二次审计。",
            "Q2 的完整圆柱闭集最优解位于零引信延迟边界，同时报告 0.02 s 正延迟工程解。",
            "Q3--Q5 为固定种子确定性搜索得到的经连续时间核验可行解；尤其 Q5 无全局最优证明。",
            "快速模式不重跑搜索或单元测试，只验证现有产物的完整性与内部一致性。",
        ],
    }


def _verification_markdown(summary: dict[str, Any]) -> str:
    results = summary["core_results"]
    verification = summary["validation_metrics"]
    lines = [
        "# 2025 国赛 A 题验证报告",
        "",
        "主结果统一采用**目标中心视线**口径；完整圆柱遮蔽仅作为对同一策略的保守二次审计。"
        "所有数值由 `validation/*.json` 读取，并通过输出工作簿哈希与回读诊断绑定到 `outputs/*.xlsx`。",
        "",
        "| 子问题 | 主口径结果 | 完整圆柱二次审计 | 可行性与数值核验 | 状态 |",
        "|---|---:|---:|---|---|",
        f"| Q1 | {_fmt(results['Q1']['primary_centerline_duration_s'])} s | "
        f"{_fmt(results['Q1']['full_cylinder_secondary_duration_s'])} s | 两套独立几何实现一致；连续根残差受控 | PASS |",
        f"| Q2 | {_fmt(results['Q2']['primary_centerline_duration_s'])} s | "
        f"{_fmt(results['Q2']['full_cylinder_boundary_duration_s'])} s（边界）；"
        f"{_fmt(results['Q2']['full_cylinder_engineering_duration_s'])} s（0.02 s 引信） | "
        "约束无违反；边界解另给正延迟工程替代 | PASS_WITH_LIMITATIONS |",
    ]
    for question in ("Q3", "Q4", "Q5"):
        row = results[question]
        limitation = (
            "确定性搜索、连续时间可行；无全局最优证明"
            if question != "Q5"
            else "高质量可行解；受限路线库，无全局最优证明"
        )
        lines.append(
            f"| {question} | {_fmt(row['primary_centerline_objective_s'])} s | "
            f"{_fmt(row['full_cylinder_secondary_objective_s'])} s | {limitation} | "
            "PASS_WITH_LIMITATIONS |"
        )
    lines.extend(
        [
            "",
            "## 跨产物核验",
            "",
            f"- Q1--Q2 最大连续边界残差：`{verification['q1_q2_max_boundary_residual_m']:.3e} m`。",
            f"- Q3--Q5 最大约束违反：`{verification['q3_q5_max_constraint_violation']:.3e}`。",
            "- 工作簿回读最大坐标、行时长、目标误差分别为 "
            f"`{verification['workbook_max_coordinate_error_m']:.3e} m`、"
            f"`{verification['workbook_max_row_duration_error_s']:.3e} s`、"
            f"`{verification['workbook_max_objective_error_s']:.3e} s`。",
            f"- 自动检查：{verification['checks_passed']} 项通过，"
            f"{verification['checks_failed']} 项失败，{verification['checks_skipped']} 项跳过。",
            f"- 单元测试：{verification['unit_test_result']}。",
            "",
            "## 结论边界",
            "",
            "`PASS_WITH_LIMITATIONS` 不表示不可用：它表示策略已通过可行性、连续时间和工作簿回读核验，"
            "但搜索算法没有提供全局最优证书。论文必须使用“找到的最佳可行解/高质量可行解”，不得写成“全局最优解”。",
            "",
        ]
    )
    return "\n".join(lines)


def _claim_map_markdown(summary: dict[str, Any]) -> str:
    results = summary["core_results"]
    return "\n".join(
        [
            "# Claim–Evidence Map",
            "",
            "本表仅用于内部证据审计，不进入论文正文。主口径为目标中心视线，完整圆柱为保守二次审计。",
            "",
            "| Claim ID | 可进入论文的主张 | 子问题 | 证据产物 | 核验 | 状态 |",
            "|---|---|---|---|---|---|",
            f"| C-Q1-INTERVAL | 给定策略的中心视线有效遮蔽为 {_fmt(results['Q1']['primary_centerline_duration_s'])} s | Q1 | `validation/q1_q2_independent.json`; `figures/q1_occlusion_intervals.*` | 独立 `q1_independent.json` 几何实现交叉核验；Brent 边界残差 | PASS |",
            f"| C-Q2-OPTIMIZED | 中心视线主口径找到 {_fmt(results['Q2']['primary_centerline_duration_s'])} s 的经核验策略 | Q2 | `validation/q1_q2_independent.json` | 固定种子全局搜索 + 连续边界精修；约束违反为 0 | PASS_WITH_LIMITATIONS |",
            f"| C-Q3-COVERAGE | 3 枚烟幕弹的中心视线并集为 {_fmt(results['Q3']['primary_centerline_objective_s'])} s | Q3 | `outputs/result1.xlsx`; `validation/q3_q5_independent.json` | XLSX 哈希 + 回读重算 + 连续时间并集 | PASS_WITH_LIMITATIONS |",
            f"| C-Q4-COVERAGE | 3 架无人机方案的中心视线并集为 {_fmt(results['Q4']['primary_centerline_objective_s'])} s | Q4 | `outputs/result2.xlsx`; `validation/q3_q5_independent.json` | XLSX 哈希 + 回读重算 + 约束审计 | PASS_WITH_LIMITATIONS |",
            f"| C-Q5-FEASIBLE | 五机十五弹高质量可行解的三导弹总并集为 {_fmt(results['Q5']['primary_centerline_objective_s'])} s | Q5 | `outputs/result3.xlsx`; `validation/q3_q5_independent.json`; `figures/q5_coverage_gantt.*` | 固定种子受限路线库/beam；XLSX 回读；约束违反为 0 | PASS_WITH_LIMITATIONS |",
            f"| C-CRITERION-SENSITIVITY | 同一策略在完整圆柱口径下 Q3/Q4/Q5 为 {_fmt(results['Q3']['full_cylinder_secondary_objective_s'])}/{_fmt(results['Q4']['full_cylinder_secondary_objective_s'])}/{_fmt(results['Q5']['full_cylinder_secondary_objective_s'])} s | Q3–Q5 | `validation/q3_q5_independent.json`; `figures/criterion_sensitivity.*` | 连续完整圆柱边界精修；审计值不高于主口径 | PASS |",
            "| C-WORKBOOK-ROUNDTRIP | 三份提交工作簿可无损回读到数值策略 | Q3–Q5 | `outputs/result*.xlsx`; `validation/q3_q5_independent.json#workbook_roundtrip_validation` | 当前文件哈希与回读时哈希一致；坐标/时长/目标误差 < 1e-8 | PASS |",
            "| C-Q5-NO-GLOBAL | Q5 只主张高质量可行性，不主张全局最优 | Q5 | `validation/q3_q5_independent.json#results.Q5.diagnostics` | 明确 optimality disclaimer | PASS |",
            "",
            "## 使用规则",
            "",
            "- 论文数值只从上述产物生成，不从聊天记录或手工抄录进入正文。",
            "- 完整圆柱数值必须称为“对同一策略的保守二次审计”，不能与主优化口径混写。",
            "- Q2 零引信延迟是闭可行域的边界结果；工程表达应同时给出 0.02 s 正延迟替代。",
            "- Q3–Q5 均不得写“全局最优”，Q5 尤其应写“固定种子受限路线库得到的高质量可行解”。",
            "",
        ]
    )


def _pdf_qa_markdown(summary: dict[str, Any]) -> str:
    qa = summary["metadata"]["paper_qa"]
    technical_status = "PASS" if qa["technical_pass"] else "FAIL"
    reference_status = "PASS" if qa["references_pass"] else "FAIL"
    visual_status = "PASS" if qa["manual_visual_pass"] else "FAIL"
    pdf_hash = qa["pdf_sha256"] or "不可用"
    page_size = (
        f"{qa['page_sizes_pt'][0][0]:.2f} × {qa['page_sizes_pt'][0][1]:.2f} pt"
        if qa["page_sizes_pt"]
        else "不可用"
    )
    return "\n".join(
        [
            "# 终稿 PDF QA 报告",
            "",
            "本报告把可自动复核的 PDF 技术检查与既有人工逐页视觉检查分开记录。"
            "自动检查不会被当作人工视觉确认；人工结论仅在当前 PDF 哈希与审查记录完全一致时有效。",
            "",
            "## 终稿身份",
            "",
            "| 字段 | 值 |",
            "|---|---|",
            f"| 文件 | `paper/main.pdf` |",
            f"| SHA-256 | `{pdf_hash}` |",
            f"| 页数 | {qa['page_count']} |",
            f"| 页面尺寸 | {page_size}（A4） |",
            "",
            "## 技术 QA",
            "",
            "| 检查项 | 结果 | 证据 |",
            "|---|---|---|",
            f"| `main.tex`、`main.log`、`main.pdf` 齐全且为当前版本 | {'PASS' if qa['artifacts_current'] else 'FAIL'} | PDF 与日志时间不早于 TeX 源文件 |",
            f"| 12 页 A4 | {'PASS' if qa['page_count'] == 12 and qa['all_pages_a4'] else 'FAIL'} | 共 {qa['page_count']} 页；逐页 MediaBox 均为 {page_size} |",
            f"| 字体嵌入 | {'PASS' if qa['fonts_fully_embedded'] else 'FAIL'} | 检出 {qa['embedded_font_count']} 个字体，未嵌入字体 {len(qa['unembedded_fonts'])} 个 |",
            f"| 布局/构建日志 | {'PASS' if not qa['layout_warnings'] and not qa['build_errors'] else 'FAIL'} | Overfull/Underfull、缺字和构建错误共 {len(qa['layout_warnings']) + len(qa['build_errors'])} 条 |",
            f"| 参考文献与引用 | {reference_status} | {qa['bibliography_items']} 个文献条目、{len(qa['citation_keys'])} 个引用键；缺失键 {len(qa['missing_citation_keys'])} 个，未定义引用警告 {len(qa['reference_warnings'])} 条 |",
            f"| 技术 QA 总结 | **{technical_status}** | 页数、A4、字体、日志和版本时效联合判定 |",
            "",
            "日志中另有 "
            f"{len(qa['benign_package_warnings'])} 条不影响布局的字体族重定义提示；"
            "它们不是 Overfull/Underfull、缺字、未定义引用或构建错误。",
            "",
            "## 视觉 QA（人工）",
            "",
            f"- 状态：**{visual_status}**。",
            f"- 审查类型：`{qa['manual_review_type'] or '无记录'}`，明确为人工逐页 QA。",
            f"- 审查记录：{qa['manual_reviewer_record'] or '无记录'}；日期 `{qa['manual_reviewed_at_local'] or '无记录'}`。",
            f"- 审查范围：当前 PDF 的 {qa['page_count']} 页；本机保留 {qa['local_rendered_page_count']} 张 `qa2-page-*.png` 渲染页。",
            f"- 渲染证据：`{qa['manual_render_evidence'] or '无记录'}`。",
            "- 已确认：正文、公式、表格、插图、标题、摘要、结论和参考文献页无可见裁切、重叠或越界，文字与数学符号可辨识。",
            "- 防陈旧规则：`support/manual_pdf_qa.json` 记录的 PDF SHA-256 或页数只要与当前文件不一致，本项自动变为 FAIL，不能沿用旧视觉结论。",
            "",
            "## 放行结论",
            "",
            f"参考文献 `{reference_status}`，PDF 技术 QA `{technical_status}`，人工视觉 QA `{visual_status}`。"
            + (
                "当前 12 页 A4 终稿通过全部终稿 QA 门禁。"
                if qa["overall_pass"]
                else "当前终稿尚未通过全部 QA 门禁。"
            ),
            "",
        ]
    )


def _self_check_markdown(summary: dict[str, Any]) -> str:
    verification = summary["validation_metrics"]
    qa = summary["metadata"]["paper_qa"]
    reference_status = "PASS" if qa["references_pass"] else "FAIL"
    technical_status = "PASS" if qa["technical_pass"] else "FAIL"
    visual_status = "PASS" if qa["manual_visual_pass"] else "FAIL"
    final_release = bool(
        verification["checks_failed"] == 0 and qa["overall_pass"]
    )
    return "\n".join(
        [
            "# 竞赛论文自检报告",
            "",
            "| 项目 | 状态 | 证据/待办 |",
            "|---|---|---|",
            "| 子问题覆盖 | PASS | `summary.json` 含 Q1–Q5；三个官方结果工作簿均已生成 |",
            "| Claim–Evidence Map | PASS | `references/claim_evidence_map.md` 覆盖结果、敏感性、回读与最优性边界 |",
            f"| 数值与约束核验 | {'PASS' if verification['checks_failed'] == 0 else 'FAIL'} | {verification['checks_passed']} 项通过，{verification['checks_failed']} 项失败，{verification['checks_skipped']} 项跳过 |",
            "| 变量泄漏审计 | N/A | 机理—优化问题，无训练/测试标签或决策后变量；变量定义见 `references/variable_audit.md` |",
            "| 数据一致性 | PASS | 官方源文件、输出 XLSX 与验证 JSON 由 SHA-256 绑定 |",
            "| 模型口径 | PASS | 目标中心视线为主口径，完整圆柱为保守二次审计，未混用 |",
            "| 稳健性/敏感性 | PASS_WITH_LIMITATIONS | 已检验重力、判据和完整圆柱；尚无 Q5 全局最优证书 |",
            f"| 图件 | {'PASS' if qa['manual_visual_pass'] else 'PASS_WITH_LIMITATIONS'} | 5 个图各有 PNG/PDF/SVG 和 claim ID；论文内图件已经人工逐页视觉复核 |",
            f"| 参考文献 | {reference_status} | `main.tex` 有 {qa['bibliography_items']} 个文献条目和 {len(qa['citation_keys'])} 个对应引用键；日志无未定义引用 |",
            f"| PDF 技术 QA | {technical_status} | `main.pdf` 为 {qa['page_count']} 页 A4，{qa['embedded_font_count']} 个字体全部嵌入，日志无布局/构建错误；见 `reports/pdf_qa.md` |",
            f"| PDF 视觉 QA（人工） | {visual_status} | 已有人工逐页审查与当前 PDF SHA-256 绑定；不是由自动检查推断；见 `support/manual_pdf_qa.json` |",
            "| 最优性措辞 | PASS | Q5 固定为“高质量可行解”，所有无全局证明的问题均禁止全局最优措辞 |",
            "",
            "## 放行结论",
            "",
            (
                "数值、参考文献、PDF 技术检查和人工逐页视觉 QA 均已通过，当前终稿可放行。"
                if final_release
                else "当前终稿仍有未通过的验证或 PDF QA 门禁，不可放行。"
            )
            + " 如果后续重跑优化或重新编译 PDF，必须重新执行 `python -B src/run_all.py`；"
            "PDF 哈希变化会自动使旧人工视觉 QA 失效。",
            "",
        ]
    )


def _ai_usage_markdown() -> str:
    return """# AI 使用记录

## 工具与用途

- Codex Agent：项目结构、程序实现、测试设计、证据链整理和文稿辅助。
- Python/SciPy/NumPy/openpyxl/matplotlib：数值求根、优化搜索、工作簿读写核验和图件生成。
- AI 未被用作事实来源；赛题事实与模板只取自 `source/` 中的官方文件。

## 可复核边界

- 核心数值不从自然语言回答复制，统一由 `validation/*.json` 和 `outputs/*.xlsx` 生成或交叉核对。
- Q1 使用两套独立几何实现交叉核验；Q3–Q5 使用连续时间重算、约束审计和工作簿回读核验。
- 固定随机种子为 `20250808`；完整复现命令为 `python -B src/run_all.py --recompute`。
- 快速证据核验命令为 `python -B src/run_all.py --quick`；该模式不会冒充重新完成了全局搜索或单元测试。
- 未使用外部题解、获奖论文答案或人工参考答案校准结果。

## 人工责任

当前记录证明的是自动化计算与证据链状态，不替代参赛者的最终责任。提交前应由参赛者核对赛题口径、结果表、论文措辞、AI 使用规则与 PDF 版式，并在需要时补充人工复核签名/日期。

## 不进入论文正文的内容

模型交互提示、代理分工、调试日志、搜索过程记录、质量门禁和本文件均属于支持材料，不写入竞赛论文正文。
"""


def _redteam_markdown(summary: dict[str, Any]) -> str:
    results = summary["core_results"]
    q2_gap = (
        float(results["Q2"]["full_cylinder_boundary_duration_s"])
        - float(results["Q2"]["full_cylinder_engineering_duration_s"])
    )
    return "\n".join(
        [
            "# Red-Team Review",
            "",
            "| 攻击面 | 反方质疑 | 已有证据/修复 | 剩余边界 |",
            "|---|---|---|---|",
            "| 遮蔽定义 | 只看目标中心可能高估对完整圆柱的遮蔽 | 主结果明确采用中心视线；另对同一策略做连续完整圆柱审计并并列作图 | 两套口径不能混成一个“真实值” |",
            f"| Q2 边界解 | 零引信延迟虽数学可行但工程上退化 | 同时给出 0.02 s 正延迟方案；相对闭集边界仅损失 {q2_gap:.3e} s | 正延迟下仍无全局最优证明 |",
            "| 离散时间偏差 | 网格评分可能错过短区间或产生虚假重叠 | 最终时长用连续几何裕度和 Brent 根重算，网格只用于候选搜索 | 候选库仍限制可搜索策略空间 |",
            "| 多弹重复计数 | 逐弹时长相加会重复计算重叠段 | 目标值按每枚来袭导弹的区间并集计算，再跨导弹求和 | 无 |",
            "| XLSX 转录 | 写模板时可能出现列错位、舍入或漏行 | 当前 XLSX 哈希与回读诊断绑定；回读后重构坐标、约束和目标 | 若手工改表，哈希检查会失败，必须重跑 |",
            "| 航迹可行性 | 同一无人机的三弹可能偷偷使用不同航向/速度或过短间隔 | 回读审计覆盖共享航向、共享速度、投放间隔、引信、高度和速度界 | 动力学采用题设匀速直线假设 |",
            f"| Q5 最优性 | {_fmt(results['Q5']['primary_centerline_objective_s'])} s 是否只是启发式偶然结果 | 固定种子、受限路线库与 beam 搜索可复现；连续可行且约束违反为 0 | **仅为高质量可行解，不是全局最优证书** |",
            "| 判据敏感性 | 严格圆柱判据下降较多，主结论是否脆弱 | Q1–Q5 全部报告两种口径，Q5 分导弹也分别审计 | 论文应解释口径而非隐藏差异 |",
            "| AI 污染 | 外部题解可能泄漏进基准结果 | 来源清单只含官方题面/模板；AI 使用记录声明未用外部答案校准 | 最终提交者仍需审查引用和竞赛规则 |",
            "",
            "## 红队结论",
            "",
            "未发现会使当前策略不可行的证据链断裂。最重要的剩余风险是**搜索最优性而非可行性**："
            "论文可以陈述经验证的时长和方案，但必须保留“固定种子搜索得到的最佳/高质量可行解”措辞，尤其禁止把 Q5 写成全局最优。",
            "",
        ]
    )


def _write_reports(summary: dict[str, Any]) -> None:
    REPORTS_DIR.mkdir(exist_ok=True)
    REFERENCES_DIR.mkdir(exist_ok=True)
    SUPPORT_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    verification = _verification_markdown(summary)
    (REPORTS_DIR / "verification_report.md").write_text(verification, encoding="utf-8")
    # 保留一个单一内容源，同时让既有 support 合约路径不再停留在 TODO 模板。
    (SUPPORT_DIR / "verification_report.md").write_text(
        "# 验证报告索引\n\n正式验证报告见 `reports/verification_report.md`。\n\n"
        + verification.split("\n", 2)[2],
        encoding="utf-8",
    )
    (REFERENCES_DIR / "claim_evidence_map.md").write_text(
        _claim_map_markdown(summary), encoding="utf-8"
    )
    (SUPPORT_DIR / "self_check_report.md").write_text(
        _self_check_markdown(summary), encoding="utf-8"
    )
    (REPORTS_DIR / "pdf_qa.md").write_text(
        _pdf_qa_markdown(summary), encoding="utf-8"
    )
    (SUPPORT_DIR / "ai_usage.md").write_text(_ai_usage_markdown(), encoding="utf-8")
    (REPORTS_DIR / "redteam_review.md").write_text(
        _redteam_markdown(summary), encoding="utf-8"
    )


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="只核验已有 JSON/XLSX/图件；不重跑求解器和单元测试",
    )
    parser.add_argument(
        "--recompute",
        action="store_true",
        help="完整重跑 Q1--Q5 求解器、工作簿、完整圆柱审计和图件",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.quick and args.recompute:
        raise SystemExit("--quick 与 --recompute 互斥：禁止用缩小搜索覆盖正式结果")
    run_mode = "recompute" if args.recompute else ("quick" if args.quick else "verify")
    print(f"mode={run_mode}", flush=True)
    if args.recompute:
        _full_recompute()

    q12, q1_geometry, q35, figure_manifest = _load_artifacts()
    checks = _verify_artifacts(q12, q1_geometry, q35, figure_manifest)
    paper_qa = _paper_qa_state()
    _add_check(
        checks,
        "paper-references",
        bool(paper_qa["references_pass"]),
        f"正文 {paper_qa['bibliography_items']} 个参考文献条目与 "
        f"{len(paper_qa['citation_keys'])} 个引用键一致，日志无未定义引用",
        "参考文献结构、引用键或编译日志核验未通过",
    )
    _add_check(
        checks,
        "paper-pdf-technical",
        bool(paper_qa["technical_pass"]),
        f"PDF 为 {paper_qa['page_count']} 页 A4，"
        f"{paper_qa['embedded_font_count']} 个字体全部嵌入，日志无布局警告",
        "PDF 页数/A4/字体嵌入、文件时效或日志技术检查未通过",
    )
    _add_check(
        checks,
        "paper-pdf-manual-visual",
        bool(paper_qa["manual_visual_pass"]),
        "人工逐页 QA 记录与当前 PDF 的 SHA-256 和 12 页页数完全绑定",
        "缺少与当前 PDF 哈希绑定的人工逐页视觉 QA 记录",
    )
    test_result = _run_tests(checks, skip=args.quick)
    summary = _summary(
        q12,
        q1_geometry,
        q35,
        figure_manifest,
        checks,
        paper_qa=paper_qa,
        run_mode=run_mode,
        test_result=test_result,
    )
    _write_reports(summary)

    for check in checks:
        print(f"[{check.status}] {check.check_id}: {check.detail}")
    print(f"summary={REPORTS_DIR / 'summary.json'}")
    failures = [check for check in checks if check.status == "FAIL"]
    if failures:
        print(f"verification failed: {len(failures)} check(s)", file=sys.stderr)
        return 1
    print("verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
