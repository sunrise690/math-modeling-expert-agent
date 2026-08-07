"""Regression and geometry checks for the independent Q1/Q2 computation.

The suite uses only the Python standard-library ``unittest`` runner so the
validation remains runnable in the contest environment without pytest.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import solve_q1_q2 as solver  # noqa: E402


VALIDATION = PROJECT_ROOT / "validation" / "q1_q2_independent.json"


def _strategy(record: dict[str, object]) -> solver.Strategy:
    return solver.Strategy(
        heading_rad=float(record["heading_rad"]),
        speed_mps=float(record["speed_mps"]),
        release_time_s=float(record["release_time_s"]),
        fuse_delay_s=float(record["fuse_delay_s"]),
    )


class Q1Q2ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not VALIDATION.exists():
            raise AssertionError("run src/solve_q1_q2.py before the tests")
        cls.result = json.loads(VALIDATION.read_text(encoding="utf-8"))

    def test_q1_both_conventions_and_gravity_sensitivity(self) -> None:
        expected = (
            ("g_9.80", 1.435082102, 1.391642668),
            ("g_9.81", 1.448916379, 1.405034214),
        )
        for gravity_key, center_expected, full_expected in expected:
            with self.subTest(gravity=gravity_key):
                q1 = self.result["q1"][gravity_key]
                self.assertAlmostEqual(
                    q1["centerline"]["duration_s"], center_expected, delta=2e-7
                )
                self.assertAlmostEqual(
                    q1["full_cylinder"]["duration_s"], full_expected, delta=2e-7
                )
                self.assertLess(
                    q1["centerline"]["boundary_residual_max_m"], 2e-8
                )
                self.assertLess(
                    q1["full_cylinder"]["boundary_residual_max_m"], 2e-8
                )
                self.assertGreater(
                    q1["centerline"]["duration_s"],
                    q1["full_cylinder"]["duration_s"],
                )

    def test_q1_fixed_release_and_explosion_positions(self) -> None:
        strategy = self.result["q1"]["g_9.80"]["strategy"]
        for actual, expected in zip(
            strategy["release_position_m"], (17620.0, 0.0, 1800.0)
        ):
            self.assertAlmostEqual(actual, expected, delta=1e-10)
        for actual, expected in zip(
            strategy["explosion_position_m"], (17188.0, 0.0, 1736.496)
        ):
            self.assertAlmostEqual(actual, expected, delta=1e-10)
        self.assertAlmostEqual(strategy["explosion_time_s"], 5.1, delta=1e-12)

    def test_q2_centerline_optimum_and_residuals(self) -> None:
        q2 = self.result["q2"]["centerline"]
        strategy = _strategy(q2["strategy"])
        self.assertAlmostEqual(q2["duration_s"], 4.832501802, delta=3e-6)
        self.assertAlmostEqual(strategy.speed_mps, 140.0, delta=1e-10)
        self.assertAlmostEqual(strategy.release_time_s, 0.0, delta=1e-10)
        self.assertAlmostEqual(strategy.fuse_delay_s, 0.7132458, delta=2e-5)
        self.assertAlmostEqual(strategy.heading_rad, 0.1206208, delta=2e-5)
        self.assertLess(q2["boundary_residual_max_m"], 2e-7)
        self.assertLess(q2["constraint_violations"]["max"], 1e-12)
        for left, right in q2["intervals_s"]:
            self.assertLess(abs(solver.centerline_margin(left, strategy, 9.8)), 2e-7)
            self.assertLess(abs(solver.centerline_margin(right, strategy, 9.8)), 2e-7)

    def test_q2_full_cylinder_zero_and_positive_fuse_plans(self) -> None:
        zero = self.result["q2"]["full_cylinder_tau_0_boundary"]
        engineering = self.result["q2"]["full_cylinder_tau_0.02_engineering"]
        zero_strategy = _strategy(zero["strategy"])
        engineering_strategy = _strategy(engineering["strategy"])

        self.assertEqual(zero_strategy.fuse_delay_s, 0.0)
        self.assertAlmostEqual(zero_strategy.speed_mps, 140.0, delta=1e-10)
        self.assertAlmostEqual(zero["duration_s"], 4.588063540, delta=4e-6)
        self.assertAlmostEqual(zero_strategy.heading_rad, 0.0890923, delta=3e-5)
        self.assertAlmostEqual(
            zero_strategy.explosion_time_s, 0.9327241, delta=3e-5
        )
        self.assertLess(zero["boundary_residual_max_m"], 2e-7)
        self.assertLess(zero["constraint_violations"]["max"], 1e-12)

        self.assertAlmostEqual(engineering_strategy.fuse_delay_s, 0.02, delta=1e-14)
        self.assertAlmostEqual(engineering["duration_s"], 4.588063344, delta=4e-6)
        self.assertLessEqual(engineering["duration_s"], zero["duration_s"] + 1e-9)
        self.assertLess(zero["duration_s"] - engineering["duration_s"], 2e-6)
        self.assertLess(engineering["constraint_violations"]["max"], 1e-12)

    def test_full_cylinder_endpoints_are_continuous_cone_roots(self) -> None:
        record = self.result["q2"]["full_cylinder_tau_0_boundary"]
        strategy = _strategy(record["strategy"])
        start, end = record["intervals_s"][0]
        start_details = solver.full_cylinder_details(start, strategy, 9.8)
        end_details = solver.full_cylinder_details(end, strategy, 9.8)
        self.assertLess(abs(start_details["margin_m"]), 2e-7)
        self.assertLess(abs(end_details["margin_m"]), 2e-7)
        self.assertAlmostEqual(start_details["worst_z_m"], 0.0, delta=1e-10)
        self.assertAlmostEqual(end_details["worst_z_m"], 10.0, delta=1e-10)
        self.assertGreater(start_details["range_margin_m"], 10_000.0)
        self.assertGreater(end_details["range_margin_m"], 10_000.0)

    def test_dense_azimuth_and_metadata(self) -> None:
        self.assertEqual(self.result["metadata"]["random_seed"], solver.RANDOM_SEED)
        self.assertTrue(self.result["metadata"]["geometry_engine_available"])
        checks = self.result["q2"]["dense_azimuth_crosscheck"]
        self.assertTrue(checks)
        self.assertLess(
            max(item["absolute_cosine_difference"] for item in checks), 5e-12
        )
        self.assertEqual(
            self.result["q2"]["centerline"]["global_search"]["seed"],
            solver.RANDOM_SEED,
        )
        self.assertEqual(
            self.result["q2"]["full_cylinder_tau_0_boundary"]["global_search"][
                "seed"
            ],
            solver.RANDOM_SEED,
        )

    def test_q2_gravity_sensitivity_is_recorded(self) -> None:
        center = self.result["q2"]["centerline"]
        same = center["gravity_sensitivity"]["same_strategy_at_g_9.81"]
        reoptimized = center["gravity_sensitivity"]["reoptimized_at_g_9.81"]
        self.assertGreater(same["duration_s"], 0.0)
        self.assertGreaterEqual(reoptimized["duration_s"], same["duration_s"] - 1e-8)

        zero = self.result["q2"]["full_cylinder_tau_0_boundary"]
        zero_981 = zero["gravity_sensitivity"]["same_strategy_at_g_9.81"]
        # With tau=0, gravity never acts before detonation, hence identical geometry.
        self.assertAlmostEqual(
            zero_981["duration_s"], zero["duration_s"], delta=2e-9
        )


if __name__ == "__main__":
    unittest.main()
