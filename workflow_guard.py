from __future__ import annotations

from typing import Any, Iterable


SCHEMA_VERSION = "1.0"
VALID_STAGES = {"draft", "final"}
VALID_CLAIM_STATUSES = {"verified", "provisional", "failed"}
VALID_DECISIONS = {"accept", "revise", "rollback"}
COMPLEXITY_LEVELS = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _texts(value: Any) -> list[str]:
    return [_text(item) for item in _items(value) if _text(item)]


def _catalog(items: Iterable[Any]) -> tuple[dict[str, dict[str, Any]], list[str], int]:
    catalog: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    invalid = 0
    for item in items:
        if not isinstance(item, dict) or not _text(item.get("id")):
            invalid += 1
            continue
        item_id = _text(item["id"])
        if item_id in catalog:
            duplicates.append(item_id)
        catalog[item_id] = item
    return catalog, duplicates, invalid


def _verified_references(value: Any, evidence: dict[str, dict[str, Any]]) -> bool:
    references = _texts(value)
    return bool(references) and all(
        reference in evidence
        and evidence[reference].get("verified") is True
        and bool(_text(evidence[reference].get("locator")))
        for reference in references
    )


def audit_modeling_workflow(manifest: dict[str, Any]) -> dict[str, Any]:
    """Audit a modeling workflow manifest without inferring missing evidence.

    The checker intentionally validates references and process state only. It does
    not try to decide whether a mathematical claim is true from polished prose.
    """

    if not isinstance(manifest, dict):
        raise TypeError("workflow manifest 必须是 JSON 对象")

    stage = _text(manifest.get("stage")).lower()
    problem = _mapping(manifest.get("problem"))
    model = _mapping(manifest.get("model"))
    assumptions = _items(manifest.get("assumptions"))
    evidence_items = _items(manifest.get("evidence"))
    claims = _items(manifest.get("claims"))
    validations = _items(manifest.get("validations"))
    iterations = _items(manifest.get("iterations"))
    figures = _items(manifest.get("figures"))
    citations = _items(manifest.get("citations"))

    assumption_by_id, assumption_duplicates, invalid_assumptions = _catalog(assumptions)
    evidence_by_id, evidence_duplicates, invalid_evidence = _catalog(evidence_items)
    claim_by_id, claim_duplicates, invalid_claims = _catalog(claims)
    validation_by_id, validation_duplicates, invalid_validations = _catalog(validations)
    figure_by_id, figure_duplicates, invalid_figures = _catalog(figures)
    citation_by_id, citation_duplicates, invalid_citations = _catalog(citations)

    gates: list[dict[str, Any]] = []

    def add_gate(gate_id: str, passed: bool, message: str, details: list[str] | None = None) -> None:
        gates.append(
            {
                "id": gate_id,
                "passed": bool(passed),
                "message": message,
                "details": list(dict.fromkeys(item for item in (details or []) if item))[:12],
            }
        )

    variables = _items(problem.get("variables"))
    variable_contract = bool(variables) and all(
        isinstance(item, dict)
        and _text(item.get("id"))
        and _text(item.get("meaning"))
        and _text(item.get("unit"))
        for item in variables
    )
    problem_contract = (
        stage in VALID_STAGES
        and bool(_texts(problem.get("facts")))
        and bool(_texts(problem.get("objectives")))
        and variable_contract
        and bool(_texts(problem.get("constraints")))
    )
    add_gate(
        "problem_contract",
        problem_contract,
        "题目合同不完整：stage、事实、目标、带单位变量或约束存在缺口。",
    )

    duplicate_ids = (
        assumption_duplicates
        + evidence_duplicates
        + claim_duplicates
        + validation_duplicates
        + figure_duplicates
        + citation_duplicates
    )
    invalid_id_count = (
        invalid_assumptions
        + invalid_evidence
        + invalid_claims
        + invalid_validations
        + invalid_figures
        + invalid_citations
    )
    add_gate(
        "identifier_integrity",
        not duplicate_ids and invalid_id_count == 0,
        "账本中存在缺失或重复 ID，引用关系无法可靠追踪。",
        [*(f"重复 ID：{item}" for item in duplicate_ids), f"缺失 ID 的条目：{invalid_id_count}" if invalid_id_count else ""],
    )

    assumption_rows_valid = bool(assumptions) and all(
        isinstance(item, dict)
        and _text(item.get("id"))
        and _text(item.get("statement"))
        and _text(item.get("basis"))
        and _text(item.get("risk"))
        and _text(item.get("validation"))
        for item in assumptions
    )
    selected = _mapping(model.get("selected"))
    selected_assumptions = _texts(selected.get("assumptionIds"))
    selected_assumptions_valid = bool(selected_assumptions) and all(
        item in assumption_by_id for item in selected_assumptions
    )
    add_gate(
        "assumption_traceability",
        assumption_rows_valid and selected_assumptions_valid,
        "模型假设未写明依据、风险和验证方式，或主模型引用了不存在的假设。",
    )

    baseline = _mapping(model.get("baseline"))
    complexity_level = _text(model.get("complexityLevel")).upper()
    baseline_valid = (
        _text(baseline.get("name"))
        and _text(baseline.get("rationale"))
        and _verified_references(baseline.get("evidenceIds"), evidence_by_id)
    )
    selected_valid = bool(_text(selected.get("name")) and _text(selected.get("rationale")))
    upgrade_required = COMPLEXITY_LEVELS.get(complexity_level, -1) > 0
    upgrade_valid = not upgrade_required or _verified_references(model.get("upgradeEvidenceIds"), evidence_by_id)
    mechanisms = _texts(model.get("mechanisms"))
    add_gate(
        "baseline_and_escalation",
        bool(baseline_valid and selected_valid and mechanisms and complexity_level in COMPLEXITY_LEVELS and upgrade_valid),
        "缺少可执行简单基线、机理关系，或复杂度升级没有经验证据。",
    )

    uses_simulation = model.get("usesSimulation") is True
    simulation_valid = (
        not uses_simulation
        or (
            bool(mechanisms)
            and bool(_text(model.get("simulationPurpose")))
            and _verified_references(model.get("simulationEvidenceIds"), evidence_by_id)
        )
    )
    add_gate(
        "mechanism_before_simulation",
        simulation_valid,
        "仿真被用来替代机理：缺少明确机理、仿真用途或可核验的校准/验证证据。",
    )

    is_np_hard = model.get("isNpHard") is True
    simplifications = _items(model.get("simplifications"))
    simplification_valid = bool(simplifications) and all(
        isinstance(item, dict)
        and _text(item.get("statement"))
        and _text(item.get("basis"))
        and _verified_references(item.get("validationEvidenceIds"), evidence_by_id)
        for item in simplifications
    )
    add_gate(
        "np_hard_engineering_strategy",
        not is_np_hard or simplification_valid,
        "NP-hard 任务没有给出可验证的降维、分解、近似或工程简化策略。",
    )

    source_evidence = [
        item
        for item in evidence_items
        if isinstance(item, dict) and _text(item.get("kind")).lower() in {"source", "problem"}
    ]
    source_evidence_valid = all(
        item.get("verified") is True and bool(_text(item.get("locator"))) for item in source_evidence
    )
    citations_valid = all(
        isinstance(item, dict)
        and _text(item.get("id"))
        and _text(item.get("title"))
        and _text(item.get("locator"))
        and item.get("verified") is True
        for item in citations
    )
    add_gate(
        "source_integrity",
        source_evidence_valid and citations_valid,
        "存在未核验或无定位信息的题面事实、外部来源或参考文献。",
    )

    final_claims = [
        item for item in claims if isinstance(item, dict) and item.get("final") is True
    ]
    claim_details: list[str] = []
    claim_links_valid = True
    for item in claims:
        if not isinstance(item, dict):
            claim_links_valid = False
            continue
        claim_id = _text(item.get("id")) or "<missing>"
        evidence_ids = _texts(item.get("evidenceIds"))
        assumption_ids = _texts(item.get("assumptionIds"))
        status = _text(item.get("status")).lower()
        valid = (
            bool(_text(item.get("statement")))
            and status in VALID_CLAIM_STATUSES
            and all(reference in evidence_by_id for reference in evidence_ids)
            and all(reference in assumption_by_id for reference in assumption_ids)
        )
        if item.get("final") is True:
            valid = (
                valid
                and status == "verified"
                and bool(evidence_ids)
                and all(
                    evidence_by_id[reference].get("verified") is True
                    and bool(_text(evidence_by_id[reference].get("locator")))
                    for reference in evidence_ids
                    if reference in evidence_by_id
                )
            )
        if not valid:
            claim_links_valid = False
            claim_details.append(claim_id)
    claim_gate_passed = claim_links_valid and (stage != "final" or bool(final_claims))
    add_gate(
        "claim_evidence_consistency",
        claim_gate_passed,
        "最终主张不是 verified、证据/假设引用失效，或最终阶段没有可交付主张。",
        [f"问题主张：{item}" for item in claim_details],
    )

    validation_details: list[str] = []
    passed_validation_claims: set[str] = set()
    validation_rows_valid = True
    for item in validations:
        if not isinstance(item, dict):
            validation_rows_valid = False
            continue
        validation_id = _text(item.get("id")) or "<missing>"
        claim_ids = _texts(item.get("claimIds"))
        evidence_ids = _texts(item.get("evidenceIds"))
        valid = (
            bool(claim_ids)
            and all(reference in claim_by_id for reference in claim_ids)
            and _text(item.get("type"))
            and _text(item.get("metric"))
            and _text(item.get("result"))
            and isinstance(item.get("passed"), bool)
            and _verified_references(evidence_ids, evidence_by_id)
        )
        if not valid:
            validation_rows_valid = False
            validation_details.append(validation_id)
        if valid and item.get("passed") is True:
            passed_validation_claims.update(claim_ids)
    result_claim_ids = {
        _text(item.get("id"))
        for item in final_claims
        if _text(item.get("kind")).lower() == "result" and _text(item.get("id"))
    }
    result_coverage = result_claim_ids.issubset(passed_validation_claims)
    if stage == "final" and not result_claim_ids:
        result_coverage = False
    add_gate(
        "validation_coverage",
        validation_rows_valid and result_coverage,
        "最终结果主张没有被带指标、结果和运行证据的通过验证覆盖。",
        [
            *(f"问题验证：{item}" for item in validation_details),
            *(f"未覆盖结果主张：{item}" for item in sorted(result_claim_ids - passed_validation_claims)),
        ],
    )

    figure_details: list[str] = []
    figures_valid = True
    for item in figures:
        if not isinstance(item, dict):
            figures_valid = False
            continue
        figure_id = _text(item.get("id")) or "<missing>"
        claim_ids = _texts(item.get("claimIds"))
        source_ids = _texts(item.get("sourceEvidenceIds"))
        valid = (
            bool(claim_ids)
            and all(reference in claim_by_id for reference in claim_ids)
            and _verified_references(source_ids, evidence_by_id)
            and bool(_text(item.get("captionClaim")))
            and isinstance(item.get("quantitative"), bool)
        )
        if item.get("quantitative") is True:
            valid = valid and bool(_text(item.get("xUnit"))) and bool(_text(item.get("yUnit")))
        if not valid:
            figures_valid = False
            figure_details.append(figure_id)
    add_gate(
        "figure_semantics",
        figures_valid,
        "图表缺少所支撑主张、源数据证据、信息型题注或定量坐标单位。",
        [f"问题图表：{item}" for item in figure_details],
    )

    uses_stochastic = model.get("usesStochastic") is True
    stochastic = _mapping(model.get("stochastic"))
    stochastic_valid = (
        not uses_stochastic
        or (
            isinstance(stochastic.get("seed"), int)
            and not isinstance(stochastic.get("seed"), bool)
            and isinstance(stochastic.get("repetitions"), int)
            and stochastic.get("repetitions", 0) >= 5
            and bool(_text(stochastic.get("convergence")))
            and bool(_text(stochastic.get("dispersion")))
        )
    )
    add_gate(
        "stochastic_reproducibility",
        stochastic_valid,
        "随机方法缺少固定种子、至少 5 次独立重复、收敛说明或离散统计。",
    )

    valid_iterations = []
    for item in iterations:
        if not isinstance(item, dict):
            continue
        evidence_ids = _texts(item.get("evidenceIds"))
        if (
            isinstance(item.get("iteration"), int)
            and item.get("iteration", 0) >= 1
            and _text(item.get("trigger"))
            and _text(item.get("change"))
            and _text(item.get("result"))
            and _text(item.get("decision")).lower() in VALID_DECISIONS
            and _verified_references(evidence_ids, evidence_by_id)
        ):
            valid_iterations.append(item)
    add_gate(
        "closed_loop_iteration",
        stage != "final" or bool(valid_iterations),
        "最终流程没有一条带证据的“触发问题—实施修改—复验结果—接受/回滚”闭环记录。",
    )

    failed_gates = [item for item in gates if not item["passed"]]
    score = round(100 * (len(gates) - len(failed_gates)) / len(gates)) if gates else 0
    return {
        "schemaVersion": SCHEMA_VERSION,
        "stage": stage,
        "passed": stage == "final" and not failed_gates,
        "score": score,
        "gates": gates,
        "issues": [item["message"] for item in failed_gates],
        "metrics": {
            "assumptions": len(assumption_by_id),
            "evidence": len(evidence_by_id),
            "claims": len(claim_by_id),
            "finalClaims": len(final_claims),
            "validations": len(validation_by_id),
            "figures": len(figure_by_id),
            "citations": len(citation_by_id),
            "validIterations": len(valid_iterations),
            "passedGates": len(gates) - len(failed_gates),
            "totalGates": len(gates),
        },
    }


def render_workflow_audit(report: dict[str, Any]) -> str:
    status = "PASS" if report.get("passed") else "FAIL"
    lines = [
        "# 数学建模过程审计",
        "",
        f"- 状态：**{status}**",
        f"- 阶段：`{report.get('stage', '')}`",
        f"- 得分：{report.get('score', 0)}/100",
        f"- 合同版本：`{report.get('schemaVersion', SCHEMA_VERSION)}`",
        "",
        "## 门禁结果",
        "",
    ]
    for gate in report.get("gates", []):
        marker = "PASS" if gate.get("passed") else "FAIL"
        lines.append(f"- `{marker}` `{gate.get('id', '')}`：{gate.get('message', '')}")
        for detail in gate.get("details", []):
            if detail:
                lines.append(f"  - {detail}")
    lines.extend(["", "## 结论", ""])
    if report.get("passed"):
        lines.append("结构化账本通过全部过程门禁；这只证明证据链完整，不替代人工复核数学正确性。")
    else:
        lines.append("当前流程不可标记为最终交付。应修复失败门禁并基于新证据重新运行审计。")
    return "\n".join(lines) + "\n"
