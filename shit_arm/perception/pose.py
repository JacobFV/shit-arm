from __future__ import annotations

from dataclasses import dataclass

from shit_arm.types import Calibration, CameraFrame, Detection, Pose, TrackedObject


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

    def bbox_to_table_pose(
        self,
        bbox_xywh: tuple[float, float, float, float],
        frame: CameraFrame | None,
        calibration: Calibration,
    ) -> Pose | None:
        if frame is None or frame.width <= 0 or frame.height <= 0:
            return None
        x, y, w, h = bbox_xywh
        cx = x + w / 2.0
        cy = y + h / 2.0
        if calibration.image_to_table_homography is not None:
            projected = apply_homography(calibration.image_to_table_homography, cx, cy)
            if projected is None:
                return None
            return Pose(projected[0], projected[1], self.table_z)
        (xmin, xmax), (ymin, ymax), _z = calibration.workspace_xyz
        table_x = xmin + (cx / frame.width) * (xmax - xmin)
        table_y = ymin + (cy / frame.height) * (ymax - ymin)
        return Pose(table_x, table_y, self.table_z)


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
