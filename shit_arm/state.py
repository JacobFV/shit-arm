from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from time import time
from typing import Any

from shit_arm.perception.pose import TablePoseEstimator
from shit_arm.robot_model import load_robot_model
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
        "guide": {
            "connected": context.guide_state.connected,
            "joints": context.guide_state.joints,
            "gripper": context.guide_state.gripper,
            "world": _pose_dict(context.guide_state.pose),
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
        "calibration": {
            "joint_limits": context.calibration.joint_limits,
            "home_joints": context.calibration.home_joints,
            "workspace_xyz": context.calibration.workspace_xyz,
        },
        "robot_model": load_robot_model(),
    }


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
