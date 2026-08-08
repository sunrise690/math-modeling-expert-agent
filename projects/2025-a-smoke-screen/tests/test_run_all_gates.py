"""Regression tests for paper freshness and multi-seed evidence gates."""

from __future__ import annotations

import subprocess
import json
import statistics
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import run_all  # noqa: E402
import solve_q3_q5  # noqa: E402


def _valid_run(seed: int, terminal: float = 4.8325018024627) -> dict[str, object]:
    return {
        "seed": seed,
        "success": True,
        "exact_duration_s": terminal,
        "max_constraint_violation": 0.0,
        "best_so_far_trace": [
            {"generation": 1, "best_coarse_duration_s": 4.0},
            {"generation": 2, "best_coarse_duration_s": 4.8},
        ],
    }


def _valid_q3_q4_run(seed: int, terminal: float) -> dict[str, object]:
    return {
        "seed": seed,
        "status": "feasible_verified",
        "final_exact_objective_s": terminal,
        "plans": [{}, {}, {}],
        "constraint_violations": {"speed": 0.0, "release_gap": 0.0},
        "max_constraint_violation": 0.0,
        "best_so_far_trace": [
            {"iteration": 0, "best_fast_objective_s": 1.0},
            {"iteration": 1, "best_fast_objective_s": 1.5},
            {"iteration": 2, "best_fast_objective_s": 1.5},
        ],
    }


class Q2MultiseedGateTests(unittest.TestCase):
    def test_gate_recomputes_from_runs_and_ignores_false_summary(self) -> None:
        payload = {
            "runs": [_valid_run(100 + index) for index in range(5)],
            "summary": {
                "all_successful": False,
                "standard_deviation_s": 999.0,
                "max_constraint_violation": 999.0,
            },
        }

        metrics = run_all._q2_multiseed_metrics(payload)

        self.assertTrue(metrics["passed"])
        self.assertEqual(metrics["unique_seed_count"], 5)
        self.assertEqual(metrics["trace_count"], 5)

    def test_duplicate_seed_fails_even_when_summary_claims_pass(self) -> None:
        runs = [_valid_run(100 + index) for index in range(5)]
        runs[-1]["seed"] = runs[0]["seed"]
        metrics = run_all._q2_multiseed_metrics(
            {"runs": runs, "summary": {"all_successful": True}}
        )

        self.assertFalse(metrics["passed"])
        self.assertEqual(metrics["unique_seed_count"], 4)

    def test_missing_trace_or_constraint_violation_fails(self) -> None:
        runs = [_valid_run(100 + index) for index in range(5)]
        runs[1]["best_so_far_trace"] = []
        runs[2]["max_constraint_violation"] = 1.0e-4

        metrics = run_all._q2_multiseed_metrics({"runs": runs})

        self.assertFalse(metrics["passed"])
        self.assertEqual(metrics["trace_count"], 4)
        self.assertAlmostEqual(metrics["max_constraint_violation"], 1.0e-4)

    def test_failed_run_and_terminal_dispersion_fail(self) -> None:
        runs = [_valid_run(100 + index) for index in range(5)]
        runs[0]["success"] = False
        runs[-1]["exact_duration_s"] = 4.9

        metrics = run_all._q2_multiseed_metrics({"runs": runs})

        self.assertFalse(metrics["passed"])
        self.assertEqual(metrics["success_count"], 4)
        self.assertGreater(metrics["standard_deviation_s"], 1.0e-9)

    def test_standard_deviation_uses_the_same_sample_definition_as_validator(self) -> None:
        values = [4.8325 + index * 1.0e-13 for index in range(5)]
        runs = [
            _valid_run(100 + index, terminal=value)
            for index, value in enumerate(values)
        ]

        metrics = run_all._q2_multiseed_metrics({"runs": runs})

        self.assertEqual(metrics["standard_deviation_s"], statistics.stdev(values))


