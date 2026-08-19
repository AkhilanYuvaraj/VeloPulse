import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Gauge, Thermometer, Battery, Zap } from 'lucide-react';
import TelemetryGauge from '../components/dashboard/TelemetryGauge';
import HealthStatusCard from '../components/dashboard/HealthStatusCard';
import LiveTelemetryChart from '../components/dashboard/LiveTelemetryChart';
import SystemOverview from '../components/dashboard/SystemOverview';
import { predictLive } from '../api/client';

export default function Dashboard({ telemetry }) {
  const { latestFrame, history, isConnected } = telemetry;
  const [prediction, setPrediction] = useState(null);
  const [predError, setPredError] = useState(null);

  // Auto-predict every 3 seconds when connected
  const runPrediction = useCallback(async () => {
    try {
      const res = await predictLive();
      setPrediction(res.data);
      setPredError(null);
    } catch (err) {
      setPredError(err.message);
    }
  }, []);

  useEffect(() => {
    if (!isConnected) return;
    runPrediction();
    const interval = setInterval(runPrediction, 3000);
    return () => clearInterval(interval);
  }, [isConnected, runPrediction]);

  return (
    <div className="page-container">
      <motion.div
        className="page-header"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h1>Vehicle Dashboard</h1>
        <p>Real-time telemetry monitoring and predictive health analysis</p>
      </motion.div>

      {/* Stats Grid */}
      <div className="stats-grid">
        <TelemetryGauge
          label="Engine RPM"
          value={latestFrame?.engine_rpm}
          unit="RPM"
          min={0}
          max={8000}
          icon={Gauge}
          color="cyan"
          decimals={0}
        />
        <TelemetryGauge
          label="Coolant Temp"
          value={latestFrame?.coolant_temp_c}
          unit="°C"
          min={0}
          max={150}
          icon={Thermometer}
          color="amber"
          decimals={1}
        />
        <TelemetryGauge
          label="Battery Voltage"
          value={latestFrame?.battery_voltage_v}
          unit="V"
          min={10}
          max={16}
          icon={Battery}
          color="green"
          decimals={2}
        />
        <TelemetryGauge
          label="Vibration Level"
          value={latestFrame?.vibration_level}
          unit="g"
          min={0}
          max={5}
          icon={Zap}
          color="red"
          decimals={3}
        />
      </div>

      {/* Main Dashboard Grid */}
      <div className="dashboard-grid">
        <LiveTelemetryChart data={history} />
        <HealthStatusCard
          healthStatus={prediction?.health_status}
          rul={prediction?.predicted_rul_km}
          anomalyScore={prediction?.anomaly_score}
        />
      </div>

      {/* Risk Factors */}
      <SystemOverview rootCauseAnalysis={prediction?.root_cause_analysis} />
    </div>
  );
}
