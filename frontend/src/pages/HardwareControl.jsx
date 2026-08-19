import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Play } from 'lucide-react';
import ModeSelector from '../components/hardware/ModeSelector';
import FaultInjector from '../components/hardware/FaultInjector';
import ConnectionStatus from '../components/hardware/ConnectionStatus';
import { setHardwareMode, simulateFault, predictLive } from '../api/client';
import { useApi } from '../hooks/useApi';

export default function HardwareControl({ telemetry }) {
  const { status, mode } = telemetry;
  const [modeLoading, setModeLoading] = useState(false);
  const [faultLoading, setFaultLoading] = useState(false);
  const [faultResult, setFaultResult] = useState(null);
  const { data: livePrediction, loading: liveLoading, execute: executeLive } = useApi(predictLive);

  const handleModeChange = useCallback(async (newMode) => {
    setModeLoading(true);
    try {
      await setHardwareMode(newMode);
    } catch (err) {
      console.error('Failed to set mode:', err);
    } finally {
      setModeLoading(false);
    }
  }, []);

  const handleFaultInject = useCallback(async (faultType, severity, duration) => {
    setFaultLoading(true);
    setFaultResult(null);
    try {
      const res = await simulateFault(faultType, severity, duration);
      setFaultResult(res.data);
    } catch (err) {
      console.error('Fault injection failed:', err);
      setFaultResult({ error: err.message });
    } finally {
      setFaultLoading(false);
    }
  }, []);

  const handleLivePredict = useCallback(async () => {
    try {
      await executeLive();
    } catch {
      // handled by useApi
    }
  }, [executeLive]);

  return (
    <div className="page-container">
      <motion.div
        className="page-header"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1>Hardware Control</h1>
        <p>Sensor configuration, fault injection, and live prediction</p>
      </motion.div>

      {/* Mode Selector */}
      <ModeSelector
        currentMode={mode}
        onModeChange={handleModeChange}
        loading={modeLoading}
      />

      {/* Main Grid */}
      <div className="dashboard-grid-full">
        <div>
          <FaultInjector onInject={handleFaultInject} loading={faultLoading} />

          {/* Fault Result */}
          {faultResult && (
            <motion.div
              className="glass-card no-hover"
              style={{ marginTop: '16px' }}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <div className="card-header">
                <span className="card-title">Fault Injection Result</span>
              </div>
              <pre className="telemetry-frame">
                {JSON.stringify(faultResult, null, 2)}
              </pre>
            </motion.div>
          )}
        </div>

        <div>
          <ConnectionStatus status={status} />

          {/* Live Predict Button */}
          <motion.button
            className="btn btn-primary btn-lg"
            style={{ width: '100%', marginTop: '16px' }}
            onClick={handleLivePredict}
            disabled={liveLoading}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Play size={18} />
            {liveLoading ? 'Predicting...' : 'Predict Live Telemetry'}
          </motion.button>

          {/* Live Prediction Result */}
          {livePrediction && (
            <motion.div
              className="glass-card no-hover"
              style={{ marginTop: '16px' }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <div className="card-header">
                <span className="card-title">Live Prediction</span>
                <span className={`health-badge ${
                  livePrediction.health_status?.toLowerCase()
                }`} style={{ fontSize: '11px', padding: '3px 10px' }}>
                  <span className="badge-dot" />
                  {livePrediction.health_status}
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="hw-detail-item">
                  <span className="hw-label">Predicted RUL</span>
                  <span className="hw-value">{Number(livePrediction.predicted_rul_km).toFixed(0)} km</span>
                </div>
                <div className="hw-detail-item">
                  <span className="hw-label">Anomaly</span>
                  <span className="hw-value" style={{
                    color: livePrediction.anomaly_detected ? 'var(--danger-light)' : 'var(--success-light)'
                  }}>
                    {livePrediction.anomaly_detected ? 'Detected' : 'None'}
                  </span>
                </div>
                <div className="hw-detail-item">
                  <span className="hw-label">Anomaly Score</span>
                  <span className="hw-value">{Number(livePrediction.anomaly_score).toFixed(4)}</span>
                </div>
                <div className="hw-detail-item">
                  <span className="hw-label">Inference Time</span>
                  <span className="hw-value">{Number(livePrediction.inference_time_ms).toFixed(1)} ms</span>
                </div>
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