class Q3Q4MultiseedGateTests(unittest.TestCase):
    def _payload(self) -> dict[str, object]:
        return {
            "problems": {
                "Q3": {
                    "runs": [
                        _valid_q3_q4_run(20250808 + index, 6.0 + 0.1 * index)
                        for index in range(5)
                    ],
                    "summary": {"best_seed": -1, "all_feasible": False},
                },
                "Q4": {
                    "runs": [
                        _valid_q3_q4_run(20250808 + index, 15.0 + 0.01 * index)
                        for index in range(5)
                    ],
                    "summary": {"best_seed": -1, "all_feasible": False},
                },
            }
        }

    def test_gate_recomputes_best_seed_and_does_not_require_low_dispersion(self) -> None:
        payload = self._payload()
        payload["problems"]["Q3"]["runs"][2]["final_exact_objective_s"] = 9.0

        metrics = run_all._q3_q4_multiseed_metrics(payload)

        self.assertTrue(metrics["Q3"]["passed"])
        self.assertTrue(metrics["Q4"]["passed"])
        self.assertEqual(metrics["Q3"]["best_seed"], 20250810)
        self.assertEqual(metrics["Q4"]["best_seed"], 20250812)

    def test_duplicate_seed_bad_plan_or_descending_trace_fails(self) -> None:
        payload = deepcopy(self._payload())
        q3_runs = payload["problems"]["Q3"]["runs"]
        q3_runs[-1]["seed"] = q3_runs[0]["seed"]
        q3_runs[1]["plans"] = [{}, {}]
        q3_runs[2]["best_so_far_trace"][1]["best_fast_objective_s"] = 0.5

        metrics = run_all._q3_q4_multiseed_metrics(payload)

        self.assertFalse(metrics["Q3"]["passed"])
        self.assertEqual(metrics["Q3"]["unique_seed_count"], 4)
        self.assertEqual(metrics["Q3"]["plan_count_ok"], 4)
        self.assertEqual(metrics["Q3"]["trace_count"], 4)

    def test_nonfinite_constraint_or_infeasible_status_fails(self) -> None:
        payload = deepcopy(self._payload())
        q4_runs = payload["problems"]["Q4"]["runs"]
        q4_runs[0]["constraint_violations"]["speed"] = float("nan")
        q4_runs[1]["status"] = "failed"

        metrics = run_all._q3_q4_multiseed_metrics(payload)

        self.assertFalse(metrics["Q4"]["passed"])
        self.assertEqual(metrics["Q4"]["feasible_count"], 4)
        self.assertGreater(metrics["Q4"]["malformed_runs"], 0)


class PerProblemSeedTests(unittest.TestCase):
    def test_compatibility_seed_is_the_default_for_each_problem(self) -> None:
        self.assertEqual(
            solve_q3_q5.resolve_problem_seeds(123),
            {"Q3": 123, "Q4": 123, "Q5": 123},
        )
        self.assertEqual(
            solve_q3_q5.resolve_problem_seeds(123, q3_seed=10, q4_seed=9),
            {"Q3": 10, "Q4": 9, "Q5": 123},
        )

    def test_cli_accepts_per_problem_seed_overrides(self) -> None:
        args = solve_q3_q5.parse_args(
            [
                "--seed",
                "8",
                "--q3-seed",
                "10",
                "--q4-seed",
                "9",
                "--q5-seed",
                "8",
            ]
        )
        self.assertEqual((args.seed, args.q3_seed, args.q4_seed, args.q5_seed), (8, 10, 9, 8))

    def test_report_records_and_solvers_receive_per_problem_seeds(self) -> None:
        fake_result = SimpleNamespace(exact_objective=1.0)
        workbook_paths = {
            "Q3": Path("result1.xlsx"),
            "Q4": Path("result2.xlsx"),
            "Q5": Path("result3.xlsx"),
        }
        with (
            patch.object(solve_q3_q5, "solve_q3", return_value=fake_result) as q3,
            patch.object(solve_q3_q5, "solve_q4", return_value=fake_result) as q4,
            patch.object(solve_q3_q5, "solve_q5", return_value=fake_result) as q5,
            patch.object(solve_q3_q5, "write_workbooks", return_value=workbook_paths),
            patch.object(solve_q3_q5, "roundtrip_validate_workbook", return_value={}),
            patch.object(solve_q3_q5, "result_to_dict", return_value={}),
            patch.object(solve_q3_q5, "sha256_file", return_value="hash"),
        ):
            _results, report = solve_q3_q5.run_all(
                seed=8,
                q3_seed=10,
                q4_seed=9,
                q5_seed=8,
                quick=True,
                full_cylinder_audit=False,
            )

        q3.assert_called_once_with(seed=10, quick=True)
        q4.assert_called_once_with(seed=9, quick=True)
        q5.assert_called_once_with(seed=8, quick=True)
        self.assertEqual(report["random_seed"], 8)
        self.assertEqual(report["random_seed_by_problem"], {"Q3": 10, "Q4": 9, "Q5": 8})
        self.assertIn("--q3-seed 10 --q4-seed 9 --q5-seed 8", report["reproduction_command"])


