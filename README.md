# shit-arm

Control shell for a guide arm, powered robot arm, and laptop-camera trash-sorting system.

The runtime backend is LeRobot hardware. The app reads real follower/leader state, emits normalized robot commands, passes through a safety filter, and can be recorded.

## Quick Start

```bash
# Install Python + Node deps
make install

# Start the real robot WebSocket server and React UI
make app ROBOT_PORT=/dev/cu.usbmodem5B140339331
```

Open http://localhost:5173 in a browser for the ARM control panel,
live camera overlay, object tracks, and SO-101 robot view.

## WebSocket Server

A standalone FastAPI server at `shit_arm/control/wss.py`:

```
ws://127.0.0.1:8765/ws
```

- Broadcasts arm state + camera frames (data URI) at ~10Hz
- Accepts control commands (jog, gripper, torque, home, stop)
- Health check: `GET http://127.0.0.1:8765/health`

```bash
make ws-server ROBOT_PORT=/dev/tty...
```

## Frontends

| App | Stack | What it shows |
|-----|-------|---------------|
| React UI (`shit_arm/control/UI/`) | Vite + React 19 + TS 6 | Joint controls, Cartesian jog pad, live camera tracking boxes, SO-101 robot view, tool position, gripper, object tracks, speed settings, current chart |

The React UI connects to the WebSocket server and sends control commands.

## Modes

Bringup and safety:

- `safe-idle`
- `emergency-stop`
- `diagnostics`
- `calibration`
- `homing`
- `recovery`

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

## CLI

```bash
python -m shit_arm.cli modes
python -m shit_arm.cli run mirror --robot-port /dev/tty... --teleop-port /dev/tty... --ticks 3
python -m shit_arm.cli run vision-monitor --robot-port /dev/tty... --ticks 1
python -m shit_arm.cli run sort --robot-port /dev/tty... --ticks 1
```

After installing, the `shit-arm` console command is also available:

```bash
shit-arm modes
shit-arm run human-confirm-sort --confirmed --ticks 1
```

## Low-Level Servo Bridge

The old one-off bring-up scripts have been consolidated into one CLI:

```bash
python -m shit_arm.cli bridge --help
python -m shit_arm.cli bridge scan --port /dev/cu.usbmodem... --ids 0-253
python -m shit_arm.cli bridge health --port /dev/cu.usbmodem... --ids 1-6
python -m shit_arm.cli bridge wiggle --port /dev/cu.usbmodem... --ids 1 --ticks 60
python -m shit_arm.cli bridge torque --port /dev/cu.usbmodem... --ids 1-6 --disable
python -m shit_arm.cli bridge identify --port /dev/cu.usbmodem...
python -m shit_arm.cli bridge demo --port /dev/cu.usbmodem... --profile full
python -m shit_arm.cli bridge verify-move --port /dev/cu.usbmodem... --id 1
python -m shit_arm.cli bridge aruco-tags --out aruco_sheet.png
```

After installation, the same tool is available as `shit-arm-bridge`.

Servo bus commands also require the Feetech `scservo_sdk` package to be
installed in the environment. The `bridge` extra installs the Python packages
that are available from PyPI for serial probing and ArUco tag generation.

## Makefile

```bash
make install            # Install Python + Node deps
make install-ws         # Install Python deps for the WebSocket server
make install-bridge     # Install Python deps for bridge helpers
make test               # Run Python tests + JS syntax checks
make app                # Start real robot WebSocket server + React UI
make ui                 # Start React UI dev server
make build-ui           # Build React UI
make bridge             # Show low-level servo bridge commands
make ws-server          # Start WebSocket server
make vision-lerobot     # Run LeRobot vision with OpenCV camera
```

See `make help` for the full target list and configurable variables.

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
                                  |
                                  v
                         WebSocket server (wss.py)
                                  |
                                  v
                           React UI (Vite)
                    (control panel, camera overlay,
                     object tracks, SO-101 robot view)
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

- `color`: dependency-free red-object blob detector for controlled camera bringup.
- `foreground`: dependency-free object proposal for non-table blobs on a plain table.
- `yolo`: optional Ultralytics YOLO detector; install with `pip install ultralytics`.

Examples:

