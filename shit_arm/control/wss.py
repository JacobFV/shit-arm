"""Standalone WebSocket server for arm state + video streaming."""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

os.environ.setdefault("OPENCV_AVFOUNDATION_SKIP_AUTH", "1")

try:
    import cv2
except ImportError:
    cv2 = None  # camera capture only available when opencv-python is installed

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from shit_arm.types import ArmState, Calibration, CameraFrame, MotionEstimate, PerceptionState, Pose, RobotCommand, TrackedObject
from shit_arm.perception import build_vision_pipeline, VisionConfig
from shit_arm.perception.calibration import load_projection_homography
from shit_arm.robot_model import URDF_PATH, load_robot_model


class ArmStateServer:
    def __init__(
        self,
        robot_port: str | None = None,
        robot_type: str = "so101_follower",
        robot_id: str = "shit_arm_follower",
        camera_index: int = 0,
        camera_width: int = 640,
        camera_height: int = 480,
        camera_fps: int = 30,
        enable_perception: bool = False,
        vision_detector: str = "foreground",
        homography_path: str | None = None,
        fps: int = 10,
        server_port: int = 8765,
    ):
        self.clients: set[WebSocket] = set()
        self._latest_state: dict | None = None
        self._running = False
        self._fps = fps
        self._robot_state: ArmState | None = None
        self._frame_id = 0
        self._server_port = server_port
        self._perception_state = PerceptionState(status="disabled")
        self.calibration = Calibration()

        if not robot_port:
            raise ValueError("robot_port is required")
        from shit_arm.hardware.lerobot_adapter import LeRobotFollowerArm
        self.robot = LeRobotFollowerArm(port=robot_port, robot_type=robot_type, robot_id=robot_id)

        self.cap: cv2.VideoCapture | None = None
        self._open_camera(camera_index, camera_width, camera_height, camera_fps)

        self.perception = None
        if enable_perception:
            vc = VisionConfig(detector_name=vision_detector)
            self.perception = build_vision_pipeline(vision_detector, vc)

        if homography_path:
            self.calibration.image_to_table_homography = load_projection_homography(Path(homography_path))

    def _open_camera(self, index: int, width: int, height: int, fps: int) -> None:
        if cv2 is None:
            print("[wss] opencv not installed; camera disabled")
            return
        try:
            cap = cv2.VideoCapture(index)
            if not cap.isOpened():
                print(f"[wss] camera {index} failed to open")
                return
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)
            self.cap = cap
            print(f"[wss] camera {index} opened ({width}x{height} @ {fps}fps)")
        except Exception as e:
            print(f"[wss] camera init error: {e}")

    def _capture_frame(self) -> tuple[Any | None, str | None]:
        if self.cap is None or cv2 is None:
            return None, None
        try:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                return None, None
            ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ok:
                return frame, None
            return frame, base64.b64encode(jpeg.tobytes()).decode()
        except Exception:
            return None, None

    def _build_state(self, jpeg_b64: str | None, camera_frame: CameraFrame | None = None) -> dict[str, Any]:
        robot_state = self._robot_state
        state: dict[str, Any] = {
            "type": "state",
            "ts": time.time(),
            "robot": {
                "connected": robot_state.connected if robot_state else False,
                "joints": list(robot_state.joints) if robot_state and robot_state.joints else [],
                "gripper": robot_state.gripper if robot_state else 0.0,
            },
            "pose": None,
            "gripper_pixel": None,
            "gripper_world": None,
            "camera": {
                "frame_id": camera_frame.frame_id if camera_frame else self._frame_id,
                "width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if self.cap and cv2 else 0,
                "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if self.cap and cv2 else 0,
            },
            "perception": _perception_dict(self._perception_state),
            "safety": {"ok": True, "estop": False, "faults": [], "warnings": []},
            "mode": "manual",
            "robot_model": _robot_model_dict(self._server_port),
        }

        if jpeg_b64:
            state["frameImageUrl"] = f"data:image/jpeg;base64,{jpeg_b64}"

        if robot_state and robot_state.pose:
            state["pose"] = {
                "x": robot_state.pose.x,
                "y": robot_state.pose.y,
                "z": robot_state.pose.z,
                "roll": robot_state.pose.roll,
                "pitch": robot_state.pose.pitch,
                "yaw": robot_state.pose.yaw,
            }

        return state

    def handle_command(self, cmd: dict) -> dict | None:
        cmd_type = cmd.get("cmd")
        if cmd_type == "jog_joint":
            joint = cmd.get("joint", 0)
            delta = cmd.get("delta", 0.0)
            if self._robot_state and self._robot_state.joints:
                joints = list(self._robot_state.joints)
                if 0 <= joint < len(joints):
                    joints[joint] += delta
                    self.robot.apply(RobotCommand.joints(tuple(joints), reason="jog"))
            return None

        elif cmd_type == "jog_cartesian":
            axis = cmd.get("axis", "x")
            delta = cmd.get("delta", 0.01)
            current = self._robot_state.pose if self._robot_state and self._robot_state.pose else Pose(0, 0, 0, 0, 0, 0)
            target = Pose(
                x=current.x + (delta if axis == "x" else 0),
                y=current.y + (delta if axis == "y" else 0),
                z=current.z + (delta if axis == "z" else 0),
                roll=current.roll,
                pitch=current.pitch,
                yaw=current.yaw,
            )
            self.robot.apply(RobotCommand.pose(target, reason="cartesian jog"))
            return None

        elif cmd_type == "gripper":
            position = cmd.get("position", 0.0)
            self.robot.apply(RobotCommand.gripper_to(position, reason="gripper"))
            return None

        elif cmd_type == "torque":
            enabled = cmd.get("enabled", False)
            return {"status": "ok", "cmd": "torque", "enabled": enabled}

        elif cmd_type == "home":
            self.robot.apply(RobotCommand.home(reason="manual home"))
            return None

        elif cmd_type == "stop":
            self.robot.apply(RobotCommand.stop(reason="manual stop"))
            return None

        return {"status": "unknown_cmd", "cmd": cmd_type}

    async def _broadcast_loop(self):
        while self._running:
            self._robot_state = await asyncio.to_thread(self.robot.read_state)
            frame, jpeg_b64 = await asyncio.to_thread(self._capture_frame)
            camera_frame = None
            if frame is not None:
                self._frame_id += 1
                height, width = frame.shape[:2]
                if cv2 is not None:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                else:
                    frame_rgb = frame
                camera_frame = CameraFrame(frame_id=self._frame_id, width=width, height=height, payload=frame_rgb)
                if self.perception:
                    self._perception_state = self.perception.update(camera_frame, self.calibration)
            elif self.perception:
                self._perception_state = PerceptionState(status="camera_missing")
            state = self._build_state(jpeg_b64, camera_frame)
            self._latest_state = state

            if self.clients:
                dead: set[WebSocket] = set()
                msg = json.dumps(state)
                for ws in self.clients:
                    try:
                        await ws.send_text(msg)
                    except Exception:
                        dead.add(ws)
                if dead:
                    self.clients -= dead

            await asyncio.sleep(1.0 / self._fps)

    def start(self):
        self._running = True

    def stop(self):
        self._running = False
        if self.cap:
            self.cap.release()

    @property
    def loop_task(self) -> asyncio.Task | None:
        return getattr(self, "_task", None)

    @loop_task.setter
    def loop_task(self, task: asyncio.Task | None):
        self._task = task


