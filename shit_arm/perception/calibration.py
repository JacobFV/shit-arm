from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from time import sleep, time
from typing import Any, Literal

import numpy as np

from shit_arm.control.safety import SafetyController
from shit_arm.types import Calibration, CameraFrame, CommandKind, Pose, RobotCommand, SafetyState


MarkerColor = Literal["red", "green", "blue", "dark", "bright"]
ChannelOrder = Literal["rgb", "bgr"]
HomographyMatrix = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


@dataclass(frozen=True)
class ProjectionCorrespondence:
    pixel_xy: tuple[float, float]
    table_xy: tuple[float, float]


@dataclass(frozen=True)
class ProjectionCalibrationResult:
    image_to_table_homography: HomographyMatrix
    table_to_image_homography: HomographyMatrix
    correspondences: tuple[ProjectionCorrespondence, ...]
    reprojection_rmse_m: float
    max_reprojection_error_m: float
    created_at: float = field(default_factory=time)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "image_to_table_homography": self.image_to_table_homography,
            "table_to_image_homography": self.table_to_image_homography,
            "reprojection_rmse_m": self.reprojection_rmse_m,
            "max_reprojection_error_m": self.max_reprojection_error_m,
            "correspondences": [
                {"pixel_xy": point.pixel_xy, "table_xy": point.table_xy}
                for point in self.correspondences
            ],
        }


