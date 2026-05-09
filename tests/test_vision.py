from __future__ import annotations

from dataclasses import dataclass

from shit_arm.perception.detectors import ForegroundDetector
from shit_arm.perception.pipeline import VisionPipeline
from shit_arm.perception.pose import TablePoseEstimator, apply_homography, invert_3x3
from shit_arm.perception.tracker import ObjectTracker, iou
from shit_arm.types import Calibration, CameraFrame, Detection, Pose, TrackStatus


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
