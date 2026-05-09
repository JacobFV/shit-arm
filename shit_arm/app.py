from __future__ import annotations

from pathlib import Path

from shit_arm.data import JsonlRecorder, NullRecorder
from shit_arm.hardware import MockCamera, MockGuideArm, MockRobotArm
from shit_arm.hardware.lerobot_adapter import LeRobotFollowerArm, LeRobotLeaderArm, LeRobotObservationCamera
from shit_arm.perception import MockPerception
from shit_arm.types import Calibration, SystemContext


def build_mock_context(record: bool = False, run_root: Path = Path("runs")) -> SystemContext:
    return SystemContext(
        mode_name="safe-idle",
        robot=MockRobotArm(),
        guide=MockGuideArm(),
        camera=MockCamera(),
        recorder=JsonlRecorder(run_root) if record else NullRecorder(),
        perception=MockPerception(),
    )


def build_lerobot_context(
    robot_type: str,
    robot_port: str,
    robot_id: str,
    teleop_type: str,
    teleop_port: str,
    teleop_id: str,
    camera_key: str = "front",
    cameras: dict[str, object] | None = None,
    record: bool = False,
    run_root: Path = Path("runs"),
) -> SystemContext:
    follower = LeRobotFollowerArm(robot_type=robot_type, port=robot_port, robot_id=robot_id, cameras=cameras)
    leader = LeRobotLeaderArm(teleop_type=teleop_type, port=teleop_port, teleop_id=teleop_id)
    return SystemContext(
        mode_name="safe-idle",
        robot=follower,
        guide=leader,
        camera=LeRobotObservationCamera(follower=follower, key=camera_key),
        recorder=JsonlRecorder(run_root) if record else NullRecorder(),
        perception=MockPerception(),
        calibration=_lerobot_calibration(),
    )


def _lerobot_calibration() -> Calibration:
    return Calibration(
        joint_limits=(
            (-180.0, 180.0),
            (-180.0, 180.0),
            (-180.0, 180.0),
            (-180.0, 180.0),
            (-180.0, 180.0),
            (0.0, 100.0),
        ),
        home_joints=(0.0, 0.0, 0.0, 0.0, 0.0, 50.0),
    )


def build_lerobot_opencv_cameras(
    key: str,
    index_or_path: str,
    fps: int = 30,
    width: int = 640,
    height: int = 480,
) -> dict[str, object]:
    from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig

    parsed_index_or_path: int | str = int(index_or_path) if index_or_path.isdigit() else index_or_path
    return {
        key: OpenCVCameraConfig(
            index_or_path=parsed_index_or_path,
            fps=fps,
            width=width,
            height=height,
        )
    }
