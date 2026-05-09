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

## LeRobot Hardware Backend

The real hardware path is designed around LeRobot's follower/leader split:

- Powered arm: LeRobot follower robot, read with `get_observation()` and commanded with `send_action(action)`.
- Guide arm: LeRobot leader teleoperator, read with `get_action()`.
- Laptop/robot camera: pulled from the follower observation by camera key, for example `front`.

Typical SO-101 setup:

```bash
lerobot-find-port

lerobot-setup-motors \
  --robot.type=so101_follower \
  --robot.port=/dev/tty.usbmodem585A0076841

lerobot-setup-motors \
  --teleop.type=so101_leader \
  --teleop.port=/dev/tty.usbmodem575E0031751

lerobot-calibrate \
  --robot.type=so101_follower \
  --robot.port=/dev/tty.usbmodem585A0076841 \
  --robot.id=shit_arm_follower

lerobot-calibrate \
  --teleop.type=so101_leader \
  --teleop.port=/dev/tty.usbmodem575E0031751 \
  --teleop.id=shit_arm_leader
```

Then run this project against those same IDs and ports:

```bash
python -m shit_arm.cli run mirror \
  --backend lerobot \
  --robot-type so101_follower \
  --robot-port /dev/tty.usbmodem585A0076841 \
  --robot-id shit_arm_follower \
  --teleop-type so101_leader \
  --teleop-port /dev/tty.usbmodem575E0031751 \
  --teleop-id shit_arm_leader \
  --ticks 1000 \
  --hz 30
```

To route a laptop camera through LeRobot's follower observation, add an OpenCV camera config:

```bash
python -m shit_arm.cli run vision-monitor \
  --backend lerobot \
  --robot-type so101_follower \
  --robot-port /dev/tty.usbmodem585A0076841 \
  --robot-id shit_arm_follower \
  --teleop-type so101_leader \
  --teleop-port /dev/tty.usbmodem575E0031751 \
  --teleop-id shit_arm_leader \
  --camera-key front \
  --opencv-camera-index 0 \
  --opencv-camera-width 640 \
  --opencv-camera-height 480 \
  --opencv-camera-fps 30
```

For SO-100, switch the type flags:

```bash
--robot-type so100_follower --teleop-type so100_leader
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

## Next Hardware Work

Implement real adapters with the same methods as the mocks:

- `guide.read_state()`
- `robot.read_state()`
- `robot.apply(command)`
- `camera.read()`
- `perception.update(frame, calibration)`

Recommended next order:

1. Set up motors and calibration with the official LeRobot tools.
2. Bring up `diagnostics`, `manual-jog`, and `homing` on real hardware.
3. Make `mirror` stable with speed limits and a deadman switch.
4. Use `record` and `teach` to collect synchronized trajectories.
5. Validate repeatability with `replay`.
6. Test camera detection in `vision-monitor`.
7. Move through `human-confirm-sort` before full `sort`.
