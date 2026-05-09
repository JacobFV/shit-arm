"""SO-101 Robot API: arms over Feetech bus + webcam (ArUco + Gemini) + IK."""
from __future__ import annotations

import os
# must come before importing cv2: skip macOS camera auth dialog from background thread
os.environ.setdefault("OPENCV_AVFOUNDATION_SKIP_AUTH", "1")

import asyncio
import json
import math
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from ikpy.chain import Chain
from pydantic import BaseModel, Field
from scservo_sdk import COMM_SUCCESS, PacketHandler, PortHandler

# ---- config ----------------------------------------------------------------

BAUD = 1_000_000

ARM_PORTS = {
    "right": "/dev/cu.usbmodem5B140339331",   # full arm
    "left":  "/dev/cu.usbmodem5B140340801",   # partial arm (id=1,3 dead)
}

URDF_PATH = "/Users/owner/code/robot/urdf/so101_new_calib.urdf"
CAMERA_INDEX = 0
ARUCO_DICT = cv2.aruco.DICT_4X4_50

# STS3215 control table
ADDR_TORQUE_ENABLE   = 40
ADDR_GOAL_POSITION   = 42
ADDR_GOAL_SPEED      = 46
ADDR_PRESENT_POS     = 56
ADDR_PRESENT_LOAD    = 60
ADDR_PRESENT_VOLTAGE = 62
ADDR_PRESENT_TEMP    = 63

JOINT_ID = {
    "shoulder_pan":  1,
    "shoulder_lift": 2,
    "elbow_flex":    3,
    "wrist_flex":    4,
    "wrist_roll":    5,
    "gripper":       6,
}
ID_JOINT = {v: k for k, v in JOINT_ID.items()}

# 4096 ticks per full revolution; servo center = 2048 = 0 rad
TICKS_PER_RAD = 4096 / (2 * math.pi)


def rad_to_ticks(rad: float) -> int:
    return int(round(2048 + rad * TICKS_PER_RAD))


def ticks_to_rad(ticks: int) -> float:
    return (ticks - 2048) / TICKS_PER_RAD


# ---- bus -------------------------------------------------------------------

class Bus:
    def __init__(self, path: str):
        self.path = path
        self.port: Optional[PortHandler] = None
        self.pk = PacketHandler(0)
        self.lock = threading.Lock()
        self._open()

    def _open(self):
        try:
            self.port = PortHandler(self.path)
            if not self.port.openPort():
                self.port = None
                return
            self.port.setBaudRate(BAUD)
        except Exception:
            self.port = None

    def call(self, fn):
        with self.lock:
            for _ in range(2):
                if self.port is None:
                    self._open()
                    if self.port is None:
                        continue
                try:
                    return fn(self.port, self.pk)
                except Exception:
                    try:
                        self.port.closePort()
                    except Exception:
                        pass
                    self.port = None
            raise HTTPException(503, f"bus {self.path} unavailable")


buses: dict[str, Bus] = {}


# ---- calibration ----------------------------------------------------------
# JSON shape: {arm_name: {joint_name: {"min": int, "max": int}}}

CAL_PATH = Path(__file__).parent / "calibration.json"
_cal_lock = threading.Lock()


def _load_calibration() -> dict:
    if not CAL_PATH.exists():
        return {}
    try:
        return json.loads(CAL_PATH.read_text())
    except Exception as e:
        print(f"[cal] failed to load {CAL_PATH}: {e}; starting empty")
        return {}


