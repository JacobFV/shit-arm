import { useState, useCallback } from 'react'
import { JointRow } from './components/JointRow'
import { CartesianPad } from './components/CartesianPad'
import { JointCurrentChart } from './components/JointCurrentChart'
import { useArmWebSocket } from './ws/useArmWebSocket'
import type { TrackedObject } from './ws/types'
import './App.css'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8765/ws'

const TABS = ['Move', 'Log', 'Teach', 'Setup'] as const
type Tab = (typeof TABS)[number]

const SPEED_PRESETS = ['Slow', 'Default', 'Fast'] as const
type SpeedPreset = (typeof SPEED_PRESETS)[number]

const JOINT_NAMES = [
  'Base',
  'Shoulder',
  'Elbow',
  'Wrist 1',
  'Wrist 2',
  'Wrist 3',
] as const

function fmt(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '-'
  return Number(v).toFixed(3)
}

function indent(text: string): string {
  return text.split('\n').map((l) => `  ${l}`).join('\n')
}

function fmtMotion(t: TrackedObject): string {
  const m = t.motion
  if (!m) return '-'
  const pd = m.pixel_delta || []
  const td = m.table_delta || []
  return `pixel dx: ${fmt(pd[0])}
pixel dy: ${fmt(pd[1])}
world dx: ${fmt(td[0])}
world dy: ${fmt(td[1])}
world dz: ${fmt(td[2])}
pixel speed/frame: ${fmt(m.pixel_speed_per_frame)}
world speed/frame: ${fmt(m.table_speed_per_frame)}
consistent: ${m.consistent}`
}

