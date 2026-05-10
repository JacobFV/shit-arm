from __future__ import annotations

from dataclasses import dataclass, field
from time import time

from shit_arm.app import _lerobot_calibration
from shit_arm.control.runner import ModeRunner
from shit_arm.data import NullRecorder
from shit_arm.hardware.lerobot_adapter import LeRobotFollowerArm, _numeric_feature_keys, _position_keys
from shit_arm.modes import MODE_CLASSES, mode_descriptions, mode_names
from shit_arm.perception.detectors import ForegroundDetector
from shit_arm.perception.pipeline import VisionPipeline
from shit_arm.types import ArmState, Calibration, CameraFrame, CommandKind, Pose, RobotCommand, SystemContext


def run_mode(name: str, ticks: int = 1):
    context = build_test_context()
    return ModeRunner(context).run(name, ticks=ticks), context


@dataclass
class GuideArmDouble:
    joints: tuple[float, ...] = (0.0, -0.6, 1.0, 0.0, 0.6, 0.0)
    gripper: float = 1.0

    def read_state(self) -> ArmState:
        return ArmState(joints=self.joints, pose=Pose(0.0, 0.35, 0.18), gripper=self.gripper, connected=True)


@dataclass
class RobotArmDouble:
    joints: tuple[float, ...] = (0.0, -0.8, 1.2, 0.0, 0.8, 0.0)
    gripper: float = 1.0
    applied: list[RobotCommand] = field(default_factory=list)

    def read_state(self) -> ArmState:
        return ArmState(joints=self.joints, pose=Pose(0.0, 0.35, 0.18), gripper=self.gripper, connected=True)

    def apply(self, command: RobotCommand) -> None:
        self.applied.append(command)
        if command.joint_targets is not None:
            self.joints = command.joint_targets
        if command.gripper is not None:
            self.gripper = command.gripper


@dataclass
class CameraDouble:
    frame_id: int = 0

    def read(self) -> CameraFrame:
        self.frame_id += 1
        image = [[(210, 210, 210) for _x in range(30)] for _y in range(20)]
        for y in range(5, 15):
            for x in range(10, 20):
                image[y][x] = (20, 20, 20)
        return CameraFrame(frame_id=self.frame_id, timestamp=time(), width=30, height=20, payload=image)


def build_test_context() -> SystemContext:
    return SystemContext(
        mode_name="safe-idle",
        robot=RobotArmDouble(),
        guide=GuideArmDouble(),
        camera=CameraDouble(),
        recorder=NullRecorder(),
        perception=VisionPipeline(detector=ForegroundDetector(min_area=50)),
        calibration=Calibration(),
    )


def test_mirror_emits_joint_command() -> None:
    result, _context = run_mode("mirror")
    assert result.last_command.kind == CommandKind.JOINT_TARGET


def test_vision_monitor_holds() -> None:
    result, context = run_mode("vision-monitor")
    assert result.last_command.kind == CommandKind.HOLD
    assert context.perception_state.tracks
    assert context.perception_state.selected_track_id == 1


def test_sort_emits_composite_command() -> None:
    result, _context = run_mode("sort")
    assert result.last_command.kind == CommandKind.COMPOSITE


def test_estop_overrides_mode_command() -> None:
    context = build_test_context()
    context.safety.estop = True
    result = ModeRunner(context).run("mirror")
    assert result.last_command.kind == CommandKind.STOP


def test_human_confirm_waits_without_confirmation() -> None:
    result, _context = run_mode("human-confirm-sort")
    assert result.last_command.kind == CommandKind.HOLD


def test_human_confirm_sorts_with_confirmation() -> None:
    context = build_test_context()
    context.options["confirmed"] = True
    result = ModeRunner(context).run("human-confirm-sort")
    assert result.last_command.kind == CommandKind.COMPOSITE


def test_runner_calls_on_tick_for_live_exports() -> None:
    context = build_test_context()
    calls = []
    ModeRunner(context, on_tick=lambda tick_context: calls.append(tick_context.camera_frame.frame_id)).run(
        "vision-monitor",
        ticks=3,
        hz=0,
    )
    assert calls == [1, 2, 3]


def test_lerobot_feature_keys_preserve_position_order() -> None:
    keys = _numeric_feature_keys({"shoulder_pan.pos": float, "front": (640, 480, 3), "gripper.pos": float})
    assert keys == ("shoulder_pan.pos", "gripper.pos")


def test_lerobot_position_keys_ignore_images() -> None:
    keys = _position_keys({"shoulder_pan.pos": 12.0, "front": object(), "gripper.pos": 44.0})
    assert keys == ("shoulder_pan.pos", "gripper.pos")


def test_lerobot_calibration_uses_degree_limits() -> None:
    calibration = _lerobot_calibration()
    assert calibration.joint_limits[0] == (-180.0, 180.0)
    assert calibration.joint_limits[-1] == (0.0, 100.0)


class LeRobotDouble:
    is_connected = True
    action_features = {"cartesian.x": float, "cartesian.y": float, "cartesian.z": float, "gripper.pos": float}

    def __init__(self) -> None:
        self.actions = []

    def send_action(self, action: dict[str, float]) -> None:
        self.actions.append(action)


def test_lerobot_adapter_sends_cartesian_action_when_features_exist() -> None:
    follower = LeRobotFollowerArm.__new__(LeRobotFollowerArm)
    follower.robot = LeRobotDouble()
    follower.last_observation = {}
    follower._last_action = {}

    follower.apply(RobotCommand.pose(Pose(0.1, 0.2, 0.3)))

    assert follower.robot.actions == [{"cartesian.x": 0.1, "cartesian.y": 0.2, "cartesian.z": 0.3, "gripper.pos": 0.0}]


def test_all_advertised_modes_have_descriptions() -> None:
    assert set(mode_names()) == set(MODE_CLASSES)
    assert set(mode_descriptions()) == set(MODE_CLASSES)
    assert all(mode_descriptions().values())