def _save_calibration(data: dict) -> None:
    tmp = CAL_PATH.with_name(CAL_PATH.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(CAL_PATH)


calibration: dict = _load_calibration()


def _limits(arm: str, joint: str) -> tuple[int, int]:
    """Return (lo, hi) ticks. Defaults to full 0..4095 if uncalibrated."""
    j = calibration.get(arm, {}).get(joint, {})
    lo = j.get("min", 0)
    hi = j.get("max", 4095)
    if lo > hi:
        lo, hi = hi, lo
    return max(0, lo), min(4095, hi)


def _clamp(arm: str, joint: str, pos: int) -> int:
    lo, hi = _limits(arm, joint)
    return max(lo, min(hi, int(pos)))


# ---- vision ---------------------------------------------------------------

class VisionCapture:
    """Background webcam capture with ArUco detection."""

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
        self.aruco_params = cv2.aruco.DetectorParameters()
        try:
            self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
            self._new_api = True
        except AttributeError:
            self.detector = None
            self._new_api = False

        self.cap: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()
        self._frame_w = 0
        self._frame_h = 0
        self._fps = 0.0
        self._latest_jpeg: Optional[bytes] = None
        self._latest_detections: list[dict] = []
        self._latest_ts: float = 0.0
        self._error: Optional[str] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._running:
            return
        # open the camera on the calling thread (main thread during app startup)
        # so macOS authorization dialog runs on the main run loop
        if not self._open_cap():
            print(f"[vision] camera open failed: {self._error}")
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self.cap:
            self.cap.release()

    def _open_cap(self) -> bool:
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                self._error = f"camera {self.camera_index} could not be opened"
                return False
            self._frame_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self._frame_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self._error = None
            return True
        except Exception as e:
            self._error = str(e)
            return False

    def _detect(self, frame):
        if self._new_api:
            corners, ids, _ = self.detector.detectMarkers(frame)
        else:
            corners, ids, _ = cv2.aruco.detectMarkers(frame, self.aruco_dict, parameters=self.aruco_params)
        return corners, ids

    def _loop(self):
        last_t = time.time()
        frame_count = 0
        while self._running:
            ok, frame = self.cap.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue

            corners, ids = self._detect(frame)
            detections = []
            if ids is not None and len(ids) > 0:
                for i, mid in enumerate(ids.flatten()):
                    c = corners[i][0]
                    cx = float(c[:, 0].mean())
                    cy = float(c[:, 1].mean())
                    detections.append({
                        "id": int(mid),
                        "center": [cx, cy],
                        "corners": c.tolist(),
                    })
                cv2.aruco.drawDetectedMarkers(frame, corners, ids)

            ok2, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            now = time.time()
            frame_count += 1
            if now - last_t >= 1.0:
                fps = frame_count / (now - last_t)
                last_t = now
                frame_count = 0
            else:
                fps = self._fps

            with self._lock:
                self._latest_jpeg = jpeg.tobytes() if ok2 else None
                self._latest_detections = detections
                self._latest_ts = now
                self._fps = fps

    def info(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "camera_index": self.camera_index,
                "frame_w": self._frame_w,
                "frame_h": self._frame_h,
                "fps": round(self._fps, 1),
                "error": self._error,
                "ts": self._latest_ts,
            }

    def latest_detections(self) -> list[dict]:
        with self._lock:
            return list(self._latest_detections)

    def latest_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_jpeg


vision = VisionCapture(CAMERA_INDEX)


# ---- gemini ---------------------------------------------------------------

def gemini_client():
    try:
        from google import genai
    except Exception:
        return None
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    return genai.Client(api_key=key)


# ---- IK -------------------------------------------------------------------

class Kinematics:
    def __init__(self, urdf_path: str):
        self.chain = Chain.from_urdf_file(urdf_path)
        self.joint_links = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
        self.lock = threading.Lock()

    def fk(self, ticks: dict[str, int]) -> tuple[float, float, float]:
        angles = np.zeros(len(self.chain.links))
        for i, link in enumerate(self.chain.links):
            if link.name in ticks:
                angles[i] = ticks_to_rad(ticks[link.name])
        m = self.chain.forward_kinematics(angles)
        return float(m[0, 3]), float(m[1, 3]), float(m[2, 3])

    def ik(self, x: float, y: float, z: float, seed_ticks: Optional[dict[str, int]] = None) -> dict[str, int]:
        with self.lock:
            initial = np.zeros(len(self.chain.links))
            if seed_ticks:
                for i, link in enumerate(self.chain.links):
                    if link.name in seed_ticks:
                        initial[i] = ticks_to_rad(seed_ticks[link.name])
            sol = self.chain.inverse_kinematics(
                target_position=np.array([x, y, z]),
                initial_position=initial,
            )
            out = {}
            for i, link in enumerate(self.chain.links):
                if link.name in self.joint_links:
                    out[link.name] = rad_to_ticks(float(sol[i]))
            return out


kin = Kinematics(URDF_PATH)


# ---- lifespan -------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    for name, path in ARM_PORTS.items():
        buses[name] = Bus(path)
        print(f"[init] arm {name!r} -> {path} (open={buses[name].port is not None})")
    print(f"[init] kinematics chain: {len(kin.chain.links)} links")
    vision.start()
    print(f"[init] vision started on camera {CAMERA_INDEX}")
    yield
    vision.stop()
    for b in buses.values():
        try:
            if b.port:
                b.port.closePort()
        except Exception:
            pass


app = FastAPI(title="SO-101 Robot API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- helpers --------------------------------------------------------------

def _arm(arm: str) -> Bus:
    if arm not in buses:
        raise HTTPException(404, f"unknown arm {arm!r}; have {list(buses)}")
    return buses[arm]


def _scan(port, pk):
    out = {}
    for sid, name in ID_JOINT.items():
        _, comm, _ = pk.ping(port, sid)
        if comm != COMM_SUCCESS:
            continue
        pos, _, _  = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
        volt, _, _ = pk.read1ByteTxRx(port, sid, ADDR_PRESENT_VOLTAGE)
        temp, _, _ = pk.read1ByteTxRx(port, sid, ADDR_PRESENT_TEMP)
        load, _, _ = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_LOAD)
        out[name] = {
            "id": sid, "position": pos,
            "voltage": round(volt / 10, 2),
            "temperature": temp, "load": load,
        }
    return out


def _read_positions(port, pk):
    out = {}
    for sid, name in ID_JOINT.items():
        pos, comm, _ = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
        if comm == COMM_SUCCESS:
            out[name] = pos
    return out


# ---- request models -------------------------------------------------------

class MoveRequest(BaseModel):
    joint: str
    position: int = Field(..., ge=0, le=4095)
    speed: int = Field(500, ge=0, le=4095)
    torque: bool = True


class TorqueRequest(BaseModel):
    enabled: bool


class MoveAllRequest(BaseModel):
    positions: dict[str, int]
    speed: int = 500


class ReachRequest(BaseModel):
    x: float
    y: float
    z: float
    speed: int = Field(500, ge=0, le=4095)
    execute: bool = Field(True, description="if false, return joint angles without sending")


class AskRequest(BaseModel):
    question: str
    model: str = "gemini-2.0-flash-exp"


class CalibrateRequest(BaseModel):
    slot: str = Field(..., description="'min' or 'max'")


# ---- arm routes -----------------------------------------------------------

@app.get("/")
def root():
    return {
        "service": "so-101 robot api",
        "arms": list(buses.keys()),
        "joints": list(JOINT_ID.keys()),
        "vision": vision.info(),
        "endpoints": {
            "arms":    ["GET /arms", "GET /arms/{arm}/scan", "GET /arms/{arm}/positions",
                        "POST /arms/{arm}/move", "POST /arms/{arm}/move_all",
                        "POST /arms/{arm}/torque", "POST /arms/{arm}/reach",
                        "WS /arms/{arm}/stream"],
            "calibration": ["GET /arms/{arm}/calibration",
                            "POST /arms/{arm}/calibrate/{joint}  {slot: 'min'|'max'}",
                            "DELETE /arms/{arm}/calibrate/{joint}"],
            "vision":  ["GET /vision/info", "GET /vision/latest", "GET /video.mjpg",
                        "WS /vision/stream", "POST /vision/ask"],
            "ik":      ["POST /ik/solve", "POST /ik/forward"],
        },
    }


@app.get("/arms")
def list_arms():
    return [
        {"name": n, "path": b.path, "connected": b.port is not None}
        for n, b in buses.items()
    ]


@app.get("/arms/{arm}/scan")
async def scan_arm(arm: str):
    return await asyncio.to_thread(_arm(arm).call, _scan)


@app.get("/arms/{arm}/positions")
async def positions(arm: str):
    return await asyncio.to_thread(_arm(arm).call, _read_positions)


@app.post("/arms/{arm}/move")
async def move_joint(arm: str, req: MoveRequest):
    sid = JOINT_ID.get(req.joint)
    if sid is None:
        raise HTTPException(400, f"unknown joint {req.joint!r}")
    goal = _clamp(arm, req.joint, req.position)

    def _do(port, pk):
        pk.write2ByteTxRx(port, sid, ADDR_GOAL_SPEED, req.speed)
        if req.torque:
            pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 1)
        pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, goal)
        return {
            "joint": req.joint, "id": sid, "goal": goal,
            "requested": req.position, "clamped": goal != req.position,
        }

    return await asyncio.to_thread(_arm(arm).call, _do)


