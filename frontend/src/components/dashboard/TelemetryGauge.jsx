import { motion } from 'framer-motion';
import { clamp, mapRange } from '../../utils/formatters';

export default function TelemetryGauge({
  label,
  value,
  unit,
  min = 0,
  max = 100,
  icon: Icon,
  color = 'cyan',
  decimals = 0,
}) {
  const safeValue = clamp(value ?? 0, min, max);
  const percentage = mapRange(safeValue, min, max, 0, 100);
  const circumference = 2 * Math.PI * 52;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  const colorMap = {
    cyan: { stroke: '#06b6d4', glow: 'rgba(6, 182, 212, 0.3)', bg: 'rgba(6, 182, 212, 0.1)' },
    green: { stroke: '#10b981', glow: 'rgba(16, 185, 129, 0.3)', bg: 'rgba(16, 185, 129, 0.1)' },
    amber: { stroke: '#f59e0b', glow: 'rgba(245, 158, 11, 0.3)', bg: 'rgba(245, 158, 11, 0.1)' },
    red: { stroke: '#ef4444', glow: 'rgba(239, 68, 68, 0.3)', bg: 'rgba(239, 68, 68, 0.1)' },
  };

  const colors = colorMap[color] || colorMap.cyan;
  const displayValue = value != null ? Number(value).toFixed(decimals) : '--';

  return (
    <div className="glass-card stat-card">
      <div className="stat-icon" style={{ background: colors.bg, color: colors.stroke }}>
        {Icon && <Icon size={20} />}
      </div>
      <div className="stat-label">{label}</div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px' }}>
        <motion.span
          className="stat-number"
          key={displayValue}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {displayValue}
        </motion.span>
        <span className="stat-unit">{unit}</span>
      </div>

      {/* Mini progress bar */}
      <div
        style={{
          marginTop: '12px',
          height: '4px',
          background: 'var(--bg-surface-hover)',
          borderRadius: '2px',
          overflow: 'hidden',
        }}
      >
        <motion.div
          style={{
            height: '100%',
            background: `linear-gradient(90deg, ${colors.stroke}, ${colors.stroke}dd)`,
            borderRadius: '2px',
          }}
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>
    </div>
  );
}