function fmtPose(p: { x: number; y: number; z: number; roll: number; pitch: number; yaw: number } | null): string {
  if (!p) return '-'
  return `x: ${fmt(p.x)}
y: ${fmt(p.y)}
z: ${fmt(p.z)}
roll: ${fmt(p.roll)}
pitch: ${fmt(p.pitch)}
yaw: ${fmt(p.yaw)}`
}

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('Move')
  const [speedPreset, setSpeedPreset] = useState<SpeedPreset>('Default')
  const [acceleration, setAcceleration] = useState(45)
  const [speed, setSpeed] = useState(25)
  const [enabled, setEnabled] = useState(false)

  const { state, connected, sendCommand } = useArmWebSocket(WS_URL)

  const handleJogJoint = useCallback(
    (joint: number, delta: number) => {
      sendCommand({ type: 'command', cmd: 'jog_joint', joint, delta })
    },
    [sendCommand],
  )

  const handleJogCartesian = useCallback(
    (axis: 'x' | 'y' | 'z', delta: number) => {
      sendCommand({ type: 'command', cmd: 'jog_cartesian', axis, delta })
    },
    [sendCommand],
  )

  const handleGripper = useCallback(
    (position: number) => {
      sendCommand({ type: 'command', cmd: 'gripper', position })
    },
    [sendCommand],
  )

  const handleTorque = useCallback(
    (on: boolean) => {
      sendCommand({ type: 'command', cmd: 'torque', enabled: on })
      setEnabled(on)
    },
    [sendCommand],
  )

  const robot = state?.robot
  const pose = state?.pose
  const safety = state?.safety
  const tracks = state?.perception?.tracks || []

  return (
    <div className="app">
      <header className="titlebar">
        <span className="titlebar__title">ARM control</span>
        <span className={`connection-pill ${connected ? 'connected' : ''}`}>
          {connected ? 'connected' : 'disconnected'}
        </span>
      </header>

      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={activeTab === t}
            className={`tab ${activeTab === t ? 'tab--active' : ''}`}
            onClick={() => setActiveTab(t)}
          >
            {t}
          </button>
        ))}
        <div className="tabs__spacer" />
        <span className="safety-pill" data-ok={safety?.ok}>
          {safety?.ok ? 'safe' : 'fault'}
        </span>
      </nav>

      <section className="toolbar">
        <div className="toolbar__group">
          <div className="toolbar__group-title">Speed settings</div>
          <div className="toolbar__presets">
            {SPEED_PRESETS.map((p) => (
              <button
                key={p}
                type="button"
                className={`preset ${
                  speedPreset === p ? 'preset--active' : ''
                }`}
                onClick={() => setSpeedPreset(p)}
              >
                {p}
              </button>
            ))}
          </div>
          <pre className="toolbar__placeholder" aria-hidden="true">
            ####{'\n'}####
          </pre>
        </div>

        <div className="toolbar__slider">
          <label htmlFor="accel">Acceleration {acceleration}%</label>
          <input
            id="accel"
            type="range"
            min={0}
            max={100}
            value={acceleration}
            onChange={(e) => setAcceleration(Number(e.target.value))}
          />
          <div className="toolbar__slider-value">{acceleration}</div>
        </div>

        <div className="toolbar__slider">
          <label htmlFor="speed">Speed {speed}%</label>
          <input
            id="speed"
            type="range"
            min={0}
            max={100}
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
          />
          <div className="toolbar__slider-value">{speed}</div>
        </div>

        <button type="button" className="set-btn">
          Set
        </button>
      </section>

      <section className="joints">
        {JOINT_NAMES.map((name, i) => (
          <JointRow
            key={name}
            name={name}
            speed={0.4006}
            acceleration={2.2778}
            radians={robot?.joints?.[i] ?? 0}
            degree={robot?.joints?.[i] !== undefined ? robot.joints[i] * (180 / Math.PI) : 0}
            encoder={0}
            current={0.0}
            temperature={0}
            progress={0.5}
            onJogMinus={() => handleJogJoint(i, -0.05)}
            onJogPlus={() => handleJogJoint(i, 0.05)}
          />
        ))}
      </section>

      <section className="center-pad">
        <div className="video-frame">
          {state?.frameImageUrl ? (
            <img src={state.frameImageUrl} alt="Camera frame" className="video-frame__img" />
          ) : (
            <div className="video-frame__placeholder">no camera frame</div>
          )}
        </div>
        <CartesianPad onJog={(axis) => {
          const d = axis.endsWith('+') ? 0.01 : -0.01
          const a = axis[0].toLowerCase() as 'x' | 'y' | 'z'
          handleJogCartesian(a, d)
        }} />
      </section>

      <aside className="side">
        <div className="side__info">
          <div className="info-row"><span className="info-label">Mode</span><span>{state?.mode || '-'}</span></div>
          <div className="info-row"><span className="info-label">Connected</span><span>{robot?.connected ? 'yes' : 'no'}</span></div>
          <div className="info-row"><span className="info-label">Frame</span><span>{state?.camera?.frame_id ?? '-'}</span></div>
        </div>

        <div className="tool-position">
          <h3>Tool position:</h3>
          <div className="tool-position__grid">
            <span>X: {fmt(pose?.x)}</span>
            <span>Base: {fmt(robot?.joints?.[0])}</span>
            <span>Y: {fmt(pose?.y)}</span>
            <span>Shoulder: {fmt(robot?.joints?.[1])}</span>
            <span>Z: {fmt(pose?.z)}</span>
            <span>Elbow: {fmt(robot?.joints?.[2])}</span>
            <span>roll: {fmt(pose?.roll)}</span>
            <span>Wrist 1: {fmt(robot?.joints?.[3])}</span>
            <span>pitch: {fmt(pose?.pitch)}</span>
            <span>Wrist 2: {fmt(robot?.joints?.[4])}</span>
            <span>yaw: {fmt(pose?.yaw)}</span>
            <span>Wrist 3: {fmt(robot?.joints?.[5])}</span>
          </div>
        </div>

        <button
          type="button"
          className={`enable-btn ${enabled ? 'enable-btn--on' : ''}`}
          onClick={() => handleTorque(!enabled)}
          aria-pressed={enabled}
        >
          <span className="enable-btn__text">
            {'Enable'.split('').map((c, i) => (
              <span key={i}>{c}</span>
            ))}
          </span>
        </button>

        <button type="button" className="ghost-btn">
          Clear error
        </button>

        <div className="grippers">
          <button type="button" className="ghost-btn" onClick={() => handleGripper(0)}>
            Close gripper
          </button>
          <button type="button" className="ghost-btn" onClick={() => handleGripper(1)}>
            Open gripper
          </button>
        </div>

        <div className="track-list">
          <h3>Objects ({tracks.length})</h3>
          {tracks.map((t) => (
            <div key={t.track_id} className="track-card">
              <div className="track-card__head">
                <span className="track-card__title">#{t.track_id} {t.label}</span>
                <span className="track-card__status">{t.status}</span>
              </div>
              <pre className="track-card__body">
bin: {t.target_bin || '-'}
confidence: {fmt(t.confidence)}
score: {fmt(t.score)}
pixel:
{indent(t.pixel ? `${fmt(t.pixel.x)}, ${fmt(t.pixel.y)}` : '-')}
world:
{indent(fmtPose(t.world))}
motion:
{indent(fmtMotion(t))}
              </pre>
            </div>
          ))}
        </div>

        <JointCurrentChart />
      </aside>
    </div>
  )
}

export default App
