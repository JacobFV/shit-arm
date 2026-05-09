from __future__ import annotations

from dataclasses import dataclass, field
from time import time

from shit_arm.types import ArmState, CameraFrame, CommandKind, Pose, RobotCommand


@dataclass
class MockGuideArm:
    joints: tuple[float, ...] = (0.0, -0.6, 1.0, 0.0, 0.6, 0.0)
    gripper: float = 1.0
    connected: bool = True

    def read_state(self) -> ArmState:
        return ArmState(joints=self.joints, pose=Pose(0.0, 0.35, 0.18), gripper=self.gripper, connected=self.connected)


@dataclass
class MockRobotArm:
    joints: tuple[float, ...] = (0.0, -0.8, 1.2, 0.0, 0.8, 0.0)
    gripper: float = 1.0
    connected: bool = True
    applied: list[RobotCommand] = field(default_factory=list)

    def read_state(self) -> ArmState:
        return ArmState(joints=self.joints, pose=Pose(0.0, 0.35, 0.18), gripper=self.gripper, connected=self.connected)

    def apply(self, command: RobotCommand) -> None:
        self.applied.append(command)
        if command.kind == CommandKind.JOINT_TARGET and command.joint_targets is not None:
            self.joints = command.joint_targets
        elif command.kind == CommandKind.GRIPPER and command.gripper is not None:
            self.gripper = command.gripper
        elif command.kind == CommandKind.HOME:
            self.joints = (0.0, -0.8, 1.2, 0.0, 0.8, 0.0)
        elif command.kind == CommandKind.COMPOSITE:
            for child in command.children:
                self.apply(child)


@dataclass
class MockCamera:
    width: int = 640
    height: int = 480
    frame_id: int = 0
    connected: bool = True

    def read(self) -> CameraFrame | None:
        if not self.connected:
            return None
        self.frame_id += 1
        return CameraFrame(frame_id=self.frame_id, timestamp=time(), width=self.width, height=self.height, payload=None)