@app.post("/arms/{arm}/move_all")
async def move_all(arm: str, req: MoveAllRequest):
    targets: list[tuple[int, str, int, int]] = []  # (sid, name, requested, goal)
    for name, pos in req.positions.items():
        sid = JOINT_ID.get(name)
        if sid is None:
            raise HTTPException(400, f"unknown joint {name!r}")
        targets.append((sid, name, int(pos), _clamp(arm, name, pos)))

    def _do(port, pk):
        for sid, _, _, _ in targets:
            pk.write2ByteTxRx(port, sid, ADDR_GOAL_SPEED, req.speed)
            pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 1)
        for sid, _, _, goal in targets:
            pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, goal)
        return {
            "sent":      {n: g for _, n, _, g in targets},
            "requested": {n: r for _, n, r, _ in targets},
            "clamped":   [n for _, n, r, g in targets if r != g],
        }

    return await asyncio.to_thread(_arm(arm).call, _do)


@app.post("/arms/{arm}/torque")
async def torque(arm: str, req: TorqueRequest):
    def _do(port, pk):
        affected = []
        for sid in JOINT_ID.values():
            _, comm, _ = pk.ping(port, sid)
            if comm == COMM_SUCCESS:
                pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 1 if req.enabled else 0)
                affected.append(ID_JOINT[sid])
        return {"enabled": req.enabled, "joints": affected}

    return await asyncio.to_thread(_arm(arm).call, _do)


