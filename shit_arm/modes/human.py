from __future__ import annotations

from shit_arm.modes.base import Mode
from shit_arm.types import RobotCommand, SystemContext


class MirrorMode(Mode):
    name = "mirror"

    def tick(self, context: SystemContext) -> RobotCommand:
        if not context.guide_state.connected:
            return RobotCommand.stop("guide arm disconnected")
        speed_scale = float(context.options.get("speed_scale", 0.5))
        mapping = context.options.get("mirror_mapping", "joint")
        if mapping == "cartesian" and context.guide_state.pose is not None:
            return RobotCommand.pose(context.guide_state.pose, speed_scale=speed_scale, reason="cartesian mirror")
        if context.guide_state.joints:
            return RobotCommand.joints(context.guide_state.joints, speed_scale=speed_scale, reason="joint mirror")
        return RobotCommand.hold("guide arm has no state")


class RecordMode(MirrorMode):
    name = "record"

    def enter(self, context: SystemContext) -> None:
        context.recorder.start_run(context.options.get("run_name"))
        super().enter(context)

    def exit(self, context: SystemContext) -> None:
        super().exit(context)
        context.recorder.stop_run()


class TeachMode(RecordMode):
    name = "teach"

    def tick(self, context: SystemContext) -> RobotCommand:
        label = context.options.get("label")
        target_bin = context.options.get("target_bin")
        if label or target_bin:
            context.recorder.record_event("teach_label", {"label": label, "target_bin": target_bin})
        return super().tick(context)


class AssistedTeleopMode(MirrorMode):
    name = "assisted-teleop"

    def tick(self, context: SystemContext) -> RobotCommand:
        selected = context.perception_state.selected
        assistance = int(context.options.get("assistance_level", 1))
        if assistance >= 3 and selected and selected.table_pose:
            return RobotCommand.pose(selected.table_pose, speed_scale=0.2, reason="vision assisted alignment")
        command = super().tick(context)
        if assistance >= 1:
            context.recorder.record_event(
                "assistance_overlay",
                {"detections": [d.label for d in context.perception_state.detections]},
            )
        return command

