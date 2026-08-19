import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Send, Plus, Trash2 } from 'lucide-react';
import FleetTable from '../components/fleet/FleetTable';
import { predictBatch } from '../api/client';
import { useApi } from '../hooks/useApi';
import { getHealthClass } from '../utils/formatters';

const sampleVehicles = [
  { vehicle_id: 'CAR-001', engine_rpm: 2200, engine_temp_c: 92, coolant_temp_c: 88, battery_voltage_v: 13.8, vibration_level: 0.45, odometer_reading: 52000, engine_load: 42, vehicle_speed: 65 },
  { vehicle_id: 'CAR-002', engine_rpm: 3500, engine_temp_c: 105, coolant_temp_c: 102, battery_voltage_v: 12.1, vibration_level: 1.8, odometer_reading: 98000, engine_load: 78, vehicle_speed: 110 },
  { vehicle_id: 'BIKE-001', engine_rpm: 4800, engine_temp_c: 88, coolant_temp_c: 82, battery_voltage_v: 14.2, vibration_level: 0.3, odometer_reading: 15000, engine_load: 35, vehicle_speed: 45 },
  { vehicle_id: 'CAR-003', engine_rpm: 1800, engine_temp_c: 130, coolant_temp_c: 125, battery_voltage_v: 11.5, vibration_level: 3.2, odometer_reading: 145000, engine_load: 90, vehicle_speed: 30 },
  { vehicle_id: 'BIKE-002', engine_rpm: 6200, engine_temp_c: 95, coolant_temp_c: 90, battery_voltage_v: 13.5, vibration_level: 0.8, odometer_reading: 28000, engine_load: 55, vehicle_speed: 80 },
];

export default function Fleet() {
  const [vehicles, setVehicles] = useState(sampleVehicles);
  const { data: batchResult, loading, error, execute } = useApi(predictBatch);

  const handleBatchPredict = useCallback(async () => {
    try {
      await execute(vehicles);
    } catch {
      // handled by useApi
    }
  }, [vehicles, execute]);

  const predictions = batchResult?.predictions || batchResult?.results || [];

  // Fleet summary
  const summary = {
    total: predictions.length,
    healthy: predictions.filter((p) => p.health_status === 'HEALTHY').length,
    advisory: predictions.filter((p) => p.health_status === 'ADVISORY').length,
    critical: predictions.filter((p) => p.health_status === 'CRITICAL').length,
  };

  return (
    <div className="page-container">
      <motion.div
        className="page-header"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1>Fleet Management</h1>
        <p>Multi-vehicle batch prediction and fleet health overview</p>
      </motion.div>

      {/* Fleet Summary */}
      {predictions.length > 0 && (
        <div className="fleet-summary">
          <div className="glass-card fleet-stat">
            <div className="fleet-stat-value" style={{ color: 'var(--primary-light)' }}>
              {summary.total}
            </div>
            <div className="fleet-stat-label">Total Vehicles</div>
          </div>
          <div className="glass-card fleet-stat success">
            <div className="fleet-stat-value" style={{ color: 'var(--success-light)' }}>
              {summary.healthy}
            </div>
            <div className="fleet-stat-label">Healthy</div>
          </div>
          <div className="glass-card fleet-stat warning">
            <div className="fleet-stat-value" style={{ color: 'var(--warning-light)' }}>
              {summary.advisory}
            </div>
            <div className="fleet-stat-label">Advisory</div>
          </div>
          <div className="glass-card fleet-stat danger">
            <div className="fleet-stat-value" style={{ color: 'var(--danger-light)' }}>
              {summary.critical}
            </div>
            <div className="fleet-stat-label">Critical</div>
          </div>
        </div>
      )}

      {/* Controls */}
      <motion.div
        className="glass-card no-hover"
        style={{ marginBottom: '24px' }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="card-header">
          <span className="card-title">Fleet Configuration</span>
          <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            {vehicles.length} vehicle{vehicles.length !== 1 ? 's' : ''} queued
          </span>
        </div>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '16px' }}>
          Sample fleet data is pre-loaded with diverse vehicle profiles including healthy, degraded, and critical states.
        </p>
        <div style={{ display: 'flex', gap: '12px' }}>
          <motion.button
            className="btn btn-primary"
            onClick={handleBatchPredict}
            disabled={loading || vehicles.length === 0}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Send size={16} />
            {loading ? 'Processing Fleet...' : 'Run Batch Prediction'}
          </motion.button>
          <button
            className="btn btn-ghost"
            onClick={() => setVehicles(sampleVehicles)}
          >
            Reset Sample Data
          </button>
        </div>
        {error && (
          <p style={{ marginTop: '12px', color: 'var(--danger-light)', fontSize: '13px' }}>
            Error: {error}
          </p>
        )}
      </motion.div>

      {/* Fleet Table */}
      <FleetTable predictions={predictions} />
    </div>
  );
}
