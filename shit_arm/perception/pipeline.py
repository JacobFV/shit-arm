from __future__ import annotations

from dataclasses import dataclass, field

from shit_arm.perception.detectors import ObjectDetector, build_detector
from shit_arm.perception.pose import TablePoseEstimator
from shit_arm.perception.selection import TargetSelector, TrashBinClassifier
from shit_arm.perception.tracker import ObjectTracker
from shit_arm.types import Calibration, CameraFrame, PerceptionState


@dataclass
class VisionPipeline:
    detector: ObjectDetector = field(default_factory=lambda: build_detector("static"))
    tracker: ObjectTracker = field(default_factory=ObjectTracker)
    pose_estimator: TablePoseEstimator = field(default_factory=TablePoseEstimator)
    bin_classifier: TrashBinClassifier = field(default_factory=TrashBinClassifier)
    target_selector: TargetSelector = field(default_factory=TargetSelector)

    def update(self, frame: CameraFrame | None, calibration: Calibration) -> PerceptionState:
        if frame is None:
            return PerceptionState(status="camera_missing")
        detections = [
            self.pose_estimator.apply_to_detection(detection, frame, calibration)
            for detection in self.detector.detect(frame)
        ]
        tracks = self.tracker.update(detections, frame_id=frame.frame_id)
        for track in tracks:
            self.pose_estimator.apply_to_track(track, frame, calibration)
            track.target_bin = self.bin_classifier.assign(track)
        selected = self.target_selector.choose(tracks, calibration)
        status = "tracking" if tracks else "no_objects"
        return PerceptionState(
            detections=detections,
            tracks=tracks,
            selected=selected,
            selected_track_id=selected.track_id if selected else None,
            status=status,
            frame_id=frame.frame_id,
            metadata={
                "detector": self.detector.__class__.__name__,
                "track_count": len(tracks),
            },
        )


@dataclass
class VisionConfig:
    detector_name: str = "static"
    tracker_min_iou: float = 0.15
    tracker_max_center_distance: float = 120.0
    tracker_smoothing: float = 0.35
    tracker_stable_after_frames: int = 3
    tracker_max_missed_frames: int = 8
    selector_min_confidence: float = 0.35
    selector_min_stable_frames: int = 1
    foreground_threshold: int = 55
    foreground_min_area: int = 250
    yolo_model: str = "yolov8n.pt"
    yolo_min_confidence: float = 0.35
    yolo_labels: set[str] | None = None


def build_vision_pipeline(detector_name: str = "static", config: VisionConfig | None = None) -> VisionPipeline:
    config = config or VisionConfig(detector_name=detector_name)
    config.detector_name = detector_name
    return VisionPipeline(
        detector=build_detector(
            config.detector_name,
            yolo_model=config.yolo_model,
            yolo_min_confidence=config.yolo_min_confidence,
            yolo_labels=config.yolo_labels,
            foreground_threshold=config.foreground_threshold,
            foreground_min_area=config.foreground_min_area,
        ),
        tracker=ObjectTracker(
            min_iou=config.tracker_min_iou,
            max_center_distance=config.tracker_max_center_distance,
            smoothing=config.tracker_smoothing,
            stable_after_frames=config.tracker_stable_after_frames,
            max_missed_frames=config.tracker_max_missed_frames,
        ),
        target_selector=TargetSelector(
            min_confidence=config.selector_min_confidence,
            min_stable_frames=config.selector_min_stable_frames,
        ),
    )
