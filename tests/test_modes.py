from __future__ import annotations

from shit_arm.app import _lerobot_calibration, build_simulated_context
from shit_arm.control.runner import ModeRunner
from shit_arm.hardware.lerobot_adapter import LeRobotFollowerArm, _numeric_feature_keys, _position_keys
from shit_arm.types import CommandKind, Pose, RobotCommand


def run_mode(name: str, ticks: int = 1):
    context = build_simulated_context()
    return ModeRunner(context).run(name, ticks=ticks), context


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
    context = build_simulated_context()
    context.safety.estop = True
    result = ModeRunner(context).run("mirror")
    assert result.last_command.kind == CommandKind.STOP


def test_human_confirm_waits_without_confirmation() -> None:
    result, _context = run_mode("human-confirm-sort")
    assert result.last_command.kind == CommandKind.HOLD


def test_human_confirm_sorts_with_confirmation() -> None:
    context = build_simulated_context()
    context.options["confirmed"] = True
    result = ModeRunner(context).run("human-confirm-sort")
    assert result.last_command.kind == CommandKind.COMPOSITE


def test_runner_calls_on_tick_for_live_exports() -> None:
    context = build_simulated_context()
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


class FakeLeRobot:
    is_connected = True
    action_features = {"cartesian.x": float, "cartesian.y": float, "cartesian.z": float, "gripper.pos": float}

    def __init__(self) -> None:
        self.actions = []

    def send_action(self, action: dict[str, float]) -> None:
        self.actions.append(action)


def test_lerobot_adapter_sends_cartesian_action_when_features_exist() -> None:
    follower = LeRobotFollowerArm.__new__(LeRobotFollowerArm)
    follower.robot = FakeLeRobot()
    follower.last_observation = {}
    follower._last_action = {}

    follower.apply(RobotCommand.pose(Pose(0.1, 0.2, 0.3)))

    assert follower.robot.actions == [{"cartesian.x": 0.1, "cartesian.y": 0.2, "cartesian.z": 0.3, "gripper.pos": 0.0}]
