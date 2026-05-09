from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Literal


ModeName = Literal[
    "safe-idle",
    "emergency-stop",
    "diagnostics",
    "calibration",
    "manual-jog",
    "homing",
    "mirror",
    "record",
    "replay",
    "teach",
    "assisted-teleop",
    "vision-monitor",
    "vision-pick",
    "vision-closed-loop",
    "human-confirm-sort",
    "sort",
    "dataset",
    "dry-run",
    "recovery",
]


class CommandKind(str, Enum):
    HOLD = "hold"
    STOP = "stop"
    HOME = "home"
    JOINT_TARGET = "joint_target"
    CARTESIAN_TARGET = "cartesian_target"
    VELOCITY = "velocity"
    GRIPPER = "gripper"
    COMPOSITE = "composite"


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    z: float
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


@dataclass(frozen=True)
class RobotCommand:
    kind: CommandKind
    joint_targets: tuple[float, ...] | None = None
    pose_target: Pose | None = None
    velocities: tuple[float, ...] | None = None
    gripper: float | None = None
    speed_scale: float = 1.0
    reason: str = ""
    children: tuple["RobotCommand", ...] = ()

    @staticmethod
    def hold(reason: str = "") -> "RobotCommand":
        return RobotCommand(CommandKind.HOLD, reason=reason)

    @staticmethod
    def stop(reason: str = "") -> "RobotCommand":
        return RobotCommand(CommandKind.STOP, reason=reason)

    @staticmethod
    def home(reason: str = "") -> "RobotCommand":
        return RobotCommand(CommandKind.HOME, reason=reason)

    @staticmethod
    def joints(targets: tuple[float, ...], speed_scale: float = 1.0, reason: str = "") -> "RobotCommand":
        return RobotCommand(CommandKind.JOINT_TARGET, joint_targets=targets, speed_scale=speed_scale, reason=reason)

    @staticmethod
    def pose(target: Pose, speed_scale: float = 1.0, reason: str = "") -> "RobotCommand":
        return RobotCommand(CommandKind.CARTESIAN_TARGET, pose_target=target, speed_scale=speed_scale, reason=reason)

    @staticmethod
    def gripper_to(position: float, reason: str = "") -> "RobotCommand":
        return RobotCommand(CommandKind.GRIPPER, gripper=position, reason=reason)

    @staticmethod
    def composite(children: tuple["RobotCommand", ...], reason: str = "") -> "RobotCommand":
        return RobotCommand(CommandKind.COMPOSITE, children=children, reason=reason)


@dataclass
class ArmState:
    joints: tuple[float, ...] = ()
    pose: Pose | None = None
    gripper: float = 0.0
    connected: bool = True
    timestamp: float = field(default_factory=time)


@dataclass
class CameraFrame:
    frame_id: int
    timestamp: float = field(default_factory=time)
    width: int = 0
    height: int = 0
    payload: Any = None


@dataclass
class Detection:
    label: str
    confidence: float
    bbox_xywh: tuple[float, float, float, float]
    table_pose: Pose | None = None
    target_bin: str | None = None


@dataclass
class PerceptionState:
    detections: list[Detection] = field(default_factory=list)
    selected: Detection | None = None
    status: str = "idle"


@dataclass
class SafetyState:
    estop: bool = False
    faults: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.estop and not self.faults


@dataclass
class Calibration:
    joint_limits: tuple[tuple[float, float], ...] = tuple((-3.14, 3.14) for _ in range(6))
    home_joints: tuple[float, ...] = (0.0, -0.8, 1.2, 0.0, 0.8, 0.0)
    workspace_xyz: tuple[tuple[float, float], tuple[float, float], tuple[float, float]] = (
        (-0.35, 0.35),
        (0.05, 0.65),
        (0.0, 0.45),
    )
    bins: dict[str, Pose] = field(
        default_factory=lambda: {
            "recycling": Pose(-0.25, 0.55, 0.15),
            "compost": Pose(0.0, 0.58, 0.15),
            "landfill": Pose(0.25, 0.55, 0.15),
            "unknown": Pose(0.0, 0.45, 0.15),
        }
    )


@dataclass
class SystemContext:
    mode_name: str
    robot: Any
    guide: Any
    camera: Any
    recorder: Any
    perception: Any
    calibration: Calibration = field(default_factory=Calibration)
    robot_state: ArmState = field(default_factory=ArmState)
    guide_state: ArmState = field(default_factory=ArmState)
    camera_frame: CameraFrame | None = None
    perception_state: PerceptionState = field(default_factory=PerceptionState)
    safety: SafetyState = field(default_factory=SafetyState)
    labels: dict[str, str] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)