@app.get("/arms/{arm}/calibration")
def get_calibration(arm: str):
    _arm(arm)
    cal = calibration.get(arm, {})
    out = {}
    for joint in JOINT_ID:
        j = cal.get(joint, {})
        lo, hi = _limits(arm, joint)
        out[joint] = {
            "min":         j.get("min"),
            "max":         j.get("max"),
            "calibrated":  "min" in j and "max" in j,
            "effective":   {"lo": lo, "hi": hi},
        }
    return out


@app.post("/arms/{arm}/calibrate/{joint}")
async def calibrate_joint(arm: str, joint: str, req: CalibrateRequest):
    b = _arm(arm)
    sid = JOINT_ID.get(joint)
    if sid is None:
        raise HTTPException(400, f"unknown joint {joint!r}")
    if req.slot not in ("min", "max"):
        raise HTTPException(400, "slot must be 'min' or 'max'")

    def _read(port, pk):
        pos, comm, _ = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
        if comm != COMM_SUCCESS:
            raise HTTPException(503, f"could not read {joint} position")
        return pos

    pos = await asyncio.to_thread(b.call, _read)
    with _cal_lock:
        calibration.setdefault(arm, {}).setdefault(joint, {})[req.slot] = pos
        _save_calibration(calibration)
        snapshot = dict(calibration[arm][joint])
    return {
        "arm": arm, "joint": joint, "slot": req.slot,
        "captured": pos, "calibration": snapshot,
    }


@app.delete("/arms/{arm}/calibrate/{joint}")
def clear_calibration(arm: str, joint: str):
    _arm(arm)
    if joint not in JOINT_ID:
        raise HTTPException(400, f"unknown joint {joint!r}")
    with _cal_lock:
        if arm in calibration and joint in calibration[arm]:
            del calibration[arm][joint]
            _save_calibration(calibration)
    return {"arm": arm, "joint": joint, "cleared": True}


