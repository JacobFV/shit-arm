from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from numbers import Real
from time import time
from typing import Any

from shit_arm.types import ArmState, CameraFrame, CommandKind, Pose, RobotCommand


SUPPORTED_FOLLOWERS = {
    "so101_follower": ("lerobot.robots.so_follower", "SO101Follower", "SO101FollowerConfig"),
    "so100_follower": ("lerobot.robots.so_follower", "SO100Follower", "SO100FollowerConfig"),
    "koch_follower": ("lerobot.robots.koch_follower", "KochFollower", "KochFollowerConfig"),
}

SUPPORTED_LEADERS = {
    "so101_leader": ("lerobot.teleoperators.so_leader", "SO101Leader", "SO101LeaderConfig"),
    "so100_leader": ("lerobot.teleoperators.so_leader", "SO100Leader", "SO100LeaderConfig"),
    "koch_leader": ("lerobot.teleoperators.koch_leader", "KochLeader", "KochLeaderConfig"),
}


@dataclass
class LeRobotFollowerArm:
    """Adapter from this project command API to a LeRobot follower robot."""

    robot_type: str
    port: str
    robot_id: str
    cameras: dict[str, Any] | None = None
    connect_on_init: bool = True

    def __post_init__(self) -> None:
        robot_cls, config_cls = _load_lerobot_class(SUPPORTED_FOLLOWERS, self.robot_type)
        kwargs: dict[str, Any] = {"port": self.port, "id": self.robot_id}
        if self.cameras is not None:
            kwargs["cameras"] = self.cameras
        self.robot = robot_cls(config_cls(**kwargs))
        self.last_observation: dict[str, Any] = {}
        self._last_action: dict[str, Any] = {}
        if self.connect_on_init:
            self.connect()

    @property
    def connected(self) -> bool:
        return bool(getattr(self.robot, "is_connected", False))

    @property
    def action_keys(self) -> tuple[str, ...]:
        return _numeric_feature_keys(getattr(self.robot, "action_features", {}))

    def connect(self) -> None:
        if not self.connected:
            self.robot.connect()

    def disconnect(self) -> None:
        if hasattr(self.robot, "disconnect") and self.connected:
            self.robot.disconnect()

    def read_state(self) -> ArmState:
        self.connect()
        self.last_observation = self.robot.get_observation()
        return _arm_state_from_mapping(self.last_observation, connected=self.connected)

    def apply(self, command: RobotCommand) -> None:
        self.connect()
        if command.kind in {CommandKind.HOLD, CommandKind.STOP}:
            return
        if command.kind == CommandKind.HOME:
            return self._send_joint_tuple(_home_for_keys(self.action_keys))
        if command.kind == CommandKind.JOINT_TARGET and command.joint_targets is not None:
            return self._send_joint_tuple(command.joint_targets)
        if command.kind == CommandKind.GRIPPER and command.gripper is not None:
            return self._send_gripper(command.gripper)
        if command.kind == CommandKind.COMPOSITE:
            for child in command.children:
                self.apply(child)
            return
        raise NotImplementedError(f"{command.kind.value} is not directly supported by LeRobot follower adapter")

    def _send_joint_tuple(self, joints: tuple[float, ...]) -> None:
        keys = self.action_keys
        if len(joints) != len(keys):
            raise ValueError(f"joint command has {len(joints)} values but LeRobot action has {len(keys)} keys")
        action = dict(zip(keys, joints))
        self._last_action = action
        self.robot.send_action(action)

    def _send_gripper(self, position: float) -> None:
        keys = [key for key in self.action_keys if "gripper" in key.lower()]
        if not keys:
            raise ValueError("LeRobot action_features has no gripper key")
        action = dict(self._last_action) if self._last_action else _current_action_from_observation(
            self.last_observation,
            self.action_keys,
        )
        for key in keys:
            action[key] = position
        self._last_action = action
        self.robot.send_action(action)


