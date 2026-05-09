PYTHON ?= uv run python
UV ?= uv
NPM ?= npm

MODE ?= vision-monitor
BACKEND ?= mock
TICKS ?= 999999
HZ ?= 10
VISION_DETECTOR ?= mock
LEROBOT_VISION_DETECTOR ?= foreground
CONTROLLER_STATE ?= controller/controller-state.json
CONTROLLER_FRAME ?= controller/latest-frame.jpg
HOMOGRAPHY_PATH ?=

ROBOT_TYPE ?= so101_follower
ROBOT_PORT ?=
ROBOT_ID ?= shit_arm_follower
TELEOP_TYPE ?= so101_leader
TELEOP_PORT ?=
TELEOP_ID ?= shit_arm_leader
CAMERA_KEY ?= front
OPENCV_CAMERA_INDEX ?= 0
OPENCV_CAMERA_WIDTH ?= 640
OPENCV_CAMERA_HEIGHT ?= 480
OPENCV_CAMERA_FPS ?= 30

WS_PORT ?= 8765
WS_HOST ?= 127.0.0.1
WS_BACKEND ?= mock

TRACKER_STABLE_AFTER_FRAMES ?= 3
TRACKER_MAX_MISSED_FRAMES ?= 8
SELECTOR_MIN_CONFIDENCE ?= 0.35
FOREGROUND_MIN_AREA ?= 250
FOREGROUND_THRESHOLD ?= 55

.PHONY: help install install-python install-ws install-node test test-python test-js modes controller controller-state ws-server vision vision-mock vision-lerobot mirror-lerobot diagnostics-lerobot clean

help:
	@printf '%s\n' \
		'Targets:' \
		'  make install              Install Python package (uv sync) and Node deps' \
		'  make install-ws           Install Python deps including WebSocket server' \
		'  make test                 Run Python tests and JS syntax checks' \
		'  make controller           Start the Electron controller app' \
		'  make controller-state     Write one mock controller-state JSON snapshot' \
		'  make vision-mock          Run mock vision and keep controller state updated' \
		'  make vision-lerobot       Run LeRobot vision with OpenCV camera' \
		'  make mirror-lerobot       Run LeRobot guide-arm mirror mode' \
		'  make diagnostics-lerobot  Run LeRobot diagnostics once' \
		'  make ws-server           Start the WebSocket server (standalone)' \
		'' \
		'Common variables:' \
		'  ROBOT_PORT=/dev/tty... TELEOP_PORT=/dev/tty...' \
		'  VISION_DETECTOR=mock|color|foreground|yolo' \
		'  LEROBOT_VISION_DETECTOR=foreground|color|yolo|mock' \
		'  TICKS=999999 HZ=10 OPENCV_CAMERA_INDEX=0' \
		'  WS_PORT=8765 WS_HOST=127.0.0.1 WS_BACKEND=mock' \
		'' \
		'Requires: uv (https://docs.astral.sh/uv/) and npm'

install: install-python install-node

install-python:
	$(UV) sync --extra dev

install-ws:
	$(UV) sync --all-extras

install-node:
	$(NPM) install

test: test-python test-js

test-python:
	$(PYTHON) tests/run_tests.py

test-js:
	node --check controller/main.js
	node --check controller/preload.js
	node --check controller/renderer.js

modes:
	$(PYTHON) -m shit_arm.cli modes

controller:
	$(NPM) start

ws-server:
	$(PYTHON) -m shit_arm.control.wss \
		--port $(WS_PORT) \
		--host $(WS_HOST) \
		--backend $(WS_BACKEND) \
		--camera-index $(OPENCV_CAMERA_INDEX) \
		$(if $(ROBOT_PORT),--robot-port $(ROBOT_PORT),) \
		$(if $(ENABLE_PERCEPTION),--enable-perception,) \
		--vision-detector $(VISION_DETECTOR)

