"""2025 CUMCM A: reusable kinematics and exact smoke-screen geometry.

The module deliberately contains no fitted or answer-specific parameters.  It
implements the motion stated in the official problem and two explicit
occlusion conventions:

``centerline``
    The segment from the missile to the geometric centre of the cylindrical
    target intersects the effective smoke sphere.

``full_cylinder``
    Every segment from the missile to a point of the complete cylindrical
    target intersects the effective smoke sphere.  This is the conservative
    convention.  Its margin is the smoke radius minus the largest distance
    from the smoke centre to any such sight segment.

The full-cylinder evaluator exposes both a vectorised surface scan (suited to
Q2--Q5 search) and continuous boundary refinement (suited to final checking).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, pi
from typing import Callable, Iterable, Literal, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import brentq, minimize


FloatVector = NDArray[np.float64]
OcclusionMode = Literal["centerline", "full_cylinder"]

GRAVITY = 9.8
SMOKE_RADIUS = 10.0
SMOKE_LIFETIME = 20.0
SMOKE_SINK_SPEED = 3.0

FALSE_TARGET = (0.0, 0.0, 0.0)
M1_INITIAL = (20_000.0, 0.0, 2_000.0)
FY1_INITIAL = (17_800.0, 0.0, 1_800.0)


def _vec3(value: ArrayLike, *, name: str = "vector") -> FloatVector:
    vector = np.asarray(value, dtype=float)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must be a finite three-dimensional vector")
    return vector


def _positive(value: float, *, name: str) -> float:
    value = float(value)
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def _nonnegative(value: float, *, name: str) -> float:
    value = float(value)
    if not np.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


@dataclass(frozen=True)
class MissileTrajectory:
    """Constant-speed straight missile trajectory aimed at a fixed point."""

    initial_position: tuple[float, float, float]
    aim_point: tuple[float, float, float] = FALSE_TARGET
    speed: float = 300.0

    def __post_init__(self) -> None:
        initial = _vec3(self.initial_position, name="initial_position")
        aim = _vec3(self.aim_point, name="aim_point")
        _positive(self.speed, name="speed")
        if np.linalg.norm(aim - initial) == 0.0:
            raise ValueError("missile initial_position and aim_point must differ")

    @property
    def velocity(self) -> FloatVector:
        initial = _vec3(self.initial_position)
        displacement = _vec3(self.aim_point) - initial
        return float(self.speed) * displacement / np.linalg.norm(displacement)

    @property
    def impact_time(self) -> float:
        return float(
            np.linalg.norm(_vec3(self.aim_point) - _vec3(self.initial_position))
            / float(self.speed)
        )

    def position(self, time: float) -> FloatVector:
        return _vec3(self.initial_position) + self.velocity * float(time)


@dataclass(frozen=True)
class UAVTrajectory:
    """Horizontal constant-speed UAV trajectory after its instantaneous turn."""

    initial_position: tuple[float, float, float]
    heading_xy: tuple[float, float]
    speed: float

    def __post_init__(self) -> None:
        _vec3(self.initial_position, name="initial_position")
        heading = np.asarray(self.heading_xy, dtype=float)
        if heading.shape != (2,) or not np.all(np.isfinite(heading)):
            raise ValueError("heading_xy must be a finite two-dimensional vector")
        if np.linalg.norm(heading) == 0.0:
            raise ValueError("heading_xy must be non-zero")
        _positive(self.speed, name="speed")

    @classmethod
    def toward_xy(
        cls,
        initial_position: Sequence[float],
        destination_xy: Sequence[float],
        speed: float,
    ) -> "UAVTrajectory":
        initial = _vec3(initial_position, name="initial_position")
        destination = np.asarray(destination_xy, dtype=float)
        if destination.shape != (2,):
            raise ValueError("destination_xy must have two coordinates")
        heading = destination - initial[:2]
        return cls(tuple(initial), tuple(heading), speed)

    @property
    def velocity(self) -> FloatVector:
        heading = np.asarray(self.heading_xy, dtype=float)
        horizontal = float(self.speed) * heading / np.linalg.norm(heading)
        return np.array((horizontal[0], horizontal[1], 0.0), dtype=float)

    def position(self, time: float) -> FloatVector:
        return _vec3(self.initial_position) + self.velocity * float(time)

    def release(self, release_time: float, fuse_delay: float) -> "BombRelease":
        return BombRelease(
            release_time=float(release_time),
            fuse_delay=float(fuse_delay),
            release_position=tuple(self.position(release_time)),
            initial_velocity=tuple(self.velocity),
        )


@dataclass(frozen=True)
class BombRelease:
    """Ballistic bomb state at release, before instantaneous smoke formation."""

    release_time: float
    fuse_delay: float
    release_position: tuple[float, float, float]
    initial_velocity: tuple[float, float, float]
    gravity: float = GRAVITY

    def __post_init__(self) -> None:
        if self.release_time < 0.0 or not np.isfinite(self.release_time):
            raise ValueError("release_time must be finite and non-negative")
        _nonnegative(self.fuse_delay, name="fuse_delay")
        _vec3(self.release_position, name="release_position")
        _vec3(self.initial_velocity, name="initial_velocity")
        _positive(self.gravity, name="gravity")

    @property
    def explosion_time(self) -> float:
        return float(self.release_time + self.fuse_delay)

    @property
    def explosion_position(self) -> FloatVector:
        delay = float(self.fuse_delay)
        gravity_acceleration = np.array((0.0, 0.0, -float(self.gravity)))
        return (
            _vec3(self.release_position)
            + _vec3(self.initial_velocity) * delay
            + 0.5 * gravity_acceleration * delay**2
        )

    def smoke_cloud(
        self,
        *,
        radius: float = SMOKE_RADIUS,
        lifetime: float = SMOKE_LIFETIME,
        sink_speed: float = SMOKE_SINK_SPEED,
    ) -> "SmokeCloud":
        return SmokeCloud(
            explosion_time=self.explosion_time,
            explosion_position=tuple(self.explosion_position),
            radius=radius,
            lifetime=lifetime,
            sink_speed=sink_speed,
        )


@dataclass(frozen=True)
class SmokeCloud:
    """Spherical effective smoke region with a uniformly descending centre."""

    explosion_time: float
    explosion_position: tuple[float, float, float]
    radius: float = SMOKE_RADIUS
    lifetime: float = SMOKE_LIFETIME
    sink_speed: float = SMOKE_SINK_SPEED

    def __post_init__(self) -> None:
        if self.explosion_time < 0.0 or not np.isfinite(self.explosion_time):
            raise ValueError("explosion_time must be finite and non-negative")
        _vec3(self.explosion_position, name="explosion_position")
        _positive(self.radius, name="radius")
        _positive(self.lifetime, name="lifetime")
        if self.sink_speed < 0.0 or not np.isfinite(self.sink_speed):
            raise ValueError("sink_speed must be finite and non-negative")

    @property
    def expiry_time(self) -> float:
        return float(self.explosion_time + self.lifetime)

    def is_active(self, time: float, *, tolerance: float = 1e-12) -> bool:
        return (
            self.explosion_time - tolerance
            <= float(time)
            <= self.expiry_time + tolerance
        )

    def center(self, time: float) -> FloatVector:
        elapsed = float(time) - self.explosion_time
        return _vec3(self.explosion_position) + np.array(
            (0.0, 0.0, -self.sink_speed * elapsed), dtype=float
        )


@dataclass(frozen=True)
class CylinderTarget:
    """Vertical solid cylinder, represented by its bottom-centre point."""

    bottom_center: tuple[float, float, float] = (0.0, 200.0, 0.0)
    radius: float = 7.0
    height: float = 10.0

    def __post_init__(self) -> None:
        _vec3(self.bottom_center, name="bottom_center")
        _positive(self.radius, name="radius")
        _positive(self.height, name="height")

    @property
    def center(self) -> FloatVector:
        return _vec3(self.bottom_center) + np.array((0.0, 0.0, self.height / 2.0))

    def surface_point(self, theta: float, z: float, radius: float | None = None) -> FloatVector:
        radial = self.radius if radius is None else float(radius)
        return _vec3(self.bottom_center) + np.array(
            (radial * np.cos(theta), radial * np.sin(theta), float(z)), dtype=float
        )


DEFAULT_TARGET = CylinderTarget()


def closest_segment_fraction(point: ArrayLike, start: ArrayLike, end: ArrayLike) -> float:
    """Return the clipped fraction of the closest point on ``start--end``."""

    point_vector = _vec3(point, name="point")
    start_vector = _vec3(start, name="start")
    segment = _vec3(end, name="end") - start_vector
    length_squared = float(np.dot(segment, segment))
    if length_squared == 0.0:
        return 0.0
    fraction = float(np.dot(point_vector - start_vector, segment) / length_squared)
    return float(np.clip(fraction, 0.0, 1.0))


def point_to_segment_distance(point: ArrayLike, start: ArrayLike, end: ArrayLike) -> float:
    fraction = closest_segment_fraction(point, start, end)
    start_vector = _vec3(start)
    closest = start_vector + fraction * (_vec3(end) - start_vector)
    return float(np.linalg.norm(_vec3(point) - closest))


def _point_to_segments_distance(
    point: ArrayLike, start: ArrayLike, ends: NDArray[np.float64]
) -> FloatVector:
    point_vector = _vec3(point)
    start_vector = _vec3(start)
    end_vectors = np.asarray(ends, dtype=float)
    if end_vectors.ndim != 2 or end_vectors.shape[1] != 3:
        raise ValueError("ends must have shape (n, 3)")
    segments = end_vectors - start_vector
    denominator = np.einsum("ij,ij->i", segments, segments)
    if np.any(denominator == 0.0):
        raise ValueError("a sight segment has zero length")
    fractions = segments @ (point_vector - start_vector) / denominator
    fractions = np.clip(fractions, 0.0, 1.0)
    residuals = point_vector - start_vector - fractions[:, None] * segments
    return np.linalg.norm(residuals, axis=1)


def segment_sphere_intersection_interval(
    start: ArrayLike,
    end: ArrayLike,
    sphere_center: ArrayLike,
    sphere_radius: float,
) -> tuple[float, float] | None:
    """Return segment fractions inside a sphere, or ``None`` when disjoint."""

    radius = _positive(sphere_radius, name="sphere_radius")
    start_vector = _vec3(start)
    segment = _vec3(end) - start_vector
    relative = start_vector - _vec3(sphere_center)
    quadratic = float(np.dot(segment, segment))
    if quadratic == 0.0:
        return (0.0, 0.0) if np.linalg.norm(relative) <= radius else None
    linear = 2.0 * float(np.dot(relative, segment))
    constant = float(np.dot(relative, relative) - radius**2)
    discriminant = linear**2 - 4.0 * quadratic * constant
    if discriminant < 0.0:
        return None
    root = float(np.sqrt(max(discriminant, 0.0)))
    left = max(0.0, (-linear - root) / (2.0 * quadratic))
    right = min(1.0, (-linear + root) / (2.0 * quadratic))
    if left > right:
        return None
    return (float(left), float(right))


def point_occlusion_margin(
    missile_position: ArrayLike,
    smoke_center: ArrayLike,
    target_point: ArrayLike,
    smoke_radius: float = SMOKE_RADIUS,
) -> float:
    """Positive exactly when the finite missile--target segment meets the sphere."""

    return float(
        _positive(smoke_radius, name="smoke_radius")
        - point_to_segment_distance(smoke_center, missile_position, target_point)
    )


@dataclass(frozen=True)
class WorstSightline:
    """The target point whose sight segment is hardest for the smoke to cover."""

    target_point: tuple[float, float, float]
    distance: float
    surface: str


class CylindricalOcclusionEvaluator:
    """Conservative complete-cylinder occlusion evaluator.

    ``sampled_worst_sightline`` is deterministic and vectorised.  It is useful
    inside a global strategy search.  ``worst_sightline`` additionally refines
    the side and both caps as continuous bounded surfaces; use it to verify a
    reported strategy and to refine effective-time roots.
    """

    def __init__(
        self,
        target: CylinderTarget = DEFAULT_TARGET,
        *,
        n_azimuth: int = 96,
        n_linear: int = 9,
        local_starts: int = 6,
    ) -> None:
        if n_azimuth < 16:
            raise ValueError("n_azimuth must be at least 16")
        if n_linear < 3:
            raise ValueError("n_linear must be at least 3")
        if local_starts < 1:
            raise ValueError("local_starts must be positive")
        self.target = target
        self.n_azimuth = int(n_azimuth)
        self.n_linear = int(n_linear)
        self.local_starts = int(local_starts)
        self._domains = self._build_domains()

    def _build_domains(self) -> dict[str, tuple[FloatVector, FloatVector, NDArray[np.float64]]]:
        theta = np.linspace(0.0, 2.0 * pi, self.n_azimuth, endpoint=False)
        z_values = np.linspace(0.0, self.target.height, self.n_linear)
        radial_values = np.linspace(0.0, self.target.radius, self.n_linear)
        bottom = _vec3(self.target.bottom_center)

        side_theta, side_z = np.meshgrid(theta, z_values, indexing="ij")
        side_points = bottom + np.column_stack(
            (
                self.target.radius * np.cos(side_theta.ravel()),
                self.target.radius * np.sin(side_theta.ravel()),
                side_z.ravel(),
            )
        )
        domains: dict[str, tuple[FloatVector, FloatVector, NDArray[np.float64]]] = {
            "side": (side_theta.ravel(), side_z.ravel(), side_points)
        }
        for label, z in (("bottom_cap", 0.0), ("top_cap", self.target.height)):
            cap_theta, cap_radius = np.meshgrid(theta, radial_values, indexing="ij")
            cap_points = bottom + np.column_stack(
                (
                    cap_radius.ravel() * np.cos(cap_theta.ravel()),
                    cap_radius.ravel() * np.sin(cap_theta.ravel()),
                    np.full(cap_theta.size, z),
                )
            )
            domains[label] = (cap_theta.ravel(), cap_radius.ravel(), cap_points)
        return domains

    def sampled_worst_sightline(
        self, missile_position: ArrayLike, smoke_center: ArrayLike
    ) -> WorstSightline:
        missile = _vec3(missile_position)
        smoke = _vec3(smoke_center)
        best: WorstSightline | None = None
        for label, (_, _, points) in self._domains.items():
            distances = _point_to_segments_distance(smoke, missile, points)
            index = int(np.argmax(distances))
            candidate = WorstSightline(tuple(points[index]), float(distances[index]), label)
            if best is None or candidate.distance > best.distance:
                best = candidate
        if best is None:  # pragma: no cover - domains are built in __init__
            raise RuntimeError("no target surface samples were generated")
        return best

    def _point_from_parameters(self, surface: str, parameters: ArrayLike) -> FloatVector:
        values = np.asarray(parameters, dtype=float)
        if surface == "side":
            theta, z = values
            return self.target.surface_point(theta, z)
        theta, radial = values
        z = 0.0 if surface == "bottom_cap" else self.target.height
        return self.target.surface_point(theta, z, radius=radial)

    def worst_sightline(
        self,
        missile_position: ArrayLike,
        smoke_center: ArrayLike,
        *,
        optimize: bool = True,
    ) -> WorstSightline:
        missile = _vec3(missile_position)
        smoke = _vec3(smoke_center)
        sampled = self.sampled_worst_sightline(missile, smoke)
        if not optimize:
            return sampled

        best = sampled
        for surface, (first, second, points) in self._domains.items():
            distances = _point_to_segments_distance(smoke, missile, points)
            count = min(self.local_starts, len(distances))
            seed_indices = np.argpartition(distances, -count)[-count:]
            if surface == "side":
                bounds = ((0.0, 2.0 * pi), (0.0, self.target.height))
            else:
                bounds = ((0.0, 2.0 * pi), (0.0, self.target.radius))

            def objective(parameters: FloatVector) -> float:
                point = self._point_from_parameters(surface, parameters)
                return -point_to_segment_distance(smoke, missile, point)

            for index in seed_indices:
                initial = np.array((first[index], second[index]), dtype=float)
                result = minimize(
                    objective,
                    initial,
                    method="Powell",
                    bounds=bounds,
                    options={"xtol": 1e-11, "ftol": 1e-13, "maxiter": 250},
                )
                point = self._point_from_parameters(surface, result.x)
                distance = point_to_segment_distance(smoke, missile, point)
                if distance > best.distance:
                    best = WorstSightline(tuple(point), float(distance), surface)
        return best

    def conservative_margin(
        self,
        missile_position: ArrayLike,
        smoke_center: ArrayLike,
        smoke_radius: float = SMOKE_RADIUS,
        *,
        optimize: bool = True,
    ) -> float:
        worst = self.worst_sightline(
            missile_position, smoke_center, optimize=optimize
        )
        return float(_positive(smoke_radius, name="smoke_radius") - worst.distance)


def trajectory_occlusion_margin(
    time: float,
    missile: MissileTrajectory,
    cloud: SmokeCloud,
    target: CylinderTarget = DEFAULT_TARGET,
    *,
    mode: OcclusionMode = "centerline",
    evaluator: CylindricalOcclusionEvaluator | None = None,
    optimize_full: bool = True,
) -> float:
    """Occlusion margin at an absolute time; inactive states return ``-inf``."""

    time = float(time)
    if not cloud.is_active(time) or time < 0.0 or time > missile.impact_time:
        return -np.inf
    missile_position = missile.position(time)
    smoke_center = cloud.center(time)
    if mode == "centerline":
        return point_occlusion_margin(
            missile_position, smoke_center, target.center, cloud.radius
        )
    if mode != "full_cylinder":
        raise ValueError(f"unsupported occlusion mode: {mode}")
    active_evaluator = evaluator or CylindricalOcclusionEvaluator(target)
    return active_evaluator.conservative_margin(
        missile_position,
        smoke_center,
        cloud.radius,
        optimize=optimize_full,
    )


def _deduplicate(values: Iterable[float], tolerance: float) -> list[float]:
    result: list[float] = []
    for value in sorted(float(item) for item in values):
        if not result or abs(value - result[-1]) > tolerance:
            result.append(value)
    return result


def find_nonnegative_intervals(
    margin: Callable[[float], float],
    start_time: float,
    end_time: float,
    *,
    max_step: float = 0.01,
    root_tolerance: float = 1e-11,
) -> list[tuple[float, float]]:
    """Find positive-measure intervals on which a continuous margin is >= 0.

    The uniform scan isolates sign-changing roots; Brent's method then refines
    each boundary.  A zero merely touched at one instant has zero duration and
    is intentionally omitted.
    """

    start = float(start_time)
    end = float(end_time)
    if not np.isfinite(start) or not np.isfinite(end) or end < start:
        raise ValueError("invalid time range")
    step = _positive(max_step, name="max_step")
    if end == start:
        return []
    count = max(1, int(ceil((end - start) / step)))
    grid = np.linspace(start, end, count + 1)
    values = np.array([float(margin(float(time))) for time in grid])
    values = np.where(np.isfinite(values), values, -np.inf)
    roots: list[float] = []
    for left_time, right_time, left_value, right_value in zip(
        grid[:-1], grid[1:], values[:-1], values[1:]
    ):
        if left_value == 0.0:
            roots.append(float(left_time))
        if np.isfinite(left_value) and np.isfinite(right_value) and left_value * right_value < 0.0:
            roots.append(
                float(
                    brentq(
                        margin,
                        float(left_time),
                        float(right_time),
                        xtol=root_tolerance,
                        rtol=max(4.0 * np.finfo(float).eps, root_tolerance),
                    )
                )
            )
    if values[-1] == 0.0:
        roots.append(end)
    boundaries = [start, *_deduplicate(roots, 10.0 * root_tolerance), end]
    intervals: list[tuple[float, float]] = []
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        if right - left <= root_tolerance:
            continue
        midpoint = 0.5 * (left + right)
        if float(margin(midpoint)) >= 0.0:
            intervals.append((float(left), float(right)))
    return merge_intervals(intervals, tolerance=10.0 * root_tolerance)


def _refine_boundary_near(
    approximate: float,
    exact_margin: Callable[[float], float],
    start: float,
    end: float,
    step: float,
) -> float:
    """Refine a sampled boundary with the continuously optimized margin."""

    left = max(start, approximate - 4.0 * step)
    right = min(end, approximate + 4.0 * step)
    left_value = float(exact_margin(left))
    right_value = float(exact_margin(right))
    if (
        np.isfinite(left_value)
        and np.isfinite(right_value)
        and left_value * right_value < 0.0
    ):
        return float(brentq(exact_margin, left, right, xtol=1e-12))
    grid = np.linspace(left, right, 33)
    values = [float(exact_margin(float(time))) for time in grid]
    roots: list[float] = []
    for a, b, fa, fb in zip(grid[:-1], grid[1:], values[:-1], values[1:]):
        if np.isfinite(fa) and np.isfinite(fb) and fa * fb < 0.0:
            roots.append(float(brentq(exact_margin, float(a), float(b), xtol=1e-12)))
        elif fa == 0.0:
            roots.append(float(a))
    return min(roots, key=lambda item: abs(item - approximate)) if roots else approximate


def effective_intervals(
    missile: MissileTrajectory,
    cloud: SmokeCloud,
    target: CylinderTarget = DEFAULT_TARGET,
    *,
    mode: OcclusionMode = "centerline",
    evaluator: CylindricalOcclusionEvaluator | None = None,
    max_step: float = 0.01,
    optimize_full: bool = True,
) -> list[tuple[float, float]]:
    """Return all effective intervals within cloud life and missile flight."""

    start = max(0.0, cloud.explosion_time)
    end = min(cloud.expiry_time, missile.impact_time)
    if end <= start:
        return []
    active_evaluator = evaluator or CylindricalOcclusionEvaluator(target)
    if mode == "centerline":
        return find_nonnegative_intervals(
            lambda time: trajectory_occlusion_margin(
                time, missile, cloud, target, mode="centerline"
            ),
            start,
            end,
            max_step=max_step,
        )
    if mode != "full_cylinder":
        raise ValueError(f"unsupported occlusion mode: {mode}")

    sampled_margin = lambda time: trajectory_occlusion_margin(
        time,
        missile,
        cloud,
        target,
        mode="full_cylinder",
        evaluator=active_evaluator,
        optimize_full=False,
    )
    sampled_intervals = find_nonnegative_intervals(
        sampled_margin, start, end, max_step=max_step
    )
    if not optimize_full:
        return sampled_intervals

    exact_margin = lambda time: trajectory_occlusion_margin(
        time,
        missile,
        cloud,
        target,
        mode="full_cylinder",
        evaluator=active_evaluator,
        optimize_full=True,
    )
    refined: list[tuple[float, float]] = []
    for left, right in sampled_intervals:
        exact_left = (
            left
            if abs(left - start) <= 1e-12 and exact_margin(start) >= 0.0
            else _refine_boundary_near(left, exact_margin, start, end, max_step)
        )
        exact_right = (
            right
            if abs(right - end) <= 1e-12 and exact_margin(end) >= 0.0
            else _refine_boundary_near(right, exact_margin, start, end, max_step)
        )
        if exact_right > exact_left and exact_margin(0.5 * (exact_left + exact_right)) >= 0.0:
            refined.append((float(exact_left), float(exact_right)))
    return merge_intervals(refined, tolerance=1e-10)


def merge_intervals(
    intervals: Iterable[tuple[float, float]], *, tolerance: float = 1e-10
) -> list[tuple[float, float]]:
    """Return the union of time intervals without double-counting overlaps."""

    ordered = sorted((float(left), float(right)) for left, right in intervals)
    merged: list[list[float]] = []
    for left, right in ordered:
        if right < left:
            raise ValueError("interval right endpoint precedes left endpoint")
        if not merged or left > merged[-1][1] + tolerance:
            merged.append([left, right])
        else:
            merged[-1][1] = max(merged[-1][1], right)
    return [(left, right) for left, right in merged if right - left > tolerance]


def interval_duration(intervals: Iterable[tuple[float, float]]) -> float:
    """Measure the union of intervals."""

    return float(sum(right - left for left, right in merge_intervals(intervals)))


def make_q1_scenario(
    *, gravity: float = GRAVITY
) -> tuple[MissileTrajectory, UAVTrajectory, BombRelease, SmokeCloud, CylinderTarget]:
    """Construct Q1 directly from the official statement's fixed parameters."""

    missile = MissileTrajectory(M1_INITIAL)
    uav = UAVTrajectory.toward_xy(FY1_INITIAL, FALSE_TARGET[:2], speed=120.0)
    release = uav.release(release_time=1.5, fuse_delay=3.6)
    if gravity != GRAVITY:
        release = BombRelease(
            release_time=release.release_time,
            fuse_delay=release.fuse_delay,
            release_position=release.release_position,
            initial_velocity=release.initial_velocity,
            gravity=gravity,
        )
    cloud = release.smoke_cloud()
    return missile, uav, release, cloud, DEFAULT_TARGET


__all__ = [
    "BombRelease",
    "CylinderTarget",
    "CylindricalOcclusionEvaluator",
    "DEFAULT_TARGET",
    "FALSE_TARGET",
    "FY1_INITIAL",
    "GRAVITY",
    "M1_INITIAL",
    "MissileTrajectory",
    "SMOKE_LIFETIME",
    "SMOKE_RADIUS",
    "SMOKE_SINK_SPEED",
    "SmokeCloud",
    "UAVTrajectory",
    "WorstSightline",
    "closest_segment_fraction",
    "effective_intervals",
    "find_nonnegative_intervals",
    "interval_duration",
    "make_q1_scenario",
    "merge_intervals",
    "point_occlusion_margin",
    "point_to_segment_distance",
    "segment_sphere_intersection_interval",
    "trajectory_occlusion_margin",
]
