from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shit_arm.state import build_controller_state
from shit_arm.types import SystemContext


def write_controller_state(context: SystemContext, path: Path, frame_image_path: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if frame_image_path is None:
        frame_image_path = path.with_name("latest-frame.svg")
    frame_image_path = write_controller_frame(context, frame_image_path)
    _atomic_write_text(path, json.dumps(build_controller_state(context, frame_image_path), indent=2, default=str) + "\n")


def write_controller_frame(context: SystemContext, path: Path) -> Path:
    frame = context.camera_frame
    if frame is None:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = frame.payload
    if payload is None:
        output_path = path.with_suffix(".svg")
        _write_status_svg(output_path, frame.width, frame.height, frame.frame_id)
        return output_path
    output_path = path.with_suffix(".jpg")
    if _write_with_pillow(payload, output_path):
        return output_path
    if _write_with_cv2(payload, output_path):
        return output_path
    output_path = path.with_suffix(".svg")
    _write_status_svg(output_path, frame.width, frame.height, frame.frame_id)
    return output_path


def _write_with_pillow(payload: Any, path: Path) -> bool:
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return False
    try:
        array = np.asarray(payload)
        image = Image.fromarray(array.astype("uint8"))
        image.save(path, quality=85)
        return True
    except Exception:
        return False


def _write_with_cv2(payload: Any, path: Path) -> bool:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return False
    try:
        array = np.asarray(payload)
        cv2.imwrite(str(path), array)
        return True
    except Exception:
        return False


def _write_status_svg(path: Path, width: int, height: int, frame_id: int) -> None:
    width = width or 640
    height = height or 480
    _atomic_write_text(
        path,
        f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#101820"/>
  <path d="M0 {height / 2}H{width}M{width / 2} 0V{height}" stroke="#263241" stroke-width="2"/>
  <text x="24" y="42" fill="#d7dee8" font-family="system-ui" font-size="24">controller frame {frame_id}</text>
  <text x="24" y="76" fill="#8b96a6" font-family="system-ui" font-size="16">no camera payload exported</text>
</svg>
""",
    )


def _atomic_write_text(path: Path, contents: str) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(contents, encoding="utf-8")
    tmp_path.replace(path)
