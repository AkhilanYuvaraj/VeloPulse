import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Zap,
  Thermometer,
  Waves,
  AlertCircle,
  Layers,
  Play,
} from 'lucide-react';

const faultTypes = [
  { id: 'voltage_drop', label: 'Voltage Drop', icon: Zap },
  { id: 'thermal_runaway', label: 'Thermal Runaway', icon: Thermometer },
  { id: 'bearing_vibration', label: 'Bearing Vibration', icon: Waves },
  { id: 'engine_misfire', label: 'Engine Misfire', icon: AlertCircle },
  { id: 'combined', label: 'Combined Faults', icon: Layers },
];

export default function FaultInjector({ onInject, loading }) {
  const [selectedFault, setSelectedFault] = useState(null);
  const [severity, setSeverity] = useState(0.8);
  const [duration, setDuration] = useState(15);

  const handleInject = () => {
    if (selectedFault) {
      onInject(selectedFault, severity, duration);
    }
  };

  return (
    <div className="glass-card no-hover">
      <div className="card-header">
        <span className="card-title">Fault Injection Console</span>
      </div>

      {/* Fault type buttons */}
      <div className="fault-grid">
        {faultTypes.map((fault) => (
          <motion.button
            key={fault.id}
            className={`fault-btn${selectedFault === fault.id ? ' selected' : ''}`}
            onClick={() => setSelectedFault(fault.id)}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
          >
            <fault.icon className="fault-icon" size={18} />
            {fault.label}
          </motion.button>
        ))}
      </div>

      {/* Severity slider */}
      <div className="slider-group">
        <label>
          Severity
          <span>{(severity * 100).toFixed(0)}%</span>
        </label>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={severity}
          onChange={(e) => setSeverity(parseFloat(e.target.value))}
        />
      </div>

      {/* Duration slider */}
      <div className="slider-group">
        <label>
          Duration
          <span>{duration}s</span>
        </label>
        <input
          type="range"
          min="1"
          max="60"
          step="1"
          value={duration}
          onChange={(e) => setDuration(parseInt(e.target.value))}
        />
      </div>

      {/* Inject button */}
      <motion.button
        className="btn btn-danger btn-lg"
        onClick={handleInject}
        disabled={!selectedFault || loading}
        whileHover={{ scale: selectedFault ? 1.02 : 1 }}
        whileTap={{ scale: selectedFault ? 0.98 : 1 }}
        style={{ width: '100%', marginTop: '8px' }}
      >
        <Play size={18} />
        {loading ? 'Injecting...' : 'Inject Fault'}
      </motion.button>
    </div>
  );
}
