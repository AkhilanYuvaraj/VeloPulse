import { Wifi, WifiOff, Monitor } from 'lucide-react';
import { formatUptime, formatTimestamp } from '../../utils/formatters';

export default function ConnectionStatus({ status }) {
  const isConnected = status?.connected ?? false;

  return (
    <div className="glass-card no-hover">
      <div className="card-header">
        <span className="card-title">Connection Status</span>
      </div>

      <div className="connection-indicator" style={{ marginBottom: '16px' }}>
        <span className={`conn-dot ${isConnected ? 'connected' : 'disconnected'}`} />
        <div className="conn-info">
          <div className="conn-label">
            {isConnected ? 'Connected' : 'Disconnected'}
          </div>
          <div className="conn-detail">
            {status?.port_or_address || 'No device'}
          </div>
        </div>
        {isConnected ? <Wifi size={20} style={{ color: 'var(--success)' }} /> : <WifiOff size={20} style={{ color: 'var(--danger)' }} />}
      </div>

      <div className="hw-detail-grid">
        <div className="hw-detail-item">
          <span className="hw-label">Mode</span>
          <span className="hw-value">{status?.mode || '--'}</span>
        </div>
        <div className="hw-detail-item">
          <span className="hw-label">Uptime</span>
          <span className="hw-value">{formatUptime(status?.uptime_seconds)}</span>
        </div>
        <div className="hw-detail-item">
          <span className="hw-label">Frames</span>
          <span className="hw-value">{status?.frames_received || 0}</span>
        </div>
        <div className="hw-detail-item">
          <span className="hw-label">Errors</span>
          <span className="hw-value">{status?.errors_count || 0}</span>
        </div>
        <div className="hw-detail-item">
          <span className="hw-label">Last Reading</span>
          <span className="hw-value">{formatTimestamp(status?.last_reading_timestamp)}</span>
        </div>
        <div className="hw-detail-item">
          <span className="hw-label">Device</span>
          <span className="hw-value">{status?.port_or_address || '--'}</span>
        </div>
      </div>

      {/* Latest raw frame */}
      {status?.latest_frame && (
        <div style={{ marginTop: '16px' }}>
          <div className="card-title" style={{ marginBottom: '8px' }}>Latest Telemetry Frame</div>
          <pre className="telemetry-frame">
            {JSON.stringify(status.latest_frame, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