```bash
python -m shit_arm.cli run vision-monitor --robot-port /dev/tty... --vision-detector color --ticks 100
python -m shit_arm.cli run vision-monitor --robot-port /dev/tty... --vision-detector foreground --foreground-min-area 300 --ticks 100
python -m shit_arm.cli run vision-monitor --robot-port /dev/tty... --vision-detector yolo --yolo-model yolov8n.pt --yolo-label bottle --ticks 100
python -m shit_arm.cli run sort --robot-port /dev/tty... --target-label can --ticks 1
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
  --robot-port /dev/tty... \
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
python -m shit_arm.cli run vision-monitor --robot-port /dev/tty... --homography-path calibration/image_to_table.json
```

To generate that file from arm motion, attach a visible marker to the tool tip,
keep the camera fixed, and run projection calibration over the reachable table
plane:

```bash
python -m shit_arm.cli calibrate-projection \
  --robot-type so101_follower \
  --robot-port /dev/tty.usbmodem585A0076841 \
  --robot-id shit_arm_follower \
  --camera-key front \
  --opencv-camera-index 0 \
  --out calibration/image_to_table.json \
  --x-min -0.20 --x-max 0.20 \
  --y-min 0.18 --y-max 0.50 \
  --z 0.04 \
  --grid-x 3 --grid-y 3 \
  --marker-color red
```

The command moves the arm to each grid point, localizes the marker in the
camera frame, solves the image-to-table homography, writes reprojection error
metrics, and updates the same calibration JSON consumed by the runtime. After
calibration, `vision-pick`, `vision-closed-loop`, and `sort` project bounding
box centers into table/world coordinates before issuing Cartesian arm targets.

## Robot Hardware

The WebSocket server requires a real LeRobot arm:

### 1. Find your robot's serial port

```bash
lerobot-find-port
# or
ls /dev/cu.usbmodem*
```

### 2. Calibrate the motors

```bash
lerobot-calibrate \
  --robot.type=so101_follower \
  --robot.port=/dev/tty.usbmodemXXXXX \
  --robot.id=shit_arm_follower
```

### 3. Start the WS server with the hardware backend

```bash
make ws-server \
  ROBOT_PORT=/dev/tty.usbmodemXXXXX \
  ROBOT_TYPE=so101_follower \
  OPENCV_CAMERA_INDEX=0
```

Or directly:

```bash
uv run python -m shit_arm.control.wss \
  --robot-port /dev/tty.usbmodemXXXXX \
  --robot-type so101_follower \
  --camera-index 0 \
  --fps 20
```

### How data flows

```
LeRobotFollowerArm.read_state()
  → ArmState(joints=[6 floats], pose=Pose(x,y,z,roll,pitch,yaw), gripper=float)
  → WebSocket JSON broadcast (~20Hz)
  → React UI displays joint rows, camera tracking boxes, tool position, gripper, SO-101 robot view

Commands from React:
  jog_joint(0, +0.05) → LeRobotFollowerArm.apply(RobotCommand.joints(...))
  jog_cartesian("x", 0.01) → Pose offset → apply(RobotCommand.pose(...))
  gripper(0.5) → apply(RobotCommand.gripper_to(...))
```

The `robot.joints` array follows SO-101 convention:
`[shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper]`

For SO-100, use `--robot-type so100_follower`.

## Legacy Controller State (file-based)

Generate a controller state file from Python (legacy, for tools that don't use WebSocket):

```bash
python -m shit_arm.cli run vision-monitor \
  --robot-port /dev/tty... \
  --ticks 5 \
  --controller-state-path runs/controller-state.json \
  --controller-frame-path runs/latest-frame.jpg
```

## Hardware Interface

Hardware adapters implement these methods:

- `guide.read_state()`
- `robot.read_state()`
- `robot.apply(command)`
- `camera.read()`
- `perception.update(frame, calibration)`

Recommended next order:

1. Set up motors and calibration with the official LeRobot tools.
2. Bring up `diagnostics`, WebSocket jog commands, and `homing` on real hardware.
3. Make `mirror` stable with speed limits and a deadman switch.
4. Use `record` and `teach` to collect synchronized trajectories.
5. Validate repeatability with `replay`.
6. Test camera detection in `vision-monitor`.
7. Move through `human-confirm-sort` before full `sort`.
