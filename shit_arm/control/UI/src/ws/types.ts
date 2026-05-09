export interface Pose {
  x: number
  y: number
  z: number
  roll: number
  pitch: number
  yaw: number
}

export interface Point {
  x: number
  y: number
}

export interface RobotState {
  connected: boolean
  joints: number[]
  gripper: number
}

export interface CameraInfo {
  frame_id: number
  width: number
  height: number
}

export interface MotionEstimate {
  pixel_delta: number[]
  table_delta: number[]
  pixel_speed_per_frame: number
  table_speed_per_frame: number
  consistent: boolean
}

export interface TrackedObject {
  track_id: number
  label: string
  confidence: number
  status: string
  score: number
  target_bin: string | null
  bbox_xywh: number[]
  pixel: Point | null
  world: Pose | null
  motion: MotionEstimate | null
  age_frames: number
  missed_frames: number
  stable_frames: number
}

export interface PerceptionState {
  status: string
  selected_track_id: number | null
  tracks: TrackedObject[]
}

export interface SafetyState {
  ok: boolean
  estop: boolean
  faults: string[]
  warnings: string[]
}

export interface ArmState {
  type: "state"
  ts: number
  mode: string
  frameImageUrl: string | null
  robot: RobotState
  pose: Pose | null
  gripper_pixel: Point | null
  gripper_world: Pose | null
  camera: CameraInfo
  perception: PerceptionState
  safety: SafetyState
}

export type Command =
  | { type: "command"; cmd: "jog_joint"; joint: number; delta: number }
  | { type: "command"; cmd: "jog_cartesian"; axis: "x" | "y" | "z"; delta: number }
  | { type: "command"; cmd: "gripper"; position: number }
  | { type: "command"; cmd: "torque"; enabled: boolean }
  | { type: "command"; cmd: "home" }
  | { type: "command"; cmd: "stop" }
  | { type: "ping" }

export type WsMessage = ArmState | { type: "pong" }
