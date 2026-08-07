"""Independent unit tests for the Q3--Q5 optimization layer."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geometry_engine import interval_duration  # noqa: E402
from optimizer import (  # noqa: E402
    BombPlan,
    MISSILES,
    aligned_candidates_for_route,
    coverage_intervals,
    coverage_objective,
    exact_evaluate,
    select_route_packages,
    solve_q3,
    strategy_constraint_violations,
)


class OptimizerGeometryTests(unittest.TestCase):
    def test_impact_times_match_official_kinematics(self) -> None:
        self.assertAlmostEqual(MISSILES["M1"].impact_time, 66.99917080747261, places=10)
        self.assertAlmostEqual(MISSILES["M2"].impact_time, 63.75038126247647, places=10)
        self.assertAlmostEqual(MISSILES["M3"].impact_time, 60.36647340296691, places=10)

    def test_aligned_route_candidate_has_positive_exact_interval(self) -> None:
        candidates = aligned_candidates_for_route(
            "FY1", 180.0, 120.0, "M1", explosion_step=0.20, time_bin=0.5
        )
        self.assertGreater(len(candidates), 0)
        best = max(candidates, key=lambda plan: interval_duration(plan.estimated_intervals))
        individual, _union = exact_evaluate([best], max_step=0.01)
        self.assertGreater(interval_duration(individual[0]), 0.1)
        self.assertLessEqual(best.release_time, best.explosion_time)
        self.assertGreater(best.explosion_position[2], 0.0)

    def test_route_package_enforces_one_second_release_gap(self) -> None:
        candidates = aligned_candidates_for_route(
            "FY1", 180.0, 130.0, "M1", explosion_step=0.12, time_bin=0.4
        )
        packages = select_route_packages(
            candidates, max_bombs=3, beam_width=50, exact_count=True
        )
        self.assertGreater(len(packages), 0)
        plan = packages[0].plans
        self.assertEqual(len(plan), 3)
        release_times = [item.release_time for item in plan]
        self.assertTrue(
            all(right - left >= 1.0 - 1e-10 for left, right in zip(release_times, release_times[1:]))
        )
        self.assertTrue(all(item.heading_deg == plan[0].heading_deg for item in plan))
        self.assertTrue(all(item.speed == plan[0].speed for item in plan))

    def test_interval_union_does_not_double_count(self) -> None:
        first = BombPlan(
            "FY1", 180.0, 120.0, 0.0, 1.0, "M1", estimated_intervals=((1.0, 4.0),)
        )
        second = BombPlan(
            "FY2", 180.0, 120.0, 0.0, 1.0, "M1", estimated_intervals=((3.0, 6.0),)
        )
        intervals = coverage_intervals(
            [first, second], lambda plan: plan.estimated_intervals
        )
        self.assertEqual(intervals["M1"], [(1.0, 6.0)])
        self.assertAlmostEqual(coverage_objective(intervals), 5.0)

    def test_constraint_audit_detects_gap_and_shared_route_errors(self) -> None:
        plans = [
            BombPlan("FY1", 180.0, 120.0, 0.0, 1.0, "M1"),
            BombPlan("FY1", 181.0, 121.0, 0.5, 1.0, "M1"),
        ]
        violations = strategy_constraint_violations(plans)
        self.assertAlmostEqual(violations["release_gap"], 0.5)
        self.assertAlmostEqual(violations["shared_heading"], 1.0)
        self.assertAlmostEqual(violations["shared_speed"], 1.0)


class OptimizerEndToEndTests(unittest.TestCase):
    def test_q3_quick_solver_is_reproducible_and_feasible(self) -> None:
        first = solve_q3(seed=20250808, quick=True)
        second = solve_q3(seed=20250808, quick=True)
        self.assertEqual(first.plans, second.plans)
        self.assertAlmostEqual(first.exact_objective, second.exact_objective, places=10)
        self.assertEqual(len(first.plans), 3)
        self.assertGreater(first.exact_objective, 1.0)
        self.assertLessEqual(first.diagnostics.max_constraint_violation, 1e-10)
        headings = {round(plan.heading_deg, 10) for plan in first.plans}
        speeds = {round(plan.speed, 10) for plan in first.plans}
        self.assertEqual(len(headings), 1)
        self.assertEqual(len(speeds), 1)


if __name__ == "__main__":
    unittest.main()
