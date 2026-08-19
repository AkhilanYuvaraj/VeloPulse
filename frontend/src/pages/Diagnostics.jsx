import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Search, Send } from 'lucide-react';
import ShapWaterfall from '../components/diagnostics/ShapWaterfall';
import AnomalyIndicator from '../components/diagnostics/AnomalyIndicator';
import RulTimeline from '../components/diagnostics/RulTimeline';
import { predict } from '../api/client';
import { useApi } from '../hooks/useApi';

const defaultValues = {
  vehicle_id: 'DIAG-001',
  engine_rpm: 2200,
  engine_temp_c: 92,
  coolant_temp_c: 88,
  battery_voltage_v: 13.8,
  vibration_level: 0.45,
  odometer_reading: 52000,
  engine_load: 42,
  vehicle_speed: 65,
};

export default function Diagnostics() {
  const [formData, setFormData] = useState(defaultValues);
  const [rulHistory, setRulHistory] = useState([]);
  const { data: prediction, loading, error, execute } = useApi(predict);

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    try {
      const result = await execute(formData);
      if (result?.predicted_rul_km != null) {
        setRulHistory((prev) => [
          ...prev,
          { index: prev.length + 1, rul: result.predicted_rul_km },
        ]);
      }
    } catch {
      // error handled by useApi
    }
  }, [formData, execute]);

  const fields = [
    { key: 'engine_rpm', label: 'Engine RPM', type: 'number' },
    { key: 'engine_temp_c', label: 'Engine Temp (°C)', type: 'number' },
    { key: 'coolant_temp_c', label: 'Coolant Temp (°C)', type: 'number' },
    { key: 'battery_voltage_v', label: 'Battery Voltage (V)', type: 'number', step: '0.1' },
    { key: 'vibration_level', label: 'Vibration Level (g)', type: 'number', step: '0.01' },
    { key: 'odometer_reading', label: 'Odometer (km)', type: 'number' },
    { key: 'engine_load', label: 'Engine Load (%)', type: 'number' },
    { key: 'vehicle_speed', label: 'Vehicle Speed (km/h)', type: 'number' },
  ];

  return (
    <div className="page-container">
      <motion.div
        className="page-header"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1>Diagnostics</h1>
        <p>Deep-dive ML predictions, SHAP explainability, and anomaly detection</p>
      </motion.div>

      {/* Predict Form */}
      <motion.div
        className="glass-card no-hover"
        style={{ marginBottom: '24px' }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="card-header">
          <span className="card-title">Single Vehicle Prediction</span>
          <div className="live-indicator">
            <Search size={14} />
            Manual Input
          </div>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="predict-form">
            {fields.map((field) => (
              <div key={field.key} className="form-group">
                <label>{field.label}</label>
                <input
                  type={field.type}
                  step={field.step || '1'}
                  value={formData[field.key]}
                  onChange={(e) =>
                    handleChange(
                      field.key,
                      field.type === 'number'
                        ? parseFloat(e.target.value) || 0
                        : e.target.value
                    )
                  }
                  placeholder={field.label}
                />
              </div>
            ))}
          </div>
          <div style={{ marginTop: '20px', display: 'flex', gap: '12px' }}>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              <Send size={16} />
              {loading ? 'Predicting...' : 'Run Prediction'}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setFormData(defaultValues)}
            >
              Reset Defaults
            </button>
          </div>
          {error && (
            <p style={{ marginTop: '12px', color: 'var(--danger-light)', fontSize: '13px' }}>
              Error: {error}
            </p>
          )}
        </form>
      </motion.div>

      {/* Results */}
      <div className="diagnostics-grid">
        <ShapWaterfall rootCauseAnalysis={prediction?.root_cause_analysis} />
        <AnomalyIndicator
          anomalyDetected={prediction?.anomaly_detected}
          anomalyScore={prediction?.anomaly_score}
          healthStatus={prediction?.health_status}
        />
      </div>

      {/* RUL Timeline */}
      <RulTimeline history={rulHistory} />

      {/* Prediction Result JSON */}
      {prediction && (
        <motion.div
          className="glass-card no-hover"
          style={{ marginTop: '24px' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <div className="card-header">
            <span className="card-title">Raw Prediction Response</span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Inference: {prediction.inference_time_ms?.toFixed(1)}ms
            </span>
          </div>
          <pre className="telemetry-frame">
            {JSON.stringify(prediction, null, 2)}
          </pre>
        </motion.div>
      )}
    </div>
  );
}
