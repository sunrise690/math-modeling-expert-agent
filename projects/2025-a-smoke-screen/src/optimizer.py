"""Reproducible route-and-release optimizers for Questions 3--5.

The search deliberately has two levels:

* a fast, deterministic route/candidate baseline constructed from smoke-centre
  crossings of a missile--target sightline;
* continuous-time verification through :mod:`geometry_engine` for every
  reported strategy.

The Q5 routine is a route-consistent beam-search baseline.  It produces a
high-quality feasible solution, but it does not claim a global optimum.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from math import cos, degrees, floor, pi, radians, sin
from typing import Callable, Iterable, Mapping, Sequence

import numpy as np

try:  # Running ``python src/solve_q3_q5.py``.
    from geometry_engine import (
        DEFAULT_TARGET,
        GRAVITY,
        SMOKE_LIFETIME,
        SMOKE_RADIUS,
        SMOKE_SINK_SPEED,
        BombRelease,
        CylindricalOcclusionEvaluator,
        MissileTrajectory,
        SmokeCloud,
        UAVTrajectory,
        effective_intervals,
        interval_duration,
        merge_intervals,
    )
except ImportError:  # Package-style import in external callers.
    from .geometry_engine import (  # type: ignore
        DEFAULT_TARGET,
        GRAVITY,
        SMOKE_LIFETIME,
        SMOKE_RADIUS,
        SMOKE_SINK_SPEED,
        BombRelease,
        CylindricalOcclusionEvaluator,
        MissileTrajectory,
        SmokeCloud,
        UAVTrajectory,
        effective_intervals,
        interval_duration,
        merge_intervals,
    )


MISSILE_INITIALS: dict[str, tuple[float, float, float]] = {
    "M1": (20_000.0, 0.0, 2_000.0),
    "M2": (19_000.0, 600.0, 2_100.0),
    "M3": (18_000.0, -600.0, 1_900.0),
}

UAV_INITIALS: dict[str, tuple[float, float, float]] = {
    "FY1": (17_800.0, 0.0, 1_800.0),
    "FY2": (12_000.0, 1_400.0, 1_400.0),
    "FY3": (6_000.0, -3_000.0, 700.0),
    "FY4": (11_000.0, 2_000.0, 1_800.0),
    "FY5": (13_000.0, -2_000.0, 1_300.0),
}

MIN_UAV_SPEED = 70.0
MAX_UAV_SPEED = 140.0
MIN_RELEASE_GAP = 1.0
DEFAULT_RANDOM_SEED = 202_508_08


def build_missiles() -> dict[str, MissileTrajectory]:
    return {
        missile_id: MissileTrajectory(initial)
        for missile_id, initial in MISSILE_INITIALS.items()
    }


MISSILES = build_missiles()


def circular_heading_difference(first: float, second: float) -> float:
    """Smallest absolute angular difference in degrees."""

    return abs((float(first) - float(second) + 180.0) % 360.0 - 180.0)


@dataclass(frozen=True)
class BombPlan:
    """One bomb, with its parent UAV route stored explicitly."""

    drone_id: str
    heading_deg: float
    speed: float
    release_time: float
    fuse_delay: float
    missile_id: str
    anchor_time: float | None = None
    estimated_intervals: tuple[tuple[float, float], ...] = ()

    @property
    def normalized_heading_deg(self) -> float:
        return float(self.heading_deg % 360.0)

    @property
    def explosion_time(self) -> float:
        return float(self.release_time + self.fuse_delay)

    @property
    def heading_xy(self) -> tuple[float, float]:
        angle = radians(self.normalized_heading_deg)
        return (cos(angle), sin(angle))

    def uav(self) -> UAVTrajectory:
        return UAVTrajectory(
            UAV_INITIALS[self.drone_id], self.heading_xy, float(self.speed)
        )

    def release(self) -> BombRelease:
        return self.uav().release(self.release_time, self.fuse_delay)

    def cloud(self) -> SmokeCloud:
        return self.release().smoke_cloud()

    @property
    def release_position(self) -> tuple[float, float, float]:
        return tuple(float(value) for value in self.release().release_position)

    @property
    def explosion_position(self) -> tuple[float, float, float]:
        return tuple(float(value) for value in self.release().explosion_position)


@dataclass(frozen=True)
class CoverageState:
    plans: tuple[BombPlan, ...]
    intervals_by_missile: Mapping[str, tuple[tuple[float, float], ...]]
    score: float


@dataclass(frozen=True)
class RoutePackage:
    drone_id: str
    heading_deg: float
    speed: float
    plans: tuple[BombPlan, ...]
    estimated_score: float

    @property
    def assignment_signature(self) -> tuple[int, int, int]:
        return tuple(
            sum(plan.missile_id == missile_id for plan in self.plans)
            for missile_id in ("M1", "M2", "M3")
        )


@dataclass
class SolveDiagnostics:
    seed: int
    status: str
    method: str
    routes_evaluated: int = 0
    candidates_generated: int = 0
    packages_retained: int = 0
    fast_baseline_objective: float = 0.0
    fast_final_objective: float = 0.0
    exact_objective: float = 0.0
    exact_union_by_missile: dict[str, float] = field(default_factory=dict)
    max_constraint_violation: float = 0.0
    constraint_violations: dict[str, float] = field(default_factory=dict)
    optimality_claim: str = "No global optimality proof."
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SolveResult:
    problem: str
    plans: tuple[BombPlan, ...]
    exact_individual_intervals: tuple[tuple[tuple[float, float], ...], ...]
    exact_union_by_missile: Mapping[str, tuple[tuple[float, float], ...]]
    diagnostics: SolveDiagnostics

    @property
    def exact_objective(self) -> float:
        return float(
            sum(interval_duration(intervals) for intervals in self.exact_union_by_missile.values())
        )


def _cross2(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    return first[..., 0] * second[..., 1] - first[..., 1] * second[..., 0]


def _batch_point_to_sightline_distance(
    times: np.ndarray,
    explosion_times: np.ndarray,
    explosion_positions: np.ndarray,
    missile: MissileTrajectory,
) -> np.ndarray:
    """Vectorised centreline distance used only to rank aligned candidates."""

    times = np.asarray(times, dtype=float)
    explosion_times = np.asarray(explosion_times, dtype=float)
    missile_positions = (
        np.asarray(missile.initial_position, dtype=float)[None, :]
        + times[:, None] * missile.velocity[None, :]
    )
    target = DEFAULT_TARGET.center
    sight = target[None, :] - missile_positions
    cloud_centres = explosion_positions.copy()
    cloud_centres[:, 2] -= SMOKE_SINK_SPEED * (times - explosion_times)
    relative = cloud_centres - missile_positions
    denominator = np.einsum("ij,ij->i", sight, sight)
    fraction = np.einsum("ij,ij->i", relative, sight) / denominator
    fraction = np.clip(fraction, 0.0, 1.0)
    residual = relative - fraction[:, None] * sight
    return np.linalg.norm(residual, axis=1)


def aligned_candidates_for_route(
    drone_id: str,
    heading_deg: float,
    speed: float,
    missile_id: str,
    *,
    explosion_step: float = 0.20,
    time_bin: float = 1.0,
    max_per_bin: int = 2,
) -> list[BombPlan]:
    """Create feasible candidates whose smoke centre crosses the sightline.

    For a fixed route and explosion time, the horizontal cloud point is known.
    Collinearity with the moving missile--target segment gives the crossing
    time analytically.  The required explosion height then determines the
    fuse delay.  This removes the zero-score plateau of a raw random search.
    """

    if drone_id not in UAV_INITIALS or missile_id not in MISSILES:
        raise KeyError("unknown drone or missile identifier")
    if not (MIN_UAV_SPEED <= speed <= MAX_UAV_SPEED):
        return []
    if explosion_step <= 0.0 or time_bin <= 0.0 or max_per_bin < 1:
        raise ValueError("candidate-grid parameters must be positive")

    missile = MISSILES[missile_id]
    initial = np.asarray(UAV_INITIALS[drone_id], dtype=float)
    target = DEFAULT_TARGET.center
    angle = radians(float(heading_deg) % 360.0)
    heading = np.array((cos(angle), sin(angle)), dtype=float)

    explosion_times = np.arange(
        max(0.02, explosion_step * 0.25),
        missile.impact_time,
        explosion_step,
        dtype=float,
    )
    horizontal = initial[:2][None, :] + speed * explosion_times[:, None] * heading
    from_target = horizontal - target[:2][None, :]
    missile_from_target = (
        np.asarray(missile.initial_position[:2], dtype=float) - target[:2]
    )
    velocity_xy = missile.velocity[:2]
    denominator = _cross2(from_target, velocity_xy)
    numerator = _cross2(from_target, missile_from_target)

    with np.errstate(divide="ignore", invalid="ignore"):
        crossing_times = -numerator / denominator
    valid = np.isfinite(crossing_times) & (np.abs(denominator) > 1e-9)
    ages = crossing_times - explosion_times
    valid &= ages >= 0.0
    valid &= ages <= SMOKE_LIFETIME
    valid &= crossing_times <= missile.impact_time

    missile_xy = (
        np.asarray(missile.initial_position[:2], dtype=float)[None, :]
        + crossing_times[:, None] * velocity_xy[None, :]
    )
    sight_xy = missile_xy - target[:2][None, :]
    sight_xy_sq = np.einsum("ij,ij->i", sight_xy, sight_xy)
    with np.errstate(divide="ignore", invalid="ignore"):
        alpha = np.einsum("ij,ij->i", from_target, sight_xy) / sight_xy_sq
    valid &= np.isfinite(alpha) & (alpha >= 0.0) & (alpha <= 1.0)

    missile_z = float(missile.initial_position[2]) + missile.velocity[2] * crossing_times
    sight_z = target[2] + alpha * (missile_z - target[2])
    explosion_z = sight_z + SMOKE_SINK_SPEED * ages
    valid &= explosion_z > 0.0
    valid &= explosion_z < initial[2]

    fuse_delays = np.full_like(explosion_times, np.nan)
    fuse_delays[valid] = np.sqrt(
        2.0 * (initial[2] - explosion_z[valid]) / GRAVITY
    )
    release_times = explosion_times - fuse_delays
    valid &= np.isfinite(fuse_delays) & (fuse_delays > 1e-5)
    valid &= release_times >= 0.0

    indices = np.flatnonzero(valid)
    if len(indices) == 0:
        return []
    e_valid = explosion_times[indices]
    t_valid = crossing_times[indices]
    r_valid = release_times[indices]
    tau_valid = fuse_delays[indices]
    positions = np.column_stack(
        (horizontal[indices, 0], horizontal[indices, 1], explosion_z[indices])
    )

    delta = 0.04
    distance_left = _batch_point_to_sightline_distance(
        t_valid - delta, e_valid, positions, missile
    )
    distance_right = _batch_point_to_sightline_distance(
        t_valid + delta, e_valid, positions, missile
    )
    transverse_speed = (distance_left + distance_right) / (2.0 * delta)
    half_width = SMOKE_RADIUS / np.maximum(transverse_speed, 0.05)
    half_width = np.clip(half_width, 0.05, SMOKE_LIFETIME)
    left = np.maximum(e_valid, t_valid - half_width)
    right = np.minimum.reduce(
        (
            e_valid + SMOKE_LIFETIME,
            np.full_like(e_valid, missile.impact_time),
            t_valid + half_width,
        )
    )
    positive = right > left

    candidates: list[BombPlan] = []
    for local_index in np.flatnonzero(positive):
        candidates.append(
            BombPlan(
                drone_id=drone_id,
                heading_deg=float(heading_deg) % 360.0,
                speed=float(speed),
                release_time=float(r_valid[local_index]),
                fuse_delay=float(tau_valid[local_index]),
                missile_id=missile_id,
                anchor_time=float(t_valid[local_index]),
                estimated_intervals=(
                    (float(left[local_index]), float(right[local_index])),
                ),
            )
        )

    # Keep temporal diversity while removing nearly interchangeable columns.
    grouped: dict[int, list[BombPlan]] = {}
    for candidate in candidates:
        key = int(floor(float(candidate.anchor_time) / time_bin))
        grouped.setdefault(key, []).append(candidate)
    pruned: list[BombPlan] = []
    for values in grouped.values():
        values.sort(
            key=lambda plan: interval_duration(plan.estimated_intervals), reverse=True
        )
        chosen: list[BombPlan] = []
        for plan in values:
            if all(abs(plan.release_time - other.release_time) > 0.15 for other in chosen):
                chosen.append(plan)
            if len(chosen) >= max_per_bin:
                break
        pruned.extend(chosen)
    return sorted(pruned, key=lambda plan: (plan.release_time, plan.anchor_time or 0.0))


def sampled_centerline_intervals(
    plan: BombPlan, *, step: float = 0.04
) -> list[tuple[float, float]]:
    """Fast time-grid approximation used only for local search ranking."""

    if step <= 0.0:
        raise ValueError("step must be positive")
    try:
        release = plan.release()
    except ValueError:
        return []
    cloud = release.smoke_cloud()
    missile = MISSILES[plan.missile_id]
    start = max(0.0, cloud.explosion_time)
    end = min(cloud.expiry_time, missile.impact_time)
    if end <= start or release.explosion_position[2] < 0.0:
        return []
    count = max(2, int(np.ceil((end - start) / step)) + 1)
    times = np.linspace(start, end, count)
    missile_positions = (
        np.asarray(missile.initial_position, dtype=float)[None, :]
        + times[:, None] * missile.velocity[None, :]
    )
    target = DEFAULT_TARGET.center
    sight = target[None, :] - missile_positions
    explosion = release.explosion_position
    cloud_centres = np.repeat(explosion[None, :], len(times), axis=0)
    cloud_centres[:, 2] -= SMOKE_SINK_SPEED * (times - cloud.explosion_time)
    relative = cloud_centres - missile_positions
    fraction = np.einsum("ij,ij->i", relative, sight) / np.einsum(
        "ij,ij->i", sight, sight
    )
    fraction = np.clip(fraction, 0.0, 1.0)
    residual = relative - fraction[:, None] * sight
    active = np.einsum("ij,ij->i", residual, residual) <= SMOKE_RADIUS**2
    intervals: list[tuple[float, float]] = []
    run_start: int | None = None
    for index, is_active in enumerate(active):
        if is_active and run_start is None:
            run_start = index
        if run_start is not None and (not is_active or index == len(active) - 1):
            run_end = index if is_active and index == len(active) - 1 else index - 1
            left = max(start, float(times[run_start] - 0.5 * step))
            right = min(end, float(times[run_end] + 0.5 * step))
            if right > left:
                intervals.append((left, right))
            run_start = None
    return merge_intervals(intervals)


def _plan_intervals_estimated(plan: BombPlan) -> list[tuple[float, float]]:
    if plan.estimated_intervals:
        return list(plan.estimated_intervals)
    return sampled_centerline_intervals(plan)


def coverage_intervals(
    plans: Iterable[BombPlan],
    interval_getter: Callable[[BombPlan], Iterable[tuple[float, float]]],
) -> dict[str, list[tuple[float, float]]]:
    by_missile: dict[str, list[tuple[float, float]]] = {
        missile_id: [] for missile_id in MISSILES
    }
    for plan in plans:
        by_missile[plan.missile_id].extend(interval_getter(plan))
    return {
        missile_id: merge_intervals(intervals)
        for missile_id, intervals in by_missile.items()
    }


def coverage_objective(
    intervals_by_missile: Mapping[str, Iterable[tuple[float, float]]]
) -> float:
    return float(
        sum(interval_duration(intervals) for intervals in intervals_by_missile.values())
    )


def _state_rank(state: CoverageState) -> tuple[float, float, int]:
    durations = [
        interval_duration(state.intervals_by_missile.get(missile_id, ()))
        for missile_id in MISSILES
    ]
    nonempty = sum(value > 0.0 for value in durations)
    return (state.score + 0.03 * min(durations), min(durations), nonempty)


def _coverage_state(plans: Sequence[BombPlan]) -> CoverageState:
    intervals = coverage_intervals(plans, _plan_intervals_estimated)
    frozen = {key: tuple(value) for key, value in intervals.items()}
    return CoverageState(tuple(plans), frozen, coverage_objective(intervals))


def select_route_packages(
    candidates: Sequence[BombPlan],
    *,
    max_bombs: int = 3,
    beam_width: int = 30,
    exact_count: bool = False,
) -> list[RoutePackage]:
    """Return diverse release-compatible packages on one fixed route."""

    if not candidates or max_bombs < 1:
        return []
    ordered = sorted(candidates, key=lambda plan: plan.release_time)
    first = ordered[0]
    route_candidates = [
        plan
        for plan in ordered
        if plan.drone_id == first.drone_id
        and circular_heading_difference(plan.heading_deg, first.heading_deg) <= 1e-10
        and abs(plan.speed - first.speed) <= 1e-10
    ]
    states: list[tuple[tuple[int, ...], CoverageState]] = [
        ((), _coverage_state(()))
    ]
    completed: list[CoverageState] = []
    for _depth in range(1, max_bombs + 1):
        expanded: list[tuple[tuple[int, ...], CoverageState]] = []
        for indices, state in states:
            start_index = indices[-1] + 1 if indices else 0
            last_release = (
                route_candidates[indices[-1]].release_time if indices else -np.inf
            )
            for index in range(start_index, len(route_candidates)):
                plan = route_candidates[index]
                if plan.release_time - last_release < MIN_RELEASE_GAP - 1e-10:
                    continue
                new_plans = (*state.plans, plan)
                expanded.append(((*indices, index), _coverage_state(new_plans)))
        if not expanded:
            break
        expanded.sort(key=lambda item: _state_rank(item[1]), reverse=True)
        # Release/time signatures prevent a beam full of near-identical states.
        unique: list[tuple[tuple[int, ...], CoverageState]] = []
        seen: set[tuple[tuple[int, ...], tuple[str, ...]]] = set()
        for item in expanded:
            state = item[1]
            signature = (
                tuple(round(plan.release_time * 4.0) for plan in state.plans),
                tuple(plan.missile_id for plan in state.plans),
            )
            if signature in seen:
                continue
            seen.add(signature)
            unique.append(item)
            if len(unique) >= beam_width:
                break
        states = unique
        if not exact_count or _depth == max_bombs:
            completed.extend(state for _, state in states)

    if exact_count:
        completed = [state for state in completed if len(state.plans) == max_bombs]
    packages: list[RoutePackage] = []
    for state in sorted(completed, key=_state_rank, reverse=True):
        packages.append(
            RoutePackage(
                drone_id=first.drone_id,
                heading_deg=first.normalized_heading_deg,
                speed=first.speed,
                plans=tuple(sorted(state.plans, key=lambda plan: plan.release_time)),
                estimated_score=state.score,
            )
        )
    return packages


def strategy_constraint_violations(
    plans: Sequence[BombPlan], *, require_positive_coverage: bool = False
) -> dict[str, float]:
    """Return non-negative violation magnitudes for every hard constraint."""

    violations = {
        "speed_lower": 0.0,
        "speed_upper": 0.0,
        "release_time": 0.0,
        "fuse_delay": 0.0,
        "explosion_below_ground": 0.0,
        "release_gap": 0.0,
        "shared_heading": 0.0,
        "shared_speed": 0.0,
        "positive_coverage": 0.0,
    }
    by_drone: dict[str, list[BombPlan]] = {}
    for plan in plans:
        violations["speed_lower"] = max(
            violations["speed_lower"], MIN_UAV_SPEED - plan.speed
        )
        violations["speed_upper"] = max(
            violations["speed_upper"], plan.speed - MAX_UAV_SPEED
        )
        violations["release_time"] = max(
            violations["release_time"], -plan.release_time
        )
        violations["fuse_delay"] = max(
            violations["fuse_delay"], 1e-6 - plan.fuse_delay
        )
        try:
            explosion_z = plan.release().explosion_position[2]
        except ValueError:
            explosion_z = -np.inf
        violations["explosion_below_ground"] = max(
            violations["explosion_below_ground"], -float(explosion_z)
        )
        if require_positive_coverage:
            violations["positive_coverage"] = max(
                violations["positive_coverage"],
                1e-9 - interval_duration(_plan_intervals_estimated(plan)),
            )
        by_drone.setdefault(plan.drone_id, []).append(plan)

    for drone_plans in by_drone.values():
        reference = drone_plans[0]
        for plan in drone_plans[1:]:
            violations["shared_heading"] = max(
                violations["shared_heading"],
                circular_heading_difference(plan.heading_deg, reference.heading_deg),
            )
            violations["shared_speed"] = max(
                violations["shared_speed"], abs(plan.speed - reference.speed)
            )
        ordered = sorted(drone_plans, key=lambda plan: plan.release_time)
        for left, right in zip(ordered[:-1], ordered[1:]):
            violations["release_gap"] = max(
                violations["release_gap"],
                MIN_RELEASE_GAP - (right.release_time - left.release_time),
            )
    return {key: max(0.0, float(value)) for key, value in violations.items()}


def exact_evaluate(
    plans: Sequence[BombPlan],
    *,
    max_step: float = 0.01,
    mode: str = "centerline",
    evaluator: CylindricalOcclusionEvaluator | None = None,
    optimize_full: bool = True,
) -> tuple[
    tuple[tuple[tuple[float, float], ...], ...],
    dict[str, tuple[tuple[float, float], ...]],
]:
    individual: list[tuple[tuple[float, float], ...]] = []
    by_missile: dict[str, list[tuple[float, float]]] = {
        missile_id: [] for missile_id in MISSILES
    }
    for plan in plans:
        intervals = effective_intervals(
            MISSILES[plan.missile_id],
            plan.cloud(),
            DEFAULT_TARGET,
            mode=mode,  # type: ignore[arg-type]
            evaluator=evaluator,
            max_step=max_step,
            optimize_full=optimize_full,
        )
        frozen = tuple((float(left), float(right)) for left, right in intervals)
        individual.append(frozen)
        by_missile[plan.missile_id].extend(frozen)
    union = {
        missile_id: tuple(merge_intervals(intervals))
        for missile_id, intervals in by_missile.items()
    }
    return tuple(individual), union


def _result_from_plans(
    problem: str,
    plans: Sequence[BombPlan],
    diagnostics: SolveDiagnostics,
    *,
    exact_step: float = 0.005,
) -> SolveResult:
    ordered = tuple(
        sorted(plans, key=lambda plan: (plan.drone_id, plan.release_time, plan.missile_id))
    )
    individual, union = exact_evaluate(ordered, max_step=exact_step)
    diagnostics.exact_union_by_missile = {
        missile_id: interval_duration(intervals)
        for missile_id, intervals in union.items()
    }
    diagnostics.exact_objective = sum(diagnostics.exact_union_by_missile.values())
    violations = strategy_constraint_violations(ordered, require_positive_coverage=False)
    diagnostics.constraint_violations = violations
    diagnostics.max_constraint_violation = max(violations.values(), default=0.0)
    diagnostics.status = (
        "feasible_verified" if diagnostics.max_constraint_violation <= 1e-8 else "constraint_violation"
    )
    return SolveResult(problem, ordered, individual, union, diagnostics)


def _route_grid(
    *, heading_step: float, speed_step: float
) -> Iterable[tuple[float, float]]:
    headings = np.arange(0.0, 360.0, heading_step)
    speeds = np.arange(MIN_UAV_SPEED, MAX_UAV_SPEED + 0.25 * speed_step, speed_step)
    for heading in headings:
        for speed in speeds:
            yield float(heading), float(min(speed, MAX_UAV_SPEED))


def _deduplicate_routes(routes: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    unique: dict[tuple[int, int], tuple[float, float]] = {}
    for heading, speed in routes:
        normalized = float(heading % 360.0)
        bounded_speed = float(np.clip(speed, MIN_UAV_SPEED, MAX_UAV_SPEED))
        key = (round(normalized * 1000.0), round(bounded_speed * 1000.0))
        unique[key] = (normalized, bounded_speed)
    return list(unique.values())


def _local_random_refine(
    plans: Sequence[BombPlan],
    *,
    seed: int,
    iterations: int,
    share_route_by_drone: bool,
) -> tuple[tuple[BombPlan, ...], float]:
    """Deterministic seeded feasibility-preserving local hill climb."""

    if not plans or iterations <= 0:
        state = tuple(plans)
        return state, coverage_objective(coverage_intervals(state, _plan_intervals_estimated))
    rng = np.random.default_rng(seed)
    best = tuple(plans)
    best_score = coverage_objective(
        coverage_intervals(best, lambda plan: sampled_centerline_intervals(plan, step=0.025))
    )
    drone_ids = sorted({plan.drone_id for plan in best})
    for iteration in range(iterations):
        progress = iteration / max(1, iterations - 1)
        heading_scale = 0.8 * (1.0 - progress) + 0.05
        speed_scale = 3.0 * (1.0 - progress) + 0.15
        time_scale = 0.25 * (1.0 - progress) + 0.01
        selected_drone = drone_ids[int(rng.integers(0, len(drone_ids)))]
        d_heading = float(rng.normal(0.0, heading_scale))
        d_speed = float(rng.normal(0.0, speed_scale))
        changed: list[BombPlan] = []
        for plan in best:
            if plan.drone_id != selected_drone:
                changed.append(plan)
                continue
            heading = plan.heading_deg + d_heading
            speed = float(np.clip(plan.speed + d_speed, MIN_UAV_SPEED, MAX_UAV_SPEED))
            release_time = plan.release_time
            fuse_delay = plan.fuse_delay
            if not share_route_by_drone or rng.random() < 0.65:
                release_time += float(rng.normal(0.0, time_scale))
                fuse_delay += float(rng.normal(0.0, time_scale))
            changed.append(
                replace(
                    plan,
                    heading_deg=heading % 360.0,
                    speed=speed,
                    release_time=release_time,
                    fuse_delay=fuse_delay,
                    anchor_time=None,
                    estimated_intervals=(),
                )
            )
        proposal = tuple(changed)
        violations = strategy_constraint_violations(proposal)
        if max(violations.values(), default=0.0) > 1e-10:
            continue
        score = coverage_objective(
            coverage_intervals(
                proposal, lambda plan: sampled_centerline_intervals(plan, step=0.025)
            )
        )
        if score > best_score + 1e-8:
            best = proposal
            best_score = score
    return best, best_score


def solve_q3(
    *, seed: int = DEFAULT_RANDOM_SEED, quick: bool = False
) -> SolveResult:
    """FY1, one fixed route, exactly three bombs against M1."""

    coarse_heading_step = 10.0 if quick else 5.0
    coarse_speed_step = 14.0 if quick else 10.0
    explosion_step = 0.25 if quick else 0.15
    diagnostics = SolveDiagnostics(
        seed=seed,
        status="searching",
        method="route grid + aligned candidate beam + seeded local refinement",
        optimality_claim="Best verified solution found by the deterministic search; no global proof.",
    )
    coarse_packages: list[RoutePackage] = []
    for heading, speed in _route_grid(
        heading_step=coarse_heading_step, speed_step=coarse_speed_step
    ):
        diagnostics.routes_evaluated += 1
        candidates = aligned_candidates_for_route(
            "FY1",
            heading,
            speed,
            "M1",
            explosion_step=explosion_step,
            time_bin=0.50,
            max_per_bin=2,
        )
        diagnostics.candidates_generated += len(candidates)
        packages = select_route_packages(
            candidates,
            max_bombs=3,
            beam_width=25 if quick else 45,
            exact_count=True,
        )
        if packages:
            coarse_packages.append(packages[0])
    if not coarse_packages:
        raise RuntimeError("Q3 search generated no feasible three-bomb route")
    coarse_packages.sort(key=lambda package: package.estimated_score, reverse=True)
    diagnostics.fast_baseline_objective = coverage_objective(
        coverage_intervals(
            coarse_packages[0].plans,
            lambda plan: sampled_centerline_intervals(plan, step=0.04),
        )
    )
    diagnostics.notes.append(
        f"Aligned-candidate surrogate score={coarse_packages[0].estimated_score:.9f}; "
        "fast baseline is the 0.04 s centreline-grid union."
    )

    seed_packages = coarse_packages[: (2 if quick else 5)]
    neighbourhood_routes: list[tuple[float, float]] = []
    heading_offsets = np.arange(-4.0, 4.0001, 1.0 if quick else 0.5)
    speed_offsets = np.arange(-8.0, 8.0001, 4.0 if quick else 2.0)
    for package in seed_packages:
        neighbourhood_routes.extend(
            (package.heading_deg + dh, package.speed + dv)
            for dh in heading_offsets
            for dv in speed_offsets
        )
    refined_packages: list[RoutePackage] = []
    for heading, speed in _deduplicate_routes(neighbourhood_routes):
        diagnostics.routes_evaluated += 1
        candidates = aligned_candidates_for_route(
            "FY1",
            heading,
            speed,
            "M1",
            explosion_step=0.10 if quick else 0.05,
            time_bin=0.25,
            max_per_bin=2,
        )
        diagnostics.candidates_generated += len(candidates)
        packages = select_route_packages(
            candidates,
            max_bombs=3,
            beam_width=45 if quick else 90,
            exact_count=True,
        )
        if packages:
            refined_packages.append(packages[0])
    all_packages = sorted(
        [*coarse_packages[:10], *refined_packages],
        key=lambda package: package.estimated_score,
        reverse=True,
    )
    diagnostics.packages_retained = len(all_packages)

    # Exact continuous-time score selects among the top approximate packages.
    exact_candidates: list[tuple[float, tuple[BombPlan, ...]]] = []
    for package in all_packages[: (8 if quick else 24)]:
        _individual, union = exact_evaluate(package.plans, max_step=0.01)
        exact_candidates.append((coverage_objective(union), package.plans))
    exact_candidates.sort(key=lambda item: item[0], reverse=True)
    starting_plans = exact_candidates[0][1]
    locally_refined, _local_fast_score = _local_random_refine(
        starting_plans,
        seed=seed + 301,
        iterations=80 if quick else 320,
        share_route_by_drone=True,
    )
    base_exact = exact_candidates[0][0]
    _, local_union = exact_evaluate(locally_refined, max_step=0.01)
    local_exact = coverage_objective(local_union)
    final_plans = locally_refined if local_exact > base_exact + 1e-8 else starting_plans
    diagnostics.fast_final_objective = coverage_objective(
        coverage_intervals(
            final_plans, lambda plan: sampled_centerline_intervals(plan, step=0.025)
        )
    )
    diagnostics.notes.append(
        f"Top approximate packages were re-ranked by continuous intervals; local exact score={local_exact:.9f}."
    )
    return _result_from_plans("Q3", final_plans, diagnostics)


def _single_candidate_pool(
    drone_id: str,
    missile_id: str,
    *,
    quick: bool,
    diagnostics: SolveDiagnostics,
) -> list[BombPlan]:
    heading_step = 10.0 if quick else 5.0
    speed_step = 14.0 if quick else 10.0
    explosion_step = 0.25 if quick else 0.15
    time_bin = 2.0
    global_bins: dict[int, list[BombPlan]] = {}
    for heading, speed in _route_grid(
        heading_step=heading_step, speed_step=speed_step
    ):
        diagnostics.routes_evaluated += 1
        candidates = aligned_candidates_for_route(
            drone_id,
            heading,
            speed,
            missile_id,
            explosion_step=explosion_step,
            time_bin=0.75,
            max_per_bin=1,
        )
        diagnostics.candidates_generated += len(candidates)
        for candidate in candidates:
            key = int(floor(float(candidate.anchor_time) / time_bin))
            global_bins.setdefault(key, []).append(candidate)
    pool: list[BombPlan] = []
    keep_per_bin = 4 if quick else 8
    for candidates in global_bins.values():
        candidates.sort(
            key=lambda plan: interval_duration(plan.estimated_intervals), reverse=True
        )
        diverse: list[BombPlan] = []
        for plan in candidates:
            if all(
                circular_heading_difference(plan.heading_deg, other.heading_deg) > 1.0
                or abs(plan.speed - other.speed) > 2.0
                for other in diverse
            ):
                diverse.append(plan)
            if len(diverse) >= keep_per_bin:
                break
        pool.extend(diverse)
    return sorted(
        pool,
        key=lambda plan: interval_duration(plan.estimated_intervals),
        reverse=True,
    )


def solve_q4(
    *, seed: int = DEFAULT_RANDOM_SEED, quick: bool = False
) -> SolveResult:
    """FY1--FY3, one bomb each, all against M1."""

    diagnostics = SolveDiagnostics(
        seed=seed,
        status="searching",
        method="temporally diverse single-bomb pools + cross-UAV coverage beam",
        optimality_claim="Best verified solution found by the deterministic search; no global proof.",
    )
    pools = {
        drone_id: _single_candidate_pool(
            drone_id, "M1", quick=quick, diagnostics=diagnostics
        )
        for drone_id in ("FY1", "FY2", "FY3")
    }
    if any(not pool for pool in pools.values()):
        raise RuntimeError("Q4 candidate generation failed for at least one UAV")
    states = [_coverage_state(())]
    for drone_id in ("FY1", "FY2", "FY3"):
        expanded: list[CoverageState] = []
        for state in states:
            for candidate in pools[drone_id]:
                expanded.append(_coverage_state((*state.plans, candidate)))
        expanded.sort(key=_state_rank, reverse=True)
        unique: list[CoverageState] = []
        seen: set[tuple[int, ...]] = set()
        for state in expanded:
            signature = tuple(
                round((plan.anchor_time or 0.0) * 2.0) for plan in state.plans
            )
            if signature in seen:
                continue
            seen.add(signature)
            unique.append(state)
            if len(unique) >= (140 if quick else 360):
                break
        states = unique
    diagnostics.fast_baseline_objective = coverage_objective(
        coverage_intervals(
            states[0].plans,
            lambda plan: sampled_centerline_intervals(plan, step=0.04),
        )
    )
    diagnostics.notes.append(
        f"Pool surrogate score={states[0].score:.9f}; fast baseline is the 0.04 s centreline-grid union."
    )
    diagnostics.packages_retained = len(states)
    exact_candidates: list[tuple[float, tuple[BombPlan, ...]]] = []
    for state in states[: (12 if quick else 36)]:
        _, union = exact_evaluate(state.plans, max_step=0.01)
        exact_candidates.append((coverage_objective(union), state.plans))
    exact_candidates.sort(key=lambda item: item[0], reverse=True)
    starting_plans = exact_candidates[0][1]
    locally_refined, _local_fast_score = _local_random_refine(
        starting_plans,
        seed=seed + 401,
        iterations=80 if quick else 280,
        share_route_by_drone=False,
    )
    _, local_union = exact_evaluate(locally_refined, max_step=0.01)
    local_exact = coverage_objective(local_union)
    final_plans = (
        locally_refined
        if local_exact > exact_candidates[0][0] + 1e-8
        else starting_plans
    )
    diagnostics.fast_final_objective = coverage_objective(
        coverage_intervals(
            final_plans, lambda plan: sampled_centerline_intervals(plan, step=0.025)
        )
    )
    diagnostics.notes.append(
        f"Temporal pools prevent three independent single-bomb maxima from overlapping; local exact score={local_exact:.9f}."
    )
    return _result_from_plans("Q4", final_plans, diagnostics)


def _route_package_options_q5(
    drone_id: str,
    heading: float,
    speed: float,
    *,
    quick: bool,
    diagnostics: SolveDiagnostics,
) -> list[RoutePackage]:
    candidates: list[BombPlan] = []
    for missile_id in MISSILES:
        generated = aligned_candidates_for_route(
            drone_id,
            heading,
            speed,
            missile_id,
            explosion_step=0.35 if quick else 0.25,
            time_bin=1.5,
            max_per_bin=1,
        )
        diagnostics.candidates_generated += len(generated)
        candidates.extend(generated)
    packages = select_route_packages(
        candidates,
        max_bombs=3,
        beam_width=16 if quick else 28,
        exact_count=True,
    )
    best_by_signature: dict[tuple[int, int, int], RoutePackage] = {}
    for package in packages:
        signature = package.assignment_signature
        if signature not in best_by_signature:
            best_by_signature[signature] = package
    return list(best_by_signature.values())


def _q5_package_pools(
    *, quick: bool, diagnostics: SolveDiagnostics
) -> dict[str, list[RoutePackage]]:
    pools: dict[str, list[RoutePackage]] = {}
    for drone_id in UAV_INITIALS:
        retained: dict[tuple[int, int, int], list[RoutePackage]] = {}
        for heading, speed in _route_grid(
            heading_step=15.0 if quick else 10.0,
            speed_step=14.0 if quick else 10.0,
        ):
            diagnostics.routes_evaluated += 1
            options = _route_package_options_q5(
                drone_id,
                heading,
                speed,
                quick=quick,
                diagnostics=diagnostics,
            )
            for package in options:
                retained.setdefault(package.assignment_signature, []).append(package)
        pool: list[RoutePackage] = []
        for packages in retained.values():
            packages.sort(key=lambda package: package.estimated_score, reverse=True)
            pool.extend(packages[: (2 if quick else 4)])
        pool.sort(key=lambda package: package.estimated_score, reverse=True)
        pools[drone_id] = pool
    return pools


def solve_q5(
    *, seed: int = DEFAULT_RANDOM_SEED, quick: bool = False
) -> SolveResult:
    """Five fixed UAV routes, at most three bombs each, three missile tasks.

    This is intentionally labelled a feasible route-package beam search rather
    than a globally solved mixed-integer nonlinear program.
    """

    diagnostics = SolveDiagnostics(
        seed=seed,
        status="searching",
        method="route-consistent package generation + multi-UAV assignment beam",
        optimality_claim=(
            "High-quality feasible solution from a deterministic restricted route library; "
            "no global optimality proof."
        ),
    )
    pools = _q5_package_pools(quick=quick, diagnostics=diagnostics)
    if any(not pool for pool in pools.values()):
        missing = [drone for drone, pool in pools.items() if not pool]
        raise RuntimeError(f"Q5 has no route packages for {missing}")

    states = [_coverage_state(())]
    for drone_id in UAV_INITIALS:
        expanded: list[CoverageState] = []
        for state in states:
            for package in pools[drone_id]:
                expanded.append(_coverage_state((*state.plans, *package.plans)))
        expanded.sort(key=_state_rank, reverse=True)
        unique: list[CoverageState] = []
        seen: set[tuple[tuple[int, ...], tuple[int, int, int]]] = set()
        for state in expanded:
            release_signature = tuple(
                round(plan.release_time * 2.0) for plan in state.plans
            )
            assignment_signature = tuple(
                sum(plan.missile_id == missile for plan in state.plans)
                for missile in MISSILES
            )
            signature = (release_signature, assignment_signature)
            if signature in seen:
                continue
            seen.add(signature)
            unique.append(state)
            if len(unique) >= (160 if quick else 420):
                break
        states = unique
    all_tasks = [
        state
        for state in states
        if all(any(plan.missile_id == missile for plan in state.plans) for missile in MISSILES)
    ]
    if not all_tasks:
        raise RuntimeError("Q5 beam did not retain a solution covering all three missile tasks")
    all_tasks.sort(key=_state_rank, reverse=True)
    diagnostics.fast_baseline_objective = coverage_objective(
        coverage_intervals(
            all_tasks[0].plans,
            lambda plan: sampled_centerline_intervals(plan, step=0.04),
        )
    )
    diagnostics.notes.append(
        f"Route-package surrogate score={all_tasks[0].score:.9f}; "
        "fast baseline is the 0.04 s centreline-grid union."
    )
    diagnostics.packages_retained = sum(len(pool) for pool in pools.values())

    exact_candidates: list[tuple[float, tuple[BombPlan, ...]]] = []
    for state in all_tasks[: (8 if quick else 24)]:
        _, union = exact_evaluate(state.plans, max_step=0.015)
        exact_candidates.append((coverage_objective(union), state.plans))
    exact_candidates.sort(key=lambda item: item[0], reverse=True)
    final_plans = exact_candidates[0][1]
    diagnostics.fast_final_objective = coverage_objective(
        coverage_intervals(
            final_plans, lambda plan: sampled_centerline_intervals(plan, step=0.04)
        )
    )
    diagnostics.notes.extend(
        [
            "Every selected per-UAV package uses one common heading and speed.",
            "The restricted package beam jointly assigns bombs to M1/M2/M3 and enforces release gaps.",
            "Result is a reproducible feasible baseline, not a global optimum certificate.",
        ]
    )
    return _result_from_plans("Q5", final_plans, diagnostics, exact_step=0.0075)


def result_to_dict(result: SolveResult) -> dict[str, object]:
    """JSON-safe summary used by the independent validation artifact."""

    plan_rows: list[dict[str, object]] = []
    for plan, intervals in zip(result.plans, result.exact_individual_intervals):
        row = asdict(plan)
        row["heading_deg"] = plan.normalized_heading_deg
        row["explosion_time"] = plan.explosion_time
        row["release_position"] = list(plan.release_position)
        row["explosion_position"] = list(plan.explosion_position)
        row["exact_centerline_intervals"] = [list(value) for value in intervals]
        row["exact_centerline_duration"] = interval_duration(intervals)
        row.pop("estimated_intervals", None)
        plan_rows.append(row)
    return {
        "problem": result.problem,
        "plans": plan_rows,
        "exact_centerline_union": {
            missile_id: [list(value) for value in intervals]
            for missile_id, intervals in result.exact_union_by_missile.items()
        },
        "exact_centerline_duration_by_missile": {
            missile_id: interval_duration(intervals)
            for missile_id, intervals in result.exact_union_by_missile.items()
        },
        "exact_centerline_objective": result.exact_objective,
        "diagnostics": asdict(result.diagnostics),
    }


__all__ = [
    "BombPlan",
    "DEFAULT_RANDOM_SEED",
    "MAX_UAV_SPEED",
    "MIN_RELEASE_GAP",
    "MIN_UAV_SPEED",
    "MISSILE_INITIALS",
    "MISSILES",
    "RoutePackage",
    "SolveDiagnostics",
    "SolveResult",
    "UAV_INITIALS",
    "aligned_candidates_for_route",
    "coverage_intervals",
    "coverage_objective",
    "exact_evaluate",
    "result_to_dict",
    "sampled_centerline_intervals",
    "select_route_packages",
    "solve_q3",
    "solve_q4",
    "solve_q5",
    "strategy_constraint_violations",
]
