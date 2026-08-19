import { motion } from 'framer-motion';
import { Shield, AlertTriangle, XOctagon, Heart } from 'lucide-react';
import { getHealthClass, formatNumber } from '../../utils/formatters';

const statusConfig = {
  HEALTHY: {
    icon: Shield,
    label: 'System Healthy',
    description: 'All systems operating within normal parameters',
    color: '#10b981',
    gradient: 'linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.05))',
  },
  ADVISORY: {
    icon: AlertTriangle,
    label: 'Advisory Alert',
    description: 'Potential degradation detected — schedule maintenance',
    color: '#f59e0b',
    gradient: 'linear-gradient(135deg, rgba(245, 158, 11, 0.15), rgba(245, 158, 11, 0.05))',
  },
  CRITICAL: {
    icon: XOctagon,
    label: 'Critical Alert',
    description: 'Immediate attention required — failure imminent',
    color: '#ef4444',
    gradient: 'linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(239, 68, 68, 0.05))',
  },
};

export default function HealthStatusCard({ healthStatus, rul, anomalyScore }) {
  const status = healthStatus?.toUpperCase() || 'HEALTHY';
  const config = statusConfig[status] || statusConfig.HEALTHY;
  const StatusIcon = config.icon;
  const healthClass = getHealthClass(status);

  // RUL ring calculation
  const maxRul = 50000;
  const rulPercent = Math.min(((rul || 0) / maxRul) * 100, 100);
  const circumference = 2 * Math.PI * 66;
  const strokeDashoffset = circumference - (rulPercent / 100) * circumference;

  return (
    <div className={`glass-card health-card ${healthClass}`}>
      {/* Health Badge */}
      <motion.div
        className={`health-badge ${healthClass}`}
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        <span className="badge-dot" />
        {config.label}
      </motion.div>

      {/* RUL Ring */}
      <div className="health-ring" style={{ marginTop: '24px' }}>
        <svg viewBox="0 0 160 160">
          <circle className="ring-bg" cx="80" cy="80" r="66" />
          <motion.circle
            className="ring-fill"
            cx="80"
            cy="80"
            r="66"
            stroke={config.color}
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset }}
            transition={{ duration: 1.2, ease: 'easeOut' }}
          />
        </svg>
        <div className="ring-label" style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', textAlign: 'center' }}>
          <motion.div
            className="ring-value"
            key={rul}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{ color: config.color }}
          >
            {rul != null ? formatNumber(rul, 0) : '--'}
          </motion.div>
          <div className="ring-unit">KM RUL</div>
        </div>
      </div>

      {/* Status Description */}
      <div style={{ marginTop: '16px' }}>
        <StatusIcon size={20} style={{ color: config.color, marginBottom: '8px' }} />
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', maxWidth: '280px' }}>
          {config.description}
        </p>
      </div>

      {/* Anomaly Score */}
      {anomalyScore != null && (
        <div style={{
          marginTop: '16px',
          padding: '8px 16px',
          background: 'var(--bg-surface)',
          borderRadius: 'var(--radius-md)',
          fontSize: '12px',
          color: 'var(--text-secondary)',
        }}>
          Anomaly Score: <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
            {Number(anomalyScore).toFixed(4)}
          </span>
        </div>
      )}
    </div>
  );
}
