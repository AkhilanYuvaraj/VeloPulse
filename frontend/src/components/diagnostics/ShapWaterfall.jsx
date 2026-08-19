import { motion } from 'framer-motion';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from 'recharts';

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  const isPositive = item.value >= 0;
  return (
    <div className="custom-tooltip">
      <div className="tooltip-label">{item.payload.label}</div>
      <div className="tooltip-item">
        <span className="tooltip-dot" style={{ background: isPositive ? '#ef4444' : '#10b981' }} />
        <span>{isPositive ? 'Risk Factor' : 'Mitigating Factor'}</span>
        <span className="tooltip-value" style={{ color: isPositive ? '#f87171' : '#34d399' }}>
          {isPositive ? '+' : ''}{Number(item.value).toFixed(2)}%
        </span>
      </div>
    </div>
  );
}

export default function ShapWaterfall({ rootCauseAnalysis }) {
  if (!rootCauseAnalysis || Object.keys(rootCauseAnalysis).length === 0) {
    return (
      <div className="glass-card no-hover">
        <div className="card-header">
          <span className="card-title">SHAP Root Cause Analysis</span>
        </div>
        <div className="empty-state">
          <h3>No Analysis Available</h3>
          <p>Run a prediction to see feature attributions</p>
        </div>
      </div>
    );
  }

  const data = Object.entries(rootCauseAnalysis)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .map(([key, value]) => ({
      feature: key,
      label: key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      value: Number(value),
      isPositive: value >= 0,
    }));

  return (
    <motion.div
      className="glass-card no-hover"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="card-header">
        <span className="card-title">SHAP Root Cause Analysis</span>
        <div style={{ display: 'flex', gap: '16px', fontSize: '11px' }}>
          <span style={{ color: '#f87171' }}>● Risk Factor</span>
          <span style={{ color: '#34d399' }}>● Mitigating</span>
        </div>
      </div>
      <div className="chart-container tall">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 8, right: 40, left: 100, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(56, 189, 248, 0.06)" horizontal={false} />
            <XAxis
              type="number"
              tick={{ fontSize: 10, fill: '#64748b' }}
              axisLine={{ stroke: 'rgba(56, 189, 248, 0.1)' }}
              tickFormatter={(v) => `${v}%`}
            />
            <YAxis
              type="category"
              dataKey="label"
              tick={{ fontSize: 11, fill: '#94a3b8' }}
              axisLine={false}
              tickLine={false}
              width={100}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine x={0} stroke="rgba(241, 245, 249, 0.2)" />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={20}>
              {data.map((entry, idx) => (
                <Cell
                  key={idx}
                  fill={entry.isPositive ? '#ef4444' : '#10b981'}
                  fillOpacity={0.8}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
