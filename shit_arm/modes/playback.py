from __future__ import annotations

from pathlib import Path

from shit_arm.modes.base import Mode
from shit_arm.types import CommandKind, Pose, RobotCommand, SystemContext


class ReplayMode(Mode):
    name = "replay"

    def enter(self, context: SystemContext) -> None:
        super().enter(context)
        path = context.options.get("replay_path")
        context.options["_replay_commands"] = self._load_commands(Path(path)) if path else []
        context.options["_replay_index"] = 0

    def tick(self, context: SystemContext) -> RobotCommand:
        commands: list[RobotCommand] = context.options.get("_replay_commands", [])
        index = int(context.options.get("_replay_index", 0))
        if index >= len(commands):
            return RobotCommand.hold("replay complete")
        context.options["_replay_index"] = index + 1
        return commands[index]

    def _load_commands(self, path: Path) -> list[RobotCommand]:
        if not path.exists():
            raise FileNotFoundError(path)
        commands: list[RobotCommand] = []
        for line in path.read_text().splitlines():
            parts = line.split()
            if not parts:
                continue
            if parts[0] == CommandKind.JOINT_TARGET.value:
                commands.append(RobotCommand.joints(tuple(float(value) for value in parts[1:])))
            elif parts[0] == CommandKind.GRIPPER.value:
                commands.append(RobotCommand.gripper_to(float(parts[1])))
            elif parts[0] == CommandKind.CARTESIAN_TARGET.value:
                x, y, z, *rest = (float(value) for value in parts[1:])
                roll, pitch, yaw = (rest + [0.0, 0.0, 0.0])[:3]
                commands.append(RobotCommand.pose(Pose(x, y, z, roll, pitch, yaw)))
        return commands

