type JointRowProps = {
  name: string
  speed: number
  acceleration: number
  radians: number
  degree: number
  encoder: number
  current: number
  temperature: number
  /** 0..1, position within joint range, used for the progress bar */
  progress: number
  onJogMinus?: () => void
  onJogPlus?: () => void
}

export function JointRow({
  name,
  speed,
  acceleration,
  radians,
  degree,
  encoder,
  current,
  temperature,
  progress,
  onJogMinus,
  onJogPlus,
}: JointRowProps) {
  const pct = Math.max(0, Math.min(1, progress)) * 100

  return (
    <div className="joint-row">
      <div className="joint-row__label">
        <div className="joint-row__name">{name}</div>
        <div className="joint-row__sub">Speed: {speed.toFixed(4)} RAD/S</div>
        <div className="joint-row__sub">
          Acceleration: {acceleration.toFixed(4)} RAD/S²
        </div>
      </div>

      <button
        type="button"
        className="jog-btn jog-btn--minus"
        aria-label={`${name} jog minus`}
        onClick={onJogMinus}
      >
        <Chevron direction="left" />
        <Chevron direction="left" />
      </button>

      <div className="joint-row__metrics">
        <div className="joint-row__metric-grid">
          <span>Radians: {radians.toFixed(1)}</span>
          <span>Current: {current.toFixed(1)} A</span>
          <span>Degree: {degree.toFixed(1)} °</span>
          <span>Temperature: {temperature.toFixed(0)} °C</span>
          <span>Encoder: {encoder}</span>
        </div>
        <div
          className="joint-row__bar"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(pct)}
        >
          <div className="joint-row__bar-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <button
        type="button"
        className="jog-btn jog-btn--plus"
        aria-label={`${name} jog plus`}
        onClick={onJogPlus}
      >
        <Chevron direction="right" />
        <Chevron direction="right" />
      </button>
    </div>
  )
}

function Chevron({ direction }: { direction: 'left' | 'right' }) {
  const points =
    direction === 'left' ? '14,4 6,12 14,20' : '6,4 14,12 6,20'
  return (
    <svg viewBox="0 0 20 24" aria-hidden="true">
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
