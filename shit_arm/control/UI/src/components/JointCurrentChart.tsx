const SERIES = [
  { name: 'Cur1', color: '#d62728' },
  { name: 'Cur2', color: '#2ca02c' },
  { name: 'Cur3', color: '#1f77b4' },
  { name: 'Cur4', color: '#17becf' },
  { name: 'Cur5', color: '#ff7f0e' },
  { name: 'Cur6', color: '#000000' },
]

const Y_TICKS = [0, 500, 1000, 1500, 2000]
const X_TICKS = [0, 200, 400, 600, 800, 1000]

export function JointCurrentChart() {
  return (
    <div className="chart">
      <div className="chart__titlebar">
        <span>Figure 1</span>
        <span className="chart__titlebar-controls" aria-hidden="true">
          <span className="chart__dot" />
          <span className="chart__dot" />
          <span className="chart__dot" />
        </span>
      </div>

      <div className="chart__legend">
        {SERIES.map((s) => (
          <span key={s.name} className="chart__legend-item">
            <span
              className="chart__legend-swatch"
              style={{ background: s.color }}
            />
            {s.name}
          </span>
        ))}
      </div>

      <div className="chart__plot">
        <div className="chart__y-label">Joint current [RPM]</div>
        <div className="chart__y-axis">
          {[...Y_TICKS].reverse().map((t) => (
            <span key={t}>{t}</span>
          ))}
        </div>
        <div className="chart__canvas">
          <svg
            viewBox="0 0 1000 400"
            preserveAspectRatio="none"
            className="chart__svg"
          >
            {Y_TICKS.map((t, i) => {
              const y = 400 - (t / 2000) * 400
              return (
                <line
                  key={`hg-${i}`}
                  x1={0}
                  x2={1000}
                  y1={y}
                  y2={y}
                  stroke="#d8d8d8"
                  strokeDasharray="2 4"
                  strokeWidth={1}
                />
              )
            })}
            {X_TICKS.map((t, i) => {
              const x = (t / 1000) * 1000
              return (
                <line
                  key={`vg-${i}`}
                  x1={x}
                  x2={x}
                  y1={0}
                  y2={400}
                  stroke="#d8d8d8"
                  strokeDasharray="2 4"
                  strokeWidth={1}
                />
              )
            })}
          </svg>
        </div>
      </div>

      <div className="chart__x-axis">
        {X_TICKS.map((t) => (
          <span key={t}>{t}</span>
        ))}
      </div>
      <div className="chart__x-label">Samples [10ms]</div>

      <div className="chart__toolbar" aria-hidden="true">
        <ToolbarBtn glyph="home" />
        <ToolbarBtn glyph="back" />
        <ToolbarBtn glyph="fwd" />
        <ToolbarBtn glyph="pan" />
        <ToolbarBtn glyph="zoom" />
        <ToolbarBtn glyph="save" />
      </div>
    </div>
  )
}

function ToolbarBtn({ glyph }: { glyph: string }) {
  return <span className={`chart__tool chart__tool--${glyph}`} />
}
