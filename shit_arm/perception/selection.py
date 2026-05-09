from __future__ import annotations

from dataclasses import dataclass

from shit_arm.types import Calibration, TrackStatus, TrackedObject


RECYCLING_LABELS = {"can", "bottle", "plastic", "paper", "cardboard", "metal", "glass", "red-object"}
COMPOST_LABELS = {"food", "organic", "compost", "banana", "apple"}
LANDFILL_LABELS = {"landfill", "trash", "wrapper"}


@dataclass
class TrashBinClassifier:
    def assign(self, track: TrackedObject) -> str:
        if track.target_bin:
            return track.target_bin
        label = track.label.lower()
        if label in RECYCLING_LABELS:
            return "recycling"
        if label in COMPOST_LABELS:
            return "compost"
        if label in LANDFILL_LABELS:
            return "landfill"
        return "unknown"


@dataclass
class TargetSelector:
    min_confidence: float = 0.35
    min_stable_frames: int = 1

    def choose(self, tracks: list[TrackedObject], calibration: Calibration) -> TrackedObject | None:
        best_track = None
        best_score = float("-inf")
        for track in tracks:
            score = self.score(track, calibration)
            track.score = score
            if score > best_score:
                best_track = track
                best_score = score
        if best_track is None or best_score < 0.0:
            return None
        best_track.status = TrackStatus.SELECTED
        return best_track

    def score(self, track: TrackedObject, calibration: Calibration) -> float:
        if track.confidence < self.min_confidence:
            return -1.0
        if track.missed_frames > 0:
            return -1.0
        if track.stable_frames < self.min_stable_frames:
            return -1.0
        if track.table_pose is None:
            return -0.5
        if not _in_workspace(track, calibration):
            return -1.0
        known_bin_bonus = 0.15 if track.target_bin and track.target_bin != "unknown" else 0.0
        stability_bonus = min(0.3, track.stable_frames * 0.05)
        area_bonus = min(0.15, _bbox_area(track.smoothed_bbox_xywh) / 100000.0)
        return track.confidence + known_bin_bonus + stability_bonus + area_bonus


def _in_workspace(track: TrackedObject, calibration: Calibration) -> bool:
    if track.table_pose is None:
        return False
    pose = track.table_pose
    for value, (low, high) in zip((pose.x, pose.y, pose.z), calibration.workspace_xyz):
        if value < low or value > high:
            return False
    return True


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    return max(0.0, bbox[2]) * max(0.0, bbox[3])

