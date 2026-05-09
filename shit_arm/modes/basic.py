from __future__ import annotations

from shit_arm.modes.base import Mode
from shit_arm.types import CommandKind, Pose, RobotCommand, SystemContext


class EmergencyStopMode(Mode):
    name = "emergency-stop"

    def enter(self, context: SystemContext) -> None:
        context.safety.estop = True
        super().enter(context)

    def tick(self, context: SystemContext) -> RobotCommand:
        return RobotCommand.stop("emergency stop mode")


class DiagnosticsMode(Mode):
    name = "diagnostics"

    def tick(self, context: SystemContext) -> RobotCommand:
        context.recorder.record_event(
            "diagnostics",
            {
                "robot_connected": context.robot_state.connected,
                "guide_connected": context.guide_state.connected,
                "camera_frame": context.camera_frame.frame_id if context.camera_frame else None,
                "detections": len(context.perception_state.detections),
                "faults": list(context.safety.faults),
            },
        )
        return RobotCommand.hold("diagnostics")


class CalibrationMode(Mode):
    name = "calibration"

    def tick(self, context: SystemContext) -> RobotCommand:
        context.recorder.record_event(
            "calibration_snapshot",
            {
                "robot_joints": context.robot_state.joints,
                "guide_joints": context.guide_state.joints,
                "workspace_xyz": context.calibration.workspace_xyz,
                "bins": sorted(context.calibration.bins),
            },
        )
        return RobotCommand.hold("calibration")


class ManualJogMode(Mode):
    name = "manual-jog"

    def tick(self, context: SystemContext) -> RobotCommand:
        jog = context.options.get("jog")
        if not jog:
            return RobotCommand.hold("manual jog waiting for command")
        kind = jog.get("kind")
        if kind == "joint":
            joints = list(context.robot_state.joints or context.calibration.home_joints)
            index = int(jog["index"])
            joints[index] += float(jog.get("delta", 0.0))
            return RobotCommand.joints(tuple(joints), speed_scale=float(jog.get("speed_scale", 0.25)), reason="manual jog")
        if kind == "gripper":
            return RobotCommand.gripper_to(float(jog.get("position", context.robot_state.gripper)), reason="manual jog")
        return RobotCommand.hold(f"unsupported jog kind {kind!r}")


class HomingMode(Mode):
    name = "homing"

    def tick(self, context: SystemContext) -> RobotCommand:
        return RobotCommand.joints(context.calibration.home_joints, speed_scale=0.25, reason="homing")


class RecoveryMode(Mode):
    name = "recovery"

    def tick(self, context: SystemContext) -> RobotCommand:
        action = context.options.get("recovery_action", "home")
        if action == "open-gripper":
            return RobotCommand.gripper_to(1.0, reason="recovery open gripper")
        if action == "stop":
            return RobotCommand.stop("recovery stop")
        return RobotCommand.joints(context.calibration.home_joints, speed_scale=0.2, reason="recovery home")


class DryRunMode(Mode):
    name = "dry-run"

    def tick(self, context: SystemContext) -> RobotCommand:
        command = context.options.get("dry_run_command")
        if isinstance(command, RobotCommand):
            context.recorder.record_event("dry_run_command", {"kind": command.kind.value})
            return command
        return RobotCommand.hold("dry run")


def pose_above(pose: Pose, dz: float = 0.08) -> Pose:
    return Pose(pose.x, pose.y, pose.z + dz, pose.roll, pose.pitch, pose.yaw)


def drop_sequence(bin_pose: Pose) -> RobotCommand:
    return RobotCommand.composite(
        (
            RobotCommand.pose(pose_above(bin_pose), speed_scale=0.35, reason="move above bin"),
            RobotCommand.pose(bin_pose, speed_scale=0.2, reason="lower to bin"),
            RobotCommand.gripper_to(1.0, reason="release object"),
        ),
        reason="drop sequence",
    )

