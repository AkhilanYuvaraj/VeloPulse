import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="custom-tooltip">
      <div className="tooltip-label">Prediction #{label}</div>
      {payload.map((entry) => (
        <div key={entry.name} className="tooltip-item">
          <span className="tooltip-dot" style={{ background: entry.color }} />
          <span>{entry.name}</span>
          <span className="tooltip-value">{Number(entry.value).toFixed(0)} km</span>
        </div>
      ))}
    </div>
  );
}

export default function RulTimeline({ history }) {
  if (!history || history.length === 0) {
    return (
      <div className="glass-card no-hover">
        <div className="card-header">
          <span className="card-title">RUL Prediction Timeline</span>
        </div>
        <div className="empty-state">
          <p>RUL history will appear as predictions accumulate</p>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card no-hover">
      <div className="card-header">
        <span className="card-title">RUL Prediction Timeline</span>
      </div>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={history} margin={{ top: 8, right: 20, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="rul-gradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#06b6d4" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(56, 189, 248, 0.06)" />
            <XAxis
              dataKey="index"
              tick={{ fontSize: 10, fill: '#64748b' }}
              axisLine={{ stroke: 'rgba(56, 189, 248, 0.1)' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#64748b' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
            />
            <Tooltip content={<CustomTooltip />} />
            {/* Warning threshold at 5000km */}
            <ReferenceLine
              y={5000}
              stroke="#f59e0b"
              strokeDasharray="5 5"
              strokeOpacity={0.5}
              label={{ value: 'Advisory', fill: '#f59e0b', fontSize: 10, position: 'insideTopRight' }}
            />
            {/* Critical threshold at 500km */}
            <ReferenceLine
              y={500}
              stroke="#ef4444"
              strokeDasharray="5 5"
              strokeOpacity={0.5}
              label={{ value: 'Critical', fill: '#ef4444', fontSize: 10, position: 'insideTopRight' }}
            />
            <Line
              type="monotone"
              dataKey="rul"
              name="Predicted RUL"
              stroke="#06b6d4"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: '#06b6d4', stroke: '#0a0e1a', strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
