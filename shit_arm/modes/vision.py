from __future__ import annotations

from shit_arm.modes.base import Mode
from shit_arm.modes.basic import drop_sequence, pose_above
from shit_arm.types import Detection, Pose, RobotCommand, SystemContext


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
            },
        )
        return RobotCommand.hold("vision monitor")


class VisionPickMode(Mode):
    name = "vision-pick"

    def tick(self, context: SystemContext) -> RobotCommand:
        detection = _choose_detection(context)
        if not detection or not detection.table_pose:
            return RobotCommand.hold("no pickable detection")
        pick = detection.table_pose
        return RobotCommand.composite(
            (
                RobotCommand.pose(pose_above(pick), speed_scale=0.25, reason="approach object"),
                RobotCommand.pose(pick, speed_scale=0.15, reason="descend to object"),
                RobotCommand.gripper_to(0.0, reason="close gripper"),
                RobotCommand.pose(pose_above(pick), speed_scale=0.25, reason="lift object"),
            ),
            reason=f"vision pick {detection.label}",
        )


class VisionClosedLoopMode(Mode):
    name = "vision-closed-loop"

    def tick(self, context: SystemContext) -> RobotCommand:
        detection = _choose_detection(context)
        min_confidence = float(context.options.get("min_confidence", 0.45))
        if not detection or detection.confidence < min_confidence or not detection.table_pose:
            return RobotCommand.hold("target lost or below confidence")
        return RobotCommand.pose(detection.table_pose, speed_scale=0.15, reason="closed-loop visual servo target")


class HumanConfirmSortMode(Mode):
    name = "human-confirm-sort"

    def tick(self, context: SystemContext) -> RobotCommand:
        detection = _choose_detection(context)
        confirmed = bool(context.options.get("confirmed", False))
        if not detection:
            return RobotCommand.hold("no sort candidate")
        context.recorder.record_event(
            "sort_proposal",
            {"label": detection.label, "target_bin": detection.target_bin, "confidence": detection.confidence},
        )
        if not confirmed:
            return RobotCommand.hold("waiting for human confirmation")
        return _sort_command(context, detection)


class SortMode(Mode):
    name = "sort"

    def tick(self, context: SystemContext) -> RobotCommand:
        detection = _choose_detection(context)
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
            },
        )
        return RobotCommand.hold("dataset capture")


def _choose_detection(context: SystemContext) -> Detection | None:
    if context.perception_state.selected:
        return context.perception_state.selected
    if not context.perception_state.detections:
        return None
    return max(context.perception_state.detections, key=lambda detection: detection.confidence)


def _sort_command(context: SystemContext, detection: Detection) -> RobotCommand:
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

