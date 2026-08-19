import { motion } from 'framer-motion';
import VehicleRow from './VehicleRow';

export default function FleetTable({ predictions }) {
  if (!predictions || predictions.length === 0) {
    return (
      <div className="glass-card no-hover">
        <div className="card-header">
          <span className="card-title">Fleet Vehicles</span>
        </div>
        <div className="empty-state">
          <h3>No Fleet Data</h3>
          <p>Run a batch prediction to see fleet vehicle statuses</p>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card no-hover" style={{ padding: 0, overflow: 'hidden' }}>
      <div className="card-header" style={{ padding: '20px 24px 12px' }}>
        <span className="card-title">Fleet Vehicles</span>
        <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
          {predictions.length} vehicle{predictions.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table className="fleet-table">
          <thead>
            <tr>
              <th>Vehicle ID</th>
              <th>Health Status</th>
              <th>Predicted RUL</th>
              <th>Anomaly</th>
              <th>Anomaly Score</th>
              <th>Top Risk Factor</th>
              <th>Inference Time</th>
            </tr>
          </thead>
          <tbody>
            {predictions.map((pred, idx) => (
              <VehicleRow key={pred.vehicle_id || idx} prediction={pred} index={idx} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
