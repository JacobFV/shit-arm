from __future__ import annotations

from dataclasses import dataclass, field

from shit_arm.types import Detection, TrackStatus, TrackedObject


@dataclass
class ObjectTracker:
    min_iou: float = 0.15
    max_center_distance: float = 120.0
    smoothing: float = 0.35
    stable_after_frames: int = 3
    max_missed_frames: int = 8
    next_track_id: int = 1
    tracks: list[TrackedObject] = field(default_factory=list)

    def update(self, detections: list[Detection], frame_id: int | None = None) -> list[TrackedObject]:
        matches: dict[int, int] = {}
        used_tracks: set[int] = set()
        existing_track_count = len(self.tracks)
        for detection_index, detection in enumerate(detections):
            track_index = self._best_match(detection, used_tracks)
            if track_index is not None:
                matches[detection_index] = track_index
                used_tracks.add(track_index)

        for detection_index, detection in enumerate(detections):
            if detection_index in matches:
                self._update_track(self.tracks[matches[detection_index]], detection, frame_id)
            else:
                self.tracks.append(self._new_track(detection, frame_id))

        matched_track_indexes = set(matches.values())
        for index, track in enumerate(self.tracks[:existing_track_count]):
            if index not in matched_track_indexes and index not in used_tracks:
                track.missed_frames += 1
                if track.missed_frames > self.max_missed_frames:
                    track.status = TrackStatus.LOST

        self.tracks = [track for track in self.tracks if track.missed_frames <= self.max_missed_frames]
        return list(self.tracks)

    def _best_match(self, detection: Detection, used_tracks: set[int]) -> int | None:
        best_index = None
        best_score = 0.0
        for index, track in enumerate(self.tracks):
            if index in used_tracks:
                continue
            score = match_score(detection.bbox_xywh, track.smoothed_bbox_xywh)
            if detection.label != track.label:
                score *= 0.75
            if score > best_score:
                best_index = index
                best_score = score
        if best_index is None:
            return None
        if best_score >= self.min_iou or center_distance(detection.bbox_xywh, self.tracks[best_index].smoothed_bbox_xywh) <= self.max_center_distance:
            return best_index
        return None

    def _new_track(self, detection: Detection, frame_id: int | None) -> TrackedObject:
        track = TrackedObject(
            track_id=self.next_track_id,
            label=detection.label,
            confidence=detection.confidence,
            bbox_xywh=detection.bbox_xywh,
            smoothed_bbox_xywh=detection.bbox_xywh,
            table_pose=detection.table_pose,
            target_bin=detection.target_bin,
            stable_frames=1,
            last_seen_frame_id=frame_id,
        )
        if self.stable_after_frames <= 1:
            track.status = TrackStatus.STABLE
        self.next_track_id += 1
        return track

    def _update_track(self, track: TrackedObject, detection: Detection, frame_id: int | None) -> None:
        track.age_frames += 1
        track.missed_frames = 0
        track.stable_frames += 1
        track.label = detection.label
        track.confidence = (track.confidence * 0.65) + (detection.confidence * 0.35)
        track.bbox_xywh = detection.bbox_xywh
        track.smoothed_bbox_xywh = smooth_bbox(track.smoothed_bbox_xywh, detection.bbox_xywh, self.smoothing)
        track.table_pose = detection.table_pose or track.table_pose
        track.target_bin = detection.target_bin or track.target_bin
        track.last_seen_frame_id = frame_id
        if track.stable_frames >= self.stable_after_frames and track.status == TrackStatus.TENTATIVE:
            track.status = TrackStatus.STABLE


def match_score(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    overlap = iou(a, b)
    distance = center_distance(a, b)
    distance_score = max(0.0, 1.0 - distance / 200.0)
    return 0.7 * overlap + 0.3 * distance_score


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh
    ix1, iy1 = max(ax, bx), max(ay, by)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    intersection = iw * ih
    union = aw * ah + bw * bh - intersection
    return intersection / union if union > 0 else 0.0


def center_distance(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    acx, acy = ax + aw / 2.0, ay + ah / 2.0
    bcx, bcy = bx + bw / 2.0, by + bh / 2.0
    return ((acx - bcx) ** 2 + (acy - bcy) ** 2) ** 0.5


def smooth_bbox(
    previous: tuple[float, float, float, float],
    current: tuple[float, float, float, float],
    alpha: float,
) -> tuple[float, float, float, float]:
    return tuple((1.0 - alpha) * old + alpha * new for old, new in zip(previous, current))