class Q5ClaimBoundaryTests(unittest.TestCase):
    def test_verified_restricted_search_wording_passes(self) -> None:
        self.assertTrue(
            run_all._q5_claim_respects_boundary(
                "Verified feasible solution from a deterministic restricted route library; no global optimality proof.",
                "Q5 is not claimed globally optimal.",
            )
        )

    def test_high_quality_or_stable_wording_fails(self) -> None:
        disclaimer = "Q5 is not claimed globally optimal."
        for adjective in ("High-quality", "Stable", "Robust"):
            with self.subTest(adjective=adjective):
                self.assertFalse(
                    run_all._q5_claim_respects_boundary(
                        f"{adjective} solution from a deterministic restricted route library; no global optimality proof.",
                        disclaimer,
                    )
                )

    def test_missing_restricted_search_or_global_disclaimer_fails(self) -> None:
        self.assertFalse(
            run_all._q5_claim_respects_boundary(
                "Verified feasible solution.",
                "The route was computed once.",
            )
        )

    def test_q5_paper_rejects_unqualified_quality_or_optimality_claims(self) -> None:
        cautious = r"""
\section{问题五：多机协同}
本文只给出受限搜索中的经验证可行解，不声称稳定性，也不声称全局最优。
\section{跨问题验证}
"""
        self.assertTrue(run_all._q5_paper_claims_are_bounded(cautious))
        for sentence in (
            "本文得到高质量策略。",
            "该随机搜索结果稳定。",
            "因此获得全局最优解。",
        ):
            with self.subTest(sentence=sentence):
                unsafe = cautious.replace("本文只给出", sentence + "\n本文只给出")
                self.assertFalse(run_all._q5_paper_claims_are_bounded(unsafe))


