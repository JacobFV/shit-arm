from __future__ import annotations

from shit_arm.app import build_mock_context
from shit_arm.control.runner import ModeRunner
from shit_arm.types import CommandKind


def run_mode(name: str, ticks: int = 1):
    context = build_mock_context()
    return ModeRunner(context).run(name, ticks=ticks), context


def test_mirror_emits_joint_command() -> None:
    result, _context = run_mode("mirror")
    assert result.last_command.kind == CommandKind.JOINT_TARGET


def test_vision_monitor_holds() -> None:
    result, _context = run_mode("vision-monitor")
    assert result.last_command.kind == CommandKind.HOLD


def test_sort_emits_composite_command() -> None:
    result, _context = run_mode("sort")
    assert result.last_command.kind == CommandKind.COMPOSITE


def test_estop_overrides_mode_command() -> None:
    context = build_mock_context()
    context.safety.estop = True
    result = ModeRunner(context).run("mirror")
    assert result.last_command.kind == CommandKind.STOP


def test_human_confirm_waits_without_confirmation() -> None:
    result, _context = run_mode("human-confirm-sort")
    assert result.last_command.kind == CommandKind.HOLD


def test_human_confirm_sorts_with_confirmation() -> None:
    context = build_mock_context()
    context.options["confirmed"] = True
    result = ModeRunner(context).run("human-confirm-sort")
    assert result.last_command.kind == CommandKind.COMPOSITE

