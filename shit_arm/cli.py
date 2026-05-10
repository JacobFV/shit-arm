from __future__ import annotations

import argparse
from pathlib import Path

from shit_arm.app import build_lerobot_context, build_lerobot_opencv_cameras
from shit_arm.controller_state import write_controller_state
from shit_arm.control.runner import ModeRunner
from shit_arm.data.bridge_tool import add_bridge_subparser
from shit_arm.hardware.lerobot_adapter import LeRobotFollowerArm, LeRobotObservationCamera
from shit_arm.modes import mode_descriptions, mode_names
from shit_arm.perception.calibration import ColorMarkerLocalizer, run_arm_motion_projection_calibration
from shit_arm.perception import VisionConfig
from shit_arm.types import Calibration


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shit-arm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    modes_parser = subparsers.add_parser("modes", help="List available operating modes.")
    modes_parser.add_argument("--names-only", action="store_true", help="Print only mode names, one per line.")
    add_bridge_subparser(subparsers)
    calibrate_parser = subparsers.add_parser(
        "calibrate-projection",
        help="Move the arm through a table grid and solve camera pixel-to-world projection.",
    )
    _add_lerobot_projection_args(calibrate_parser)

    run_parser = subparsers.add_parser("run", help="Run a mode.")
    run_parser.add_argument("mode", choices=mode_names())
    run_parser.add_argument("--ticks", type=int, default=1)
    run_parser.add_argument("--hz", type=float, default=10.0)
    run_parser.add_argument("--record", action="store_true")
    run_parser.add_argument("--run-root", type=Path, default=Path("runs"))
    run_parser.add_argument("--controller-state-path", type=Path)
    run_parser.add_argument("--controller-frame-path", type=Path)
    run_parser.add_argument("--robot-type", default="so101_follower")
    run_parser.add_argument("--robot-port")
    run_parser.add_argument("--robot-id", default="shit_arm_follower")
    run_parser.add_argument("--teleop-type", default="so101_leader")
    run_parser.add_argument("--teleop-port")
    run_parser.add_argument("--teleop-id", default="shit_arm_leader")
    run_parser.add_argument("--camera-key", default="front")
    run_parser.add_argument("--opencv-camera-index")
    run_parser.add_argument("--opencv-camera-fps", type=int, default=30)
    run_parser.add_argument("--opencv-camera-width", type=int, default=640)
    run_parser.add_argument("--opencv-camera-height", type=int, default=480)
    run_parser.add_argument("--vision-detector", choices=["color", "foreground", "yolo"], default="foreground")
    run_parser.add_argument("--homography-path", type=Path)
    run_parser.add_argument("--tracker-min-iou", type=float, default=0.15)
    run_parser.add_argument("--tracker-max-center-distance", type=float, default=120.0)
    run_parser.add_argument("--tracker-smoothing", type=float, default=0.35)
    run_parser.add_argument("--tracker-stable-after-frames", type=int, default=3)
    run_parser.add_argument("--tracker-max-missed-frames", type=int, default=8)
    run_parser.add_argument("--selector-min-confidence", type=float, default=0.35)
    run_parser.add_argument("--selector-min-stable-frames", type=int, default=1)
    run_parser.add_argument("--foreground-threshold", type=int, default=55)
    run_parser.add_argument("--foreground-min-area", type=int, default=250)
    run_parser.add_argument("--yolo-model", default="yolov8n.pt")
    run_parser.add_argument("--yolo-min-confidence", type=float, default=0.35)
    run_parser.add_argument("--yolo-label", action="append", default=[])
    run_parser.add_argument("--replay-path", type=Path)
    run_parser.add_argument("--label")
    run_parser.add_argument("--target-bin")
    run_parser.add_argument("--target-label")
    run_parser.add_argument("--target-track-id", type=int)
    run_parser.add_argument("--confirmed", action="store_true")
    run_parser.add_argument("--min-confidence", type=float, default=None)
    run_parser.add_argument("--speed-scale", type=float, default=None)
    run_parser.add_argument("--assistance-level", type=int, default=None)

    args = parser.parse_args(argv)
    if args.command == "modes":
        if args.names_only:
            for name in mode_names():
                print(name)
        else:
            for name, description in mode_descriptions().items():
                print(f"{name:20s} {description}")
        return 0
    if args.command == "bridge":
        return args.func(args)
    if args.command == "calibrate-projection":
        return _run_projection_calibration(args, parser)

    should_record = args.record or args.mode in {"record", "teach"}
    vision_config = VisionConfig(
        detector_name=args.vision_detector,
        tracker_min_iou=args.tracker_min_iou,
        tracker_max_center_distance=args.tracker_max_center_distance,
        tracker_smoothing=args.tracker_smoothing,
        tracker_stable_after_frames=args.tracker_stable_after_frames,
        tracker_max_missed_frames=args.tracker_max_missed_frames,
        selector_min_confidence=args.selector_min_confidence,
        selector_min_stable_frames=args.selector_min_stable_frames,
        foreground_threshold=args.foreground_threshold,
        foreground_min_area=args.foreground_min_area,
        yolo_model=args.yolo_model,
        yolo_min_confidence=args.yolo_min_confidence,
        yolo_labels=set(args.yolo_label) if args.yolo_label else None,
    )

    if not args.robot_port:
        parser.error("--robot-port is required")
    if args.mode in {"mirror", "record", "teach", "assisted-teleop"} and not args.teleop_port:
        parser.error(f"{args.mode} requires --teleop-port")
    cameras = None
    if args.opencv_camera_index is not None:
        cameras = build_lerobot_opencv_cameras(
            key=args.camera_key,
            index_or_path=args.opencv_camera_index,
            fps=args.opencv_camera_fps,
            width=args.opencv_camera_width,
            height=args.opencv_camera_height,
        )
    context = build_lerobot_context(
        robot_type=args.robot_type,
        robot_port=args.robot_port,
        robot_id=args.robot_id,
        teleop_type=args.teleop_type,
        teleop_port=args.teleop_port,
        teleop_id=args.teleop_id,
        camera_key=args.camera_key,
        cameras=cameras,
        vision_detector=args.vision_detector,
        vision_config=vision_config,
        homography_path=args.homography_path,
        record=should_record,
        run_root=args.run_root,
    )
    if args.replay_path:
        context.options["replay_path"] = str(args.replay_path)
    if args.label:
        context.options["label"] = args.label
    if args.target_bin:
        context.options["target_bin"] = args.target_bin
    if args.target_label:
        context.options["target_label"] = args.target_label
    if args.target_track_id is not None:
        context.options["target_track_id"] = args.target_track_id
    if args.confirmed:
        context.options["confirmed"] = True
    if args.min_confidence is not None:
        context.options["min_confidence"] = args.min_confidence
    if args.speed_scale is not None:
        context.options["speed_scale"] = args.speed_scale
    if args.assistance_level is not None:
        context.options["assistance_level"] = args.assistance_level

    on_tick = None
    if args.controller_state_path:
        on_tick = lambda tick_context: write_controller_state(
            tick_context,
            args.controller_state_path,
            args.controller_frame_path,
        )
    result = ModeRunner(context, on_tick=on_tick).run(args.mode, ticks=args.ticks, hz=args.hz)
    print(f"mode={args.mode} ticks={result.ticks} last_command={result.last_command.kind.value} reason={result.last_command.reason}")
    return 0


