import { motion } from 'framer-motion';
import { getHealthClass, formatNumber } from '../../utils/formatters';

export default function VehicleRow({ prediction, index }) {
  const healthClass = getHealthClass(prediction.health_status);

  // Find top risk factor
  let topRisk = '--';
  if (prediction.root_cause_analysis) {
    const entries = Object.entries(prediction.root_cause_analysis);
    if (entries.length > 0) {
      const sorted = entries.sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
      const [key, value] = sorted[0];
      topRisk = `${key.replace(/_/g, ' ')} (${value >= 0 ? '+' : ''}${Number(value).toFixed(1)}%)`;
    }
  }

  return (
    <motion.tr
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
    >
      <td className="vehicle-id">{prediction.vehicle_id || `Vehicle-${index + 1}`}</td>
      <td>
        <span className={`health-badge ${healthClass}`} style={{ fontSize: '11px', padding: '4px 10px' }}>
          <span className="badge-dot" />
          {prediction.health_status}
        </span>
      </td>
      <td style={{ fontWeight: 600 }}>
        {formatNumber(prediction.predicted_rul_km, 0)} <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>km</span>
      </td>
      <td>
        {prediction.anomaly_detected ? (
          <span style={{ color: 'var(--danger-light)', fontWeight: 600 }}>Yes</span>
        ) : (
          <span style={{ color: 'var(--success-light)' }}>No</span>
        )}
      </td>
      <td style={{ fontFamily: 'monospace', fontSize: '13px' }}>
        {prediction.anomaly_score != null ? Number(prediction.anomaly_score).toFixed(4) : '--'}
      </td>
      <td style={{ fontSize: '13px' }}>{topRisk}</td>
      <td style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
        {prediction.inference_time_ms != null ? `${Number(prediction.inference_time_ms).toFixed(1)}ms` : '--'}
      </td>
    </motion.tr>
  );
}
