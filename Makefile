PYTHON ?= uv run python
UV ?= uv
NPM ?= npm

MODE ?= vision-monitor
TICKS ?= 999999
HZ ?= 10
VISION_DETECTOR ?= foreground
LEROBOT_VISION_DETECTOR ?= foreground
CONTROLLER_STATE ?= runs/controller-state.json
CONTROLLER_FRAME ?= runs/latest-frame.jpg
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
APP_VISION_DETECTOR ?= foreground

TRACKER_STABLE_AFTER_FRAMES ?= 3
TRACKER_MAX_MISSED_FRAMES ?= 8
SELECTOR_MIN_CONFIDENCE ?= 0.35
FOREGROUND_MIN_AREA ?= 250
FOREGROUND_THRESHOLD ?= 55

.PHONY: help install install-python install-ws install-bridge install-node test test-python test-js lint-js build-ui modes bridge app ui controller-state ws-server vision vision-lerobot mirror-lerobot diagnostics-lerobot clean clobber

help:
	@printf '%s\n' \
		'Targets:' \
		'  make install              Install WebSocket Python deps and Node deps' \
		'  make install-ws           Install Python deps including WebSocket server' \
		'  make install-bridge       Install Python deps including bridge tools' \
		'  make test                 Run Python tests and JS syntax checks' \
		'  make app                  Start real robot WebSocket server + React UI' \
		'  make ui                   Start only the React UI dev server' \
		'  make bridge               Show low-level servo bridge commands' \
		'  make controller-state     Write one real controller-state JSON snapshot' \
		'  make vision-lerobot       Run LeRobot vision with OpenCV camera' \
		'  make mirror-lerobot       Run LeRobot guide-arm mirror mode' \
		'  make diagnostics-lerobot  Run LeRobot diagnostics once' \
		'  make ws-server           Start the WebSocket server (standalone)' \
		'' \
		'Common variables:' \
		'  ROBOT_PORT=/dev/tty... TELEOP_PORT=/dev/tty...' \
		'  VISION_DETECTOR=color|foreground|yolo' \
		'  LEROBOT_VISION_DETECTOR=foreground|color|yolo' \
		'  TICKS=999999 HZ=10 OPENCV_CAMERA_INDEX=0' \
		'  WS_PORT=8765 WS_HOST=127.0.0.1' \
		'' \
		'Requires: uv (https://docs.astral.sh/uv/) and npm'

install: install-ws install-node

install-python:
	$(UV) sync --extra dev

install-ws:
	$(UV) sync --extra dev --extra ws

install-bridge:
	$(UV) sync --extra dev --extra bridge

install-node:
	$(NPM) install

test: test-python test-js

test-python:
	$(UV) run --extra dev pytest

test-js: lint-js

lint-js:
	$(NPM) test

build-ui:
	$(NPM) run build:ui

modes:
	$(PYTHON) -m shit_arm.cli modes

bridge:
	$(PYTHON) -m shit_arm.cli bridge --help

ui:
	$(NPM) run ui

app:
	@$(PYTHON) -m shit_arm.control.wss \
		--port $(WS_PORT) \
		--host $(WS_HOST) \
		--robot-port $(ROBOT_PORT) \
		--robot-type $(ROBOT_TYPE) \
		--robot-id $(ROBOT_ID) \
		--camera-index $(OPENCV_CAMERA_INDEX) \
		--enable-perception \
		--vision-detector $(APP_VISION_DETECTOR) \
		$(if $(HOMOGRAPHY_PATH),--homography-path $(HOMOGRAPHY_PATH),) & \
	WS_PID=$$!; \
	trap 'kill $$WS_PID 2>/dev/null || true' INT TERM EXIT; \
	$(NPM) run ui

ws-server:
	$(PYTHON) -m shit_arm.control.wss \
		--port $(WS_PORT) \
		--host $(WS_HOST) \
		--camera-index $(OPENCV_CAMERA_INDEX) \
		--robot-port $(ROBOT_PORT) \
		--robot-type $(ROBOT_TYPE) \
		--robot-id $(ROBOT_ID) \
		$(if $(ENABLE_PERCEPTION),--enable-perception,) \
		--vision-detector $(VISION_DETECTOR) \
		$(if $(HOMOGRAPHY_PATH),--homography-path $(HOMOGRAPHY_PATH),)

controller-state:
	$(PYTHON) -m shit_arm.cli run vision-monitor \
		--ticks 3 \
		--robot-type $(ROBOT_TYPE) \
		--robot-port $(ROBOT_PORT) \
		--robot-id $(ROBOT_ID) \
		$(if $(TELEOP_PORT),--teleop-type $(TELEOP_TYPE),) \
		$(if $(TELEOP_PORT),--teleop-port $(TELEOP_PORT),) \
		$(if $(TELEOP_PORT),--teleop-id $(TELEOP_ID),) \
		--camera-key $(CAMERA_KEY) \
		--opencv-camera-index $(OPENCV_CAMERA_INDEX) \
		--opencv-camera-width $(OPENCV_CAMERA_WIDTH) \
		--opencv-camera-height $(OPENCV_CAMERA_HEIGHT) \
		--opencv-camera-fps $(OPENCV_CAMERA_FPS) \
		--vision-detector $(LEROBOT_VISION_DETECTOR) \
		--controller-state-path $(CONTROLLER_STATE) \
		--controller-frame-path $(CONTROLLER_FRAME)

vision: vision-lerobot

vision-lerobot:
	$(PYTHON) -m shit_arm.cli run $(MODE) \
		--robot-type $(ROBOT_TYPE) \
		--robot-port $(ROBOT_PORT) \
		--robot-id $(ROBOT_ID) \
		$(if $(TELEOP_PORT),--teleop-type $(TELEOP_TYPE),) \
		$(if $(TELEOP_PORT),--teleop-port $(TELEOP_PORT),) \
		$(if $(TELEOP_PORT),--teleop-id $(TELEOP_ID),) \
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
		--robot-type $(ROBOT_TYPE) \
		--robot-port $(ROBOT_PORT) \
		--robot-id $(ROBOT_ID) \
		$(if $(TELEOP_PORT),--teleop-type $(TELEOP_TYPE),) \
		$(if $(TELEOP_PORT),--teleop-port $(TELEOP_PORT),) \
		$(if $(TELEOP_PORT),--teleop-id $(TELEOP_ID),) \
		--ticks 1

clean:
	find . \( -name __pycache__ -o -name '*.pyc' \) -prune -exec rm -rf {} +
	rm -f $(CONTROLLER_STATE)
	rm -f $(CONTROLLER_FRAME)

clobber: clean
	rm -rf node_modules shit_arm.egg-info .pytest_cache
	rm -rf shit_arm/control/UI/node_modules
	rm -rf shit_arm/control/UI/dist