@app.post("/arms/{arm}/reach")
async def reach(arm: str, req: ReachRequest):
    """Solve IK to (x, y, z) in robot base frame, optionally execute on arm."""
    seed = await asyncio.to_thread(_arm(arm).call, _read_positions)
    target_ticks = await asyncio.to_thread(kin.ik, req.x, req.y, req.z, seed)

    if not req.execute:
        return {"target_xyz": [req.x, req.y, req.z], "ticks": target_ticks, "executed": False}

    targets = [(JOINT_ID[name], name, _clamp(arm, name, t)) for name, t in target_ticks.items()]
    sent = {name: goal for _, name, goal in targets}
    clamped_joints = [name for _, name, goal in targets if goal != target_ticks[name]]

    def _do(port, pk):
        for sid, _, _ in targets:
            pk.write2ByteTxRx(port, sid, ADDR_GOAL_SPEED, req.speed)
            pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 1)
        for sid, _, goal in targets:
            pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, goal)
        return {
            "target_xyz": [req.x, req.y, req.z],
            "ticks": target_ticks, "sent": sent,
            "clamped": clamped_joints, "executed": True,
        }

    return await asyncio.to_thread(_arm(arm).call, _do)


@app.websocket("/arms/{arm}/stream")
async def stream_positions(ws: WebSocket, arm: str):
    if arm not in buses:
        await ws.close(code=1008); return
    b = buses[arm]
    await ws.accept()
    try:
        while True:
            try:
                data = await asyncio.to_thread(b.call, _read_positions)
            except HTTPException as e:
                await ws.send_json({"error": e.detail})
                await asyncio.sleep(0.5); continue
            await ws.send_json(data)
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        return


# ---- ik routes ------------------------------------------------------------

@app.post("/ik/solve")
async def ik_solve(req: ReachRequest):
    seed = None
    if "right" in buses:
        try:
            seed = await asyncio.to_thread(buses["right"].call, _read_positions)
        except Exception:
            pass
    ticks = await asyncio.to_thread(kin.ik, req.x, req.y, req.z, seed)
    return {"target_xyz": [req.x, req.y, req.z], "ticks": ticks}


class FKRequest(BaseModel):
    ticks: dict[str, int]


@app.post("/ik/forward")
def ik_forward(req: FKRequest):
    x, y, z = kin.fk(req.ticks)
    return {"xyz": [x, y, z]}


# ---- vision routes --------------------------------------------------------

@app.get("/vision/info")
def vision_info():
    return vision.info()


@app.get("/vision/latest")
def vision_latest():
    return {
        "info": vision.info(),
        "detections": vision.latest_detections(),
    }


@app.get("/video.mjpg")
def video_mjpg():
    boundary = b"--frame"

    def gen():
        while True:
            jpeg = vision.latest_jpeg()
            if jpeg:
                yield boundary + b"\r\nContent-Type: image/jpeg\r\nContent-Length: " \
                      + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n"
            time.sleep(0.05)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.websocket("/vision/stream")
async def vision_stream(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_json({
                "info": vision.info(),
                "detections": vision.latest_detections(),
            })
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        return


@app.post("/vision/ask")
async def vision_ask(req: AskRequest):
    client = gemini_client()
    if client is None:
        raise HTTPException(503, "Gemini unavailable: install google-genai and set GEMINI_API_KEY")
    jpeg = vision.latest_jpeg()
    if jpeg is None:
        raise HTTPException(503, "no frame available yet")

    def _ask():
        from google.genai import types as gtypes
        return client.models.generate_content(
            model=req.model,
            contents=[
                gtypes.Part.from_bytes(data=jpeg, mime_type="image/jpeg"),
                req.question,
            ],
        )

    resp = await asyncio.to_thread(_ask)
    return {
        "question": req.question,
        "answer": getattr(resp, "text", str(resp)),
        "detections": vision.latest_detections(),
    }
