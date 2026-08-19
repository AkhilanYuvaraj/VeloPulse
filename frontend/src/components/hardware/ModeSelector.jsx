import { Usb, Bluetooth, Play } from 'lucide-react';
import { motion } from 'framer-motion';

const modes = [
  {
    id: 'SERIAL',
    name: 'USB Serial',
    desc: 'ESP32 / Arduino via USB',
    icon: Usb,
  },
  {
    id: 'BLUETOOTH_OBD',
    name: 'Bluetooth OBD-II',
    desc: 'ELM327 Scan Tool',
    icon: Bluetooth,
  },
  {
    id: 'SIMULATION',
    name: 'Simulation',
    desc: 'Physics-Based Emulator',
    icon: Play,
  },
];

export default function ModeSelector({ currentMode, onModeChange, loading }) {
  return (
    <div>
      <div className="card-header">
        <span className="card-title">Hardware Mode</span>
      </div>
      <div className="mode-selector-grid">
        {modes.map((mode) => (
          <motion.div
            key={mode.id}
            className={`glass-card mode-card${currentMode === mode.id ? ' active' : ''}`}
            onClick={() => !loading && onModeChange(mode.id)}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            style={{ cursor: loading ? 'wait' : 'pointer' }}
          >
            <div className="mode-icon">
              <mode.icon size={24} />
            </div>
            <div className="mode-name">{mode.name}</div>
            <div className="mode-desc">{mode.desc}</div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
