"""Multi-seed stability audit for the stochastic global stage in Question 2."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import solve_q1_q2 as solver
from run_identity import RUN_ID


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "validation" / "q2_multiseed.json"
SEEDS = tuple(range(20_250_808, 20_250_816))


def main() -> None:
    original_seed = solver.RANDOM_SEED
    runs: list[dict[str, object]] = []
    try:
        for seed in SEEDS:
            solver.RANDOM_SEED = seed
            global_result = solver.run_global_search("centerline", 9.8)
            decoded = global_result["decoded_strategy"]
            refined = solver._refine_centerline_face(
                9.8,
                float(decoded["heading_rad"]),
                float(decoded["explosion_time_s"]),
            )
            exact = solver._interval_record(
                refined,
                "centerline",
                9.8,
                max_step_s=0.005,
            )
            runs.append(
                {
                    "seed": seed,
                    "coarse_duration_s": global_result["coarse_duration_s"],
                    "exact_duration_s": exact["duration_s"],
                    "iterations": global_result["iterations"],
                    "function_evaluations": global_result["function_evaluations"],
                    "success": global_result["success"],
                    "best_so_far_trace": global_result["best_so_far_trace"],
                    "strategy": refined.as_record(9.8),
                    "max_constraint_violation": exact["constraint_violations"]["max"],
                }
            )
    finally:
        solver.RANDOM_SEED = original_seed

    values = np.asarray([float(run["exact_duration_s"]) for run in runs])
    output = {
        "schema_version": "2.0",
        "run_id": RUN_ID,
        "purpose": "Q2 stochastic global-search convergence and multi-seed stability; every generation stores the incumbent and every final value is continuously polished and re-evaluated",
        "runs": runs,
        "summary": {
            "n": len(runs),
            "minimum_s": float(values.min()),
            "median_s": float(np.median(values)),
            "maximum_s": float(values.max()),
            "standard_deviation_s": float(values.std(ddof=1)),
            "iqr_s": float(np.percentile(values, 75) - np.percentile(values, 25)),
            "all_successful": all(bool(run["success"]) for run in runs),
            "failed_runs": sum(not bool(run["success"]) for run in runs),
            "max_constraint_violation": max(float(run["max_constraint_violation"]) for run in runs),
        },
        "reproduction_command": "python -B src/validate_q2_multiseed.py",
    }
    OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "output": str(OUTPUT), "summary": output["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
