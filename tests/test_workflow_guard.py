from __future__ import annotations

import copy
import tempfile
import unittest
import uuid
from pathlib import Path

from agent_backend import build_prompt, build_system_prompt
from agent_tools import ToolRegistry
from quality_scoring import QualityEvaluator
from workflow_guard import audit_modeling_workflow


def valid_manifest() -> dict:
    return {
        "stage": "final",
        "problem": {
            "facts": ["需求和容量取自题面表 1。"],
            "objectives": ["在满足容量约束时最小化总成本。"],
            "variables": [
                {"id": "x_i", "meaning": "设施 i 的分配量", "unit": "件"},
                {"id": "c", "meaning": "总成本", "unit": "元"},
            ],
            "constraints": ["分配量非负且不超过设施容量。"],
        },
        "assumptions": [
            {
                "id": "a-demand",
                "statement": "规划期内需求已知。",
                "basis": "题面给出固定规划期需求。",
                "risk": "需求波动会改变最优分配。",
                "validation": "对需求做正负 10% 敏感性分析。",
            }
        ],
        "model": {
            "mechanisms": ["流量守恒把各设施分配与总需求连接。"],
            "baseline": {
                "name": "最近设施贪心分配",
                "rationale": "提供可解释且可执行的成本基线。",
                "evidenceIds": ["ev-baseline"],
            },
            "selected": {
                "name": "分解式混合整数规划",
                "rationale": "基线在容量冲突场景下不可行。",
                "assumptionIds": ["a-demand"],
            },
            "complexityLevel": "L2",
            "upgradeEvidenceIds": ["ev-upgrade"],
            "usesSimulation": True,
            "simulationPurpose": "只用于需求扰动下的稳健性复验，不替代流量守恒模型。",
            "simulationEvidenceIds": ["ev-simulation"],
            "isNpHard": True,
            "simplifications": [
                {
                    "statement": "按连通分量分解并删除支配候选边。",
                    "basis": "目标可加且分量间无共享容量。",
                    "validationEvidenceIds": ["ev-simplification"],
                }
            ],
            "usesStochastic": True,
            "stochastic": {
                "seed": 20260811,
                "repetitions": 10,
                "convergence": "10 次运行均在 200 轮内满足停止条件。",
                "dispersion": "目标值标准差为 0.7%。",
            },
        },
        "evidence": [
            {"id": "ev-problem", "kind": "problem", "locator": "题面第 1 页表 1", "verified": True},
            {"id": "ev-baseline", "kind": "calculation", "locator": "outputs/baseline.json", "verified": True},
            {"id": "ev-upgrade", "kind": "validation", "locator": "outputs/baseline-gap.json", "verified": True},
            {"id": "ev-simulation", "kind": "validation", "locator": "outputs/sensitivity.csv", "verified": True},
            {"id": "ev-simplification", "kind": "validation", "locator": "outputs/reduction-check.json", "verified": True},
            {"id": "ev-result", "kind": "calculation", "locator": "outputs/solution.json", "verified": True},
            {"id": "ev-validation", "kind": "validation", "locator": "outputs/constraint-audit.json", "verified": True},
            {"id": "ev-iteration", "kind": "validation", "locator": "outputs/revision-comparison.csv", "verified": True},
            {"id": "ev-figure", "kind": "calculation", "locator": "outputs/cost-curve.csv", "verified": True},
        ],
        "claims": [
            {
                "id": "claim-cost",
                "kind": "result",
                "statement": "主模型降低成本并满足全部容量约束。",
                "status": "verified",
                "final": True,
                "evidenceIds": ["ev-result", "ev-validation"],
                "assumptionIds": ["a-demand"],
            }
        ],
        "validations": [
            {
                "id": "val-constraints",
                "claimIds": ["claim-cost"],
                "type": "constraint_recalculation",
                "metric": "maximum_violation",
                "result": "0",
                "passed": True,
                "evidenceIds": ["ev-validation"],
            }
        ],
        "iterations": [
            {
                "iteration": 1,
                "trigger": "基线在两个高需求场景中违反容量约束。",
                "change": "加入容量耦合约束并按连通分量分解。",
                "result": "最大约束违反量从 18 件降为 0 件。",
                "decision": "accept",
                "evidenceIds": ["ev-iteration"],
            }
        ],
        "figures": [
            {
                "id": "fig-cost",
                "claimIds": ["claim-cost"],
                "sourceEvidenceIds": ["ev-figure"],
                "captionClaim": "容量约束启用后成本下降且方案保持可行。",
                "quantitative": True,
                "xUnit": "% demand change",
                "yUnit": "CNY",
            }
        ],
        "citations": [
            {
                "id": "cite-rules",
                "title": "竞赛题面",
                "locator": "题面第 1 页",
                "verified": True,
            }
        ],
    }


def gate_state(report: dict, gate_id: str) -> bool:
    return next(item["passed"] for item in report["gates"] if item["id"] == gate_id)


