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

MODE_DESCRIPTIONS: dict[str, str] = {
    "assisted-teleop": "Mirror guide-arm input with optional vision alignment assistance.",
    "calibration": "Record a calibration snapshot without moving hardware.",
    "dataset": "Capture perception metadata for dataset labeling.",
    "diagnostics": "Record current robot, guide, camera, perception, and safety status.",
    "dry-run": "Execute an injected in-process command for tests and development harnesses.",
    "emergency-stop": "Latch safety stop and emit a stop command.",
    "homing": "Move to configured home joints at low speed.",
    "human-confirm-sort": "Propose a sort target and wait for explicit confirmation.",
    "manual-jog": "Apply a single injected joint or gripper jog command.",
    "mirror": "Mirror guide-arm joint or cartesian state to the robot arm.",
    "record": "Mirror guide-arm input while recording ticks to a run log.",
    "recovery": "Run a configured recovery action, defaulting to low-speed home.",
    "replay": "Replay commands from a text trajectory file.",
    "safe-idle": "Hold position without issuing movement.",
    "sort": "Pick and drop the selected confident perception target.",
    "teach": "Record guided motion with optional label/bin metadata.",
    "vision-closed-loop": "Servo directly toward the selected vision target.",
    "vision-monitor": "Run perception and tracking without moving hardware.",
    "vision-pick": "Pick the selected vision target without dropping it into a bin.",
}


def create_mode(name: str) -> Mode:
    try:
        return MODE_CLASSES[name]()
    except KeyError as exc:
        raise ValueError(f"unknown mode {name!r}; expected one of {', '.join(sorted(MODE_CLASSES))}") from exc


def mode_names() -> list[str]:
    return sorted(MODE_CLASSES)


def mode_descriptions() -> dict[str, str]:
    return {name: MODE_DESCRIPTIONS[name] for name in mode_names()}
