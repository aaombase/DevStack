// Dependency-free SVG charts. Colors come from CSS variables so they follow the theme.

const W = 560;
const H = 180;
const PAD = { l: 34, r: 8, t: 8, b: 22 };

function scale(max) {
  const top = Math.max(max, 1);
  const step = top <= 5 ? 1 : Math.ceil(top / 4);
  const ticks = [];
  for (let v = 0; v <= top; v += step) ticks.push(v);
  return { top: ticks[ticks.length - 1] < top ? top : ticks[ticks.length - 1], ticks };
}

function Axes({ ticks, top }) {
  const y = (v) => PAD.t + (H - PAD.t - PAD.b) * (1 - v / top);
  return ticks.map((v) => (
    <g key={v}>
      <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} className="grid-line" />
      <text x={PAD.l - 6} y={y(v) + 4} textAnchor="end" className="axis-text">{v}</text>
    </g>
  ));
}

export function Legend({ items }) {
  return (
    <div className="legend">
      {items.map((i) => (
        <span key={i.label}><i style={{ background: i.color }} /> {i.label}</span>
      ))}
    </div>
  );
}

// series: [{label, color, values: number[]}]; labels: string[] (x axis)
export function LineChart({ labels, series, dashed = [] }) {
  const max = Math.max(0, ...series.flatMap((s) => s.values));
  const { top, ticks } = scale(max);
  const n = labels.length;
  const x = (i) => PAD.l + (n <= 1 ? 0 : ((W - PAD.l - PAD.r) * i) / (n - 1));
  const y = (v) => PAD.t + (H - PAD.t - PAD.b) * (1 - v / top);
  const every = Math.max(1, Math.ceil(n / 7));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img">
      <Axes ticks={ticks} top={top} />
      {labels.map((l, i) =>
        i % every === 0 || i === n - 1 ? (
          <text
            key={i}
            x={x(i)}
            y={H - 6}
            textAnchor={i === n - 1 && n > 1 ? "end" : i === 0 ? "start" : "middle"}
            className="axis-text"
          >
            {l}
          </text>
        ) : null,
      )}
      {series.map((s) => (
        <polyline
          key={s.label}
          fill="none"
          stroke={s.color}
          strokeWidth="2"
          strokeDasharray={dashed.includes(s.label) ? "5 4" : undefined}
          points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")}
        />
      ))}
    </svg>
  );
}

// Grouped bars: groups = [{label, values: number[]}], colors per series index.
export function BarChart({ groups, colors }) {
  const max = Math.max(0, ...groups.flatMap((g) => g.values));
  const { top, ticks } = scale(max);
  const slot = (W - PAD.l - PAD.r) / Math.max(groups.length, 1);
  const bar = Math.min(26, (slot * 0.8) / colors.length);
  const y = (v) => PAD.t + (H - PAD.t - PAD.b) * (1 - v / top);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img">
      <Axes ticks={ticks} top={top} />
      {groups.map((g, gi) => {
        const start = PAD.l + slot * gi + (slot - bar * colors.length) / 2;
        return (
          <g key={g.label}>
            {g.values.map((v, vi) => (
              <rect
                key={vi}
                x={start + bar * vi}
                y={y(v)}
                width={bar - 2}
                height={Math.max(y(0) - y(v), 0)}
                fill={colors[vi]}
                rx="2"
              >
                <title>{`${g.label}: ${v}`}</title>
              </rect>
            ))}
            <text x={PAD.l + slot * gi + slot / 2} y={H - 6} textAnchor="middle" className="axis-text">
              {g.label.length > 12 ? g.label.slice(0, 11) + "…" : g.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
