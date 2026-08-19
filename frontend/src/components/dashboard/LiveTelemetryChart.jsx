import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

const channels = [
  { key: 'engine_rpm', name: 'RPM', color: '#06b6d4', yAxisId: 'rpm' },
  { key: 'coolant_temp_c', name: 'Coolant °C', color: '#f59e0b', yAxisId: 'temp' },
  { key: 'battery_voltage_v', name: 'Voltage V', color: '#10b981', yAxisId: 'voltage' },
  { key: 'vibration_level', name: 'Vibration', color: '#f87171', yAxisId: 'vibration' },
];

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="custom-tooltip">
      <div className="tooltip-label">Sample #{label}</div>
      {payload.map((entry) => (
        <div key={entry.name} className="tooltip-item">
          <span className="tooltip-dot" style={{ background: entry.color }} />
          <span>{entry.name}</span>
          <span className="tooltip-value">{Number(entry.value).toFixed(2)}</span>
        </div>
      ))}
    </div>
  );
}

export default function LiveTelemetryChart({ data }) {
  if (!data || data.length === 0) {
    return (
      <div className="glass-card no-hover">
        <div className="card-header">
          <span className="card-title">Live Telemetry Stream</span>
          <span className="live-indicator">
            <span className="live-dot" />
            Waiting...
          </span>
        </div>
        <div className="chart-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="empty-state">
            <p>Waiting for telemetry data...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card no-hover">
      <div className="card-header">
        <span className="card-title">Live Telemetry Stream</span>
        <span className="live-indicator">
          <span className="live-dot" />
          Live
        </span>
      </div>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, left: -10, bottom: 0 }}>
            <defs>
              {channels.map((ch) => (
                <linearGradient key={ch.key} id={`gradient-${ch.key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={ch.color} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={ch.color} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(56, 189, 248, 0.06)" />
            <XAxis
              dataKey="index"
              tick={{ fontSize: 10, fill: '#64748b' }}
              axisLine={{ stroke: 'rgba(56, 189, 248, 0.1)' }}
              tickLine={false}
            />
            <YAxis
              yAxisId="rpm"
              orientation="left"
              tick={{ fontSize: 10, fill: '#64748b' }}
              axisLine={false}
              tickLine={false}
              domain={[0, 'auto']}
            />
            <YAxis yAxisId="temp" hide />
            <YAxis yAxisId="voltage" hide />
            <YAxis yAxisId="vibration" hide />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              verticalAlign="top"
              height={30}
              wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }}
            />
            {channels.map((ch) => (
              <Area
                key={ch.key}
                yAxisId={ch.yAxisId}
                type="monotone"
                dataKey={ch.key}
                name={ch.name}
                stroke={ch.color}
                strokeWidth={2}
                fill={`url(#gradient-${ch.key})`}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
