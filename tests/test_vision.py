from __future__ import annotations

from dataclasses import dataclass

from shit_arm.perception.calibration import (
    ColorMarkerLocalizer,
    ProjectionCorrespondence,
    load_projection_homography,
    run_arm_motion_projection_calibration,
    solve_image_to_table_homography,
)
from shit_arm.perception.detectors import ForegroundDetector
from shit_arm.perception.pipeline import VisionPipeline
from shit_arm.perception.pose import TablePoseEstimator, apply_homography, invert_3x3
from shit_arm.perception.tracker import ObjectTracker, iou
from shit_arm.types import ArmState, Calibration, CameraFrame, Detection, Pose, RobotCommand, TrackStatus


@dataclass
class SequenceDetector:
    detections: list[Detection]

    def detect(self, frame: CameraFrame | None) -> list[Detection]:
        if frame is None:
            return []
        return list(self.detections)


def test_iou_overlap() -> None:
    assert round(iou((0, 0, 10, 10), (5, 5, 10, 10)), 2) == 0.14


def test_tracker_keeps_persistent_id_for_nearby_detection() -> None:
    tracker = ObjectTracker(stable_after_frames=2)
    first = tracker.update([Detection("can", 0.8, (100, 100, 40, 40))], frame_id=1)
    second = tracker.update([Detection("can", 0.9, (105, 102, 40, 40))], frame_id=2)
    assert first[0].track_id == second[0].track_id
    assert second[0].status == TrackStatus.STABLE


def test_vision_pipeline_selects_stable_track() -> None:
    pipeline = VisionPipeline(
        detector=SequenceDetector([Detection("can", 0.9, (260, 180, 80, 130), table_pose=Pose(0.05, 0.32, 0.04))]),
        tracker=ObjectTracker(stable_after_frames=1),
    )
    frame = CameraFrame(frame_id=1, width=640, height=480)
    state = pipeline.update(frame, Calibration())
    assert state.selected is not None
    assert state.selected_track_id == 1
    assert state.tracks[0].target_bin == "recycling"


def test_tracker_drops_lost_track_after_missed_limit() -> None:
    tracker = ObjectTracker(max_missed_frames=1)
    tracks = tracker.update([Detection("can", 0.8, (100, 100, 40, 40))], frame_id=1)
    assert tracks[0].track_id == 1
    assert tracker.update([], frame_id=2)
    assert tracker.update([], frame_id=3) == []


def test_homography_projection() -> None:
    h = ((0.001, 0.0, -0.32), (0.0, 0.001, 0.08), (0.0, 0.0, 1.0))
    assert apply_homography(h, 320.0, 240.0) == (0.0, 0.32)


def test_table_pose_estimator_uses_homography() -> None:
    calibration = Calibration(
        image_to_table_homography=((0.001, 0.0, -0.32), (0.0, 0.001, 0.08), (0.0, 0.0, 1.0))
    )
    pose = TablePoseEstimator().bbox_to_table_pose((300, 220, 40, 40), CameraFrame(1, width=640, height=480), calibration)
    assert pose == Pose(0.0, 0.32, 0.04)


def test_motion_estimate_compares_pixel_and_world_delta() -> None:
    calibration = Calibration(
        image_to_table_homography=((0.001, 0.0, -0.32), (0.0, 0.001, 0.08), (0.0, 0.0, 1.0))
    )
    pipeline = VisionPipeline(
        detector=SequenceDetector([Detection("can", 0.9, (300, 220, 40, 40))]),
        tracker=ObjectTracker(stable_after_frames=1),
    )
    frame = CameraFrame(1, width=640, height=480)
    pipeline.update(frame, calibration)
    pipeline.detector = SequenceDetector([Detection("can", 0.9, (310, 225, 40, 40))])
    state = pipeline.update(CameraFrame(2, width=640, height=480), calibration)
    motion = state.tracks[0].motion
    assert motion is not None
    assert motion.pixel_delta == (3.5, 1.75)
    assert motion.projected_table_delta is not None
    assert round(motion.projected_table_delta[0], 4) == 0.0035
    assert motion.consistent is True


def test_inverse_homography_round_trip() -> None:
    h = ((0.001, 0.0, -0.32), (0.0, 0.001, 0.08), (0.0, 0.0, 1.0))
    inverse = invert_3x3(h)
    assert inverse is not None
    assert apply_homography(inverse, 0.0, 0.32) == (320.0, 240.0)


