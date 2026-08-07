from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from geometry_engine import (  # noqa: E402
    CylindricalOcclusionEvaluator,
    FY1_INITIAL,
    UAVTrajectory,
    effective_intervals,
    find_nonnegative_intervals,
    interval_duration,
    make_q1_scenario,
    merge_intervals,
    point_occlusion_margin,
    segment_sphere_intersection_interval,
    trajectory_occlusion_margin,
)


class KinematicsTests(unittest.TestCase):
    def test_zero_fuse_delay_is_a_valid_closed_boundary(self) -> None:
        uav = UAVTrajectory(FY1_INITIAL, (1.0, 0.0), 140.0)
        release = uav.release(0.5, 0.0)
        self.assertAlmostEqual(release.explosion_time, 0.5)
        np.testing.assert_allclose(release.explosion_position, uav.position(0.5))

    def test_q1_missile_and_bomb_states_follow_official_parameters(self) -> None:
        missile, uav, release, cloud, _ = make_q1_scenario()

        np.testing.assert_allclose(uav.velocity, (-120.0, 0.0, 0.0), atol=1e-12)
        np.testing.assert_allclose(release.release_position, (17_620.0, 0.0, 1_800.0))
        self.assertAlmostEqual(release.explosion_time, 5.1, places=12)
        np.testing.assert_allclose(
            release.explosion_position, (17_188.0, 0.0, 1_736.496), atol=1e-10
        )
        np.testing.assert_allclose(cloud.center(7.1), (17_188.0, 0.0, 1_730.496))
        np.testing.assert_allclose(missile.position(missile.impact_time), (0.0, 0.0, 0.0), atol=1e-9)

    def test_segment_sphere_intersection_is_finite_segment_geometry(self) -> None:
        hit = segment_sphere_intersection_interval(
            (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (5.0, 0.0, 0.0), 1.0
        )
        self.assertIsNotNone(hit)
        assert hit is not None
        np.testing.assert_allclose(hit, (0.4, 0.6), atol=1e-12)
        self.assertIsNone(
            segment_sphere_intersection_interval(
                (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (5.0, 0.0, 0.0), 1.0
            )
        )


class IntervalTests(unittest.TestCase):
    def test_continuous_root_refinement_and_union_measure(self) -> None:
        intervals = find_nonnegative_intervals(
            lambda time: 1.0 - (time - 2.0) ** 2,
            0.0,
            4.0,
            max_step=0.17,
        )
        self.assertEqual(len(intervals), 1)
        np.testing.assert_allclose(intervals[0], (1.0, 3.0), atol=1e-10)
        merged = merge_intervals([(0.0, 1.0), (0.5, 2.0), (3.0, 4.0)])
        self.assertEqual(merged, [(0.0, 2.0), (3.0, 4.0)])
        self.assertAlmostEqual(interval_duration(merged), 3.0)


class Q1IndependentReproductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.missile, _, _, cls.cloud, cls.target = make_q1_scenario()
        cls.evaluator = CylindricalOcclusionEvaluator(
            cls.target, n_azimuth=144, n_linear=11, local_starts=5
        )

    def test_centerline_interval_and_duration(self) -> None:
        intervals = effective_intervals(
            self.missile,
            self.cloud,
            self.target,
            mode="centerline",
            max_step=0.01,
        )
        self.assertEqual(len(intervals), 1)
        np.testing.assert_allclose(
            intervals[0],
            (8.013006056738, 9.448088158702),
            rtol=0.0,
            atol=2e-9,
        )
        self.assertAlmostEqual(interval_duration(intervals), 1.435082101964, places=9)

    def test_complete_cylinder_conservative_interval_and_duration(self) -> None:
        intervals = effective_intervals(
            self.missile,
            self.cloud,
            self.target,
            mode="full_cylinder",
            evaluator=self.evaluator,
            max_step=0.01,
            optimize_full=True,
        )
        self.assertEqual(len(intervals), 1)
        np.testing.assert_allclose(
            intervals[0],
            (8.056445490431, 9.448088158702),
            rtol=0.0,
            atol=3e-8,
        )
        self.assertAlmostEqual(interval_duration(intervals), 1.391642668270, places=7)

        entry, exit_time = intervals[0]
        for time in (entry, exit_time):
            margin = trajectory_occlusion_margin(
                time,
                self.missile,
                self.cloud,
                self.target,
                mode="full_cylinder",
                evaluator=self.evaluator,
                optimize_full=True,
            )
            self.assertAlmostEqual(margin, 0.0, places=7)

    def test_conservative_interval_is_subset_of_centerline_interval(self) -> None:
        center = effective_intervals(
            self.missile, self.cloud, self.target, mode="centerline", max_step=0.02
        )[0]
        full = effective_intervals(
            self.missile,
            self.cloud,
            self.target,
            mode="full_cylinder",
            evaluator=self.evaluator,
            max_step=0.02,
            optimize_full=True,
        )[0]
        self.assertGreaterEqual(full[0] + 1e-10, center[0])
        self.assertLessEqual(full[1], center[1] + 1e-10)

        midpoint = 0.5 * (full[0] + full[1])
        center_margin = point_occlusion_margin(
            self.missile.position(midpoint),
            self.cloud.center(midpoint),
            self.target.center,
            self.cloud.radius,
        )
        full_margin = trajectory_occlusion_margin(
            midpoint,
            self.missile,
            self.cloud,
            self.target,
            mode="full_cylinder",
            evaluator=self.evaluator,
            optimize_full=True,
        )
        self.assertGreaterEqual(center_margin, full_margin)
        self.assertGreater(full_margin, 0.0)


if __name__ == "__main__":
    unittest.main()
