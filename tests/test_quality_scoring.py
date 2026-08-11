from __future__ import annotations

import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

from agent_backend import AgentSettings, RunManager, RunStore
from quality_scoring import MODE_WEIGHTS, QualityEvaluator, rubric_spec


STRONG_ANSWER = """## 问题拆解

问题一先明确目标、变量、假设与约束。设决策变量 $x_i$，目标函数为
$\\min \\sum_i c_i x_i$，并满足资源非负约束。比较线性规划与启发式基线，
选择可解释的线性规划并给出求解步骤。

## 证据与验证

数据需要先检查缺失、异常值和独立样本单位。采用按主体分组的五折交叉验证，
报告 MAE=2.31、R2=0.78 和 95% 置信区间，并使用 Bootstrap、参数扰动和敏感性分析，
防止同一主体跨折造成数据泄漏。

## 结论与边界

最终按约束输出方案与可复现代码。上述数值只用于说明报告结构，真实结论必须由运行结果替换。
局限包括样本代表性、模型假设和外推风险，不能直接外推到新地区。
"""

RESULT_ANSWER = """## 问题与模型

目标是在给定资源约束下计算一组可执行方案。定义决策变量、目标函数与硬约束，
使用确定性脚本读取输入并生成结果表。所有最终数字均应由本次工具运行产生，
并在结论中给出单位、适用范围和文件位置。

## 结果

代码已运行并生成数值结果。下述句子用于测试专项质量门禁，其他验证信息只在确实执行后补充。
"""


class RevisingProvider:
    calls = 0

    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings

    def stream(self, system_prompt, user_prompt, cancel_event, **kwargs):
        type(self).calls += 1
        if type(self).calls == 1:
            yield "先做回归分析。"
        else:
            yield STRONG_ANSWER