class WorkflowGuardTests(unittest.TestCase):
    def test_complete_final_manifest_passes(self) -> None:
        report = audit_modeling_workflow(valid_manifest())
        self.assertTrue(report["passed"], report["issues"])
        self.assertEqual(report["score"], 100)

    def test_simulation_cannot_replace_mechanism(self) -> None:
        manifest = valid_manifest()
        manifest["model"]["mechanisms"] = []
        report = audit_modeling_workflow(manifest)
        self.assertFalse(gate_state(report, "mechanism_before_simulation"))

    def test_np_hard_problem_requires_validated_engineering_strategy(self) -> None:
        manifest = valid_manifest()
        manifest["model"]["simplifications"] = []
        report = audit_modeling_workflow(manifest)
        self.assertFalse(gate_state(report, "np_hard_engineering_strategy"))

    def test_unverified_source_and_broken_claim_reference_fail(self) -> None:
        manifest = valid_manifest()
        manifest["citations"][0]["verified"] = False
        manifest["claims"][0]["evidenceIds"].append("ev-invented")
        report = audit_modeling_workflow(manifest)
        self.assertFalse(gate_state(report, "source_integrity"))
        self.assertFalse(gate_state(report, "claim_evidence_consistency"))

    def test_final_claim_cannot_remain_provisional(self) -> None:
        manifest = valid_manifest()
        manifest["claims"][0]["status"] = "provisional"
        report = audit_modeling_workflow(manifest)
        self.assertFalse(gate_state(report, "claim_evidence_consistency"))

    def test_figure_needs_units_and_closed_loop_needs_evidence(self) -> None:
        manifest = valid_manifest()
        manifest["figures"][0]["yUnit"] = ""
        manifest["iterations"] = []
        report = audit_modeling_workflow(manifest)
        self.assertFalse(gate_state(report, "figure_semantics"))
        self.assertFalse(gate_state(report, "closed_loop_iteration"))

    def test_stochastic_method_needs_repeats_convergence_and_dispersion(self) -> None:
        manifest = valid_manifest()
        manifest["model"]["stochastic"]["repetitions"] = 1
        report = audit_modeling_workflow(manifest)
        self.assertFalse(gate_state(report, "stochastic_reproducibility"))

    def test_tool_writes_manifest_and_audit_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = ToolRegistry(Path(temp_dir))
            run_id = uuid.uuid4().hex
            result = registry.execute(
                "audit_modeling_workflow",
                {"manifest": valid_manifest(), "filename": "workflow-final"},
                run_id,
            )
            self.assertTrue(result["workflowAudit"]["passed"])
            names = {item["name"] for item in result["artifacts"]}
            self.assertTrue(
                {"workflow-final-manifest.json", "workflow-final.json", "workflow-final.md"}.issubset(names)
            )

    def test_quality_gate_requires_latest_final_pass(self) -> None:
        answer = (
            "先定义目标、变量、单位和约束，建立简单基线，再依据基线误差选择主模型。"
            "模型给出目标函数、约束、适用范围和风险边界，并使用独立验证检查结果。"
            "所有最终结论都绑定计算产物，图表绑定源数据、单位和具体主张。"
        ) * 4
        missing = QualityEvaluator(82).evaluate(
            mode="cumcm",
            prompt="用户内容：完成整题",
            answer=answer,
            meta={"workflowAuditRequired": True},
        )
        self.assertFalse(gate_state(missing, "modeling_workflow_audit"))
        self.assertLessEqual(missing["total"], 68)

        audit = audit_modeling_workflow(valid_manifest())
        present = QualityEvaluator(82).evaluate(
            mode="cumcm",
            prompt="用户内容：完成整题",
            answer=answer,
            meta={"workflowAuditRequired": True},
            tool_history=[
                {
                    "name": "audit_modeling_workflow",
                    "ok": True,
                    "workflowAudit": audit,
                    "artifacts": [],
                }
            ],
        )
        self.assertTrue(gate_state(present, "modeling_workflow_audit"))
        self.assertTrue(present["metrics"]["workflowAuditPassed"])
        self.assertEqual(present["metrics"]["evidenceTools"], 0)

    def test_prompt_marks_only_full_workflows_as_required(self) -> None:
        cumcm = build_prompt({"mode": "cumcm", "content": "完成赛题"})
        brief_solver = build_prompt({"mode": "solver", "content": "解释这个约束"})
        full_solver = build_prompt({"mode": "solver", "content": "完成整题并给出结果"})
        brief_paper = build_prompt({"mode": "paper", "content": "润色这一段摘要"})
        full_paper = build_prompt({"mode": "paper", "content": "完成整篇数学建模竞赛论文"})
        self.assertTrue(cumcm["meta"]["workflowAuditRequired"])
        self.assertFalse(brief_solver["meta"]["workflowAuditRequired"])
        self.assertTrue(full_solver["meta"]["workflowAuditRequired"])
        self.assertFalse(brief_paper["meta"]["workflowAuditRequired"])
        self.assertTrue(full_paper["meta"]["workflowAuditRequired"])
        self.assertIn("audit_modeling_workflow", cumcm["prompt"])
        self.assertIn("audit_modeling_workflow", build_system_prompt("cumcm"))

    def test_latest_failed_audit_overrides_an_older_pass(self) -> None:
        passed = audit_modeling_workflow(valid_manifest())
        failed_manifest = copy.deepcopy(valid_manifest())
        failed_manifest["iterations"] = []
        failed = audit_modeling_workflow(failed_manifest)
        report = QualityEvaluator(82).evaluate(
            mode="cumcm",
            prompt="用户内容：完成整题",
            answer="目标、变量、约束、基线、模型、验证、结论和风险边界。" * 20,
            meta={"workflowAuditRequired": True},
            tool_history=[
                {"name": "audit_modeling_workflow", "ok": True, "workflowAudit": passed},
                {"name": "audit_modeling_workflow", "ok": True, "workflowAudit": failed},
            ],
        )
        self.assertFalse(gate_state(report, "modeling_workflow_audit"))


if __name__ == "__main__":
    unittest.main()
