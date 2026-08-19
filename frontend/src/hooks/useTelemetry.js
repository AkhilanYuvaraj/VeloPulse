import { useState, useCallback, useRef, useEffect } from 'react';
import { getHardwareStatus } from '../api/client';
import { usePolling } from './usePolling';

const MAX_HISTORY = 120; // 60 seconds at 2Hz

/**
 * Manages live telemetry state with rolling history buffer
 */
export function useTelemetry(enabled = true) {
  const [history, setHistory] = useState([]);
  const historyRef = useRef([]);
  const counterRef = useRef(0);

  const fetchStatus = useCallback(async () => {
    const res = await getHardwareStatus();
    return res;
  }, []);

  const { data: status, error, loading } = usePolling(fetchStatus, 500, enabled);

  // Update history when new data arrives
  useEffect(() => {
    if (status?.latest_frame) {
      const frame = {
        ...status.latest_frame,
        timestamp: status.last_reading_timestamp || new Date().toISOString(),
        index: counterRef.current++,
      };

      historyRef.current = [...historyRef.current, frame].slice(-MAX_HISTORY);
      setHistory([...historyRef.current]);
    }
  }, [status]);

  const latestFrame = status?.latest_frame || null;

  return {
    status,
    latestFrame,
    history,
    error,
    loading,
    isConnected: status?.connected ?? false,
    mode: status?.mode || 'UNKNOWN',
    framesReceived: status?.frames_received || 0,
    uptime: status?.uptime_seconds || 0,
  };
}

export default useTelemetry;
