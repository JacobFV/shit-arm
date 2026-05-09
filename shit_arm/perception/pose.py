from __future__ import annotations

from dataclasses import dataclass

from math import sqrt

from shit_arm.types import Calibration, CameraFrame, Detection, MotionEstimate, Pose, TrackedObject


@dataclass
class TablePoseEstimator:
    table_z: float = 0.04

    def apply_to_detection(self, detection: Detection, frame: CameraFrame | None, calibration: Calibration) -> Detection:
        if detection.table_pose is not None:
            return detection
        pose = self.bbox_to_table_pose(detection.bbox_xywh, frame, calibration)
        return Detection(
            label=detection.label,
            confidence=detection.confidence,
            bbox_xywh=detection.bbox_xywh,
            table_pose=pose,
            target_bin=detection.target_bin,
            mask=detection.mask,
            metadata=detection.metadata,
        )

    def apply_to_track(self, track: TrackedObject, frame: CameraFrame | None, calibration: Calibration) -> None:
        if track.table_pose is None:
            track.table_pose = self.bbox_to_table_pose(track.smoothed_bbox_xywh, frame, calibration)
        self.update_motion(track, frame, calibration)

    def update_motion(self, track: TrackedObject, frame: CameraFrame | None, calibration: Calibration) -> None:
        if track.previous_pixel_centroid is None or track.pixel_centroid is None:
            return
        pixel_delta = (
            track.pixel_centroid[0] - track.previous_pixel_centroid[0],
            track.pixel_centroid[1] - track.previous_pixel_centroid[1],
        )
        frame_delta = None
        if track.previous_seen_frame_id is not None and track.last_seen_frame_id is not None:
            frame_delta = max(1, track.last_seen_frame_id - track.previous_seen_frame_id)
        table_delta = None
        table_speed = None
        if track.previous_table_pose is not None and track.table_pose is not None:
            table_delta = (
                track.table_pose.x - track.previous_table_pose.x,
                track.table_pose.y - track.previous_table_pose.y,
                track.table_pose.z - track.previous_table_pose.z,
            )
            if frame_delta:
                table_speed = vector_norm(table_delta) / frame_delta
        projected_table_delta = self.project_pixel_delta_to_table_delta(
            track.previous_pixel_centroid,
            track.pixel_centroid,
            frame,
            calibration,
        )
        table_delta_error = None
        consistent = True
        if table_delta is not None and projected_table_delta is not None:
            error_delta = tuple(actual - projected for actual, projected in zip(table_delta, projected_table_delta))
            table_delta_error = vector_norm(error_delta)
            consistent = table_delta_error <= 0.03
        pixel_speed = None
        if frame_delta:
            pixel_speed = vector_norm((pixel_delta[0], pixel_delta[1])) / frame_delta
        track.motion = MotionEstimate(
            pixel_delta=pixel_delta,
            table_delta=table_delta,
            projected_table_delta=projected_table_delta,
            table_delta_error=table_delta_error,
            pixel_speed_per_frame=pixel_speed,
            table_speed_per_frame=table_speed,
            frame_delta=frame_delta,
            consistent=consistent,
        )

    def project_pixel_delta_to_table_delta(
        self,
        previous_pixel: tuple[float, float],
        current_pixel: tuple[float, float],
        frame: CameraFrame | None,
        calibration: Calibration,
    ) -> tuple[float, float, float] | None:
        previous_pose = self.point_to_table_pose(previous_pixel, frame, calibration)
        current_pose = self.point_to_table_pose(current_pixel, frame, calibration)
        if previous_pose is None or current_pose is None:
            return None
        return current_pose.x - previous_pose.x, current_pose.y - previous_pose.y, current_pose.z - previous_pose.z

    def bbox_to_table_pose(
        self,
        bbox_xywh: tuple[float, float, float, float],
        frame: CameraFrame | None,
        calibration: Calibration,
    ) -> Pose | None:
        if frame is None or frame.width <= 0 or frame.height <= 0:
            return None
        x, y, w, h = bbox_xywh
        return self.point_to_table_pose((x + w / 2.0, y + h / 2.0), frame, calibration)

    def point_to_table_pose(
        self,
        pixel_xy: tuple[float, float],
        frame: CameraFrame | None,
        calibration: Calibration,
    ) -> Pose | None:
        if frame is None or frame.width <= 0 or frame.height <= 0:
            return None
        cx, cy = pixel_xy
        if calibration.image_to_table_homography is not None:
            projected = apply_homography(calibration.image_to_table_homography, cx, cy)
            if projected is None:
                return None
            return Pose(projected[0], projected[1], self.table_z)
        (xmin, xmax), (ymin, ymax), _z = calibration.workspace_xyz
        table_x = xmin + (cx / frame.width) * (xmax - xmin)
        table_y = ymin + (cy / frame.height) * (ymax - ymin)
        return Pose(table_x, table_y, self.table_z)

    def table_pose_to_pixel(
        self,
        pose: Pose | None,
        frame: CameraFrame | None,
        calibration: Calibration,
    ) -> tuple[float, float] | None:
        if pose is None or frame is None or frame.width <= 0 or frame.height <= 0:
            return None
        if calibration.image_to_table_homography is not None:
            inverse = invert_3x3(calibration.image_to_table_homography)
            if inverse is None:
                return None
            return apply_homography(inverse, pose.x, pose.y)
        (xmin, xmax), (ymin, ymax), _z = calibration.workspace_xyz
        if xmax == xmin or ymax == ymin:
            return None
        px = ((pose.x - xmin) / (xmax - xmin)) * frame.width
        py = ((pose.y - ymin) / (ymax - ymin)) * frame.height
        return px, py


def apply_homography(
    homography: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
    x: float,
    y: float,
) -> tuple[float, float] | None:
    h = homography
    denom = h[2][0] * x + h[2][1] * y + h[2][2]
    if abs(denom) < 1e-9:
        return None
    table_x = (h[0][0] * x + h[0][1] * y + h[0][2]) / denom
    table_y = (h[1][0] * x + h[1][1] * y + h[1][2]) / denom
    return table_x, table_y


def invert_3x3(
    matrix: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]] | None:
    a, b, c = matrix[0]
    d, e, f = matrix[1]
    g, h, i = matrix[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-12:
        return None
    inv_det = 1.0 / det
    return (
        ((e * i - f * h) * inv_det, (c * h - b * i) * inv_det, (b * f - c * e) * inv_det),
        ((f * g - d * i) * inv_det, (a * i - c * g) * inv_det, (c * d - a * f) * inv_det),
        ((d * h - e * g) * inv_det, (b * g - a * h) * inv_det, (a * e - b * d) * inv_det),
    )


def vector_norm(values: tuple[float, ...]) -> float:
    return sqrt(sum(value * value for value in values))