state_server: ArmStateServer | None = None


def _build_server(port: int, **kwargs) -> FastAPI:
    global state_server
    state_server = ArmStateServer(server_port=port, **kwargs)

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        if state_server:
            state_server.start()
            state_server.loop_task = asyncio.create_task(state_server._broadcast_loop())
        yield
        if state_server:
            state_server.stop()
            if state_server.loop_task:
                state_server.loop_task.cancel()

    app = FastAPI(title="shit-arm WS Server", lifespan=_lifespan)
    app.mount("/robot-assets", StaticFiles(directory=URDF_PATH.parent), name="robot-assets")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        if state_server is None:
            await ws.close(code=1011, reason="server not initialized")
            return
        await ws.accept()
        state_server.clients.add(ws)
        if state_server._latest_state:
            await ws.send_json(state_server._latest_state)
        try:
            while True:
                data = await ws.receive_text()
                msg = json.loads(data)
                if msg.get("type") == "command":
                    state_server.handle_command(msg)
                elif msg.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
        except WebSocketDisconnect:
            state_server.clients.discard(ws)
        except Exception:
            state_server.clients.discard(ws)

    @app.get("/health")
    def health():
        return {"status": "ok", "clients": len(state_server.clients) if state_server else 0}

    return app


def _robot_model_dict(port: int) -> dict[str, Any]:
    model = dict(load_robot_model())
    model["asset_base_url"] = f"http://127.0.0.1:{port}/robot-assets"
    return model


