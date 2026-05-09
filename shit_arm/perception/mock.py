from __future__ import annotations

from dataclasses import dataclass, field

from shit_arm.perception.detectors import StaticDetector
from shit_arm.perception.pipeline import VisionPipeline
from shit_arm.types import Calibration, CameraFrame, Detection, PerceptionState, Pose


@dataclass
class MockPerception(VisionPipeline):
    detections: list[Detection] = field(
        default_factory=lambda: [
            Detection(
                label="can",
                confidence=0.82,
                bbox_xywh=(260, 180, 80, 130),
                table_pose=Pose(0.05, 0.32, 0.04),
                target_bin="recycling",
            )
        ]
    )

    def update(self, frame: CameraFrame | None, calibration: Calibration) -> PerceptionState:
        self.detector = StaticDetector(self.detections)
        return super().update(frame, calibration)
