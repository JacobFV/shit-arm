from __future__ import annotations

from pathlib import Path

from shit_arm.data import JsonlRecorder, NullRecorder
from shit_arm.hardware import MockCamera, MockGuideArm, MockRobotArm
from shit_arm.perception import MockPerception
from shit_arm.types import SystemContext


def build_mock_context(record: bool = False, run_root: Path = Path("runs")) -> SystemContext:
    return SystemContext(
        mode_name="safe-idle",
        robot=MockRobotArm(),
        guide=MockGuideArm(),
        camera=MockCamera(),
        recorder=JsonlRecorder(run_root) if record else NullRecorder(),
        perception=MockPerception(),
    )

