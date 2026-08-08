"""Independent, reproducible computation for 2025 CUMCM A, Questions 1--2.

Only the kinematics stated in the official problem are used.  Two occlusion
conventions are reported side by side:

``centerline``
    The smoke sphere intersects the finite segment from M1 to the geometric
    centre ``(0, 200, 5)`` of the protected cylinder.

``full_cylinder``
    Every finite segment from M1 to every point of the solid cylinder is
    required to intersect the smoke sphere.  Seen from the missile, the
    sphere defines a circular shadow cone.  Cone containment of the convex
    cylinder is checked continuously on the two extreme rim circles, not on
    an arbitrary collection of target points.

The global stage uses a fixed random seed.  Final interval boundaries are
Brent roots of continuous geometric margins, and continuous azimuthal
minimisation is used for the complete-cylinder results.  Run this file to
write ``validation/q1_q2_independent.json``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from math import ceil, cos, pi, sin, sqrt
from pathlib import Path
from typing import Callable, Literal, Sequence

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import brentq, differential_evolution, minimize, minimize_scalar
from run_identity import RUN_ID

# Use the shared engine's public point/segment primitive when it is present.
# Q2's mathematically important tau=0 boundary is represented locally because
# geometry_engine.BombRelease intentionally requires a strictly positive fuse.
try:
    from geometry_engine import point_to_segment_distance as _engine_segment_distance

    GEOMETRY_ENGINE_AVAILABLE = True
except ImportError:  # pragma: no cover - the project ships geometry_engine.py
    try:  # Support ``python -m src.solve_q1_q2`` as well as direct execution.
        from .geometry_engine import point_to_segment_distance as _engine_segment_distance

        GEOMETRY_ENGINE_AVAILABLE = True
    except ImportError:
        GEOMETRY_ENGINE_AVAILABLE = False
        _engine_segment_distance = None


FloatArray = NDArray[np.float64]
Mode = Literal["centerline", "full_cylinder"]

RANDOM_SEED = 20_250_808
MISSILE_INITIAL = np.array((20_000.0, 0.0, 2_000.0))
MISSILE_SPEED = 300.0
MISSILE_VELOCITY = -MISSILE_SPEED * MISSILE_INITIAL / np.linalg.norm(MISSILE_INITIAL)
MISSILE_IMPACT_TIME = float(np.linalg.norm(MISSILE_INITIAL) / MISSILE_SPEED)
FY1_INITIAL = np.array((17_800.0, 0.0, 1_800.0))
TARGET_BOTTOM_CENTER = np.array((0.0, 200.0, 0.0))
TARGET_RADIUS = 7.0
TARGET_HEIGHT = 10.0
TARGET_CENTER = TARGET_BOTTOM_CENTER + np.array((0.0, 0.0, TARGET_HEIGHT / 2.0))
SMOKE_RADIUS = 10.0
SMOKE_LIFETIME = 20.0
SMOKE_SINK_SPEED = 3.0
SPEED_MIN = 70.0
SPEED_MAX = 140.0
GRAVITIES = (9.8, 9.81)


def _canonical_angle(theta: float) -> float:
    """Map an angle to [-pi, pi)."""

    return float((float(theta) + pi) % (2.0 * pi) - pi)


@dataclass(frozen=True)
class Strategy:
    """One FY1 release, including the zero-fuse limiting strategy."""

    heading_rad: float
    speed_mps: float
    release_time_s: float
    fuse_delay_s: float

    @property
    def explosion_time_s(self) -> float:
        return float(self.release_time_s + self.fuse_delay_s)

    @property
    def heading_unit(self) -> FloatArray:
        return np.array((cos(self.heading_rad), sin(self.heading_rad), 0.0))

    def release_position(self) -> FloatArray:
        return FY1_INITIAL + self.speed_mps * self.release_time_s * self.heading_unit

    def explosion_position(self, gravity: float) -> FloatArray:
        horizontal = self.speed_mps * self.explosion_time_s * self.heading_unit
        return FY1_INITIAL + horizontal + np.array(
            (0.0, 0.0, -0.5 * float(gravity) * self.fuse_delay_s**2)
        )

    def as_record(self, gravity: float) -> dict[str, object]:
        return {
            **asdict(self),
            "heading_deg": float(np.degrees(self.heading_rad)),
            "heading_unit": self.heading_unit.tolist(),
            "explosion_time_s": self.explosion_time_s,
            "release_position_m": self.release_position().tolist(),
            "explosion_position_m": self.explosion_position(gravity).tolist(),
        }


def missile_position(time_s: float | FloatArray) -> FloatArray:
    time = np.asarray(time_s, dtype=float)
    if time.ndim == 0:
        return MISSILE_INITIAL + float(time) * MISSILE_VELOCITY
    return MISSILE_INITIAL[None, :] + time[:, None] * MISSILE_VELOCITY[None, :]


def smoke_center(strategy: Strategy, time_s: float | FloatArray, gravity: float) -> FloatArray:
    time = np.asarray(time_s, dtype=float)
    explosion = strategy.explosion_position(gravity)
    elapsed = time - strategy.explosion_time_s
    if time.ndim == 0:
        return explosion + np.array((0.0, 0.0, -SMOKE_SINK_SPEED * float(elapsed)))
    result = np.repeat(explosion[None, :], len(time), axis=0)
    result[:, 2] -= SMOKE_SINK_SPEED * elapsed
    return result


def _point_to_segment_distance(point: FloatArray, start: FloatArray, end: FloatArray) -> float:
    if _engine_segment_distance is not None:
        return float(_engine_segment_distance(point, start, end))
    segment = end - start
    fraction = float(np.dot(point - start, segment) / np.dot(segment, segment))
    closest = start + np.clip(fraction, 0.0, 1.0) * segment
    return float(np.linalg.norm(point - closest))


def centerline_margin(time_s: float, strategy: Strategy, gravity: float) -> float:
    """Smoke-radius margin for the finite M1--target-centre segment."""

    return float(
        SMOKE_RADIUS
        - _point_to_segment_distance(
            smoke_center(strategy, time_s, gravity),
            missile_position(time_s),
            TARGET_CENTER,
        )
    )


def _rim_point(phi: float, z: float) -> FloatArray:
    return TARGET_BOTTOM_CENTER + np.array(
        (TARGET_RADIUS * cos(phi), TARGET_RADIUS * sin(phi), float(z))
    )


def _minimum_direction_cosine(
    missile: FloatArray,
    cloud: FloatArray,
    *,
    n_brackets: int = 96,
) -> tuple[float, float, float]:
    """Return min cos(angle) and its (phi, z) on the two extreme rims."""

    relative_cloud = cloud - missile
    rho = float(np.linalg.norm(relative_cloud))
    if rho == 0.0:
        return -1.0, 0.0, 0.0
    axis = relative_cloud / rho
    best = (2.0, 0.0, 0.0)
    grid = np.arange(n_brackets, dtype=float) * (2.0 * pi / n_brackets)
    bracket_width = 2.0 * pi / n_brackets
    for z in (0.0, TARGET_HEIGHT):

        def direction_cosine(phi: float) -> float:
            sight = _rim_point(phi % (2.0 * pi), z) - missile
            return float(np.dot(axis, sight) / np.linalg.norm(sight))

        sampled = np.array([direction_cosine(phi) for phi in grid])
        candidate_indices = [
            index
            for index in range(n_brackets)
            if sampled[index] <= sampled[index - 1]
            and sampled[index] <= sampled[(index + 1) % n_brackets]
        ]
        if not candidate_indices:
            candidate_indices = [int(np.argmin(sampled))]
        for index in candidate_indices:
            centre = grid[index]
            result = minimize_scalar(
                lambda phi: direction_cosine(phi),
                bounds=(centre - bracket_width, centre + bracket_width),
                method="bounded",
                options={"xatol": 5e-15, "maxiter": 300},
            )
            candidate = (float(result.fun), float(result.x % (2.0 * pi)), z)
            if candidate[0] < best[0]:
                best = candidate
    return best


def _minimum_range_to_target_cylinder(missile: FloatArray) -> float:
    horizontal = float(np.linalg.norm(missile[:2] - TARGET_BOTTOM_CENTER[:2]))
    horizontal_gap = max(0.0, horizontal - TARGET_RADIUS)
    if missile[2] < TARGET_BOTTOM_CENTER[2]:
        vertical_gap = float(TARGET_BOTTOM_CENTER[2] - missile[2])
    elif missile[2] > TARGET_BOTTOM_CENTER[2] + TARGET_HEIGHT:
        vertical_gap = float(missile[2] - TARGET_BOTTOM_CENTER[2] - TARGET_HEIGHT)
    else:
        vertical_gap = 0.0
    return float(np.hypot(horizontal_gap, vertical_gap))


def full_cylinder_details(time_s: float, strategy: Strategy, gravity: float) -> dict[str, float]:
    """Continuous shadow-cone check for every point of the solid cylinder.

    Outside the smoke sphere, the sphere subtends a half-angle
    ``asin(R/rho)`` at the missile.  The cone violation is convex in target
    position, so a maximum over the solid cylinder is attained on an extreme
    point: one of the two rim circles.  A separate conservative range check
    confirms that the whole sphere lies before the nearest target point.
    """

    missile = missile_position(time_s)
    cloud = smoke_center(strategy, time_s, gravity)
    rho = float(np.linalg.norm(cloud - missile))
    target_range = _minimum_range_to_target_cylinder(missile)
    range_margin = float(target_range - (rho + SMOKE_RADIUS))
    if rho <= SMOKE_RADIUS:
        return {
            "margin_m": float(SMOKE_RADIUS - rho),
            "rho_m": rho,
            "required_radius_m": 0.0,
            "min_direction_cosine": 1.0,
            "worst_phi_rad": 0.0,
            "worst_z_m": 0.0,
            "range_margin_m": range_margin,
        }

    min_cosine, worst_phi, worst_z = _minimum_direction_cosine(missile, cloud)
    if min_cosine <= 0.0:
        required_radius = rho
    else:
        required_radius = rho * sqrt(max(0.0, 1.0 - min_cosine**2))
    angular_margin = float(SMOKE_RADIUS - required_radius)
    margin = float(min(angular_margin, range_margin))
    return {
        "margin_m": margin,
        "rho_m": rho,
        "required_radius_m": float(required_radius),
        "min_direction_cosine": float(min_cosine),
        "worst_phi_rad": float(worst_phi),
        "worst_z_m": float(worst_z),
        "range_margin_m": range_margin,
    }


def full_cylinder_margin(time_s: float, strategy: Strategy, gravity: float) -> float:
    return float(full_cylinder_details(time_s, strategy, gravity)["margin_m"])


def _sampled_rims(n_azimuth: int) -> FloatArray:
    phi = np.arange(n_azimuth, dtype=float) * (2.0 * pi / n_azimuth)
    bottom = np.column_stack(
        (
            TARGET_RADIUS * np.cos(phi),
            TARGET_BOTTOM_CENTER[1] + TARGET_RADIUS * np.sin(phi),
            np.zeros(n_azimuth),
        )
    )
    top = bottom.copy()
    top[:, 2] = TARGET_HEIGHT
    return np.vstack((bottom, top))


def _sampled_full_margin_scalar(
    time_s: float,
    strategy: Strategy,
    gravity: float,
    *,
    n_azimuth: int = 96,
) -> float:
    missile = missile_position(time_s)
    cloud = smoke_center(strategy, time_s, gravity)
    relative_cloud = cloud - missile
    rho = float(np.linalg.norm(relative_cloud))
    if rho <= SMOKE_RADIUS:
        return float(SMOKE_RADIUS - rho)
    axis = relative_cloud / rho
    sight = _sampled_rims(n_azimuth) - missile
    cosines = sight @ axis / np.linalg.norm(sight, axis=1)
    min_cosine = float(np.min(cosines))
    required = rho if min_cosine <= 0.0 else rho * sqrt(max(0.0, 1.0 - min_cosine**2))
    range_margin = _minimum_range_to_target_cylinder(missile) - (rho + SMOKE_RADIUS)
    return float(min(SMOKE_RADIUS - required, range_margin))


def _margin_function(mode: Mode, strategy: Strategy, gravity: float) -> Callable[[float], float]:
    if mode == "centerline":
        return lambda time_s: centerline_margin(time_s, strategy, gravity)
    return lambda time_s: full_cylinder_margin(time_s, strategy, gravity)


def _deduplicate(values: Sequence[float], tolerance: float) -> list[float]:
    output: list[float] = []
    for value in sorted(float(item) for item in values):
        if not output or abs(value - output[-1]) > tolerance:
            output.append(value)
    return output


def find_effective_intervals(
    margin: Callable[[float], float],
    start_s: float,
    end_s: float,
    *,
    max_step_s: float = 0.01,
    root_tolerance_s: float = 1e-12,
) -> list[tuple[float, float]]:
    """Bracket every sign change and refine interval boundaries with Brent."""

    if end_s <= start_s:
        return []
    count = max(1, int(ceil((end_s - start_s) / max_step_s)))
    times = np.linspace(start_s, end_s, count + 1)
    values = np.array([float(margin(float(time_s))) for time_s in times])
    roots: list[float] = []
    for left, right, f_left, f_right in zip(
        times[:-1], times[1:], values[:-1], values[1:]
    ):
        if f_left == 0.0:
            roots.append(float(left))
        if f_left * f_right < 0.0:
            roots.append(
                float(
                    brentq(
                        margin,
                        float(left),
                        float(right),
                        xtol=root_tolerance_s,
                        rtol=4.0 * np.finfo(float).eps,
                    )
                )
            )
    if values[-1] == 0.0:
        roots.append(float(end_s))
    boundaries = [
        float(start_s),
        *_deduplicate(roots, 10.0 * root_tolerance_s),
        float(end_s),
    ]
    intervals: list[tuple[float, float]] = []
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        if right - left <= root_tolerance_s:
            continue
        if margin(0.5 * (left + right)) >= 0.0:
            intervals.append((float(left), float(right)))
    # Numerical tangency can create two positive pieces separated only by a
    # duplicate root at machine precision.  Return their measure-theoretic
    # union so downstream duration and endpoint checks see one interval.
    merged: list[list[float]] = []
    for left, right in intervals:
        if not merged or left > merged[-1][1] + 100.0 * root_tolerance_s:
            merged.append([left, right])
        else:
            merged[-1][1] = max(merged[-1][1], right)
    return [(left, right) for left, right in merged]


def interval_duration(intervals: Sequence[tuple[float, float]]) -> float:
    return float(sum(right - left for left, right in intervals))


def strategy_intervals(
    strategy: Strategy,
    mode: Mode,
    gravity: float,
    *,
    max_step_s: float,
) -> list[tuple[float, float]]:
    start = strategy.explosion_time_s
    end = min(start + SMOKE_LIFETIME, MISSILE_IMPACT_TIME)
    return find_effective_intervals(
        _margin_function(mode, strategy, gravity),
        start,
        end,
        max_step_s=max_step_s,
    )


def constraint_violations(strategy: Strategy, gravity: float) -> dict[str, float]:
    explosion_z = float(strategy.explosion_position(gravity)[2])
    violations = {
        "speed_below_70_mps": max(0.0, SPEED_MIN - strategy.speed_mps),
        "speed_above_140_mps": max(0.0, strategy.speed_mps - SPEED_MAX),
        "negative_release_time_s": max(0.0, -strategy.release_time_s),
        "negative_fuse_delay_s": max(0.0, -strategy.fuse_delay_s),
        "explosion_after_impact_s": max(
            0.0, strategy.explosion_time_s - MISSILE_IMPACT_TIME
        ),
        "explosion_below_ground_m": max(0.0, -explosion_z),
        "heading_norm_error": abs(float(np.linalg.norm(strategy.heading_unit)) - 1.0),
    }
    violations["max"] = max(violations.values())
    return violations


def _interval_record(
    strategy: Strategy,
    mode: Mode,
    gravity: float,
    *,
    max_step_s: float,
) -> dict[str, object]:
    margin = _margin_function(mode, strategy, gravity)
    intervals = strategy_intervals(
        strategy, mode, gravity, max_step_s=max_step_s
    )
    residuals = [abs(float(margin(boundary))) for pair in intervals for boundary in pair]
    return {
        "intervals_s": [[left, right] for left, right in intervals],
        "duration_s": interval_duration(intervals),
        "boundary_residual_max_m": max(residuals, default=0.0),
        "constraint_violations": constraint_violations(strategy, gravity),
    }


def q1_strategy() -> Strategy:
    return Strategy(
        heading_rad=pi,
        speed_mps=120.0,
        release_time_s=1.5,
        fuse_delay_s=3.6,
    )


def solve_q1() -> dict[str, object]:
    strategy = q1_strategy()
    by_gravity: dict[str, object] = {}
    for gravity in GRAVITIES:
        by_gravity[f"g_{gravity:.2f}"] = {
            "gravity_mps2": gravity,
            "strategy": strategy.as_record(gravity),
            "centerline": _interval_record(
                strategy, "centerline", gravity, max_step_s=0.01
            ),
            "full_cylinder": _interval_record(
                strategy, "full_cylinder", gravity, max_step_s=0.02
            ),
        }
    return by_gravity


def _decode_global_variables(values: Sequence[float]) -> Strategy:
    theta, speed, explosion_time, fuse_fraction = map(float, values)
    fuse = np.clip(fuse_fraction, 0.0, 1.0) * explosion_time
    return Strategy(
        heading_rad=_canonical_angle(theta),
        speed_mps=speed,
        release_time_s=explosion_time - fuse,
        fuse_delay_s=fuse,
    )


def _linear_measure(times: FloatArray, margins: FloatArray) -> float:
    left = margins[:-1]
    right = margins[1:]
    widths = np.diff(times)
    duration = float(np.sum(widths[(left >= 0.0) & (right >= 0.0)]))
    falling = (left >= 0.0) & (right < 0.0)
    duration += float(
        np.sum(widths[falling] * left[falling] / (left[falling] - right[falling]))
    )
    rising = (left < 0.0) & (right >= 0.0)
    duration += float(
        np.sum(widths[rising] * right[rising] / (right[rising] - left[rising]))
    )
    return duration


def _coarse_margins(
    strategy: Strategy,
    mode: Mode,
    gravity: float,
    *,
    step_s: float,
    full_azimuth: int = 24,
) -> tuple[FloatArray, FloatArray]:
    start = strategy.explosion_time_s
    end = min(start + SMOKE_LIFETIME, MISSILE_IMPACT_TIME)
    count = max(2, int(ceil((end - start) / step_s)) + 1)
    times = np.linspace(start, end, count)
    missile = missile_position(times)
    cloud = smoke_center(strategy, times, gravity)
    if mode == "centerline":
        segment = TARGET_CENTER[None, :] - missile
        relative = cloud - missile
        fraction = np.einsum("ij,ij->i", relative, segment) / np.einsum(
            "ij,ij->i", segment, segment
        )
        closest = missile + np.clip(fraction, 0.0, 1.0)[:, None] * segment
        margins = SMOKE_RADIUS - np.linalg.norm(cloud - closest, axis=1)
        return times, margins

    rims = _sampled_rims(full_azimuth)
    relative_cloud = cloud - missile
    rho = np.linalg.norm(relative_cloud, axis=1)
    axis = relative_cloud / rho[:, None]
    sight = rims[None, :, :] - missile[:, None, :]
    cosines = np.einsum("ti,tqi->tq", axis, sight) / np.linalg.norm(sight, axis=2)
    min_cosine = np.min(cosines, axis=1)
    required = np.where(
        min_cosine > 0.0,
        rho * np.sqrt(np.maximum(0.0, 1.0 - min_cosine**2)),
        rho,
    )
    margins = SMOKE_RADIUS - required
    inside = rho <= SMOKE_RADIUS
    margins[inside] = SMOKE_RADIUS - rho[inside]
    return times, margins


def run_global_search(mode: Mode, gravity: float = 9.8) -> dict[str, object]:
    """Seeded broad search; exact boundary faces are polished afterwards."""

    search_trace: list[dict[str, float | int]] = []

    def objective(values: FloatArray) -> float:
        strategy = _decode_global_variables(values)
        violations = constraint_violations(strategy, gravity)["max"]
        if violations > 1e-10:
            return 100.0 + float(violations)
        times, margins = _coarse_margins(
            strategy,
            mode,
            gravity,
            step_s=0.04 if mode == "centerline" else 0.06,
            full_azimuth=24,
        )
        duration = _linear_measure(times, margins)
        # A tiny smooth guide prevents the zero-duration plateau from trapping
        # the population; duration remains the dominant term once feasible.
        guide = float(np.clip(np.max(margins), -100.0, 10.0))
        return -duration - 1e-5 * guide

    def record_generation(values: FloatArray, convergence: float) -> bool:
        """Persist the DE incumbent so convergence can be audited per seed."""

        strategy = _decode_global_variables(values)
        violations = constraint_violations(strategy, gravity)["max"]
        times, margins = _coarse_margins(
            strategy,
            mode,
            gravity,
            step_s=0.04 if mode == "centerline" else 0.06,
            full_azimuth=24,
        )
        search_trace.append(
            {
                "generation": len(search_trace) + 1,
                "best_objective": float(objective(values)),
                "best_coarse_duration_s": float(_linear_measure(times, margins)),
                "best_max_constraint_violation": float(violations),
                "population_convergence": float(convergence),
            }
        )
        return False

    result = differential_evolution(
        objective,
        bounds=((-pi, pi), (SPEED_MIN, SPEED_MAX), (0.03, 14.0), (0.0, 1.0)),
        seed=RANDOM_SEED,
        popsize=12,
        maxiter=220,
        tol=2e-6,
        atol=1e-9,
        polish=True,
        updating="immediate",
        workers=1,
        callback=record_generation,
    )
    strategy = _decode_global_variables(result.x)
    times, margins = _coarse_margins(
        strategy,
        mode,
        gravity,
        step_s=0.01,
        full_azimuth=96,
    )
    return {
        "seed": RANDOM_SEED,
        "variables_theta_speed_te_fuse_fraction": [float(value) for value in result.x],
        "decoded_strategy": strategy.as_record(gravity),
        "coarse_duration_s": _linear_measure(times, margins),
        "coarse_margin_max_m": float(np.max(margins)),
        "objective": float(result.fun),
        "iterations": int(result.nit),
        "function_evaluations": int(result.nfev),
        "success": bool(result.success),
        "message": str(result.message),
        "best_so_far_trace": search_trace,
    }


def _refine_centerline_face(
    gravity: float,
    initial_theta: float,
    initial_explosion_time: float,
) -> Strategy:
    """Polish the globally identified s=140, release-at-command face."""

    def objective(values: FloatArray) -> float:
        theta, explosion_time = map(float, values)
        if not (0.05 <= explosion_time <= 3.0):
            return 100.0 + abs(explosion_time)
        strategy = Strategy(_canonical_angle(theta), SPEED_MAX, 0.0, explosion_time)
        intervals = strategy_intervals(
            strategy, "centerline", gravity, max_step_s=0.02
        )
        return -interval_duration(intervals)

    result = minimize(
        objective,
        np.array((initial_theta, initial_explosion_time)),
        method="Nelder-Mead",
        bounds=((-pi, pi), (0.05, 3.0)),
        options={"xatol": 2e-11, "fatol": 2e-12, "maxiter": 700},
    )
    return Strategy(
        heading_rad=_canonical_angle(float(result.x[0])),
        speed_mps=SPEED_MAX,
        release_time_s=0.0,
        fuse_delay_s=float(result.x[1]),
    )


def _exact_theta_roots_at_explosion(
    explosion_time: float,
    fuse_delay: float,
    gravity: float,
    *,
    theta_hint: float,
) -> list[float]:
    """Find all full-cylinder start-tangency headings near a search candidate."""

    release_time = explosion_time - fuse_delay
    if release_time < 0.0:
        return []
    span = 0.55
    sampled_theta = np.linspace(theta_hint - span, theta_hint + span, 111)
    sampled_values = []
    for theta in sampled_theta:
        strategy = Strategy(theta, SPEED_MAX, release_time, fuse_delay)
        sampled_values.append(
            _sampled_full_margin_scalar(
                explosion_time, strategy, gravity, n_azimuth=96
            )
        )
    approximate_brackets: list[tuple[float, float]] = []
    for left, right, f_left, f_right in zip(
        sampled_theta[:-1],
        sampled_theta[1:],
        sampled_values[:-1],
        sampled_values[1:],
    ):
        if f_left * f_right < 0.0:
            approximate_brackets.append((float(left), float(right)))

    roots: list[float] = []
    theta_step = float(sampled_theta[1] - sampled_theta[0])
    for left, right in approximate_brackets:
        exact_grid = np.linspace(left - theta_step, right + theta_step, 9)
        exact_values = []
        for theta in exact_grid:
            strategy = Strategy(theta, SPEED_MAX, release_time, fuse_delay)
            exact_values.append(full_cylinder_margin(explosion_time, strategy, gravity))
        for a, b, f_a, f_b in zip(
            exact_grid[:-1], exact_grid[1:], exact_values[:-1], exact_values[1:]
        ):
            if f_a * f_b < 0.0:
                root = brentq(
                    lambda theta: full_cylinder_margin(
                        explosion_time,
                        Strategy(theta, SPEED_MAX, release_time, fuse_delay),
                        gravity,
                    ),
                    float(a),
                    float(b),
                    xtol=2e-13,
                    rtol=4.0 * np.finfo(float).eps,
                )
                roots.append(_canonical_angle(root))
    return _deduplicate(roots, 1e-9)


def _full_exit_after_tangent(strategy: Strategy, gravity: float) -> float | None:
    start = strategy.explosion_time_s
    end = min(start + 8.0, MISSILE_IMPACT_TIME)
    sampled = lambda time_s: _sampled_full_margin_scalar(
        time_s, strategy, gravity, n_azimuth=144
    )
    times = np.linspace(start + 1e-5, end, 241)
    values = np.array([sampled(float(time_s)) for time_s in times])
    brackets: list[tuple[float, float]] = []
    for left, right, f_left, f_right in zip(
        times[:-1], times[1:], values[:-1], values[1:]
    ):
        if f_left >= 0.0 and f_right < 0.0:
            brackets.append((float(left), float(right)))
    if not brackets:
        return None
    # The interval beginning at the explosion uses the first falling crossing.
    approximate_left, approximate_right = brackets[0]
    exact_grid = np.linspace(approximate_left - 0.08, approximate_right + 0.08, 13)
    exact_values = [
        full_cylinder_margin(float(time_s), strategy, gravity)
        for time_s in exact_grid
    ]
    for left, right, f_left, f_right in zip(
        exact_grid[:-1], exact_grid[1:], exact_values[:-1], exact_values[1:]
    ):
        if f_left >= 0.0 and f_right < 0.0:
            return float(
                brentq(
                    lambda time_s: full_cylinder_margin(time_s, strategy, gravity),
                    float(left),
                    float(right),
                    xtol=2e-13,
                    rtol=4.0 * np.finfo(float).eps,
                )
            )
    return None


def _best_full_tangent_at_time(
    explosion_time: float,
    fuse_delay: float,
    gravity: float,
    theta_hint: float,
) -> tuple[float, Strategy, float] | None:
    roots = _exact_theta_roots_at_explosion(
        explosion_time,
        fuse_delay,
        gravity,
        theta_hint=theta_hint,
    )
    best: tuple[float, Strategy, float] | None = None
    for theta in roots:
        strategy = Strategy(
            theta,
            SPEED_MAX,
            explosion_time - fuse_delay,
            fuse_delay,
        )
        epsilon = min(1e-4, 0.1 * max(explosion_time, 1e-4))
        if full_cylinder_margin(explosion_time + epsilon, strategy, gravity) < 0.0:
            continue
        exit_time = _full_exit_after_tangent(strategy, gravity)
        if exit_time is None:
            continue
        candidate = (float(exit_time - explosion_time), strategy, exit_time)
        if best is None or candidate[0] > best[0]:
            best = candidate
    return best


def _refine_full_boundary_face(
    fuse_delay: float,
    gravity: float,
    *,
    theta_hint: float,
    explosion_hint: float,
) -> tuple[Strategy, float]:
    """Maximise a full-cylinder tangent interval on a fixed fuse-delay face."""

    lower = max(fuse_delay + 1e-4, 0.15, explosion_hint - 0.65)
    upper = min(2.5, explosion_hint + 0.85)
    coarse_times = np.linspace(lower, upper, 17)
    coarse: list[tuple[float, float]] = []
    for explosion_time in coarse_times:
        candidate = _best_full_tangent_at_time(
            float(explosion_time), fuse_delay, gravity, theta_hint
        )
        coarse.append((candidate[0] if candidate else 0.0, float(explosion_time)))
    best_index = int(np.argmax([item[0] for item in coarse]))
    left = coarse_times[max(0, best_index - 1)]
    right = coarse_times[min(len(coarse_times) - 1, best_index + 1)]

    def objective(explosion_time: float) -> float:
        candidate = _best_full_tangent_at_time(
            float(explosion_time), fuse_delay, gravity, theta_hint
        )
        return -(candidate[0] if candidate else 0.0)

    result = minimize_scalar(
        objective,
        bounds=(float(left), float(right)),
        method="bounded",
        options={"xatol": 2e-9, "maxiter": 120},
    )
    candidate = _best_full_tangent_at_time(
        float(result.x), fuse_delay, gravity, theta_hint
    )
    if candidate is None:  # pragma: no cover - guarded by the coarse scan
        raise RuntimeError("full-cylinder boundary refinement found no tangent interval")
    duration, strategy, exit_time = candidate
    return strategy, float(exit_time)


def _dense_azimuth_crosscheck(
    time_s: float,
    strategy: Strategy,
    gravity: float,
    *,
    n_azimuth: int = 23_040,
) -> dict[str, float]:
    details = full_cylinder_details(time_s, strategy, gravity)
    missile = missile_position(time_s)
    cloud = smoke_center(strategy, time_s, gravity)
    rho = float(np.linalg.norm(cloud - missile))
    if rho <= SMOKE_RADIUS:
        return {
            "time_s": time_s,
            "exact_min_cosine": 1.0,
            "dense_min_cosine": 1.0,
            "absolute_cosine_difference": 0.0,
        }
    axis = (cloud - missile) / rho
    sight = _sampled_rims(n_azimuth) - missile
    dense_min = float(np.min(sight @ axis / np.linalg.norm(sight, axis=1)))
    exact_min = float(details["min_direction_cosine"])
    return {
        "time_s": time_s,
        "exact_min_cosine": exact_min,
        "dense_min_cosine": dense_min,
        "absolute_cosine_difference": abs(dense_min - exact_min),
    }


def solve_q2(*, run_search: bool = True) -> dict[str, object]:
    gravity = 9.8
    if run_search:
        center_global = run_global_search("centerline", gravity)
        full_global = run_global_search("full_cylinder", gravity)
        center_seed_strategy = Strategy(
            **{
                key: value
                for key, value in center_global["decoded_strategy"].items()
                if key
                in {
                    "heading_rad",
                    "speed_mps",
                    "release_time_s",
                    "fuse_delay_s",
                }
            }
        )
        full_seed_strategy = Strategy(
            **{
                key: value
                for key, value in full_global["decoded_strategy"].items()
                if key
                in {
                    "heading_rad",
                    "speed_mps",
                    "release_time_s",
                    "fuse_delay_s",
                }
            }
        )
    else:
        # Deterministic warm starts used by tests that only need exact polishing.
        center_seed_strategy = Strategy(0.12, 140.0, 0.0, 0.71)
        full_seed_strategy = Strategy(0.09, 140.0, 0.93, 0.0)
        center_global = {"seed": RANDOM_SEED, "skipped": True}
        full_global = {"seed": RANDOM_SEED, "skipped": True}

    center = _refine_centerline_face(
        gravity,
        center_seed_strategy.heading_rad,
        center_seed_strategy.explosion_time_s,
    )
    center_record = {
        "strategy": center.as_record(gravity),
        **_interval_record(center, "centerline", gravity, max_step_s=0.005),
        "global_search": center_global,
    }

    # Re-optimise the same active face at g=9.81 and also evaluate the g=9.8
    # strategy unchanged; these answer two distinct sensitivity questions.
    center_981 = _refine_centerline_face(
        9.81, center.heading_rad, center.explosion_time_s
    )
    center_record["gravity_sensitivity"] = {
        "same_strategy_at_g_9.81": _interval_record(
            center, "centerline", 9.81, max_step_s=0.005
        ),
        "reoptimized_at_g_9.81": {
            "strategy": center_981.as_record(9.81),
            **_interval_record(center_981, "centerline", 9.81, max_step_s=0.005),
        },
    }

    full_theta_hint = full_seed_strategy.heading_rad
    full_explosion_hint = full_seed_strategy.explosion_time_s
    # A broad search can occasionally return the other tangent branch.  The
    # physical +x branch is still within this canonical neighbourhood.
    if abs(full_theta_hint) > 0.8 or not (0.2 < full_explosion_hint < 2.5):
        full_theta_hint, full_explosion_hint = 0.1, 0.95

    full_zero, full_zero_exit = _refine_full_boundary_face(
        0.0,
        gravity,
        theta_hint=full_theta_hint,
        explosion_hint=full_explosion_hint,
    )
    full_zero_record = {
        "interpretation": "closed feasible set tau >= 0; exact boundary optimum",
        "strategy": full_zero.as_record(gravity),
        **_interval_record(full_zero, "full_cylinder", gravity, max_step_s=0.01),
        "polished_exit_time_s": full_zero_exit,
        "global_search": full_global,
    }
    full_zero_record["gravity_sensitivity"] = {
        "same_strategy_at_g_9.81": _interval_record(
            full_zero, "full_cylinder", 9.81, max_step_s=0.01
        )
    }

    full_engineering, full_engineering_exit = _refine_full_boundary_face(
        0.02,
        gravity,
        theta_hint=full_zero.heading_rad,
        explosion_hint=full_zero.explosion_time_s,
    )
    full_engineering_record = {
        "interpretation": "engineering plan with strictly positive 0.02 s fuse",
        "strategy": full_engineering.as_record(gravity),
        **_interval_record(
            full_engineering, "full_cylinder", gravity, max_step_s=0.01
        ),
        "polished_exit_time_s": full_engineering_exit,
        "gravity_sensitivity": {
            "same_strategy_at_g_9.81": _interval_record(
                full_engineering, "full_cylinder", 9.81, max_step_s=0.01
            )
        },
    }

    full_intervals = full_zero_record["intervals_s"]
    azimuth_checks = [
        _dense_azimuth_crosscheck(float(boundary), full_zero, gravity)
        for pair in full_intervals
        for boundary in pair
    ]
    return {
        "centerline": center_record,
        "full_cylinder_tau_0_boundary": full_zero_record,
        "full_cylinder_tau_0.02_engineering": full_engineering_record,
        "comparison": {
            "centerline_minus_full_cylinder_s": float(
                center_record["duration_s"] - full_zero_record["duration_s"]
            ),
            "engineering_loss_from_tau_0_s": float(
                full_zero_record["duration_s"]
                - full_engineering_record["duration_s"]
            ),
        },
        "dense_azimuth_crosscheck": azimuth_checks,
    }


def solve_all(*, run_search: bool = True) -> dict[str, object]:
    q1 = solve_q1()
    q2 = solve_q2(run_search=run_search)
    return {
        "metadata": {
            "run_id": RUN_ID,
            "title": "2025 CUMCM A Q1-Q2 independent validation",
            "official_source": "source/A题.pdf",
            "random_seed": RANDOM_SEED,
            "geometry_engine_available": GEOMETRY_ENGINE_AVAILABLE,
            "gravity_values_mps2": list(GRAVITIES),
            "root_method": "uniform bracketing followed by scipy.optimize.brentq",
            "full_target_method": "continuous shadow-cone containment on top and bottom rim circles",
            "units": {"position": "m", "time": "s", "speed": "m/s"},
        },
        "constants": {
            "missile_initial_m": MISSILE_INITIAL.tolist(),
            "missile_velocity_mps": MISSILE_VELOCITY.tolist(),
            "missile_impact_time_s": MISSILE_IMPACT_TIME,
            "fy1_initial_m": FY1_INITIAL.tolist(),
            "target_bottom_center_m": TARGET_BOTTOM_CENTER.tolist(),
            "target_radius_m": TARGET_RADIUS,
            "target_height_m": TARGET_HEIGHT,
            "smoke_radius_m": SMOKE_RADIUS,
            "smoke_lifetime_s": SMOKE_LIFETIME,
            "smoke_sink_speed_mps": SMOKE_SINK_SPEED,
        },
        "q1": q1,
        "q2": q2,
    }


def default_output_path() -> Path:
    return Path(__file__).resolve().parents[1] / "validation" / "q1_q2_independent.json"


def write_validation(path: Path, *, run_search: bool = True) -> dict[str, object]:
    result = solve_all(run_search=run_search)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    return result


def _summary(result: dict[str, object]) -> str:
    q1 = result["q1"]
    q2 = result["q2"]
    rows = [
        "Q1/Q2 independent validation",
        f"seed={RANDOM_SEED}",
    ]
    for gravity_key in ("g_9.80", "g_9.81"):
        rows.append(
            f"Q1 {gravity_key}: center={q1[gravity_key]['centerline']['duration_s']:.9f} s, "
            f"full={q1[gravity_key]['full_cylinder']['duration_s']:.9f} s"
        )
    rows.extend(
        (
            f"Q2 centerline={q2['centerline']['duration_s']:.9f} s",
            "Q2 full tau=0="
            f"{q2['full_cylinder_tau_0_boundary']['duration_s']:.9f} s",
            "Q2 full tau=0.02="
            f"{q2['full_cylinder_tau_0.02_engineering']['duration_s']:.9f} s",
        )
    )
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=default_output_path())
    parser.add_argument(
        "--skip-global-search",
        action="store_true",
        help="use deterministic warm starts and only run exact polishing",
    )
    args = parser.parse_args()
    result = write_validation(args.output, run_search=not args.skip_global_search)
    print(_summary(result))
    print(f"validation={args.output.resolve()}")


if __name__ == "__main__":
    main()