def _add_lerobot_projection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--robot-type", default="so101_follower")
    parser.add_argument("--robot-port", required=True)
    parser.add_argument("--robot-id", default="shit_arm_follower")
    parser.add_argument("--camera-key", default="front")
    parser.add_argument("--opencv-camera-index")
    parser.add_argument("--opencv-camera-fps", type=int, default=30)
    parser.add_argument("--opencv-camera-width", type=int, default=640)
    parser.add_argument("--opencv-camera-height", type=int, default=480)
    parser.add_argument("--out", type=Path, default=Path("calibration/image_to_table.json"))
    parser.add_argument("--x-min", type=float, default=-0.20)
    parser.add_argument("--x-max", type=float, default=0.20)
    parser.add_argument("--y-min", type=float, default=0.18)
    parser.add_argument("--y-max", type=float, default=0.50)
    parser.add_argument("--z", type=float, default=0.04)
    parser.add_argument("--grid-x", type=int, default=3)
    parser.add_argument("--grid-y", type=int, default=3)
    parser.add_argument("--settle-s", type=float, default=0.7)
    parser.add_argument("--samples-per-point", type=int, default=5)
    parser.add_argument("--speed-scale", type=float, default=0.18)
    parser.add_argument("--marker-color", choices=["red", "green", "blue", "dark", "bright"], default="red")
    parser.add_argument("--marker-channel-order", choices=["rgb", "bgr"], default="rgb")
    parser.add_argument("--marker-min-area-px", type=int, default=20)


def _run_projection_calibration(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    cameras = None
    if args.opencv_camera_index is not None:
        cameras = build_lerobot_opencv_cameras(
            key=args.camera_key,
            index_or_path=args.opencv_camera_index,
            fps=args.opencv_camera_fps,
            width=args.opencv_camera_width,
            height=args.opencv_camera_height,
        )
    robot = LeRobotFollowerArm(
        robot_type=args.robot_type,
        port=args.robot_port,
        robot_id=args.robot_id,
        cameras=cameras,
    )
    calibration = Calibration()
    localizer = ColorMarkerLocalizer(
        color=args.marker_color,
        channel_order=args.marker_channel_order,
        min_area_px=args.marker_min_area_px,
    )
    camera = LeRobotObservationCamera(follower=robot, key=args.camera_key)
    try:
        result = run_arm_motion_projection_calibration(
            robot=robot,
            camera=camera,
            calibration=calibration,
            output_path=args.out,
            localizer=localizer,
            x_range=(args.x_min, args.x_max),
            y_range=(args.y_min, args.y_max),
            z=args.z,
            grid=(args.grid_x, args.grid_y),
            settle_s=args.settle_s,
            samples_per_point=args.samples_per_point,
            speed_scale=args.speed_scale,
        )
    except Exception as exc:
        parser.exit(2, f"projection calibration failed: {exc}\n")
    print(
        "projection calibration saved "
        f"path={args.out} points={len(result.correspondences)} "
        f"rmse_m={result.reprojection_rmse_m:.5f} max_error_m={result.max_reprojection_error_m:.5f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