@dataclass
class ColorMarkerLocalizer:
    """Find a colored tool-tip marker centroid in camera pixel coordinates."""

    color: MarkerColor = "red"
    channel_order: ChannelOrder = "rgb"
    min_area_px: int = 20
    dominance_margin: int = 45
    brightness_threshold: int = 80

    def locate(self, frame: CameraFrame | None) -> tuple[float, float] | None:
        if frame is None or frame.payload is None:
            return None
        try:
            image = np.asarray(frame.payload)
        except Exception:
            return None
        if image.ndim < 3 or image.shape[2] < 3:
            return None
        channels = image[..., :3].astype(np.int16)
        if self.channel_order == "bgr":
            b, g, r = channels[..., 0], channels[..., 1], channels[..., 2]
        else:
            r, g, b = channels[..., 0], channels[..., 1], channels[..., 2]

        mask = self._mask(r, g, b)
        ys, xs = np.nonzero(mask)
        if len(xs) < self.min_area_px:
            return None
        return float(xs.mean()), float(ys.mean())

    def _mask(self, r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
        if self.color == "red":
            return (r > g + self.dominance_margin) & (r > b + self.dominance_margin) & (r > self.brightness_threshold)
        if self.color == "green":
            return (g > r + self.dominance_margin) & (g > b + self.dominance_margin) & (g > self.brightness_threshold)
        if self.color == "blue":
            return (b > r + self.dominance_margin) & (b > g + self.dominance_margin) & (b > self.brightness_threshold)
        intensity = (r + g + b) / 3.0
        if self.color == "bright":
            return intensity > self.brightness_threshold
        return intensity < self.brightness_threshold


def solve_image_to_table_homography(correspondences: list[ProjectionCorrespondence]) -> ProjectionCalibrationResult:
    if len(correspondences) < 4:
        raise ValueError("at least 4 image/table correspondences are required to solve a homography")
    image_points = np.asarray([point.pixel_xy for point in correspondences], dtype=np.float64)
    table_points = np.asarray([point.table_xy for point in correspondences], dtype=np.float64)
    if _rank_2d(image_points) < 2 or _rank_2d(table_points) < 2:
        raise ValueError("homography correspondences must not be collinear")

    image_to_table = _homography_from_points(image_points, table_points)
    table_to_image = _homography_from_points(table_points, image_points)
    projected = _apply_homography_array(image_to_table, image_points)
    errors = np.linalg.norm(projected - table_points, axis=1)
    return ProjectionCalibrationResult(
        image_to_table_homography=_matrix_tuple(image_to_table),
        table_to_image_homography=_matrix_tuple(table_to_image),
        correspondences=tuple(correspondences),
        reprojection_rmse_m=float(np.sqrt(np.mean(errors * errors))),
        max_reprojection_error_m=float(np.max(errors)),
    )


def save_projection_calibration(result: ProjectionCalibrationResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(result.to_json_dict(), indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def load_projection_homography(path: Path) -> HomographyMatrix:
    payload = json.loads(path.read_text(encoding="utf-8"))
    matrix = payload.get("image_to_table_homography", payload) if isinstance(payload, dict) else payload
    rows = tuple(tuple(float(value) for value in row) for row in matrix)
    if len(rows) != 3 or any(len(row) != 3 for row in rows):
        raise ValueError(f"{path} does not contain a 3x3 image_to_table_homography")
    return rows  # type: ignore[return-value]


def run_arm_motion_projection_calibration(
    *,
    robot: Any,
    camera: Any,
    calibration: Calibration,
    output_path: Path,
    localizer: ColorMarkerLocalizer,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    z: float,
    grid: tuple[int, int] = (3, 3),
    settle_s: float = 0.7,
    samples_per_point: int = 5,
    speed_scale: float = 0.18,
    safety: SafetyController | None = None,
) -> ProjectionCalibrationResult:
    points = _grid_points(x_range, y_range, grid)
    safety = safety or SafetyController(max_speed_scale=speed_scale)
    correspondences: list[ProjectionCorrespondence] = []

    for x, y in points:
        target = Pose(x=x, y=y, z=z)
        command = safety.filter(
            RobotCommand.pose(target, speed_scale=speed_scale, reason="projection calibration"),
            _SafetyContext(calibration),
        )
        if command.kind == CommandKind.STOP:
            raise ValueError(f"calibration point {target} rejected by safety: {command.reason}")
        robot.apply(command)
        if settle_s > 0:
            sleep(settle_s)
        pixel = _sample_marker(camera, localizer, samples_per_point)
        if pixel is None:
            raise RuntimeError(f"could not localize calibration marker at table point ({x:.4f}, {y:.4f}, {z:.4f})")
        correspondences.append(ProjectionCorrespondence(pixel_xy=pixel, table_xy=(x, y)))

    result = solve_image_to_table_homography(correspondences)
    save_projection_calibration(result, output_path)
    calibration.image_to_table_homography = result.image_to_table_homography
    return result


def _sample_marker(camera: Any, localizer: ColorMarkerLocalizer, samples: int) -> tuple[float, float] | None:
    pixels: list[tuple[float, float]] = []
    for _ in range(max(1, samples)):
        follower = getattr(camera, "follower", None)
        if follower is not None and hasattr(follower, "read_state"):
            follower.read_state()
        frame = camera.read()
        pixel = localizer.locate(frame)
        if pixel is not None:
            pixels.append(pixel)
        sleep(0.03)
    if not pixels:
        return None
    return float(np.mean([point[0] for point in pixels])), float(np.mean([point[1] for point in pixels]))


def _grid_points(x_range: tuple[float, float], y_range: tuple[float, float], grid: tuple[int, int]) -> list[tuple[float, float]]:
    x_count, y_count = grid
    if x_count < 2 or y_count < 2:
        raise ValueError("projection calibration grid must be at least 2x2")
    xs = np.linspace(x_range[0], x_range[1], x_count)
    ys = np.linspace(y_range[0], y_range[1], y_count)
    return [(float(x), float(y)) for y in ys for x in xs]


def _homography_from_points(source: np.ndarray, destination: np.ndarray) -> np.ndarray:
    source_norm, source_t = _normalize_points(source)
    dest_norm, dest_t = _normalize_points(destination)
    rows = []
    for (x, y), (u, v) in zip(source_norm, dest_norm):
        rows.append([-x, -y, -1.0, 0.0, 0.0, 0.0, u * x, u * y, u])
        rows.append([0.0, 0.0, 0.0, -x, -y, -1.0, v * x, v * y, v])
    _u, _s, vt = np.linalg.svd(np.asarray(rows, dtype=np.float64))
    h = vt[-1].reshape(3, 3)
    denormalized = np.linalg.inv(dest_t) @ h @ source_t
    if abs(denormalized[2, 2]) > 1e-12:
        denormalized = denormalized / denormalized[2, 2]
    return denormalized


def _normalize_points(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    centroid = points.mean(axis=0)
    shifted = points - centroid
    mean_distance = np.mean(np.linalg.norm(shifted, axis=1))
    scale = np.sqrt(2.0) / mean_distance if mean_distance > 1e-12 else 1.0
    transform = np.asarray(
        (
            (scale, 0.0, -scale * centroid[0]),
            (0.0, scale, -scale * centroid[1]),
            (0.0, 0.0, 1.0),
        ),
        dtype=np.float64,
    )
    homogeneous = np.column_stack((points, np.ones(len(points))))
    normalized = (transform @ homogeneous.T).T
    return normalized[:, :2], transform


def _apply_homography_array(homography: np.ndarray, points: np.ndarray) -> np.ndarray:
    homogeneous = np.column_stack((points, np.ones(len(points))))
    projected = (homography @ homogeneous.T).T
    projected = projected / projected[:, 2:3]
    return projected[:, :2]


def _rank_2d(points: np.ndarray) -> int:
    centered = points - points.mean(axis=0)
    return int(np.linalg.matrix_rank(centered, tol=1e-9))


def _matrix_tuple(matrix: np.ndarray) -> HomographyMatrix:
    return tuple(tuple(float(value) for value in row) for row in matrix)  # type: ignore[return-value]


@dataclass
class _SafetyContext:
    calibration: Calibration
    safety: SafetyState = field(default_factory=SafetyState)
