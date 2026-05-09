from __future__ import annotations

import json
from pathlib import Path

from shit_arm.data import JsonlRecorder, NullRecorder
from shit_arm.hardware.lerobot_adapter import LeRobotFollowerArm, LeRobotLeaderArm, LeRobotObservationCamera
from shit_arm.perception import VisionConfig, build_vision_pipeline
from shit_arm.types import Calibration, SystemContext


def build_lerobot_context(
    robot_type: str,
    robot_port: str,
    robot_id: str,
    teleop_type: str,
    teleop_port: str,
    teleop_id: str,
    camera_key: str = "front",
    cameras: dict[str, object] | None = None,
    vision_detector: str = "foreground",
    vision_config: VisionConfig | None = None,
    homography_path: Path | None = None,
    record: bool = False,
    run_root: Path = Path("runs"),
) -> SystemContext:
    follower = LeRobotFollowerArm(robot_type=robot_type, port=robot_port, robot_id=robot_id, cameras=cameras)
    leader = LeRobotLeaderArm(teleop_type=teleop_type, port=teleop_port, teleop_id=teleop_id)
    calibration = _lerobot_calibration()
    _load_homography(calibration, homography_path)
    return SystemContext(
        mode_name="safe-idle",
        robot=follower,
        guide=leader,
        camera=LeRobotObservationCamera(follower=follower, key=camera_key),
        recorder=JsonlRecorder(run_root) if record else NullRecorder(),
        perception=build_vision_pipeline(vision_detector, vision_config),
        calibration=calibration,
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


def _load_homography(calibration: Calibration, path: Path | None) -> None:
    if path is None:
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    matrix = payload.get("image_to_table_homography", payload)
    calibration.image_to_table_homography = tuple(tuple(float(value) for value in row) for row in matrix)  # type: ignore[assignment]
