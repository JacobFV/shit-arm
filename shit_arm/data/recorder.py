from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from time import strftime, time
from typing import Any

from shit_arm.types import RobotCommand, SystemContext


class NullRecorder:
    def start_run(self, run_name: str | None = None) -> None:
        pass

    def stop_run(self) -> None:
        pass

    def record_event(self, event_type: str, payload: dict[str, Any]) -> None:
        pass

    def record_tick(self, context: SystemContext, command: RobotCommand) -> None:
        pass


@dataclass
class JsonlRecorder:
    root: Path = Path("runs")
    run_dir: Path | None = None

    def start_run(self, run_name: str | None = None) -> None:
        name = run_name or strftime("%Y-%m-%d_%H-%M-%S")
        self.run_dir = self.root / name
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.record_event("run_start", {"run_name": name})

    def stop_run(self) -> None:
        self.record_event("run_stop", {})
        self.run_dir = None

    def record_event(self, event_type: str, payload: dict[str, Any]) -> None:
        self._write("events.jsonl", {"type": event_type, "timestamp": time(), "payload": payload})

    def record_tick(self, context: SystemContext, command: RobotCommand) -> None:
        self._write(
            "trajectory.jsonl",
            {
                "timestamp": time(),
                "mode": context.mode_name,
                "robot_joints": context.robot_state.joints,
                "guide_joints": context.guide_state.joints,
                "camera_frame_id": context.camera_frame.frame_id if context.camera_frame else None,
                "command": _command_dict(command),
            },
        )

    def _write(self, filename: str, payload: dict[str, Any]) -> None:
        if self.run_dir is None:
            return
        path = self.run_dir / filename
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":"), default=str) + "\n")


def _command_dict(command: RobotCommand) -> dict[str, Any]:
    data = asdict(command)
    data["kind"] = command.kind.value
    if command.children:
        data["children"] = [_command_dict(child) for child in command.children]
    return data