controller-state:
	$(PYTHON) -m shit_arm.cli run vision-monitor \
		--ticks 3 \
		--vision-detector mock \
		--controller-state-path $(CONTROLLER_STATE) \
		--controller-frame-path $(CONTROLLER_FRAME)

vision: vision-mock

vision-mock:
	$(PYTHON) -m shit_arm.cli run $(MODE) \
		--backend mock \
		--ticks $(TICKS) \
		--hz $(HZ) \
		--vision-detector $(VISION_DETECTOR) \
		--tracker-stable-after-frames $(TRACKER_STABLE_AFTER_FRAMES) \
		--tracker-max-missed-frames $(TRACKER_MAX_MISSED_FRAMES) \
		--selector-min-confidence $(SELECTOR_MIN_CONFIDENCE) \
		--foreground-min-area $(FOREGROUND_MIN_AREA) \
		--foreground-threshold $(FOREGROUND_THRESHOLD) \
		$(if $(HOMOGRAPHY_PATH),--homography-path $(HOMOGRAPHY_PATH),) \
		--controller-state-path $(CONTROLLER_STATE) \
		--controller-frame-path $(CONTROLLER_FRAME)

vision-lerobot:
	$(PYTHON) -m shit_arm.cli run $(MODE) \
		--backend lerobot \
		--robot-type $(ROBOT_TYPE) \
		--robot-port $(ROBOT_PORT) \
		--robot-id $(ROBOT_ID) \
		--teleop-type $(TELEOP_TYPE) \
		--teleop-port $(TELEOP_PORT) \
		--teleop-id $(TELEOP_ID) \
		--camera-key $(CAMERA_KEY) \
		--opencv-camera-index $(OPENCV_CAMERA_INDEX) \
		--opencv-camera-width $(OPENCV_CAMERA_WIDTH) \
		--opencv-camera-height $(OPENCV_CAMERA_HEIGHT) \
		--opencv-camera-fps $(OPENCV_CAMERA_FPS) \
		--ticks $(TICKS) \
		--hz $(HZ) \
		--vision-detector $(LEROBOT_VISION_DETECTOR) \
		--tracker-stable-after-frames $(TRACKER_STABLE_AFTER_FRAMES) \
		--tracker-max-missed-frames $(TRACKER_MAX_MISSED_FRAMES) \
		--selector-min-confidence $(SELECTOR_MIN_CONFIDENCE) \
		--foreground-min-area $(FOREGROUND_MIN_AREA) \
		--foreground-threshold $(FOREGROUND_THRESHOLD) \
		$(if $(HOMOGRAPHY_PATH),--homography-path $(HOMOGRAPHY_PATH),) \
		--controller-state-path $(CONTROLLER_STATE) \
		--controller-frame-path $(CONTROLLER_FRAME)

mirror-lerobot:
	$(PYTHON) -m shit_arm.cli run mirror \
		--backend lerobot \
		--robot-type $(ROBOT_TYPE) \
		--robot-port $(ROBOT_PORT) \
		--robot-id $(ROBOT_ID) \
		--teleop-type $(TELEOP_TYPE) \
		--teleop-port $(TELEOP_PORT) \
		--teleop-id $(TELEOP_ID) \
		--ticks $(TICKS) \
		--hz $(HZ)

diagnostics-lerobot:
	$(PYTHON) -m shit_arm.cli run diagnostics \
		--backend lerobot \
		--robot-type $(ROBOT_TYPE) \
		--robot-port $(ROBOT_PORT) \
		--robot-id $(ROBOT_ID) \
		--teleop-type $(TELEOP_TYPE) \
		--teleop-port $(TELEOP_PORT) \
		--teleop-id $(TELEOP_ID) \
		--ticks 1

clean:
	find . \( -name __pycache__ -o -name '*.pyc' \) -prune -exec rm -rf {} +
	rm -f $(CONTROLLER_STATE)
	rm -f $(CONTROLLER_FRAME) controller/latest-frame.svg