def _perception_dict(perception: PerceptionState) -> dict[str, Any]:
    return {
        "status": perception.status,
        "selected_track_id": perception.selected_track_id,
        "tracks": [_track_dict(track) for track in perception.tracks],
    }


def _track_dict(track: TrackedObject) -> dict[str, Any]:
    return {
        "track_id": track.track_id,
        "label": track.label,
        "confidence": track.confidence,
        "status": track.status.value,
        "score": track.score,
        "target_bin": track.target_bin,
        "pixel": _point_dict(track.pixel_centroid),
        "previous_pixel": _point_dict(track.previous_pixel_centroid),
        "world": _pose_dict(track.table_pose),
        "previous_world": _pose_dict(track.previous_table_pose),
        "bbox_xywh": track.smoothed_bbox_xywh,
        "age_frames": track.age_frames,
        "missed_frames": track.missed_frames,
        "stable_frames": track.stable_frames,
        "motion": _motion_dict(track.motion),
    }


def _motion_dict(motion: MotionEstimate | None) -> dict[str, Any] | None:
    if motion is None:
        return None
    return {
        "pixel_delta": motion.pixel_delta,
        "table_delta": motion.table_delta,
        "projected_table_delta": motion.projected_table_delta,
        "table_delta_error": motion.table_delta_error,
        "pixel_speed_per_frame": motion.pixel_speed_per_frame,
        "table_speed_per_frame": motion.table_speed_per_frame,
        "frame_delta": motion.frame_delta,
        "consistent": motion.consistent,
    }


def _pose_dict(pose: Pose | None) -> dict[str, float] | None:
    if pose is None:
        return None
    return {
        "x": pose.x,
        "y": pose.y,
        "z": pose.z,
        "roll": pose.roll,
        "pitch": pose.pitch,
        "yaw": pose.yaw,
    }


def _point_dict(point: tuple[float, float] | None) -> dict[str, float] | None:
    if point is None:
        return None
    return {"x": point[0], "y": point[1]}


def main() -> None:
    parser = argparse.ArgumentParser(description="shit-arm WebSocket server")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket server port")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--robot-port", required=True, help="Serial port for LeRobot follower")
    parser.add_argument("--robot-type", default="so101_follower")
    parser.add_argument("--robot-id", default="shit_arm_follower")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--camera-width", type=int, default=640)
    parser.add_argument("--camera-height", type=int, default=480)
    parser.add_argument("--camera-fps", type=int, default=30)
    parser.add_argument("--fps", type=int, default=10, help="Broadcast rate")
    parser.add_argument("--vision-detector", choices=["color", "foreground", "yolo"], default="foreground")
    parser.add_argument("--homography-path")
    parser.add_argument("--enable-perception", action="store_true")

    args = parser.parse_args()
    kwargs = {
        "robot_port": args.robot_port,
        "robot_type": args.robot_type,
        "robot_id": args.robot_id,
        "camera_index": args.camera_index,
        "camera_width": args.camera_width,
        "camera_height": args.camera_height,
        "camera_fps": args.camera_fps,
        "enable_perception": args.enable_perception,
        "vision_detector": args.vision_detector,
        "homography_path": args.homography_path,
        "fps": args.fps,
    }

    app = _build_server(args.port, **kwargs)

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
