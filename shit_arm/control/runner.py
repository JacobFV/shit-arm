from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, sleep

from shit_arm.control.safety import SafetyController
from shit_arm.modes import create_mode
from shit_arm.types import RobotCommand, SystemContext


@dataclass
class RunResult:
    ticks: int
    last_command: RobotCommand


class ModeRunner:
    def __init__(self, context: SystemContext, safety: SafetyController | None = None) -> None:
        self.context = context
        self.safety = safety or SafetyController()

    def run(self, mode_name: str, ticks: int = 1, hz: float = 10.0) -> RunResult:
        self.context.mode_name = mode_name
        mode = create_mode(mode_name)
        period = 1.0 / hz if hz > 0 else 0.0
        last_command = RobotCommand.hold("not started")
        mode.enter(self.context)
        try:
            for tick in range(ticks):
                started = monotonic()
                self._refresh_inputs()
                command = mode.tick(self.context)
                safe_command = self.safety.filter(command, self.context)
                self.context.robot.apply(safe_command)
                self.context.recorder.record_tick(self.context, safe_command)
                last_command = safe_command
                remaining = period - (monotonic() - started)
                if remaining > 0 and tick + 1 < ticks:
                    sleep(remaining)
        finally:
            mode.exit(self.context)
        return RunResult(ticks=ticks, last_command=last_command)

    def _refresh_inputs(self) -> None:
        self.context.robot_state = self.context.robot.read_state()
        self.context.guide_state = self.context.guide.read_state()
        self.context.camera_frame = self.context.camera.read()
        self.context.perception_state = self.context.perception.update(
            self.context.camera_frame,
            self.context.calibration,
        )

