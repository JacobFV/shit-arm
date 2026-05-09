from __future__ import annotations

from shit_arm.modes.base import Mode
from shit_arm.modes.basic import drop_sequence, pose_above
from shit_arm.types import Detection, Pose, RobotCommand, SystemContext, TrackedObject


class VisionMonitorMode(Mode):
    name = "vision-monitor"

    def tick(self, context: SystemContext) -> RobotCommand:
        context.recorder.record_event(
            "vision_monitor",
            {
                "status": context.perception_state.status,
                "detections": [
                    {"label": d.label, "confidence": d.confidence, "target_bin": d.target_bin}
                    for d in context.perception_state.detections
                ],
                "tracks": [_track_payload(track) for track in context.perception_state.tracks],
                "selected_track_id": context.perception_state.selected_track_id,
            },
        )
        return RobotCommand.hold("vision monitor")


class VisionPickMode(Mode):
    name = "vision-pick"

    def tick(self, context: SystemContext) -> RobotCommand:
        target = _choose_target(context)
        if not target or not target.table_pose:
            return RobotCommand.hold("no pickable detection")
        pick = target.table_pose
        return RobotCommand.composite(
            (
                RobotCommand.pose(pose_above(pick), speed_scale=0.25, reason="approach object"),
                RobotCommand.pose(pick, speed_scale=0.15, reason="descend to object"),
                RobotCommand.gripper_to(0.0, reason="close gripper"),
                RobotCommand.pose(pose_above(pick), speed_scale=0.25, reason="lift object"),
            ),
            reason=f"vision pick {target.label}",
        )


class VisionClosedLoopMode(Mode):
    name = "vision-closed-loop"

    def tick(self, context: SystemContext) -> RobotCommand:
        detection = _choose_target(context)
        min_confidence = float(context.options.get("min_confidence", 0.45))
        if not detection or detection.confidence < min_confidence or not detection.table_pose:
            return RobotCommand.hold("target lost or below confidence")
        return RobotCommand.pose(detection.table_pose, speed_scale=0.15, reason="closed-loop visual servo target")


class HumanConfirmSortMode(Mode):
    name = "human-confirm-sort"

    def tick(self, context: SystemContext) -> RobotCommand:
        detection = _choose_target(context)
        confirmed = bool(context.options.get("confirmed", False))
        if not detection:
            return RobotCommand.hold("no sort candidate")
        context.recorder.record_event(
            "sort_proposal",
            {
                "track_id": detection.track_id if isinstance(detection, TrackedObject) else None,
                "label": detection.label,
                "target_bin": detection.target_bin,
                "confidence": detection.confidence,
            },
        )
        if not confirmed:
            return RobotCommand.hold("waiting for human confirmation")
        return _sort_command(context, detection)


class SortMode(Mode):
    name = "sort"

    def tick(self, context: SystemContext) -> RobotCommand:
        detection = _choose_target(context)
        min_confidence = float(context.options.get("min_confidence", 0.55))
        if not detection or detection.confidence < min_confidence:
            return RobotCommand.hold("no confident sort candidate")
        return _sort_command(context, detection)


class DatasetMode(Mode):
    name = "dataset"

    def tick(self, context: SystemContext) -> RobotCommand:
        label = context.options.get("label", "unknown")
        context.recorder.record_event(
            "dataset_frame",
            {
                "frame_id": context.camera_frame.frame_id if context.camera_frame else None,
                "label": label,
                "detections": len(context.perception_state.detections),
                "tracks": [_track_payload(track) for track in context.perception_state.tracks],
                "selected_track_id": context.perception_state.selected_track_id,
            },
        )
        return RobotCommand.hold("dataset capture")


def _choose_target(context: SystemContext) -> Detection | TrackedObject | None:
    target_track_id = context.options.get("target_track_id")
    if target_track_id is not None:
        for track in context.perception_state.tracks:
            if track.track_id == int(target_track_id):
                return track
    target_label = context.options.get("target_label")
    if target_label:
        tracks = [track for track in context.perception_state.tracks if track.label == target_label]
        if tracks:
            return max(tracks, key=lambda track: track.score)
    if context.perception_state.selected is not None:
        return context.perception_state.selected
    if context.perception_state.tracks:
        return max(context.perception_state.tracks, key=lambda track: track.score)
    if not context.perception_state.detections:
        return None
    return max(context.perception_state.detections, key=lambda detection: detection.confidence)


def _sort_command(context: SystemContext, detection: Detection | TrackedObject) -> RobotCommand:
    if not detection.table_pose:
        return RobotCommand.hold("sort candidate has no table pose")
    target_bin = detection.target_bin or _bin_for_label(detection.label)
    bin_pose = context.calibration.bins.get(target_bin) or context.calibration.bins["unknown"]
    pick = detection.table_pose
    return RobotCommand.composite(
        (
            RobotCommand.pose(pose_above(pick), speed_scale=0.25, reason="approach object"),
            RobotCommand.pose(pick, speed_scale=0.15, reason="descend to object"),
            RobotCommand.gripper_to(0.0, reason="close gripper"),
            RobotCommand.pose(pose_above(pick), speed_scale=0.25, reason="lift object"),
            drop_sequence(bin_pose),
        ),
        reason=f"sort {detection.label} to {target_bin}",
    )


def _bin_for_label(label: str) -> str:
    label = label.lower()
    if label in {"can", "bottle", "plastic", "paper", "cardboard", "metal", "glass"}:
        return "recycling"
    if label in {"food", "organic", "compost"}:
        return "compost"
    if label in {"landfill", "trash"}:
        return "landfill"
    return "unknown"


def _track_payload(track: TrackedObject) -> dict[str, object]:
    return {
        "track_id": track.track_id,
        "label": track.label,
        "confidence": track.confidence,
        "bbox_xywh": track.smoothed_bbox_xywh,
        "target_bin": track.target_bin,
        "status": track.status.value,
        "age_frames": track.age_frames,
        "missed_frames": track.missed_frames,
        "stable_frames": track.stable_frames,
        "score": track.score,
        "table_pose": track.table_pose,
        "pixel_centroid": track.pixel_centroid,
        "motion": track.motion,
    }
