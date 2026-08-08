"""Multi-seed convergence audit for the stochastic Q3/Q4 local refinements."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import optimizer
from run_identity import RUN_ID


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "validation" / "q3_q4_multiseed.json"
SEEDS = tuple(range(20_250_808, 20_250_813))


def _run_problem(problem: str) -> dict[str, object]:
    solve = optimizer.solve_q3 if problem == "Q3" else optimizer.solve_q4
    runs: list[dict[str, object]] = []
    for seed in SEEDS:
        result = solve(seed=seed, quick=False)
        diagnostics = result.diagnostics
        serialized = optimizer.result_to_dict(result)
        runs.append(
            {
                "seed": seed,
                "local_refinement_seed": diagnostics.local_refinement_seed,
                "local_refinement_iterations": diagnostics.local_refinement_iterations,
                "best_so_far_trace": diagnostics.local_refinement_trace,
                "start_exact_objective_s": diagnostics.local_refinement_start_exact_objective,
                "candidate_exact_objective_s": diagnostics.local_refinement_candidate_exact_objective,
                "final_exact_objective_s": result.exact_objective,
                "plans": serialized["plans"],
                "exact_centerline_union": serialized["exact_centerline_union"],
                "exact_centerline_duration_by_missile": serialized[
                    "exact_centerline_duration_by_missile"
                ],
                "status": diagnostics.status,
                "constraint_violations": diagnostics.constraint_violations,
                "max_constraint_violation": diagnostics.max_constraint_violation,
            }
        )

    values = np.asarray([float(run["final_exact_objective_s"]) for run in runs])
    best_index = int(np.argmax(values))
    worst_index = int(np.argmin(values))
    return {
        "runs": runs,
        "summary": {
            "n": len(runs),
            "minimum_s": float(values.min()),
            "median_s": float(np.median(values)),
            "maximum_s": float(values.max()),
            "standard_deviation_s": float(values.std(ddof=1)),
            "iqr_s": float(np.percentile(values, 75) - np.percentile(values, 25)),
            "all_feasible": all(run["status"] == "feasible_verified" for run in runs),
            "failed_runs": sum(run["status"] != "feasible_verified" for run in runs),
            "best_seed": int(runs[best_index]["seed"]),
            "worst_seed": int(runs[worst_index]["seed"]),
            "max_constraint_violation": max(
                float(run["max_constraint_violation"]) for run in runs
            ),
        },
    }


def main() -> None:
    output = {
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "purpose": "Q3/Q4 seeded local-refinement convergence and multi-seed feasibility audit",
        "seed_set": list(SEEDS),
        "problems": {
            "Q3": _run_problem("Q3"),
            "Q4": _run_problem("Q4"),
        },
        "reproduction_command": "python -B src/validate_q3_q4_multiseed.py",
    }
    OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    summaries = {
        problem: record["summary"] for problem, record in output["problems"].items()
    }
    print(json.dumps({"ok": True, "output": str(OUTPUT), "summaries": summaries}, ensure_ascii=False))


if __name__ == "__main__":
    main()
