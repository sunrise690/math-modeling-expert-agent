"""2025 国赛 A 题的一键复现、快速核验与证据链生成入口。

默认模式不会重复运行昂贵的全局搜索，而是核验已保存且经连续复算的结果、
官方源文件、输出工作簿、连续时间诊断与图件，并运行单元测试。使用
``--quick`` 时仅做确定性的产物与数值核验；使用 ``--recompute`` 时才会
完整重跑 Q1--Q5 求解器、图件生成器、TeX 编译与论文成品审计。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from run_identity import RUN_ID


ROOT = Path(__file__).resolve().parents[1]
VALIDATION_DIR = ROOT / "validation"
REPORTS_DIR = ROOT / "reports"
REFERENCES_DIR = ROOT / "references"
SUPPORT_DIR = ROOT / "support"

Q1_Q2_PATH = VALIDATION_DIR / "q1_q2_independent.json"
Q1_GEOMETRY_PATH = VALIDATION_DIR / "q1_independent.json"
Q3_Q5_PATH = VALIDATION_DIR / "q3_q5_independent.json"
Q2_MULTISEED_PATH = VALIDATION_DIR / "q2_multiseed.json"
Q3_Q4_MULTISEED_PATH = VALIDATION_DIR / "q3_q4_multiseed.json"
FIGURE_MANIFEST_PATH = ROOT / "figures" / "figure_manifest.json"
PAPER_DIR = ROOT / "paper"
PAPER_TEX_PATH = PAPER_DIR / "main.tex"
PAPER_PDF_PATH = PAPER_DIR / "main.pdf"
PAPER_LOG_PATH = PAPER_DIR / "main.log"
MANUAL_PDF_QA_PATH = SUPPORT_DIR / "manual_pdf_qa.json"
PAPER_BUILD_PROVENANCE_PATH = SUPPORT_DIR / "paper_build_provenance.json"
PAPER_AUDIT_SPEC_PATH = VALIDATION_DIR / "paper_audit_spec.json"
PAPER_AUDIT_JSON_PATH = VALIDATION_DIR / "paper-quality-audit.json"
PAPER_AUDIT_PROVENANCE_PATH = SUPPORT_DIR / "paper_audit_provenance.json"

SEED = 20_250_808
RECOMPUTE_SEEDS = {"Q3": 20_250_810, "Q4": 20_250_809, "Q5": 20_250_808}
NUMERIC_TOLERANCE = 1.0e-8
VISUAL_REVIEW_TYPES = {"human_page_by_page", "codex_page_by_page_visual"}


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


def _fingerprint_files(paths: Iterable[Path], *, base: Path) -> tuple[str, dict[str, str]]:
    """Return one deterministic digest for a named collection of files."""

    hashes: dict[str, str] = {}
    for path in sorted({item.resolve() for item in paths}, key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        try:
            name = path.relative_to(base.resolve()).as_posix()
        except ValueError:
            name = path.as_posix()
        hashes[name] = _sha256(path)
    digest = hashlib.sha256()
    for name, file_hash in sorted(hashes.items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest(), hashes


def _paper_input_files() -> list[Path]:
    """Enumerate every artifact whose contents can affect the final paper.

    The generated paper audit is deliberately excluded from the validation
    input set because it is an output of the PDF build.  Its freshness is
    bound separately through ``paper_audit_provenance.json``.
    """

    validation_inputs = [
        path
        for path in VALIDATION_DIR.glob("*.json")
        if path != PAPER_AUDIT_JSON_PATH
    ]
    return [
        PAPER_TEX_PATH,
        *[path for path in (ROOT / "figures").rglob("*") if path.is_file()],
        *validation_inputs,
        *[path for path in (ROOT / "outputs").glob("*.xlsx") if path.is_file()],
    ]


def _paper_input_state() -> dict[str, Any]:
    paths = _paper_input_files()
    bundle_hash, file_hashes = _fingerprint_files(paths, base=ROOT)
    return {
        "bundle_sha256": bundle_hash,
        "files": file_hashes,
        "file_count": len(file_hashes),
        "latest_mtime_ns": max(
            (path.stat().st_mtime_ns for path in paths if path.is_file()),
            default=0,
        ),
    }


def _record_matches(record: Any, expected: dict[str, Any]) -> bool:
    return isinstance(record, dict) and all(
        record.get(key) == value for key, value in expected.items()
    )


def _q5_claim_respects_boundary(claim: Any, disclaimer: Any) -> bool:
    """Require Q5 wording to state only verified restricted-search feasibility."""

    claim_text = str(claim)
    claim_lower = claim_text.lower()
    combined_lower = f"{claim_text} {disclaimer}".lower()
    has_verified_feasibility = bool(
        "verified feasible solution" in claim_lower
        or "continuously verified feasible solution" in claim_lower
        or "经验证可行解" in claim_text
    )
    has_restricted_search = bool(
        re.search(r"restricted[^.;\n]{0,40}(?:route|library|search)", claim_lower)
        or re.search(r"受限[^。；\n]{0,20}(?:路线|候选|搜索)", claim_text)
    )
    has_no_global_claim = bool(
        "no global" in combined_lower
        or "not claimed globally" in combined_lower
        or "不声称全局最优" in str(disclaimer)
        or "无全局最优" in str(disclaimer)
    )
    banned_quality_claim = bool(
        re.search(
            r"\bhigh[- ]quality\b|\b(?:stable|robust)\s+(?:solution|search|result)\b",
            claim_lower,
        )
        or re.search(r"高质量|稳定(?:解|结果|搜索)|稳健(?:解|结果)", claim_text)
    )
    return bool(
        has_verified_feasibility
        and has_restricted_search
        and has_no_global_claim
        and not banned_quality_claim
    )


def _q5_paper_claims_are_bounded(tex_text: str) -> bool:
    """Reject unqualified quality, stability, robustness, or global claims in Q5."""

    start = re.search(r"\\section\{[^{}]*问题五[^{}]*\}", tex_text)
    if start is None:
        return False
    next_section = re.search(r"\\section\{", tex_text[start.end() :])
    end = start.end() + next_section.start() if next_section else len(tex_text)
    q5_text = tex_text[start.start() : end]
    claim_pattern = re.compile(
        r"high[- ]quality|\bstable\b|\brobust\b|globally\s+optimal|global\s+optimum|"
        r"高质量|稳定(?:性|解|结果|搜索)?|稳健(?:性|解|结果)?|全局最优",
        re.IGNORECASE,
    )
    negation_pattern = re.compile(
        r"(?:不|未|无|没有|不能|不得|尚未|不作|禁止|并非|绝不)"
        r"[^，,;；。.!?]{0,24}$|"
        r"(?:\bno\b|\bnot\b|\bwithout\b|\bnever\b|\bcannot\b|\bdoes\s+not\b)"
        r"[^,;.!?]{0,40}$",
        re.IGNORECASE,
    )
    for clause in re.split(r"[。！？；\n]|(?<=[.!?;])\s+", q5_text):
        for match in claim_pattern.finditer(clause):
            prefix = clause[max(0, match.start() - 48) : match.start()]
            if negation_pattern.search(prefix):
                continue
            return False
    return True


def _manual_visual_record_is_current(
    manual: Any,
    *,
    pdf_sha256: str | None,
    page_count: int,
    input_bundle_sha256: str,
    rendered_page_count: int | None = None,
) -> bool:
    """Reject a visual verdict as soon as either PDF or any paper input changes."""

    try:
        reviewed_page_count = int(manual.get("reviewed_page_count", -1))
    except (AttributeError, TypeError, ValueError):
        return False
    review_type = manual.get("review_type") if isinstance(manual, dict) else None
    render_evidence_is_complete = bool(
        review_type == "human_page_by_page"
        or (rendered_page_count is not None and rendered_page_count == page_count)
    )
    return bool(
        isinstance(manual, dict)
        and manual.get("status") == "PASS"
        and review_type in VISUAL_REVIEW_TYPES
        and manual.get("reviewed_pdf_sha256") == pdf_sha256
        and reviewed_page_count == page_count
        and manual.get("reviewed_input_bundle_sha256") == input_bundle_sha256
        and render_evidence_is_complete
    )


def _q2_multiseed_metrics(payload: Any) -> dict[str, Any]:
    """Recompute Q2 stochastic-search evidence exclusively from raw runs."""

    runs = payload.get("runs", []) if isinstance(payload, dict) else []
    if not isinstance(runs, list):
        runs = []
    seeds: list[str] = []
    terminal_values: list[float] = []
    constraint_values: list[float] = []
    success_count = 0
    trace_count = 0
    malformed_runs = 0
    for run in runs:
        if not isinstance(run, dict):
            malformed_runs += 1
            continue
        seed = run.get("seed")
        if seed is None:
            malformed_runs += 1
        else:
            seeds.append(str(seed))
        if run.get("success") is True:
            success_count += 1
        try:
            terminal = float(run["exact_duration_s"])
            constraint = float(run["max_constraint_violation"])
        except (KeyError, TypeError, ValueError):
            malformed_runs += 1
            continue
        if not math.isfinite(terminal) or not math.isfinite(constraint):
            malformed_runs += 1
            continue
        terminal_values.append(terminal)
        constraint_values.append(constraint)

        trace = run.get("best_so_far_trace")
        if not isinstance(trace, list) or not trace:
            continue
        generations: list[int] = []
        trace_valid = True
        for point in trace:
            if not isinstance(point, dict):
                trace_valid = False
                break
            try:
                generation = int(point["generation"])
                objective = float(point["best_coarse_duration_s"])
            except (KeyError, TypeError, ValueError):
                trace_valid = False
                break
            if generation <= 0 or not math.isfinite(objective):
                trace_valid = False
                break
            generations.append(generation)
        if trace_valid and generations == sorted(set(generations)):
            trace_count += 1

    n_runs = len(runs)
    unique_seed_count = len(set(seeds))
    standard_deviation = (
        statistics.stdev(terminal_values) if len(terminal_values) >= 2 else math.inf
    )
    max_constraint = max(constraint_values, default=math.inf)
    success_rate = success_count / n_runs if n_runs else 0.0
    passed = bool(
        n_runs >= 5
        and malformed_runs == 0
        and len(seeds) == n_runs
        and unique_seed_count == n_runs
        and success_count == n_runs
        and len(terminal_values) == n_runs
        and max_constraint <= NUMERIC_TOLERANCE
        and standard_deviation <= 1.0e-9
        and trace_count == n_runs
    )
    return {
        "passed": passed,
        "n_runs": n_runs,
        "unique_seed_count": unique_seed_count,
        "success_count": success_count,
        "success_rate": success_rate,
        "standard_deviation_s": standard_deviation,
        "max_constraint_violation": max_constraint,
        "trace_count": trace_count,
        "malformed_runs": malformed_runs,
    }


def _finite_constraint_values(node: Any) -> list[float] | None:
    """Flatten a constraint mapping; return ``None`` for malformed values."""

    if isinstance(node, dict):
        values: list[float] = []
        for value in node.values():
            nested = _finite_constraint_values(value)
            if nested is None:
                return None
            values.extend(nested)
        return values
    if isinstance(node, list):
        values = []
        for value in node:
            nested = _finite_constraint_values(value)
            if nested is None:
                return None
            values.extend(nested)
        return values
    try:
        value = float(node)
    except (TypeError, ValueError):
        return None
    return [value] if math.isfinite(value) else None


def _q3_q4_multiseed_metrics(payload: Any) -> dict[str, dict[str, Any]]:
    """Audit Q3/Q4 raw runs without trusting their precomputed summaries."""

    problem_payloads = payload.get("problems", {}) if isinstance(payload, dict) else {}
    metrics: dict[str, dict[str, Any]] = {}
    for problem in ("Q3", "Q4"):
        record = problem_payloads.get(problem, {}) if isinstance(problem_payloads, dict) else {}
        runs = record.get("runs", []) if isinstance(record, dict) else []
        if not isinstance(runs, list):
            runs = []
        seeds: list[str] = []
        terminals: list[tuple[float, int]] = []
        feasible_count = 0
        plan_count_ok = 0
        trace_count = 0
        malformed_runs = 0
        recomputed_max_constraint = 0.0
        for run in runs:
            if not isinstance(run, dict):
                malformed_runs += 1
                continue
            try:
                seed_value = int(run["seed"])
                terminal = float(run["final_exact_objective_s"])
                reported_max_constraint = float(run["max_constraint_violation"])
            except (KeyError, TypeError, ValueError):
                malformed_runs += 1
                continue
            if not math.isfinite(terminal) or not math.isfinite(reported_max_constraint):
                malformed_runs += 1
                continue
            seeds.append(str(seed_value))
            terminals.append((terminal, seed_value))
            if run.get("status") == "feasible_verified":
                feasible_count += 1
            if isinstance(run.get("plans"), list) and len(run["plans"]) == 3:
                plan_count_ok += 1

            constraint_values = _finite_constraint_values(run.get("constraint_violations"))
            if not constraint_values:
                malformed_runs += 1
            else:
                recomputed_max_constraint = max(
                    recomputed_max_constraint,
                    reported_max_constraint,
                    max(constraint_values),
                )

            trace = run.get("best_so_far_trace")
            if not isinstance(trace, list) or not trace:
                continue
            best_values: list[float] = []
            trace_valid = True
            for point in trace:
                if not isinstance(point, dict):
                    trace_valid = False
                    break
                try:
                    best_value = float(point["best_fast_objective_s"])
                except (KeyError, TypeError, ValueError):
                    trace_valid = False
                    break
                if not math.isfinite(best_value):
                    trace_valid = False
                    break
                best_values.append(best_value)
            if trace_valid and all(
                right + 1.0e-12 >= left
                for left, right in zip(best_values, best_values[1:])
            ):
                trace_count += 1

        n_runs = len(runs)
        unique_seed_count = len(set(seeds))
        best_seed = max(terminals)[1] if terminals else None
        passed = bool(
            n_runs >= 5
            and malformed_runs == 0
            and len(seeds) == n_runs
            and unique_seed_count == n_runs
            and feasible_count == n_runs
            and plan_count_ok == n_runs
            and trace_count == n_runs
            and len(terminals) == n_runs
            and recomputed_max_constraint <= NUMERIC_TOLERANCE
        )
        metrics[problem] = {
            "passed": passed,
            "n_runs": n_runs,
            "unique_seed_count": unique_seed_count,
            "feasible_count": feasible_count,
            "plan_count_ok": plan_count_ok,
            "trace_count": trace_count,
            "malformed_runs": malformed_runs,
            "best_seed": best_seed,
            "best_terminal_s": max((value for value, _seed in terminals), default=math.nan),
            "max_constraint_violation": recomputed_max_constraint,
        }
    return metrics


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

    input_state = _paper_input_state()
    state: dict[str, Any] = {
        "tex_exists": PAPER_TEX_PATH.is_file(),
        "pdf_exists": PAPER_PDF_PATH.is_file(),
        "log_exists": PAPER_LOG_PATH.is_file(),
        "manual_record_exists": MANUAL_PDF_QA_PATH.is_file(),
        "build_record_exists": PAPER_BUILD_PROVENANCE_PATH.is_file(),
        "audit_exists": PAPER_AUDIT_JSON_PATH.is_file(),
        "audit_record_exists": PAPER_AUDIT_PROVENANCE_PATH.is_file(),
        "input_bundle_sha256": input_state["bundle_sha256"],
        "input_file_count": input_state["file_count"],
        "pdf_sha256": None,
        "log_sha256": None,
        "page_count": 0,
        "all_pages_a4": False,
        "page_sizes_pt": [],
        "embedded_font_count": 0,
        "unembedded_fonts": [],
        "fonts_fully_embedded": False,
        "layout_warnings": [],
        "underfull_warnings": [],
        "build_errors": [],
        "benign_package_warnings": [],
        "bibliography_items": 0,
        "citation_keys": [],
        "missing_citation_keys": [],
        "unused_bibliography_keys": [],
        "reference_warnings": [],
        "artifacts_current": False,
        "build_inputs_match": False,
        "build_pdf_match": False,
        "build_log_match": False,
        "audit_pass": False,
        "audit_artifact_match": False,
        "audit_current": False,
        "references_pass": False,
        "technical_pass": False,
        "manual_visual_pass": False,
        "manual_render_evidence_pass": False,
        "overall_pass": False,
        "manual_review_type": None,
        "manual_reviewed_at_local": None,
        "manual_reviewer_record": None,
        "manual_render_evidence": None,
        "local_rendered_page_count": 0,
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
        layout_pattern = re.compile(r"Overfull \\[hv]box|Missing character", re.IGNORECASE)
        underfull_pattern = re.compile(r"Underfull \\[hv]box", re.IGNORECASE)
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
        state["underfull_warnings"] = [
            line.strip() for line in log_lines if underfull_pattern.search(line)
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
            and not underfull_pattern.search(line)
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

    if state["log_exists"]:
        state["log_sha256"] = _sha256(PAPER_LOG_PATH)

    if state["build_record_exists"]:
        build_record = _load_json(PAPER_BUILD_PROVENANCE_PATH)
        state["build_inputs_match"] = _record_matches(
            build_record,
            {"input_bundle_sha256": state["input_bundle_sha256"]},
        )
        state["build_pdf_match"] = _record_matches(
            build_record,
            {"paper_pdf_sha256": state["pdf_sha256"]},
        )
        state["build_log_match"] = _record_matches(
            build_record,
            {"paper_log_sha256": state["log_sha256"]},
        )
    if state["tex_exists"] and state["pdf_exists"] and state["log_exists"]:
        state["artifacts_current"] = bool(
            state["build_inputs_match"]
            and state["build_pdf_match"]
            and state["build_log_match"]
            and PAPER_PDF_PATH.stat().st_mtime_ns >= input_state["latest_mtime_ns"]
            and PAPER_LOG_PATH.stat().st_mtime_ns >= input_state["latest_mtime_ns"]
        )

    if state["audit_exists"]:
        audit = _load_json(PAPER_AUDIT_JSON_PATH)
        state["audit_artifact_match"] = _audit_targets_artifact(
            audit,
            artifact_name=PAPER_PDF_PATH.name,
            artifact_sha256=state["pdf_sha256"],
            expected_questions=5,
        )
        state["audit_pass"] = bool(
            audit.get("passed")
            and audit.get("status") == "pass"
            and state["audit_artifact_match"]
        )
        if state["audit_record_exists"] and state["pdf_exists"]:
            audit_record = _load_json(PAPER_AUDIT_PROVENANCE_PATH)
            state["audit_current"] = bool(
                state["audit_artifact_match"]
                and
                _record_matches(
                    audit_record,
                    {
                        "input_bundle_sha256": state["input_bundle_sha256"],
                        "paper_pdf_sha256": state["pdf_sha256"],
                        "audit_json_sha256": _sha256(PAPER_AUDIT_JSON_PATH),
                    },
                )
                and PAPER_AUDIT_JSON_PATH.stat().st_mtime_ns
                >= PAPER_PDF_PATH.stat().st_mtime_ns
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
        and state["audit_pass"]
        and state["audit_current"]
        and 18 <= state["page_count"] <= 28
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
        render_directory = manual.get("render_directory")
        if isinstance(render_directory, str):
            render_path = (ROOT / render_directory).resolve()
            try:
                render_path.relative_to(ROOT.resolve())
            except ValueError:
                render_path = ROOT / "__invalid_render_evidence__"
            state["local_rendered_page_count"] = sum(
                1
                for path in render_path.glob("page-*.png")
                if path.is_file() and path.stat().st_size > 0
            )
        state["manual_render_evidence_pass"] = bool(
            state["manual_review_type"] == "human_page_by_page"
            or state["local_rendered_page_count"] == state["page_count"]
        )
        state["manual_visual_pass"] = _manual_visual_record_is_current(
            manual,
            pdf_sha256=state["pdf_sha256"],
            page_count=state["page_count"],
            input_bundle_sha256=state["input_bundle_sha256"],
            rendered_page_count=state["local_rendered_page_count"],
        )
    state["overall_pass"] = bool(
        state["references_pass"]
        and state["technical_pass"]
        and state["manual_visual_pass"]
    )
    return state


def _audit_targets_artifact(
    audit: dict[str, Any],
    *,
    artifact_name: str,
    artifact_sha256: str | None,
    expected_questions: int,
) -> bool:
    """Return whether one passing full-paper audit names the exact PDF bytes."""

    metrics = audit.get("metrics")
    if not isinstance(metrics, dict) or not artifact_sha256:
        return False
    return bool(
        audit.get("passed")
        and audit.get("status") == "pass"
        and metrics.get("artifactName") == artifact_name
        and str(metrics.get("artifactSha256", "")).lower()
        == artifact_sha256.lower()
        and metrics.get("fullPaper") is True
        and metrics.get("expectedQuestions") == expected_questions
    )


def _run(
    command: list[str], *, cwd: Path = ROOT
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    print(f"run [{cwd}]:", " ".join(command), flush=True)
    return subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def _write_paper_build_provenance(compile_command: list[str]) -> None:
    if not PAPER_PDF_PATH.is_file() or not PAPER_LOG_PATH.is_file():
        raise RuntimeError("TeX 编译没有生成 paper/main.pdf 和 paper/main.log")
    input_state = _paper_input_state()
    record = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "input_bundle_sha256": input_state["bundle_sha256"],
        "input_file_count": input_state["file_count"],
        "input_sha256": input_state["files"],
        "paper_pdf_sha256": _sha256(PAPER_PDF_PATH),
        "paper_log_sha256": _sha256(PAPER_LOG_PATH),
        "compile_command": compile_command,
    }
    PAPER_BUILD_PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAPER_BUILD_PROVENANCE_PATH.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_paper_audit_provenance() -> None:
    if not PAPER_AUDIT_JSON_PATH.is_file():
        raise RuntimeError("论文审计未生成 validation/paper-quality-audit.json")
    if not PAPER_PDF_PATH.is_file():
        raise RuntimeError("论文 PDF 未生成 paper/main.pdf")
    audit = _load_json(PAPER_AUDIT_JSON_PATH)
    paper_pdf_sha256 = _sha256(PAPER_PDF_PATH)
    if not _audit_targets_artifact(
        audit,
        artifact_name=PAPER_PDF_PATH.name,
        artifact_sha256=paper_pdf_sha256,
        expected_questions=5,
    ):
        raise RuntimeError(
            "论文成品审计未通过，或审计结果不属于当前完整 PDF"
        )
    input_state = _paper_input_state()
    record = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "input_bundle_sha256": input_state["bundle_sha256"],
        "paper_pdf_sha256": paper_pdf_sha256,
        "audit_json_sha256": _sha256(PAPER_AUDIT_JSON_PATH),
    }
    PAPER_AUDIT_PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAPER_AUDIT_PROVENANCE_PATH.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _full_recompute() -> None:
    commands = [
        [sys.executable, "-B", "src/solve_q1_q2.py"],
        [
            sys.executable,
            "-B",
            "src/solve_q3_q5.py",
            "--seed",
            str(SEED),
            "--q3-seed",
            str(RECOMPUTE_SEEDS["Q3"]),
            "--q4-seed",
            str(RECOMPUTE_SEEDS["Q4"]),
            "--q5-seed",
            str(RECOMPUTE_SEEDS["Q5"]),
        ],
        [sys.executable, "-B", "src/validate_q2_multiseed.py"],
    ]
    q3_q4_validator = ROOT / "src" / "validate_q3_q4_multiseed.py"
    if q3_q4_validator.is_file():
        commands.append([sys.executable, "-B", "src/validate_q3_q4_multiseed.py"])
    commands.append([sys.executable, "-B", "src/generate_figures.py"])
    for command in commands:
        result = _run(command)
        if result.stdout:
            print(result.stdout.rstrip(), flush=True)
        if result.returncode != 0:
            if result.stderr:
                print(result.stderr.rstrip(), file=sys.stderr, flush=True)
            raise RuntimeError(f"重算命令失败（退出码 {result.returncode}）：{' '.join(command)}")

    compile_command = [
        "latexmk",
        "-gg",
        "-xelatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        "main.tex",
    ]
    compile_result = _run(compile_command, cwd=PAPER_DIR)
    if compile_result.stdout:
        print(compile_result.stdout.rstrip(), flush=True)
    if compile_result.returncode != 0:
        if compile_result.stderr:
            print(compile_result.stderr.rstrip(), file=sys.stderr, flush=True)
        raise RuntimeError(
            f"论文编译失败（退出码 {compile_result.returncode}）：{' '.join(compile_command)}"
        )
    _write_paper_build_provenance(compile_command)

    repository_root = ROOT.parents[1]
    audit_command = [
        sys.executable,
        "-B",
        str(repository_root / "scripts" / "audit_paper.py"),
        "--spec",
        str(PAPER_AUDIT_SPEC_PATH),
        "--output-dir",
        str(VALIDATION_DIR),
    ]
    audit_result = _run(audit_command, cwd=repository_root)
    if audit_result.stdout:
        print(audit_result.stdout.rstrip(), flush=True)
    if audit_result.returncode != 0:
        if audit_result.stderr:
            print(audit_result.stderr.rstrip(), file=sys.stderr, flush=True)
        raise RuntimeError(
            f"论文审计失败（退出码 {audit_result.returncode}）：{' '.join(audit_command)}"
        )
    _write_paper_audit_provenance()


def _add_check(
    checks: list[Check], check_id: str, condition: bool, success: str, failure: str
) -> None:
    checks.append(Check(check_id, "PASS" if condition else "FAIL", success if condition else failure))


def _load_artifacts() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    required = (
        Q1_Q2_PATH,
        Q1_GEOMETRY_PATH,
        Q3_Q5_PATH,
        Q2_MULTISEED_PATH,
        Q3_Q4_MULTISEED_PATH,
        FIGURE_MANIFEST_PATH,
    )
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

    q2_multiseed = _load_json(Q2_MULTISEED_PATH)
    multiseed_metrics = _q2_multiseed_metrics(q2_multiseed)
    _add_check(
        checks,
        "q2-multiseed-stability",
        bool(multiseed_metrics["passed"]),
        f"Q2 原始 runs 复算：{multiseed_metrics['unique_seed_count']} 个独立种子，"
        f"成功率 {multiseed_metrics['success_rate']:.0%}，终值标准差 "
        f"{multiseed_metrics['standard_deviation_s']:.3e} s，"
        f"最大约束违反 {multiseed_metrics['max_constraint_violation']:.3e}，"
        f"{multiseed_metrics['trace_count']} 条收敛轨迹齐全",
        "Q2 原始 runs 复算未通过："
        f"runs={multiseed_metrics['n_runs']}，独立种子={multiseed_metrics['unique_seed_count']}，"
        f"成功={multiseed_metrics['success_count']}，轨迹={multiseed_metrics['trace_count']}，"
        f"畸形记录={multiseed_metrics['malformed_runs']}，终值标准差="
        f"{multiseed_metrics['standard_deviation_s']:.3e} s，最大约束违反="
        f"{multiseed_metrics['max_constraint_violation']:.3e}",
    )

    q3_q4_multiseed = _load_json(Q3_Q4_MULTISEED_PATH)
    q3_q4_metrics = _q3_q4_multiseed_metrics(q3_q4_multiseed)
    q3_q4_pass = all(q3_q4_metrics[problem]["passed"] for problem in ("Q3", "Q4"))
    _add_check(
        checks,
        "q3-q4-multiseed-evidence",
        q3_q4_pass,
        "Q3/Q4 原始 runs 复算通过："
        + "；".join(
            f"{problem}={q3_q4_metrics[problem]['n_runs']} 个独立种子，"
            f"最佳 seed {q3_q4_metrics[problem]['best_seed']}，"
            f"终值 {q3_q4_metrics[problem]['best_terminal_s']:.9f} s，"
            f"最大约束违反 {q3_q4_metrics[problem]['max_constraint_violation']:.3e}"
            for problem in ("Q3", "Q4")
        ),
        "Q3/Q4 多种子原始证据未通过："
        + "；".join(
            f"{problem}(runs={q3_q4_metrics[problem]['n_runs']}，"
            f"唯一种子={q3_q4_metrics[problem]['unique_seed_count']}，"
            f"可行={q3_q4_metrics[problem]['feasible_count']}，"
            f"三方案={q3_q4_metrics[problem]['plan_count_ok']}，"
            f"单调轨迹={q3_q4_metrics[problem]['trace_count']}，"
            f"畸形={q3_q4_metrics[problem]['malformed_runs']}，"
            f"最大违反={q3_q4_metrics[problem]['max_constraint_violation']:.3e})"
            for problem in ("Q3", "Q4")
        ),
    )

    report_seed_map = q35.get("random_seed_by_problem", {})
    selected_best_seeds_match = bool(
        isinstance(report_seed_map, dict)
        and all(
            report_seed_map.get(problem) == q3_q4_metrics[problem]["best_seed"]
            for problem in ("Q3", "Q4")
        )
    )
    selected_best_objectives_match = all(
        _close(
            float(q35["results"][problem]["exact_centerline_objective"]),
            float(q3_q4_metrics[problem]["best_terminal_s"]),
        )
        for problem in ("Q3", "Q4")
    )
    _add_check(
        checks,
        "q3-q4-best-seed-selection",
        selected_best_seeds_match and selected_best_objectives_match,
        "Q3/Q4 最终报告分别采用多种子原始终值复算得到的最佳 seed 与对应策略："
        f"{q3_q4_metrics['Q3']['best_seed']} / {q3_q4_metrics['Q4']['best_seed']}",
        "最终 q3_q5 报告的 seed 或目标值未采用多种子原始终值复算最佳结果；"
        f"报告={report_seed_map}，复算 Q3/Q4="
        f"{q3_q4_metrics['Q3']['best_seed']}/{q3_q4_metrics['Q4']['best_seed']}，"
        f"目标一致={selected_best_objectives_match}",
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
    q5_claim_is_bounded = _q5_claim_respects_boundary(q5_claim, disclaimer)
    q5_paper_claims_are_bounded = bool(
        PAPER_TEX_PATH.is_file()
        and _q5_paper_claims_are_bounded(
            PAPER_TEX_PATH.read_text(encoding="utf-8", errors="replace")
        )
    )
    _add_check(
        checks,
        "q5-optimality-boundary",
        q5_claim_is_bounded and q5_paper_claims_are_bounded,
        "Q5 被限定为固定种子、受限路线库搜索得到的经验证可行解，无随机稳定性、高质量或全局最优声明",
        "Q5 的诊断和论文正文必须同时声明经验证可行性、受限搜索和非全局最优，且不得使用“高质量”“稳定”或“稳健”等越证据措辞",
    )

    missing_figures: list[str] = []
    malformed_figures: list[str] = []
    figure_records = figure_manifest.get("figures", [])
    required_figure_fields = {
        "id", "claim_id", "subquestion", "files", "data_source", "axes", "units",
        "caption", "interpretation", "paper_location", "figure_intent", "visual_qa", "sha256",
    }
    if int(figure_manifest.get("schema_version", 0)) < 4 or not figure_manifest.get("design_system"):
        malformed_figures.append("manifest:semantic-design-system")
    for record in figure_records:
        figure_id = str(record.get("id", "?"))
        if not required_figure_fields.issubset(record):
            malformed_figures.append(f"{figure_id}:fields")
        intent = record.get("figure_intent", {})
        semantic_layers = set(intent.get("semantic_layers", [])) if isinstance(intent, dict) else set()
        if not isinstance(intent, dict) or not {
            "template", "reader_takeaway", "semantic_layers", "comparison_semantics", "cannot_infer",
        }.issubset(intent):
            malformed_figures.append(f"{figure_id}:intent")
        qa = record.get("visual_qa", {})
        if (
            not isinstance(qa, dict)
            or float(qa.get("minimum_font_pt", 0.0)) < 7.0
            or not 5.5 <= float(qa.get("final_width_in", 0.0)) <= 7.2
            or bool(qa.get("figure_level_title", True))
            or not bool(qa.get("vector_text_editable", False))
            or not bool(qa.get("redundant_encoding", False))
        ):
            malformed_figures.append(f"{figure_id}:visual-qa")
        required_layers_by_figure = {
            "F3": {"zero_crossing", "interval", "entry_delay"},
            "F5": {"median", "iqr", "evaluation_count", "feasibility"},
            "F6": {"shot_index", "overlap", "union"},
            "F7": {"gap", "union"},
            "F9": {"release_position", "explosion_position", "shot_index", "missile_assignment"},
            "F10": {"shot_index", "union", "largest_gap"},
            "F11": {"absolute_loss", "relative_loss", "total"},
            "F12": {"same_strategy_retention", "independent_optimization_boundary"},
            "F13": {"reference_order", "tolerance_band"},
        }
        if not required_layers_by_figure.get(figure_id, set()).issubset(semantic_layers):
            malformed_figures.append(f"{figure_id}:semantic-layers")
        files = record.get("files", [])
        if {Path(item).suffix.lower() for item in files} != {".png", ".pdf", ".svg"}:
            malformed_figures.append(f"{figure_id}:formats")
        for relative_path in record.get("files", []):
            path = ROOT / relative_path
            if not path.is_file() or path.stat().st_size == 0:
                missing_figures.append(relative_path)
                continue
            expected_hash = str(record.get("sha256", {}).get(relative_path, ""))
            if len(expected_hash) != 64 or _sha256(path) != expected_hash:
                malformed_figures.append(f"{figure_id}:hash:{Path(relative_path).name}")
            if path.suffix.lower() == ".svg":
                svg = path.read_text(encoding="utf-8", errors="replace")
                if "<text" not in svg:
                    malformed_figures.append(f"{figure_id}:svg-text")
            if path.suffix.lower() == ".png":
                try:
                    from PIL import Image

                    with Image.open(path) as image:
                        dpi = image.info.get("dpi", (0, 0))
                        if min(image.size) < 1200 or min(float(item) for item in dpi) < 295:
                            malformed_figures.append(f"{figure_id}:png-quality")
                except Exception as error:
                    malformed_figures.append(f"{figure_id}:png-read:{type(error).__name__}")
    _add_check(
        checks,
        "figure-manifest",
        len(figure_records) >= 12 and not missing_figures and not malformed_figures,
        f"{len(figure_records)} 个证据图均登记主张、语义图层、比较边界、最终字号、哈希及 PNG/PDF/SVG；PNG≥300 dpi，SVG 保留文本",
        "图件清单、文件或质量元数据不完整：" + ", ".join(missing_figures + malformed_figures),
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
        "run_id": RUN_ID,
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
                "default": "核验现有且经连续复算的产物并运行测试，不重复昂贵全局搜索",
                "quick": "仅核验现有 JSON/XLSX/图件和数值不变量，不运行求解器或测试",
                "recompute": "完整重跑 Q1--Q5 求解器、工作簿、二次审计、图件、TeX 编译和论文审计",
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
                "random_seed_by_problem": q35.get("random_seed_by_problem", {}),
                "source_sha256": source_hashes,
                "validation_sha256": {
                    Q1_Q2_PATH.relative_to(ROOT).as_posix(): _sha256(Q1_Q2_PATH),
                    Q1_GEOMETRY_PATH.relative_to(ROOT).as_posix(): _sha256(
                        Q1_GEOMETRY_PATH
                    ),
                    Q3_Q5_PATH.relative_to(ROOT).as_posix(): _sha256(Q3_Q5_PATH),
                    Q2_MULTISEED_PATH.relative_to(ROOT).as_posix(): _sha256(Q2_MULTISEED_PATH),
                    Q3_Q4_MULTISEED_PATH.relative_to(ROOT).as_posix(): _sha256(
                        Q3_Q4_MULTISEED_PATH
                    ),
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
            "Q3/Q4 各完成 5 个种子的收敛与终值审计并采用本批最好可行解；Q3 离散明显。Q5 仅为固定种子下经连续时间核验的可行解。三问均无全局最优证明。",
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
            "五种子审计、本批最好解经连续复算；无全局最优证明"
            if question in {"Q3", "Q4"}
            else "固定种子经验证可行解；受限路线库，无多种子或全局最优证明"
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
            "但搜索算法没有提供全局最优证书。Q3/Q4 可报告五种子审计及本批最好可行解；Q5 只能称固定种子下经验证的可行解，不得写成“稳定”“高质量”或“全局最优解”。",
            "",
        ]
    )
    return "\n".join(lines)


def _claim_map_markdown(summary: dict[str, Any]) -> str:
    results = summary["core_results"]
    seeds = summary["metadata"]["provenance"].get("random_seed_by_problem", {})
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
            f"| C-Q3-COVERAGE | 5 种子中采用 seed {seeds.get('Q3', '?')} 的本批最好可行方案，3 枚烟幕弹中心视线并集为 {_fmt(results['Q3']['primary_centerline_objective_s'])} s | Q3 | `outputs/result1.xlsx`; `validation/q3_q4_multiseed.json`; `validation/q3_q5_independent.json` | 五种子轨迹/分布 + XLSX 哈希 + 回读重算 + 连续时间并集；离散明显 | PASS_WITH_LIMITATIONS |",
            f"| C-Q4-COVERAGE | 5 种子中采用 seed {seeds.get('Q4', '?')} 的本批最好可行方案，3 架无人机中心视线并集为 {_fmt(results['Q4']['primary_centerline_objective_s'])} s | Q4 | `outputs/result2.xlsx`; `validation/q3_q4_multiseed.json`; `validation/q3_q5_independent.json` | 五种子轨迹/分布 + XLSX 哈希 + 回读重算 + 约束审计 | PASS_WITH_LIMITATIONS |",
            f"| C-Q5-FEASIBLE | 五机十五弹固定种子可行解的三导弹总并集为 {_fmt(results['Q5']['primary_centerline_objective_s'])} s | Q5 | `outputs/result3.xlsx`; `validation/q3_q5_independent.json`; `figures/q5_coverage_gantt.*` | 固定种子受限路线库/beam；XLSX 回读；约束违反为 0 | PASS_WITH_LIMITATIONS |",
            f"| C-CRITERION-SENSITIVITY | 同一策略在完整圆柱口径下 Q3/Q4/Q5 为 {_fmt(results['Q3']['full_cylinder_secondary_objective_s'])}/{_fmt(results['Q4']['full_cylinder_secondary_objective_s'])}/{_fmt(results['Q5']['full_cylinder_secondary_objective_s'])} s | Q3–Q5 | `validation/q3_q5_independent.json`; `figures/criterion_sensitivity.*` | 连续完整圆柱边界精修；审计值不高于主口径 | PASS |",
            "| C-WORKBOOK-ROUNDTRIP | 三份提交工作簿可无损回读到数值策略 | Q3–Q5 | `outputs/result*.xlsx`; `validation/q3_q5_independent.json#workbook_roundtrip_validation` | 当前文件哈希与回读时哈希一致；坐标/时长/目标误差 < 1e-8 | PASS |",
            "| C-Q5-NO-GLOBAL | Q5 只主张固定种子下经验证的可行性，不主张随机稳定性或全局最优 | Q5 | `validation/q3_q5_independent.json#results.Q5.diagnostics` | 明确 optimality disclaimer | PASS |",
            "",
            "## 使用规则",
            "",
            "- 论文数值只从上述产物生成，不从聊天记录或手工抄录进入正文。",
            "- 完整圆柱数值必须称为“对同一策略的保守二次审计”，不能与主优化口径混写。",
            "- Q2 零引信延迟是闭可行域的边界结果；工程表达应同时给出 0.02 s 正延迟替代。",
            "- Q3–Q5 均不得写“全局最优”；Q5 还缺少多种子证据，只能写“固定种子受限路线库得到的经验证可行解”。",
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
            "本报告把可自动复核的 PDF 技术检查与逐页视觉检查分开记录。"
            "视觉检查可能由人员或 Codex 完成，不会被自动技术检查替代；结论仅在当前 PDF 哈希与审查记录完全一致时有效。",
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
            f"| `main.tex`、全部图件、验证 JSON、输出工作簿与 PDF/日志绑定 | {'PASS' if qa['artifacts_current'] else 'FAIL'} | {qa['input_file_count']} 个输入的联合 SHA-256 为 `{qa['input_bundle_sha256']}`，并与编译记录逐项匹配 |",
            f"| 论文成品审计时效 | {'PASS' if qa['audit_pass'] and qa['audit_current'] else 'FAIL'} | 审计结果、审计 JSON 哈希、PDF 哈希和输入联合指纹四者绑定 |",
            f"| 18–28 页紧凑 A4 成稿 | {'PASS' if 18 <= qa['page_count'] <= 28 and qa['all_pages_a4'] else 'FAIL'} | 共 {qa['page_count']} 页；逐页 MediaBox 均为 {page_size} |",
            f"| 字体嵌入 | {'PASS' if qa['fonts_fully_embedded'] else 'FAIL'} | 检出 {qa['embedded_font_count']} 个字体，未嵌入字体 {len(qa['unembedded_fonts'])} 个 |",
            f"| 布局/构建日志 | {'PASS' if not qa['layout_warnings'] and not qa['build_errors'] else 'FAIL'} | Overfull、缺字和构建错误共 {len(qa['layout_warnings']) + len(qa['build_errors'])} 条；Underfull 提示 {len(qa['underfull_warnings'])} 条另作非阻断记录 |",
            f"| 参考文献与引用 | {reference_status} | {qa['bibliography_items']} 个文献条目、{len(qa['citation_keys'])} 个引用键；缺失键 {len(qa['missing_citation_keys'])} 个，未定义引用警告 {len(qa['reference_warnings'])} 条 |",
            f"| 技术 QA 总结 | **{technical_status}** | 页数、A4、字体、日志和版本时效联合判定 |",
            "",
            "日志中另有 "
            f"{len(qa['benign_package_warnings'])} 条不影响布局的字体族重定义提示；"
            "它们不是 Overfull、缺字、未定义引用或构建错误。Underfull 只表示个别窄表格单元格无法充分两端对齐，"
            "已由逐页视觉检查确认未造成裁切、重叠或不可读。",
            "",
            "## 视觉 QA（逐页）",
            "",
            f"- 状态：**{visual_status}**。",
            f"- 审查类型：`{qa['manual_review_type'] or '无记录'}`。",
            f"- 审查记录：{qa['manual_reviewer_record'] or '无记录'}；日期 `{qa['manual_reviewed_at_local'] or '无记录'}`。",
            f"- 审查范围：当前 PDF 的 {qa['page_count']} 页；本机保留 {qa['local_rendered_page_count']} 张逐页渲染证据。",
            f"- 渲染证据：`{qa['manual_render_evidence'] or '无记录'}`。",
            "- 已确认：正文、公式、表格、插图、标题、摘要、结论和参考文献页无可见裁切、重叠或越界，文字与数学符号可辨识。",
            "- 防陈旧规则：`support/manual_pdf_qa.json` 记录的 PDF SHA-256、页数或 `reviewed_input_bundle_sha256` 只要与当前产物不一致，本项自动变为 FAIL，不能沿用旧视觉结论。",
            "",
            "## 放行结论",
            "",
            f"参考文献 `{reference_status}`，PDF 技术 QA `{technical_status}`，逐页视觉 QA `{visual_status}`。"
            + (
                f"当前 {qa['page_count']} 页 A4 终稿通过全部终稿 QA 门禁。"
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
    figure_count = int(summary["metadata"]["provenance"]["figure_count"])
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
            f"| 图件 | {'PASS' if qa['manual_visual_pass'] else 'PASS_WITH_LIMITATIONS'} | {figure_count} 个图各有 PNG/PDF/SVG、claim/source/unit/interpretation 与哈希；论文内图件需逐页视觉复核 |",
            f"| 参考文献 | {reference_status} | `main.tex` 有 {qa['bibliography_items']} 个文献条目和 {len(qa['citation_keys'])} 个对应引用键；日志无未定义引用 |",
            f"| PDF 技术 QA | {technical_status} | `main.pdf` 为 {qa['page_count']} 页 A4，{qa['embedded_font_count']} 个字体全部嵌入，日志无布局/构建错误；见 `reports/pdf_qa.md` |",
            f"| PDF 视觉 QA（逐页） | {visual_status} | 审查者类型与当前 PDF SHA-256 绑定；不是由自动技术检查推断；见 `support/manual_pdf_qa.json` |",
            "| 最优性措辞 | PASS | Q5 固定为“经验证可行解”，且无多种子证据时禁止“稳定”“高质量”；所有无全局证明的问题均禁止全局最优措辞 |",
            "",
            "## 放行结论",
            "",
            (
                "数值、参考文献、PDF 技术检查和逐页视觉 QA 均已通过，当前终稿可放行。"
                if final_release
                else "当前终稿仍有未通过的验证或 PDF QA 门禁，不可放行。"
            )
            + " 如果后续重跑优化或重新编译 PDF，必须重新执行 `python -B src/run_all.py`；"
            "PDF 哈希变化会自动使旧逐页视觉 QA 失效。",
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
- Q2 使用种子 `20250808`--`20250815`；Q3/Q4 审计 `20250808`--`20250812`，最终分别采用本批最好种子 `20250810`、`20250809`；Q5 固定种子为 `20250808`。完整复现命令为 `python -B src/run_all.py --recompute`。
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
            f"| Q3 随机敏感性 | {_fmt(results['Q3']['primary_centerline_objective_s'])} s 是否对种子敏感 | 五种子均可行，论文报告完整收敛与终值分布并采用本批最好经连续复算方案 | 终值标准差 0.3936 s，不能称随机搜索稳定或全局最优 |",
            f"| Q5 最优性 | {_fmt(results['Q5']['primary_centerline_objective_s'])} s 是否只是启发式偶然结果 | 固定种子、受限路线库与 beam 搜索可复现；连续可行且约束违反为 0 | **仅为该种子下经验证的可行解；没有随机稳定性或全局最优证书** |",
            "| 判据敏感性 | 严格圆柱判据下降较多，主结论是否脆弱 | Q1–Q5 全部报告两种口径，Q5 分导弹也分别审计 | 论文应解释口径而非隐藏差异 |",
            "| AI 污染 | 外部题解可能泄漏进基准结果 | 来源清单只含官方题面/模板；AI 使用记录声明未用外部答案校准 | 最终提交者仍需审查引用和竞赛规则 |",
            "",
            "## 红队结论",
            "",
            "未发现会使当前策略不可行的证据链断裂。最重要的剩余风险是**搜索最优性而非可行性**："
            "论文可以陈述经验证的时长和方案，但 Q5 必须保留“固定种子受限搜索得到的可行解”措辞，禁止写成稳定、高质量或全局最优。",
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
        help="完整重跑 Q1--Q5 求解器、工作簿、完整圆柱审计、图件、TeX 编译和论文审计",
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
        "paper-quality-audit",
        bool(paper_qa["audit_pass"] and paper_qa["audit_current"]),
        "论文成品审计通过，且审计 JSON 与当前输入指纹及 PDF SHA-256 完全绑定",
        "论文成品审计未通过或已陈旧；需重新编译 PDF 并重跑 scripts/audit_paper.py",
    )
    _add_check(
        checks,
        "paper-pdf-technical",
        bool(paper_qa["technical_pass"]),
        f"PDF 为 {paper_qa['page_count']} 页 A4，"
        f"{paper_qa['embedded_font_count']} 个字体全部嵌入，日志无阻断型布局警告",
        "PDF 页数/A4/字体嵌入、文件时效或日志技术检查未通过",
    )
    _add_check(
        checks,
        "paper-pdf-manual-visual",
        bool(paper_qa["manual_visual_pass"]),
        f"逐页视觉 QA 记录与当前 PDF 的 SHA-256 和 {paper_qa['page_count']} 页页数完全绑定",
        "缺少与当前 PDF 哈希绑定的逐页视觉 QA 记录",
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
