from __future__ import annotations

from abc import ABC, abstractmethod

from shit_arm.types import RobotCommand, SystemContext


class Mode(ABC):
    name: str

    def enter(self, context: SystemContext) -> None:
        context.recorder.record_event("mode_enter", {"mode": self.name})

    @abstractmethod
    def tick(self, context: SystemContext) -> RobotCommand:
        """Return the command for one control cycle."""

    def exit(self, context: SystemContext) -> None:
        context.recorder.record_event("mode_exit", {"mode": self.name})


class HoldMode(Mode):
    name = "safe-idle"

    def tick(self, context: SystemContext) -> RobotCommand:
        return RobotCommand.hold("safe idle")
