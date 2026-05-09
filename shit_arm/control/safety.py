from __future__ import annotations

from dataclasses import dataclass

from shit_arm.types import CommandKind, RobotCommand, SystemContext


@dataclass
class SafetyController:
    """Last gate before robot hardware."""

    max_speed_scale: float = 1.0

    def filter(self, command: RobotCommand, context: SystemContext) -> RobotCommand:
        if context.safety.estop:
            return RobotCommand.stop("emergency stop active")
        if context.safety.faults:
            return RobotCommand.stop("; ".join(context.safety.faults))
        if command.kind == CommandKind.JOINT_TARGET:
            return self._filter_joints(command, context)
        if command.kind == CommandKind.CARTESIAN_TARGET:
            return self._filter_pose(command, context)
        if command.kind == CommandKind.COMPOSITE:
            return RobotCommand.composite(
                tuple(self.filter(child, context) for child in command.children),
                reason=command.reason,
            )
        return command

    def _filter_joints(self, command: RobotCommand, context: SystemContext) -> RobotCommand:
        if command.joint_targets is None:
            return RobotCommand.stop("joint command missing targets")
        if len(command.joint_targets) != len(context.calibration.joint_limits):
            return RobotCommand.stop("joint command has wrong dimension")
        for index, (value, (low, high)) in enumerate(zip(command.joint_targets, context.calibration.joint_limits)):
            if value < low or value > high:
                return RobotCommand.stop(f"joint {index} target {value:.3f} outside [{low:.3f}, {high:.3f}]")
        return RobotCommand.joints(
            command.joint_targets,
            speed_scale=min(command.speed_scale, self.max_speed_scale),
            reason=command.reason,
        )

    def _filter_pose(self, command: RobotCommand, context: SystemContext) -> RobotCommand:
        if command.pose_target is None:
            return RobotCommand.stop("cartesian command missing pose")
        pose = command.pose_target
        for axis, value, (low, high) in zip("xyz", (pose.x, pose.y, pose.z), context.calibration.workspace_xyz):
            if value < low or value > high:
                return RobotCommand.stop(f"{axis} target {value:.3f} outside workspace [{low:.3f}, {high:.3f}]")
        return RobotCommand.pose(
            pose,
            speed_scale=min(command.speed_scale, self.max_speed_scale),
            reason=command.reason,
        )

