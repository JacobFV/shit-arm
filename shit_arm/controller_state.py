from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from time import time
from typing import Any

from shit_arm.perception.pose import TablePoseEstimator
from shit_arm.types import MotionEstimate, Pose, SystemContext, TrackedObject


def build_controller_state(context: SystemContext, frame_image_path: Path | None = None) -> dict[str, Any]:
    pose_estimator = TablePoseEstimator()
    gripper_world = context.robot_state.pose
    gripper_pixel = pose_estimator.table_pose_to_pixel(gripper_world, context.camera_frame, context.calibration)
    selected = context.perception_state.selected
    return {
        "timestamp": time(),
        "mode": context.mode_name,
        "camera": {
            "frame_id": context.camera_frame.frame_id if context.camera_frame else None,
            "width": context.camera_frame.width if context.camera_frame else 0,
            "height": context.camera_frame.height if context.camera_frame else 0,
            "frame_image_path": str(frame_image_path.resolve()) if frame_image_path else None,
        },
        "robot": {
            "connected": context.robot_state.connected,
            "joints": context.robot_state.joints,
            "gripper": context.robot_state.gripper,
        },
        "gripper": {
            "pixel": _point_dict(gripper_pixel),
            "world": _pose_dict(gripper_world),
        },
        "perception": {
            "status": context.perception_state.status,
            "selected_track_id": context.perception_state.selected_track_id,
            "selected_label": getattr(selected, "label", None),
            "tracks": [_track_dict(track) for track in context.perception_state.tracks],
        },
        "safety": {
            "ok": context.safety.ok,
            "estop": context.safety.estop,
            "faults": context.safety.faults,
            "warnings": context.safety.warnings,
        },
    }


def write_controller_state(context: SystemContext, path: Path, frame_image_path: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if frame_image_path is None:
        frame_image_path = path.with_name("latest-frame.svg")
    frame_image_path = write_controller_frame(context, frame_image_path)
    _atomic_write_text(path, json.dumps(build_controller_state(context, frame_image_path), indent=2, default=str) + "\n")


def write_controller_frame(context: SystemContext, path: Path) -> Path:
    frame = context.camera_frame
    if frame is None:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = frame.payload
    if payload is None:
        output_path = path.with_suffix(".svg")
        _write_status_svg(output_path, frame.width, frame.height, frame.frame_id)
        return output_path
    output_path = path.with_suffix(".jpg")
    if _write_with_pillow(payload, output_path):
        return output_path
    if _write_with_cv2(payload, output_path):
        return output_path
    output_path = path.with_suffix(".svg")
    _write_status_svg(output_path, frame.width, frame.height, frame.frame_id)
    return output_path


def _track_dict(track: TrackedObject) -> dict[str, Any]:
    return {
        "track_id": track.track_id,
        "label": track.label,
        "confidence": track.confidence,
        "status": track.status.value,
        "score": track.score,
        "target_bin": track.target_bin,
        "pixel": _point_dict(track.pixel_centroid),
        "previous_pixel": _point_dict(track.previous_pixel_centroid),
        "world": _pose_dict(track.table_pose),
        "previous_world": _pose_dict(track.previous_table_pose),
        "bbox_xywh": track.smoothed_bbox_xywh,
        "age_frames": track.age_frames,
        "missed_frames": track.missed_frames,
        "stable_frames": track.stable_frames,
        "motion": _motion_dict(track.motion),
    }


def _motion_dict(motion: MotionEstimate | None) -> dict[str, Any] | None:
    if motion is None:
        return None
    return asdict(motion)


def _pose_dict(pose: Pose | None) -> dict[str, float] | None:
    if pose is None:
        return None
    return {
        "x": pose.x,
        "y": pose.y,
        "z": pose.z,
        "roll": pose.roll,
        "pitch": pose.pitch,
        "yaw": pose.yaw,
    }


def _point_dict(point: tuple[float, float] | None) -> dict[str, float] | None:
    if point is None:
        return None
    return {"x": point[0], "y": point[1]}


def _write_with_pillow(payload: Any, path: Path) -> bool:
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return False
    try:
        array = np.asarray(payload)
        image = Image.fromarray(array.astype("uint8"))
        image.save(path, quality=85)
        return True
    except Exception:
        return False


def _write_with_cv2(payload: Any, path: Path) -> bool:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return False
    try:
        array = np.asarray(payload)
        cv2.imwrite(str(path), array)
        return True
    except Exception:
        return False


def _write_status_svg(path: Path, width: int, height: int, frame_id: int) -> None:
    width = width or 640
    height = height or 480
    _atomic_write_text(
        path,
        f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#101820"/>
  <path d="M0 {height / 2}H{width}M{width / 2} 0V{height}" stroke="#263241" stroke-width="2"/>
  <text x="24" y="42" fill="#d7dee8" font-family="system-ui" font-size="24">controller frame {frame_id}</text>
  <text x="24" y="76" fill="#8b96a6" font-family="system-ui" font-size="16">no camera payload exported</text>
</svg>
""",
    )


def _atomic_write_text(path: Path, contents: str) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(contents, encoding="utf-8")
    tmp_path.replace(path)
