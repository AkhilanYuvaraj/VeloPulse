import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for error handling
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.detail || error.message || 'An error occurred';
    console.error('[API Error]', message);
    return Promise.reject(error);
  }
);

// ─── System ───
export const getHealth = () => client.get('/health');

// ─── Inference ───
export const predict = (telemetryData) => client.post('/predict', telemetryData);

export const predictBatch = (payloads) => client.post('/predict/batch', { payloads });

export const predictLive = () => client.post('/hardware/predict-live');

// ─── Hardware ───
export const getHardwareStatus = () => client.get('/hardware/status');

export const setHardwareMode = (mode, port = null, baudrate = null) => {
  const data = { mode };
  if (port) data.port = port;
  if (baudrate) data.baudrate = baudrate;
  return client.post('/hardware/mode', data);
};

export const simulateFault = (faultType, severity = 0.8, durationSeconds = 15.0) =>
  client.post('/hardware/simulate-fault', {
    fault_type: faultType,
    severity,
    duration_seconds: durationSeconds,
  });

export default client;
