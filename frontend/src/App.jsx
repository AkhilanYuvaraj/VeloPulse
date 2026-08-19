import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import AppLayout from './components/layout/AppLayout';
import Dashboard from './pages/Dashboard';
import Diagnostics from './pages/Diagnostics';
import HardwareControl from './pages/HardwareControl';
import Fleet from './pages/Fleet';
import { useTelemetry } from './hooks/useTelemetry';
import { getHealth } from './api/client';

export default function App() {
  const [backendStatus, setBackendStatus] = useState('offline');
  const telemetry = useTelemetry(backendStatus === 'online');

  // Check backend health
  const checkHealth = useCallback(async () => {
    try {
      await getHealth();
      setBackendStatus('online');
    } catch {
      setBackendStatus('offline');
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  return (
    <BrowserRouter>
      <Routes>
        <Route
          element={
            <AppLayout backendStatus={backendStatus} telemetry={telemetry} />
          }
        >
          <Route index element={<Dashboard telemetry={telemetry} />} />
          <Route path="diagnostics" element={<Diagnostics />} />
          <Route
            path="hardware"
            element={<HardwareControl telemetry={telemetry} />}
          />
          <Route path="fleet" element={<Fleet />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
