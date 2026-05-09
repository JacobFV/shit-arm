type Axis = 'X+' | 'X-' | 'Y+' | 'Y-' | 'Z+' | 'Z-'

type CartesianPadProps = {
  onJog?: (axis: Axis) => void
}

export function CartesianPad({ onJog }: CartesianPadProps) {
  const handle = (axis: Axis) => () => onJog?.(axis)

  return (
    <div className="cartesian-pad" role="group" aria-label="Cartesian jog pad">
      <ArrowButton
        className="cartesian-pad__z-minus"
        color="blue"
        direction="down"
        label="Z-"
        onClick={handle('Z-')}
      />
      <ArrowButton
        className="cartesian-pad__z-plus"
        color="blue"
        direction="up"
        label="Z+"
        onClick={handle('Z+')}
      />
      <ArrowButton
        className="cartesian-pad__x-minus"
        color="red"
        direction="up"
        label="X-"
        onClick={handle('X-')}
      />
      <ArrowButton
        className="cartesian-pad__x-plus"
        color="red"
        direction="down"
        label="X+"
        onClick={handle('X+')}
      />
      <ArrowButton
        className="cartesian-pad__y-minus"
        color="green"
        direction="left"
        label="Y-"
        onClick={handle('Y-')}
      />
      <ArrowButton
        className="cartesian-pad__y-plus"
        color="green"
        direction="right"
        label="Y+"
        onClick={handle('Y+')}
      />
    </div>
  )
}

type ArrowButtonProps = {
  className: string
  color: 'red' | 'green' | 'blue'
  direction: 'up' | 'down' | 'left' | 'right'
  label: string
  onClick: () => void
}

function ArrowButton({
  className,
  color,
  direction,
  label,
  onClick,
}: ArrowButtonProps) {
  return (
    <button
      type="button"
      className={`arrow-btn arrow-btn--${color} ${className}`}
      onClick={onClick}
      aria-label={label}
    >
      <ArrowShape direction={direction} />
      <span className="arrow-btn__label">{label}</span>
    </button>
  )
}

function ArrowShape({
  direction,
}: {
  direction: 'up' | 'down' | 'left' | 'right'
}) {
  // Base shape: arrow pointing up. Rotate via CSS based on direction.
  const rotation = {
    up: 0,
    right: 90,
    down: 180,
    left: 270,
  }[direction]

  return (
    <svg
      viewBox="0 0 100 100"
      aria-hidden="true"
      style={{ transform: `rotate(${rotation}deg)` }}
      className="arrow-btn__shape"
    >
      <polygon
        points="50,6 92,52 70,52 70,94 30,94 30,52 8,52"
        fill="currentColor"
        stroke="rgba(0,0,0,0.45)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  )
}