def test_foreground_detector_finds_non_table_blob() -> None:
    image = [
        [(210, 210, 210) for _x in range(30)]
        for _y in range(20)
    ]
    for y in range(5, 15):
        for x in range(10, 20):
            image[y][x] = (20, 20, 20)
    detections = ForegroundDetector(min_area=50).detect(CameraFrame(1, width=30, height=20, payload=image))
    assert len(detections) == 1
    assert detections[0].bbox_xywh == (10.0, 5.0, 10.0, 10.0)


def test_projection_calibration_solves_homography_from_correspondences() -> None:
    correspondences = [
        ProjectionCorrespondence((100.0, 100.0), (-0.2, 0.2)),
        ProjectionCorrespondence((500.0, 100.0), (0.2, 0.2)),
        ProjectionCorrespondence((500.0, 400.0), (0.2, 0.5)),
        ProjectionCorrespondence((100.0, 400.0), (-0.2, 0.5)),
        ProjectionCorrespondence((300.0, 250.0), (0.0, 0.35)),
    ]
    result = solve_image_to_table_homography(correspondences)

    projected = apply_homography(result.image_to_table_homography, 300.0, 250.0)
    assert projected is not None
    assert round(projected[0], 4) == 0.0
    assert round(projected[1], 4) == 0.35
    assert result.reprojection_rmse_m < 1e-10


def test_color_marker_localizer_finds_red_centroid() -> None:
    image = [[(20, 20, 20) for _x in range(8)] for _y in range(6)]
    for y in range(2, 4):
        for x in range(3, 6):
            image[y][x] = (220, 30, 30)

    pixel = ColorMarkerLocalizer(color="red", min_area_px=3).locate(CameraFrame(1, width=8, height=6, payload=image))

    assert pixel == (4.0, 2.5)


def test_projection_calibration_file_round_trip(tmp_path) -> None:
    result = solve_image_to_table_homography(
        [
            ProjectionCorrespondence((0.0, 0.0), (0.0, 0.0)),
            ProjectionCorrespondence((10.0, 0.0), (1.0, 0.0)),
            ProjectionCorrespondence((10.0, 10.0), (1.0, 1.0)),
            ProjectionCorrespondence((0.0, 10.0), (0.0, 1.0)),
        ]
    )
    path = tmp_path / "projection.json"
    from shit_arm.perception.calibration import save_projection_calibration

    save_projection_calibration(result, path)

    assert load_projection_homography(path) == result.image_to_table_homography
    raw_path = tmp_path / "raw_matrix.json"
    raw_path.write_text("[[1, 0, 0], [0, 1, 0], [0, 0, 1]]\n", encoding="utf-8")
    assert load_projection_homography(raw_path) == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


@dataclass
class CalibrationRobotDouble:
    pose: Pose = Pose(0.0, 0.0, 0.0)

    def read_state(self) -> ArmState:
        return ArmState(pose=self.pose, connected=True)

    def apply(self, command: RobotCommand) -> None:
        if command.pose_target is not None:
            self.pose = command.pose_target


@dataclass
class CalibrationCameraDouble:
    robot: CalibrationRobotDouble
    frame_id: int = 0

    def read(self) -> CameraFrame:
        self.frame_id += 1
        width, height = 640, 480
        image = [[(20, 20, 20) for _x in range(width)] for _y in range(height)]
        px = int(round((self.robot.pose.x + 0.32) / 0.001))
        py = int(round((self.robot.pose.y - 0.08) / 0.001))
        for y in range(max(0, py - 2), min(height, py + 3)):
            for x in range(max(0, px - 2), min(width, px + 3)):
                image[y][x] = (220, 20, 20)
        return CameraFrame(self.frame_id, width=width, height=height, payload=image)


def test_arm_motion_projection_calibration_end_to_end(tmp_path) -> None:
    robot = CalibrationRobotDouble()
    camera = CalibrationCameraDouble(robot)
    calibration = Calibration()
    result = run_arm_motion_projection_calibration(
        robot=robot,
        camera=camera,
        calibration=calibration,
        output_path=tmp_path / "image_to_table.json",
        localizer=ColorMarkerLocalizer(color="red", min_area_px=5),
        x_range=(-0.2, 0.2),
        y_range=(0.2, 0.5),
        z=0.04,
        grid=(2, 2),
        settle_s=0.0,
        samples_per_point=1,
    )

    pose = TablePoseEstimator().point_to_table_pose((320.0, 380.0), CameraFrame(1, width=640, height=480), calibration)
    assert pose is not None
    assert round(pose.x, 3) == 0.0
    assert round(pose.y, 3) == 0.46
    assert result.max_reprojection_error_m < 1e-9