class PaperFreshnessGateTests(unittest.TestCase):
    def test_audit_must_target_exact_full_paper_artifact(self) -> None:
        audit = {
            "passed": True,
            "status": "pass",
            "metrics": {
                "artifactName": "main.pdf",
                "artifactSha256": "abc123",
                "fullPaper": True,
                "expectedQuestions": 5,
            },
        }
        self.assertTrue(
            run_all._audit_targets_artifact(
                audit,
                artifact_name="main.pdf",
                artifact_sha256="abc123",
                expected_questions=5,
            )
        )
        stale = deepcopy(audit)
        stale["metrics"]["artifactSha256"] = "old-pdf"
        self.assertFalse(
            run_all._audit_targets_artifact(
                stale,
                artifact_name="main.pdf",
                artifact_sha256="abc123",
                expected_questions=5,
            )
        )

    def test_audit_provenance_rejects_a_stale_passing_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            pdf = base / "main.pdf"
            audit_path = base / "paper-quality-audit.json"
            provenance = base / "paper-audit-provenance.json"
            pdf.write_bytes(b"current-pdf")
            audit_path.write_text(
                json.dumps(
                    {
                        "passed": True,
                        "status": "pass",
                        "metrics": {
                            "artifactName": "main.pdf",
                            "artifactSha256": "stale-hash",
                            "fullPaper": True,
                            "expectedQuestions": 5,
                        },
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(run_all, "PAPER_PDF_PATH", pdf),
                patch.object(run_all, "PAPER_AUDIT_JSON_PATH", audit_path),
                patch.object(run_all, "PAPER_AUDIT_PROVENANCE_PATH", provenance),
            ):
                with self.assertRaises(RuntimeError):
                    run_all._write_paper_audit_provenance()

    def test_input_bundle_changes_when_any_dependency_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            tex = base / "main.tex"
            figure = base / "figure.svg"
            tex.write_text("version one", encoding="utf-8")
            figure.write_text("figure one", encoding="utf-8")
            first, _ = run_all._fingerprint_files([tex, figure], base=base)

            figure.write_text("figure two", encoding="utf-8")
            second, _ = run_all._fingerprint_files([tex, figure], base=base)

        self.assertNotEqual(first, second)

    def test_old_visual_qa_cannot_pass_new_pdf_or_input_bundle(self) -> None:
        manual = {
            "status": "PASS",
            "review_type": "codex_page_by_page_visual",
            "reviewed_pdf_sha256": "pdf-new",
            "reviewed_page_count": 23,
            "reviewed_input_bundle_sha256": "bundle-new",
        }
        self.assertTrue(
            run_all._manual_visual_record_is_current(
                manual,
                pdf_sha256="pdf-new",
                page_count=23,
                input_bundle_sha256="bundle-new",
                rendered_page_count=23,
            )
        )
        self.assertFalse(
            run_all._manual_visual_record_is_current(
                manual,
                pdf_sha256="pdf-old",
                page_count=23,
                input_bundle_sha256="bundle-new",
                rendered_page_count=23,
            )
        )
        self.assertFalse(
            run_all._manual_visual_record_is_current(
                manual,
                pdf_sha256="pdf-new",
                page_count=23,
                input_bundle_sha256="bundle-changed",
                rendered_page_count=23,
            )
        )
        self.assertFalse(
            run_all._manual_visual_record_is_current(
                manual,
                pdf_sha256="pdf-new",
                page_count=23,
                input_bundle_sha256="bundle-new",
                rendered_page_count=22,
            )
        )

    def test_build_and_audit_records_require_exact_hashes(self) -> None:
        build_record = {
            "input_bundle_sha256": "bundle",
            "paper_pdf_sha256": "pdf",
            "paper_log_sha256": "log",
        }
        self.assertTrue(
            run_all._record_matches(
                build_record,
                {
                    "input_bundle_sha256": "bundle",
                    "paper_pdf_sha256": "pdf",
                    "paper_log_sha256": "log",
                },
            )
        )
        self.assertFalse(
            run_all._record_matches(
                build_record,
                {"input_bundle_sha256": "changed", "paper_pdf_sha256": "pdf"},
            )
        )

    def test_full_recompute_compiles_tex_then_runs_paper_audit(self) -> None:
        calls: list[tuple[list[str], Path]] = []

        def fake_run(
            command: list[str], *, cwd: Path = run_all.ROOT
        ) -> subprocess.CompletedProcess[str]:
            calls.append((command, cwd))
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with (
            patch.object(run_all, "_run", side_effect=fake_run),
            patch.object(run_all, "_write_paper_build_provenance") as build_record,
            patch.object(run_all, "_write_paper_audit_provenance") as audit_record,
        ):
            run_all._full_recompute()

        command_names = [command[0] for command, _cwd in calls]
        latex_index = command_names.index("latexmk")
        audit_index = next(
            index
            for index, (command, _cwd) in enumerate(calls)
            if any(str(item).endswith("audit_paper.py") for item in command)
        )
        self.assertLess(latex_index, audit_index)
        self.assertEqual(calls[latex_index][1], run_all.PAPER_DIR)
        q3_q5_command = next(
            command
            for command, _cwd in calls
            if "src/solve_q3_q5.py" in command
        )
        self.assertEqual(
            q3_q5_command[q3_q5_command.index("--q3-seed") + 1],
            "20250810",
        )
        self.assertEqual(
            q3_q5_command[q3_q5_command.index("--q4-seed") + 1],
            "20250809",
        )
        self.assertEqual(
            q3_q5_command[q3_q5_command.index("--q5-seed") + 1],
            "20250808",
        )
        build_record.assert_called_once()
        audit_record.assert_called_once()


if __name__ == "__main__":
    unittest.main()
