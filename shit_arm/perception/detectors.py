from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from shit_arm.types import CameraFrame, Detection, Pose


class ObjectDetector(Protocol):
    def detect(self, frame: CameraFrame | None) -> list[Detection]:
        ...


@dataclass
class ColorBlobDetector:
    """Small dependency-free detector for controlled bringup with bright colored items.

    This accepts simple list-like RGB/BGR frames. It is intentionally conservative and
    exists so real camera tests can work before adding a model backend.
    """

    min_area: int = 120
    red_margin: int = 45

    def detect(self, frame: CameraFrame | None) -> list[Detection]:
        image = frame.payload if frame else None
        if image is None:
            return []
        points: list[tuple[int, int]] = []
        try:
            rows = image.tolist() if hasattr(image, "tolist") else image
            for y, row in enumerate(rows):
                for x, pixel in enumerate(row):
                    if len(pixel) < 3:
                        continue
                    r, g, b = int(pixel[0]), int(pixel[1]), int(pixel[2])
                    if r > g + self.red_margin and r > b + self.red_margin and r > 80:
                        points.append((x, y))
        except TypeError:
            return []
        if len(points) < self.min_area:
            return []
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        area_ratio = len(points) / max(1, frame.width * frame.height)
        return [
            Detection(
                label="red-object",
                confidence=min(0.95, 0.45 + area_ratio * 12.0),
                bbox_xywh=(float(x0), float(y0), float(x1 - x0 + 1), float(y1 - y0 + 1)),
            )
        ]


@dataclass
class ForegroundDetector:
    """Dependency-light object proposal for items on a plain table.

    It thresholds pixels that are sufficiently different from a configurable
    light table color and returns one bounding box around the foreground mass.
    This is not a final trash model; it is a practical bridge from camera
    bringup to stable pick targets.
    """

    label: str = "object"
    table_rgb: tuple[int, int, int] = (210, 210, 210)
    threshold: int = 55
    min_area: int = 250

    def detect(self, frame: CameraFrame | None) -> list[Detection]:
        image = frame.payload if frame else None
        if image is None:
            return []
        points: list[tuple[int, int]] = []
        try:
            rows = image.tolist() if hasattr(image, "tolist") else image
            for y, row in enumerate(rows):
                for x, pixel in enumerate(row):
                    if len(pixel) < 3:
                        continue
                    if color_distance(pixel, self.table_rgb) >= self.threshold:
                        points.append((x, y))
        except TypeError:
            return []
        if len(points) < self.min_area:
            return []
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        area_ratio = len(points) / max(1, frame.width * frame.height)
        return [
            Detection(
                label=self.label,
                confidence=min(0.9, 0.4 + area_ratio * 8.0),
                bbox_xywh=(float(x0), float(y0), float(x1 - x0 + 1), float(y1 - y0 + 1)),
                metadata={"area_px": len(points), "detector": "foreground"},
            )
        ]


@dataclass
class YoloDetector:
    """Optional YOLO detector using ultralytics when installed."""

    model_name: str = "yolov8n.pt"
    min_confidence: float = 0.35
    allowed_labels: set[str] | None = None
    _model: object | None = None

    def detect(self, frame: CameraFrame | None) -> list[Detection]:
        image = frame.payload if frame else None
        if image is None:
            return []
        model = self._load_model()
        results = model(image, verbose=False)
        detections: list[Detection] = []
        for result in results:
            names = getattr(result, "names", {})
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                confidence = float(box.conf[0])
                if confidence < self.min_confidence:
                    continue
                label = str(names.get(int(box.cls[0]), int(box.cls[0])))
                if self.allowed_labels and label not in self.allowed_labels:
                    continue
                x1, y1, x2, y2 = [float(value) for value in box.xyxy[0]]
                detections.append(
                    Detection(
                        label=label,
                        confidence=confidence,
                        bbox_xywh=(x1, y1, x2 - x1, y2 - y1),
                        metadata={"detector": "yolo", "model": self.model_name},
                    )
                )
        return detections

    def _load_model(self) -> object:
        if self._model is None:
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise ImportError("YOLO detector requires `pip install ultralytics`.") from exc
            self._model = YOLO(self.model_name)
        return self._model


def build_detector(
    name: str,
    *,
    yolo_model: str = "yolov8n.pt",
    yolo_min_confidence: float = 0.35,
    yolo_labels: set[str] | None = None,
    foreground_threshold: int = 55,
    foreground_min_area: int = 250,
) -> ObjectDetector:
    if name == "color":
        return ColorBlobDetector()
    if name == "foreground":
        return ForegroundDetector(threshold=foreground_threshold, min_area=foreground_min_area)
    if name == "yolo":
        return YoloDetector(model_name=yolo_model, min_confidence=yolo_min_confidence, allowed_labels=yolo_labels)
    raise ValueError(f"unknown vision detector {name!r}; expected color, foreground, or yolo")


def color_distance(pixel: object, rgb: tuple[int, int, int]) -> int:
    r, g, b = int(pixel[0]), int(pixel[1]), int(pixel[2])  # type: ignore[index]
    return abs(r - rgb[0]) + abs(g - rgb[1]) + abs(b - rgb[2])