class QualityScoringTests(unittest.TestCase):
    def test_rubric_weights_are_complete(self) -> None:
        spec = rubric_spec()
        self.assertEqual(spec["version"], "2026.6")
        self.assertEqual({item["id"] for item in spec["dimensions"]}, set(MODE_WEIGHTS["solver"]))
        self.assertTrue(all(sum(weights.values()) == 100 for weights in MODE_WEIGHTS.values()))
        gate_ids = {item["id"] for item in spec["hardGates"]}
        self.assertTrue(
            {
                "optimization_comparison",
                "stochastic_robustness",
                "predictive_validation",
                "mechanistic_consistency",
                "modeling_workflow_audit",
                "abstract_numeric_evidence",
            }.issubset(gate_ids)
        )

    def test_uninspected_attachment_triggers_hard_cap(self) -> None:
        report = QualityEvaluator(82).evaluate(
            mode="cumcm",
            prompt="用户内容：分析附件并完成论文",
            answer=STRONG_ANSWER,
            meta={"uploads": [{"id": "a" * 32, "name": "data.csv"}]},
            tool_history=[],
            artifacts=[],
        )
        gate = next(item for item in report["gates"] if item["id"] == "data_inspection")
        self.assertFalse(gate["passed"])
        self.assertEqual(report["cap"], 55)
        self.assertLessEqual(report["total"], 55)

    def test_supported_answer_can_pass(self) -> None:
        report = QualityEvaluator(82).evaluate(
            mode="solver",
            prompt="用户内容：建立优化模型并验证",
            answer=STRONG_ANSWER,
            tool_history=[{"name": "solve_linear_program", "ok": True, "artifacts": []}],
            artifacts=[],
        )
        self.assertTrue(report["passed"])
        self.assertGreaterEqual(report["total"], 82)

    def test_routing_tools_do_not_count_as_execution_evidence(self) -> None:
        report = QualityEvaluator(82).evaluate(
            mode="solver",
            prompt="用户内容：给出模型运行结果",
            answer=STRONG_ANSWER.replace(
                "真实结论必须由运行结果替换",
                "模型已经运行，运行结果显示目标值为 12.4。",
            ),
            tool_history=[{"name": "search_skills", "ok": True, "artifacts": []}],
            artifacts=[],
        )
        gate = next(item for item in report["gates"] if item["id"] == "unsupported_execution")
        self.assertFalse(gate["passed"])
        self.assertEqual(report["metrics"]["evidenceTools"], 0)
        self.assertLessEqual(report["total"], 70)

    def test_material_sources_improve_grounding_but_not_execution_evidence(self) -> None:
        report = QualityEvaluator(82).evaluate(
            mode="solver",
            prompt="用户内容：依据本地资料给出模型运行结果",
            answer=STRONG_ANSWER.replace(
                "真实结论必须由运行结果替换",
                "根据《优化方法》第 3 页，模型已经运行，运行结果显示目标值为 12.4。",
            ),
            tool_history=[
                {"name": "search_materials", "ok": True, "artifacts": []},
                {"name": "read_material", "ok": True, "artifacts": []},
            ],
            artifacts=[],
        )
        gate = next(item for item in report["gates"] if item["id"] == "unsupported_execution")
        self.assertFalse(gate["passed"])
        self.assertEqual(report["metrics"]["evidenceTools"], 0)
        self.assertEqual(report["metrics"]["sourceTools"], 1)

    def test_brief_depth_uses_adaptive_minimum(self) -> None:
        answer = "目标是选择稳健方案。先定义变量、目标函数和约束，再比较基线模型。结论应报告误差、敏感性、局限与适用范围，并给出下一步验证建议。" * 2
        report = QualityEvaluator(60).evaluate(
            mode="paper",
            prompt="用户内容：简要润色摘要",
            answer=answer,
            meta={"depth": "简要"},
        )
        gate = next(item for item in report["gates"] if item["id"] == "minimum_content")
        self.assertTrue(gate["passed"])

    def test_optimization_claim_requires_feasibility_evidence(self) -> None:
        answer = STRONG_ANSWER + "\n运行后得到最优方案为 x=3，目标值为 12.4。"
        report = QualityEvaluator(82).evaluate(
            mode="solver",
            prompt="用户内容：求解优化问题",
            answer=answer,
            tool_history=[{"name": "run_python", "ok": True, "artifacts": []}],
        )
        gate = next(item for item in report["gates"] if item["id"] == "optimization_feasibility")
        self.assertFalse(gate["passed"])
        self.assertLessEqual(report["total"], 78)

    def test_global_optimum_claim_requires_certificate(self) -> None:
        answer = STRONG_ANSWER + "\n最大约束违反量为 0，运行后得到全局最优方案为 x=3。"
        report = QualityEvaluator(82).evaluate(
            mode="solver",
            prompt="用户内容：求解非凸优化问题",
            answer=answer,
            tool_history=[{"name": "run_python", "ok": True, "artifacts": []}],
        )
        feasibility = next(item for item in report["gates"] if item["id"] == "optimization_feasibility")
        optimality = next(item for item in report["gates"] if item["id"] == "global_optimality")
        self.assertTrue(feasibility["passed"])
        self.assertFalse(optimality["passed"])
        self.assertLessEqual(report["total"], 76)

    def test_hedged_global_optimum_limitation_does_not_trigger_claim_gate(self) -> None:
        answer = STRONG_ANSWER + "\n当前结果是最大约束违反量为 0 的高质量可行解，未证明全局最优。"
        report = QualityEvaluator(82).evaluate(
            mode="solver",
            prompt="用户内容：给出启发式优化结果",
            answer=answer,
            tool_history=[{"name": "run_python", "ok": True, "artifacts": []}],
        )
        optimality = next(item for item in report["gates"] if item["id"] == "global_optimality")
        self.assertTrue(optimality["passed"])

    def test_cumcm_optimization_result_requires_quality_comparison(self) -> None:
        answer = RESULT_ANSWER + "\n最大约束违反量为 0，运行后得到最优方案为 x=3，目标值为 12.4。"
        report = QualityEvaluator(82).evaluate(
            mode="cumcm",
            prompt="用户内容：完成竞赛优化问题",
            answer=answer,
            tool_history=[{"name": "run_python", "ok": True, "artifacts": []}],
        )
        gate = next(item for item in report["gates"] if item["id"] == "optimization_comparison")
        self.assertFalse(gate["passed"])
        self.assertLessEqual(report["total"], 80)

        compared = answer + "\n理论上界为 12.8，当前方案与上界的相对间隙为 3.1%。"
        report = QualityEvaluator(82).evaluate(
            mode="cumcm",
            prompt="用户内容：完成竞赛优化问题",
            answer=compared,
            tool_history=[{"name": "run_python", "ok": True, "artifacts": []}],
        )
        gate = next(item for item in report["gates"] if item["id"] == "optimization_comparison")
        self.assertTrue(gate["passed"])

    def test_prediction_result_requires_out_of_sample_metric(self) -> None:
        answer = RESULT_ANSWER + "\n时间序列模型预测结果为 128.4。"
        report = QualityEvaluator(82).evaluate(
            mode="cumcm",
            prompt="用户内容：预测下一期需求",
            answer=answer,
            tool_history=[{"name": "run_python", "ok": True, "artifacts": []}],
        )
        gate = next(item for item in report["gates"] if item["id"] == "predictive_validation")
        self.assertFalse(gate["passed"])

        validated = answer + "\n按时间顺序划分测试集并滚动验证，样本外 MAE=4.2。"
        report = QualityEvaluator(82).evaluate(
            mode="cumcm",
            prompt="用户内容：预测下一期需求",
            answer=validated,
            tool_history=[{"name": "run_python", "ok": True, "artifacts": []}],
        )
        gate = next(item for item in report["gates"] if item["id"] == "predictive_validation")
        self.assertTrue(gate["passed"])

    def test_stochastic_optimization_requires_multi_seed_statistics(self) -> None:
        answer = STRONG_ANSWER + "\n模拟退火的优化结果为 12.4，最大约束违反量为 0。"
        report = QualityEvaluator(82).evaluate(
            mode="solver",
            prompt="用户内容：用模拟退火优化",
            answer=answer,
            tool_history=[{"name": "run_python", "ok": True, "artifacts": []}],
        )
        gate = next(item for item in report["gates"] if item["id"] == "stochastic_robustness")
        self.assertFalse(gate["passed"])

        too_few = answer + "\n使用 3 个不同随机种子独立运行，中位数与四分位距为 12.2 和 0.3，停止阈值为 1e-6。"
        report = QualityEvaluator(82).evaluate(
            mode="solver",
            prompt="用户内容：用模拟退火优化",
            answer=too_few,
            tool_history=[{"name": "run_python", "ok": True, "artifacts": []}],
        )
        gate = next(item for item in report["gates"] if item["id"] == "stochastic_robustness")
        self.assertFalse(gate["passed"])

        robust = answer + "\n使用 30 个不同随机种子独立运行，中位数与四分位距为 12.2 和 0.3，停止阈值为 1e-6。"
        report = QualityEvaluator(82).evaluate(
            mode="solver",
            prompt="用户内容：用模拟退火优化",
            answer=robust,
            tool_history=[{"name": "run_python", "ok": True, "artifacts": []}],
        )
        gate = next(item for item in report["gates"] if item["id"] == "stochastic_robustness")
        self.assertTrue(gate["passed"])

    def test_mechanistic_result_requires_units_and_consistency_check(self) -> None:
        answer = STRONG_ANSWER + "\n热传导机理模型计算结果表明峰值温度为 245 摄氏度。"
        report = QualityEvaluator(82).evaluate(
            mode="cumcm",
            prompt="用户内容：建立热传导机理模型",
            answer=answer,
            tool_history=[{"name": "run_python", "ok": True, "artifacts": []}],
        )
        gate = next(item for item in report["gates"] if item["id"] == "mechanistic_consistency")
        self.assertFalse(gate["passed"])

        checked = answer + "\n方程左右两端量纲一致；边界条件的最大残差为 2.1e-9，并完成步长收敛复算。"
        report = QualityEvaluator(82).evaluate(
            mode="cumcm",
            prompt="用户内容：建立热传导机理模型",
            answer=checked,
            tool_history=[{"name": "run_python", "ok": True, "artifacts": []}],
        )
        gate = next(item for item in report["gates"] if item["id"] == "mechanistic_consistency")
        self.assertTrue(gate["passed"])

    def test_negated_evidence_never_satisfies_specialist_gates(self) -> None:
        answer = RESULT_ANSWER + """

运行后得到全局最优方案为 x=3，但没有全局上界、最优间隙或最优性证明，
也没有基线和独立算法。模拟退火的优化结果为 12.4；不同随机种子尚未运行，
没有收敛曲线。预测结果为 128.4，但测试集未设置、未报告 RMSE。
热传导机理模型计算结果表明峰值温度为 245 摄氏度，未做量纲检查，边界条件未验证。
最大约束违反量为 0。
"""
        report = QualityEvaluator(82).evaluate(
            mode="cumcm",
            prompt="用户内容：完成含机理、随机优化和预测的整题",
            answer=answer,
            tool_history=[{"name": "run_python", "ok": True, "artifacts": []}],
        )
        gates = {item["id"]: item["passed"] for item in report["gates"]}
        self.assertFalse(gates["optimization_comparison"])
        self.assertFalse(gates["global_optimality"])
        self.assertFalse(gates["stochastic_robustness"])
        self.assertFalse(gates["predictive_validation"])
        self.assertFalse(gates["mechanistic_consistency"])

    def test_negated_feasibility_is_not_numeric_evidence(self) -> None:
        answer = RESULT_ANSWER + "\n运行后得到最优方案为 x=3，但可行性未检查，约束违反量未知。"
        report = QualityEvaluator(82).evaluate(
            mode="solver",
            prompt="用户内容：求解优化问题",
            answer=answer,
            tool_history=[{"name": "run_python", "ok": True, "artifacts": []}],
        )
        gate = next(item for item in report["gates"] if item["id"] == "optimization_feasibility")
        self.assertFalse(gate["passed"])

    def test_zero_gap_is_a_global_certificate(self) -> None:
        answer = RESULT_ANSWER + "\n最大约束违反量为 0，求得全局最优解为 x=3，MIP gap=0%。"
        report = QualityEvaluator(82).evaluate(
            mode="solver",
            prompt="用户内容：求解整数规划",
            answer=answer,
            tool_history=[{"name": "run_python", "ok": True, "artifacts": []}],
        )
        gate = next(item for item in report["gates"] if item["id"] == "global_optimality")
        self.assertTrue(gate["passed"])

    def test_deterministic_optimization_does_not_require_random_seeds(self) -> None:
        answer = RESULT_ANSWER + "\n线性规划运行后得到最优方案为 x=3，最大约束违反量为 0。"
        report = QualityEvaluator(82).evaluate(
            mode="solver",
            prompt="用户内容：求解线性规划",
            answer=answer,
            tool_history=[{"name": "solve_linear_program", "ok": True, "artifacts": []}],
        )
        gate = next(item for item in report["gates"] if item["id"] == "stochastic_robustness")
        self.assertTrue(gate["passed"])

    def test_reviewer_can_report_missing_evidence_without_self_penalty(self) -> None:
        answer = RESULT_ANSWER + """

高风险：原论文声称模拟退火得到全局最优方案，但没有多随机种子、收敛统计、
全局上界或最优性证明。预测结果也未设置测试集、未报告 RMSE；机理结果未做量纲检查。
建议作者补齐这些证据后再进入摘要。
"""
        report = QualityEvaluator(82).evaluate(
            mode="reviewer",
            prompt="用户内容：审查论文证据链",
            answer=answer,
        )
        specialist = {
            item["id"]: item["passed"]
            for item in report["gates"]
            if item["id"]
            in {
                "optimization_feasibility",
                "optimization_comparison",
                "global_optimality",
                "stochastic_robustness",
                "predictive_validation",
                "mechanistic_consistency",
            }
        }
        self.assertTrue(all(specialist.values()))

    def test_negated_sensitivity_does_not_raise_validation_score(self) -> None:
        evaluator = QualityEvaluator(82)
        base = evaluator.evaluate(
            mode="solver",
            prompt="用户内容：说明模型",
            answer=RESULT_ANSWER,
        )
        negated = evaluator.evaluate(
            mode="solver",
            prompt="用户内容：说明模型",
            answer=RESULT_ANSWER + "\n本轮未做敏感性分析，也没有鲁棒性检验。",
        )
        base_score = next(item["score"] for item in base["dimensions"] if item["id"] == "validation")
        negated_score = next(item["score"] for item in negated["dimensions"] if item["id"] == "validation")
        self.assertEqual(negated_score, base_score)

    def test_formal_abstract_requires_quantified_result_per_named_problem(self) -> None:
        hollow = """## 摘要

本文研究 2025 年赛题，共 2 问。问题一建立优化模型，问题二给出预测模型；
随机种子为 42，具体结果待替换。

## 正文

正文略。
"""
        report = QualityEvaluator(82).evaluate(
            mode="paper",
            prompt="用户内容：撰写正式摘要",
            answer=hollow,
        )
        gate = next(item for item in report["gates"] if item["id"] == "abstract_numeric_evidence")
        self.assertFalse(gate["passed"])

        quantified = """## 摘要

问题一建立约束优化模型，目标值为 53.08 秒，最大违反量为 0；
问题二采用时间外推验证，样本外 MAE=2.31，并给出适用边界。

## 正文

正文中的数值由结果表复核。
"""
        report = QualityEvaluator(82).evaluate(
            mode="paper",
            prompt="用户内容：撰写正式摘要",
            answer=quantified,
        )
        gate = next(item for item in report["gates"] if item["id"] == "abstract_numeric_evidence")
        self.assertTrue(gate["passed"])

    def test_missing_artifact_link_triggers_integrity_gate(self) -> None:
        run_id = "a" * 32
        answer = STRONG_ANSWER + f"\n[图形](/api/artifacts/{run_id}/missing.zip)"
        report = QualityEvaluator(82).evaluate(
            mode="solver",
            prompt="用户内容：生成可下载图形",
            answer=answer,
            tool_history=[{"name": "create_plot", "ok": True, "artifacts": []}],
            artifacts=[{"name": "figure.png"}],
        )
        gate = next(item for item in report["gates"] if item["id"] == "artifact_link_integrity")
        self.assertFalse(gate["passed"])
        self.assertLessEqual(report["total"], 70)

    def test_registered_artifact_link_passes_integrity_gate(self) -> None:
        run_id = "b" * 32
        answer = STRONG_ANSWER + f"\n[图形](/api/artifacts/{run_id}/figure.png)"
        report = QualityEvaluator(82).evaluate(
            mode="solver",
            prompt="用户内容：生成可下载图形",
            answer=answer,
            tool_history=[{"name": "create_plot", "ok": True, "artifacts": []}],
            artifacts=[{"name": "figure.png"}],
        )
        gate = next(item for item in report["gates"] if item["id"] == "artifact_link_integrity")
        self.assertTrue(gate["passed"])

    def test_paper_artifact_requires_completed_manuscript_audit(self) -> None:
        report = QualityEvaluator(82).evaluate(
            mode="paper",
            prompt="用户内容：完成整篇数学建模竞赛论文",
            answer=STRONG_ANSWER,
            artifacts=[{"name": "submission.pdf"}],
        )
        gates = {item["id"]: item for item in report["gates"]}
        self.assertFalse(gates["paper_artifact_audit"]["passed"])
        self.assertFalse(gates["paper_visual_evidence"]["passed"])
        self.assertLessEqual(report["total"], 72)

    def test_successful_paper_audit_satisfies_artifact_gates(self) -> None:
        audit_gates = [
            {"id": gate_id, "passed": True}
            for gate_id in (
                "paper_structure",
                "quantitative_abstract",
                "question_depth",
                "visual_evidence",
                "validation_traceability",
                "scholarly_traceability",
                "manuscript_integrity",
            )
        ]
        report = QualityEvaluator(82).evaluate(
            mode="paper",
            prompt="用户内容：完成整篇数学建模竞赛论文",
            answer=STRONG_ANSWER,
            artifacts=[{"name": "submission.pdf", "sha256": "a" * 64}],
            tool_history=[
                {
                    "name": "audit_competition_paper",
                    "ok": True,
                    "arguments": {"artifact_name": "submission.pdf", "full_paper": True},
                    "artifacts": [],
                    "audit": {
                        "passed": True,
                        "score": 100,
                        "gates": audit_gates,
                        "metrics": {
                            "artifactName": "submission.pdf",
                            "artifactSha256": "a" * 64,
                            "fullPaper": True,
                        },
                    },
                }
            ],
        )
        gates = {item["id"]: item["passed"] for item in report["gates"]}
        self.assertTrue(gates["paper_artifact_audit"])
        self.assertTrue(gates["paper_visual_evidence"])
        self.assertTrue(gates["paper_scholarly_structure"])

    def test_report_named_manuscript_cannot_bypass_audit(self) -> None:
        report = QualityEvaluator(82).evaluate(
            mode="paper",
            prompt="用户内容：完成整篇数学建模竞赛论文",
            answer=STRONG_ANSWER,
            artifacts=[{"name": "modeling-report.pdf", "sha256": "a" * 64}],
        )
        gates = {item["id"]: item["passed"] for item in report["gates"]}
        self.assertFalse(gates["paper_artifact_audit"])
        self.assertFalse(gates["paper_visual_evidence"])
        self.assertFalse(gates["paper_scholarly_structure"])

    def test_paper_audit_must_match_name_hash_and_full_paper(self) -> None:
        audit_gates = [
            {"id": gate_id, "passed": True}
            for gate_id in (
                "paper_structure",
                "quantitative_abstract",
                "question_depth",
                "visual_evidence",
                "validation_traceability",
                "scholarly_traceability",
                "manuscript_integrity",
            )
        ]
        cases = (
            ("old-draft.pdf", "a" * 64, True),
            ("submission.pdf", "b" * 64, True),
            ("submission.pdf", "a" * 64, False),
        )
        for audited_name, audited_hash, full_paper in cases:
            with self.subTest(name=audited_name, sha=audited_hash[:1], full_paper=full_paper):
                report = QualityEvaluator(82).evaluate(
                    mode="paper",
                    prompt="用户内容：完成整篇数学建模竞赛论文",
                    answer=STRONG_ANSWER,
                    artifacts=[{"name": "submission.pdf", "sha256": "a" * 64}],
                    tool_history=[
                        {
                            "name": "audit_competition_paper",
                            "ok": True,
                            "arguments": {"artifact_name": audited_name, "full_paper": full_paper},
                            "artifacts": [],
                            "audit": {
                                "passed": True,
                                "gates": audit_gates,
                                "metrics": {
                                    "artifactName": audited_name,
                                    "artifactSha256": audited_hash,
                                    "fullPaper": full_paper,
                                },
                            },
                        }
                    ],
                )
                gate = next(item for item in report["gates"] if item["id"] == "paper_artifact_audit")
                self.assertFalse(gate["passed"])

    def test_visual_and_scholarly_paper_gates_are_independent(self) -> None:
        base = {
            "paper_structure": True,
            "quantitative_abstract": True,
            "question_depth": True,
            "visual_evidence": True,
            "validation_traceability": True,
            "scholarly_traceability": True,
            "manuscript_integrity": True,
        }

        def evaluate(overrides: dict[str, bool]) -> dict[str, bool]:
            states = {**base, **overrides}
            report = QualityEvaluator(82).evaluate(
                mode="paper",
                prompt="用户内容：完成整篇数学建模竞赛论文",
                answer=STRONG_ANSWER,
                artifacts=[{"name": "submission.pdf", "sha256": "a" * 64}],
                tool_history=[
                    {
                        "name": "audit_competition_paper",
                        "ok": True,
                        "arguments": {"artifact_name": "submission.pdf", "full_paper": True},
                        "artifacts": [],
                        "audit": {
                            "passed": all(states.values()),
                            "gates": [
                                {"id": gate_id, "passed": passed}
                                for gate_id, passed in states.items()
                            ],
                            "metrics": {
                                "artifactName": "submission.pdf",
                                "artifactSha256": "a" * 64,
                                "fullPaper": True,
                            },
                        },
                    }
                ],
            )
            return {item["id"]: item["passed"] for item in report["gates"]}

        structure_failure = evaluate({"question_depth": False})
        self.assertTrue(structure_failure["paper_visual_evidence"])
        self.assertFalse(structure_failure["paper_scholarly_structure"])
        visual_failure = evaluate({"visual_evidence": False})
        self.assertFalse(visual_failure["paper_visual_evidence"])
        self.assertTrue(visual_failure["paper_scholarly_structure"])

    def test_run_auto_revision_keeps_better_answer(self) -> None:
        RevisingProvider.calls = 0
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = RunStore(root / "runs.db")
            settings = AgentSettings(
                provider="test",
                base_url="http://127.0.0.1:1/v1",
                api_key="",
                model="fake-model",
                quality_threshold=60,
                max_revisions=1,
            )
            manager = RunManager(
                store,
                root,
                settings_loader=lambda: settings,
                provider_factory=RevisingProvider,
            )
            run = manager.create({"mode": "solver", "content": "建立优化模型并验证"})
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                current = store.get(run["id"])
                if current["status"] == "completed":
                    break
                time.sleep(0.01)
            else:
                self.fail("run did not complete")

            self.assertEqual(current["output"], STRONG_ANSWER)
            self.assertEqual(current["revisionCount"], 1)
            self.assertTrue(current["quality"]["passed"])
            event_types = [event["type"] for event in store.events_after(run["id"], 0)]
            self.assertIn("REVISION_STARTED", event_types)
            self.assertIn("TEXT_MESSAGE_REPLACE", event_types)

    def test_run_store_migrates_legacy_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "runs.db"
            with closing(sqlite3.connect(database)) as connection:
                connection.execute(
                    """
                    CREATE TABLE runs (
                        id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        mode TEXT NOT NULL,
                        target TEXT NOT NULL,
                        provider TEXT NOT NULL DEFAULT '',
                        model TEXT NOT NULL DEFAULT '',
                        prompt TEXT NOT NULL,
                        output TEXT NOT NULL DEFAULT '',
                        error TEXT NOT NULL DEFAULT '',
                        meta_json TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                connection.commit()
            store = RunStore(database)
            with closing(sqlite3.connect(database)) as connection:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(runs)").fetchall()}
            self.assertIn("quality_json", columns)
            self.assertIn("revision_count", columns)
            run = store.create(
                {
                    "mode": "solver",
                    "target": "$math-modeling-solver",
                    "prompt": "测试",
                    "meta": {},
                }
            )
            self.assertEqual(run["quality"], {})
            self.assertEqual(run["revisionCount"], 0)


if __name__ == "__main__":
    unittest.main()
