import { motion } from 'framer-motion';

export default function SystemOverview({ rootCauseAnalysis }) {
  if (!rootCauseAnalysis || Object.keys(rootCauseAnalysis).length === 0) {
    return (
      <div className="glass-card no-hover">
        <div className="card-header">
          <span className="card-title">Top Risk Factors</span>
        </div>
        <div className="empty-state" style={{ padding: '30px 20px' }}>
          <p style={{ fontSize: '13px' }}>Run a prediction to view risk factors</p>
        </div>
      </div>
    );
  }

  // Sort by absolute value, take top 5
  const sorted = Object.entries(rootCauseAnalysis)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 5);

  const maxAbsVal = Math.max(...sorted.map(([, v]) => Math.abs(v)), 1);

  return (
    <div className="glass-card no-hover">
      <div className="card-header">
        <span className="card-title">Top Risk Factors (SHAP)</span>
      </div>
      <div className="shap-bar-container">
        {sorted.map(([key, value], idx) => {
          const isPositive = value >= 0;
          const barWidth = (Math.abs(value) / maxAbsVal) * 100;
          const formattedLabel = key
            .replace(/_/g, ' ')
            .replace(/\b\w/g, (c) => c.toUpperCase());

          return (
            <motion.div
              key={key}
              className="shap-bar-row"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.08, duration: 0.4 }}
            >
              <span className="shap-bar-label">{formattedLabel}</span>
              <div className="shap-bar-track">
                <motion.div
                  className={`shap-bar-fill ${isPositive ? 'positive' : 'negative'}`}
                  initial={{ width: 0 }}
                  animate={{ width: `${barWidth}%` }}
                  transition={{ delay: idx * 0.08 + 0.2, duration: 0.6, ease: 'easeOut' }}
                />
              </div>
              <span className={`shap-bar-value ${isPositive ? 'positive' : 'negative'}`}>
                {isPositive ? '+' : ''}{Number(value).toFixed(2)}%
              </span>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
