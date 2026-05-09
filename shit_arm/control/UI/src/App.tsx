import { useState } from 'react'
import { JointRow } from './components/JointRow'
import { CartesianPad } from './components/CartesianPad'
import { JointCurrentChart } from './components/JointCurrentChart'
import './App.css'

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

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('Move')
  const [speedPreset, setSpeedPreset] = useState<SpeedPreset>('Default')
  const [acceleration, setAcceleration] = useState(45)
  const [speed, setSpeed] = useState(25)
  const [enabled, setEnabled] = useState(false)

  return (
    <div className="app">
      <header className="titlebar">
        <span className="titlebar__title">ARM control</span>
        <div className="titlebar__controls" aria-hidden="true">
          <span className="titlebar__btn">−</span>
          <span className="titlebar__btn">▢</span>
          <span className="titlebar__btn">×</span>
        </div>
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
        <button type="button" className="help-btn" aria-label="Help">
          ?
        </button>
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
        {JOINT_NAMES.map((name) => (
          <JointRow
            key={name}
            name={name}
            speed={0.4006}
            acceleration={2.2778}
            radians={0.0}
            degree={0.0}
            encoder={0}
            current={0.0}
            temperature={0}
            progress={0.5}
          />
        ))}
      </section>

      <section className="center-pad">
        <CartesianPad />
      </section>

      <aside className="side">
        <div className="side__top">
          <div className="tool-position">
            <h3>Tool position:</h3>
            <div className="tool-position__grid">
              <span>X: 0.0</span>
              <span>Base: 0.0</span>
              <span>Y: 0.0</span>
              <span>Shoulder: 0.0</span>
              <span>Z: 0.0</span>
              <span>Elbow: 0.0</span>
              <span>phi: 0.0</span>
              <span>Wrist 1: 0.0</span>
              <span>theta: 0.0</span>
              <span>Wrist 2: 0.0</span>
              <span>psi: 0.0</span>
              <span>Wrist 3: 0.0</span>
            </div>
          </div>

          <button
            type="button"
            className={`enable-btn ${enabled ? 'enable-btn--on' : ''}`}
            onClick={() => setEnabled((v) => !v)}
            aria-pressed={enabled}
          >
            <span className="enable-btn__text">
              {'Enable'.split('').map((c, i) => (
                <span key={i}>{c}</span>
              ))}
            </span>
          </button>
        </div>

        <button type="button" className="ghost-btn">
          Clear error
        </button>

        <div className="grippers">
          <button type="button" className="ghost-btn">
            Close gripper
          </button>
          <button type="button" className="ghost-btn">
            Open gripper
          </button>
        </div>

        <JointCurrentChart />
      </aside>
    </div>
  )
}

export default App
