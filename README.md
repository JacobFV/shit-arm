# shit-arm

Control shell for a guide arm, powered robot arm, and laptop-camera trash-sorting system.

The first implementation is intentionally hardware-light: every mode runs against mock adapters, emits normalized robot commands, passes through a safety filter, and can be recorded. Real guide-arm, robot-arm, and camera drivers can replace the mock classes without changing the modes.

## Modes

Bringup and safety:

- `safe-idle`
- `emergency-stop`
- `diagnostics`
- `calibration`
- `manual-jog`
- `homing`
- `recovery`
- `dry-run`

Human control and data:

- `mirror`
- `record`
- `teach`
- `assisted-teleop`

Playback:

- `replay`

Vision and sorting:

- `vision-monitor`
- `vision-pick`
- `vision-closed-loop`
- `human-confirm-sort`
- `sort`
- `dataset`

## Quick Start

```bash
python -m shit_arm.cli modes
python -m shit_arm.cli run mirror --ticks 3
python -m shit_arm.cli run vision-monitor --ticks 1
python -m shit_arm.cli run sort --ticks 1
python -m shit_arm.cli run record --ticks 5 --run-root runs
```

After installing the package, the `shit-arm` console command is also available:

```bash
pip install -e ".[dev]"
shit-arm modes
shit-arm run human-confirm-sort --confirmed --ticks 1
```

## Architecture

```text
guide arm        camera
   |               |
   v               v
input adapters -> context refresh -> mode -> safety filter -> robot driver
                                  |
                                  v
                              recorder
```

Every mode returns a `RobotCommand`:

- `hold`
- `stop`
- `home`
- `joint_target`
- `cartesian_target`
- `velocity`
- `gripper`
- `composite`

This means mirror, replay, assisted teleop, and sorting all share the same final safety and hardware path.

## Prerequisites
lerobot
feetech


## Next Hardware Work

Implement real adapters with the same methods as the mocks:

- `guide.read_state()`
- `robot.read_state()`
- `robot.apply(command)`
- `camera.read()`
- `perception.update(frame, calibration)`

Recommended next order:

1. Bring up `diagnostics`, `manual-jog`, and `homing` on real hardware.
2. Make `mirror` stable with speed limits and a deadman switch.
3. Use `record` and `teach` to collect synchronized trajectories.
4. Validate repeatability with `replay`.
5. Test camera detection in `vision-monitor`.
6. Move through `human-confirm-sort` before full `sort`.

