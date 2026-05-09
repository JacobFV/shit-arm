from __future__ import annotations

import argparse
from pathlib import Path

from shit_arm.app import build_lerobot_context, build_lerobot_opencv_cameras
from shit_arm.controller_state import write_controller_state
from shit_arm.control.runner import ModeRunner
from shit_arm.data.bridge_tool import add_bridge_subparser
from shit_arm.modes import mode_descriptions, mode_names
from shit_arm.perception import VisionConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shit-arm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    modes_parser = subparsers.add_parser("modes", help="List available operating modes.")
    modes_parser.add_argument("--names-only", action="store_true", help="Print only mode names, one per line.")
    add_bridge_subparser(subparsers)

    run_parser = subparsers.add_parser("run", help="Run a mode.")
    run_parser.add_argument("mode", choices=mode_names())
    run_parser.add_argument("--backend", choices=["lerobot"], default="lerobot")
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

    if not args.robot_port or not args.teleop_port:
        parser.error("--backend lerobot requires --robot-port and --teleop-port")
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


if __name__ == "__main__":
    raise SystemExit(main())