@dataclass
class LeRobotLeaderArm:
    """Adapter from a LeRobot leader/teleoperator to this project guide API."""

    teleop_type: str
    port: str
    teleop_id: str
    connect_on_init: bool = True

    def __post_init__(self) -> None:
        teleop_cls, config_cls = _load_lerobot_class(SUPPORTED_LEADERS, self.teleop_type)
        self.teleop = teleop_cls(config_cls(port=self.port, id=self.teleop_id))
        self.last_action: dict[str, Any] = {}
        if self.connect_on_init:
            self.connect()

    @property
    def connected(self) -> bool:
        return bool(getattr(self.teleop, "is_connected", False))

    def connect(self) -> None:
        if not self.connected:
            self.teleop.connect()

    def disconnect(self) -> None:
        if hasattr(self.teleop, "disconnect") and self.connected:
            self.teleop.disconnect()

    def read_state(self) -> ArmState:
        self.connect()
        self.last_action = self.teleop.get_action()
        return _arm_state_from_mapping(self.last_action, connected=self.connected)


@dataclass
class LeRobotObservationCamera:
    """Expose a camera frame from the follower's latest LeRobot observation."""

    follower: LeRobotFollowerArm
    key: str = "front"
    frame_id: int = 0

    def read(self) -> CameraFrame | None:
        observation = self.follower.last_observation
        if self.key not in observation:
            return None
        image = observation[self.key]
        self.frame_id += 1
        height, width = _image_shape(image)
        return CameraFrame(
            frame_id=self.frame_id,
            timestamp=time(),
            width=width,
            height=height,
            payload=image,
        )


def _load_lerobot_class(registry: dict[str, tuple[str, str, str]], key: str) -> tuple[type, type]:
    if key not in registry:
        raise ValueError(f"unsupported LeRobot hardware type {key!r}; expected one of {', '.join(sorted(registry))}")
    module_name, class_name, config_name = registry[key]
    try:
        module = import_module(module_name)
    except ImportError as exc:
        raise ImportError(
            "LeRobot is not installed or its package layout changed. Install with `pip install lerobot` "
            "and the needed hardware extras, for example `pip install 'lerobot[feetech]'`."
        ) from exc
    return getattr(module, class_name), getattr(module, config_name)


def _numeric_feature_keys(features: dict[str, Any]) -> tuple[str, ...]:
    position_keys = tuple(key for key in features if key.endswith(".pos"))
    if position_keys:
        return position_keys
    keys = []
    for key, value in features.items():
        if value is float or value == float or str(value).endswith("float'>"):
            keys.append(key)
    return tuple(keys)


def _arm_state_from_mapping(values: dict[str, Any], connected: bool) -> ArmState:
    keys = _position_keys(values)
    joints = tuple(float(values[key]) for key in keys)
    gripper = _gripper_value(values, default=0.0)
    return ArmState(joints=joints, pose=Pose(0.0, 0.0, 0.0), gripper=gripper, connected=connected)


def _position_keys(values: dict[str, Any]) -> tuple[str, ...]:
    keys = [key for key, value in values.items() if key.endswith(".pos") and _is_number(value)]
    if keys:
        return tuple(keys)
    return tuple(key for key, value in values.items() if _is_number(value))


def _gripper_value(values: dict[str, Any], default: float) -> float:
    for key, value in values.items():
        if "gripper" in key.lower() and _is_number(value):
            return float(value)
    return default


def _current_action_from_observation(observation: dict[str, Any], action_keys: tuple[str, ...]) -> dict[str, Any]:
    action = {}
    for key in action_keys:
        action[key] = float(observation.get(key, 0.0))
    return action


def _home_for_keys(keys: tuple[str, ...]) -> tuple[float, ...]:
    return tuple(0.0 for _ in keys)


def _image_shape(image: Any) -> tuple[int, int]:
    shape = getattr(image, "shape", None)
    if shape and len(shape) >= 2:
        return int(shape[0]), int(shape[1])
    if isinstance(image, list) and image:
        return len(image), len(image[0])
    return 0, 0


def _is_number(value: Any) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)
