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
python -m shit_arm.cli run vision-monitor --vision-detector color --ticks 30
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

## Vision Pipeline

Vision is persistent rather than frame-local. Each camera frame is processed as:

```text
camera frame -> detector -> tracker -> table pose estimator -> bin classifier -> target selector
```

The detector returns one-frame `Detection` values. The tracker turns those into persistent `TrackedObject` values with:

- `track_id`
- smoothed bounding box
- age and missed-frame counts
- stable/selected/lost status
- table pose
- target bin
- target-selection score

Available detector backends:

- `mock`: deterministic fake can for tests and mode development.
- `color`: dependency-free red-object blob detector for controlled camera bringup.
- `foreground`: dependency-free object proposal for non-table blobs on a plain table.
- `yolo`: optional Ultralytics YOLO detector; install with `pip install ultralytics`.

Examples:

```bash
python -m shit_arm.cli run vision-monitor --vision-detector mock --ticks 5
python -m shit_arm.cli run vision-monitor --vision-detector color --ticks 100
python -m shit_arm.cli run vision-monitor --vision-detector foreground --foreground-min-area 300 --ticks 100
python -m shit_arm.cli run vision-monitor --vision-detector yolo --yolo-model yolov8n.pt --yolo-label bottle --ticks 100
python -m shit_arm.cli run sort --target-label can --ticks 1
```

The sorting modes prefer selected tracks over raw detections, so closed-loop behavior can keep following the same physical object by `track_id`.

Each track also carries a motion estimate comparing pixel-space and table/world-space movement:

- `pixel_delta`: centroid motion in image pixels.
- `table_delta`: motion of the estimated world/table pose.
- `projected_table_delta`: expected table motion from projecting the pixel delta.
- `table_delta_error`: discrepancy between world motion and projected pixel motion.
- `consistent`: whether the discrepancy is within tolerance.

Tracker and selector settings are exposed from the CLI:

```bash
python -m shit_arm.cli run vision-monitor \
  --vision-detector foreground \
  --tracker-stable-after-frames 3 \
  --tracker-max-missed-frames 8 \
  --selector-min-confidence 0.4
```

For calibrated table coordinates, pass a 3x3 image-to-table homography JSON file:

```json
{
  "image_to_table_homography": [
    [0.001, 0.0, -0.32],
    [0.0, 0.001, 0.08],
    [0.0, 0.0, 1.0]
  ]
}
```

Then run:

```bash
python -m shit_arm.cli run vision-monitor --homography-path calibration/image_to_table.json
```

## Controller App

The Electron controller app lives in `controller/`. It shows a left sidebar with:

- session/mode status
- live webcam video in the main workspace
- gripper pixel coordinate
- gripper world coordinate
- every tracked object with pixel coordinate, world coordinate, bin, confidence, score, and motion comparison

Generate a controller state file from Python:

```bash
python -m shit_arm.cli run vision-monitor \
  --ticks 5 \
  --controller-state-path controller/controller-state.json
```

Run the app:

```bash
npm install
npm start
```

To point the app at another state file:

```bash
SHIT_ARM_CONTROLLER_STATE=/tmp/shit-arm-controller.json npm start
```

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
