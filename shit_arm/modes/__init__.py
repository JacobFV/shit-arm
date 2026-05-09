from __future__ import annotations

from shit_arm.modes.base import HoldMode, Mode
from shit_arm.modes.basic import (
    CalibrationMode,
    DiagnosticsMode,
    DryRunMode,
    EmergencyStopMode,
    HomingMode,
    ManualJogMode,
    RecoveryMode,
)
from shit_arm.modes.human import AssistedTeleopMode, MirrorMode, RecordMode, TeachMode
from shit_arm.modes.playback import ReplayMode
from shit_arm.modes.vision import (
    DatasetMode,
    HumanConfirmSortMode,
    SortMode,
    VisionClosedLoopMode,
    VisionMonitorMode,
    VisionPickMode,
)

MODE_CLASSES: dict[str, type[Mode]] = {
    cls.name: cls
    for cls in (
        HoldMode,
        EmergencyStopMode,
        DiagnosticsMode,
        CalibrationMode,
        ManualJogMode,
        HomingMode,
        MirrorMode,
        RecordMode,
        ReplayMode,
        TeachMode,
        AssistedTeleopMode,
        VisionMonitorMode,
        VisionPickMode,
        VisionClosedLoopMode,
        HumanConfirmSortMode,
        SortMode,
        DatasetMode,
        DryRunMode,
        RecoveryMode,
    )
}


def create_mode(name: str) -> Mode:
    try:
        return MODE_CLASSES[name]()
    except KeyError as exc:
        raise ValueError(f"unknown mode {name!r}; expected one of {', '.join(sorted(MODE_CLASSES))}") from exc


def mode_names() -> list[str]:
    return sorted(MODE_CLASSES)

