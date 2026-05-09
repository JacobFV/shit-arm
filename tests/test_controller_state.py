from __future__ import annotations

from shit_arm.control.runner import ModeRunner
from shit_arm.state import build_controller_state
from test_modes import build_test_context


def test_controller_state_includes_gripper_and_track_coordinates() -> None:
    context = build_test_context()
    ModeRunner(context).run("vision-monitor", ticks=2, hz=0)
    state = build_controller_state(context)
    assert state["gripper"]["world"] is not None
    assert state["guide"]["world"] is not None
    assert state["calibration"]["joint_limits"]
    assert state["robot_model"]["format"] == "urdf"
    assert state["robot_model"]["joints"][0]["name"] == "shoulder_pan"
    assert state["gripper"]["pixel"] is not None
    assert state["perception"]["tracks"]
    track = state["perception"]["tracks"][0]
    assert track["pixel"] is not None
    assert track["world"] is not None
    assert "motion" in track
