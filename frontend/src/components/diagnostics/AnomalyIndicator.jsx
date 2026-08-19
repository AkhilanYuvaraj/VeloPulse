import { motion } from 'framer-motion';

export default function AnomalyIndicator({ anomalyDetected, anomalyScore, healthStatus }) {
  const normalizedScore = anomalyScore != null ? Math.abs(anomalyScore) : 0;
  const displayScore = anomalyScore != null ? Number(anomalyScore).toFixed(4) : '--';

  // Visual ring
  const circumference = 2 * Math.PI * 45;
  const fillPercent = Math.min(normalizedScore * 100, 100);
  const strokeDashoffset = circumference - (fillPercent / 100) * circumference;

  const ringColor = anomalyDetected ? '#ef4444' : '#10b981';

  return (
    <div className="glass-card no-hover" style={{ textAlign: 'center', padding: '32px 24px' }}>
      <div className="card-header" style={{ justifyContent: 'center' }}>
        <span className="card-title">Anomaly Detection</span>
      </div>

      <div className="anomaly-ring" style={{ margin: '20px auto' }}>
        <svg viewBox="0 0 120 120">
          <circle className="ring-bg" cx="60" cy="60" r="45" />
          <motion.circle
            className="ring-fill"
            cx="60"
            cy="60"
            r="45"
            stroke={ringColor}
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset }}
            transition={{ duration: 1, ease: 'easeOut' }}
          />
        </svg>
        <div className="ring-center">
          <div className="ring-score" style={{ color: ringColor }}>
            {displayScore}
          </div>
          <div className="ring-label">Score</div>
        </div>
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        style={{
          marginTop: '16px',
          padding: '10px 20px',
          borderRadius: 'var(--radius-full)',
          background: anomalyDetected
            ? 'rgba(239, 68, 68, 0.15)'
            : 'rgba(16, 185, 129, 0.15)',
          color: anomalyDetected ? '#f87171' : '#34d399',
          fontSize: '13px',
          fontWeight: 600,
          display: 'inline-block',
        }}
      >
        {anomalyDetected ? '⚠ Anomaly Detected' : '✓ Normal Operation'}
      </motion.div>

      {healthStatus && (
        <p style={{ marginTop: '12px', fontSize: '12px', color: 'var(--text-muted)' }}>
          Health Status: <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>{healthStatus}</span>
        </p>
      )}
    </div>
  );
}
