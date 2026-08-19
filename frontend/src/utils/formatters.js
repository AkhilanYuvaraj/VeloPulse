/**
 * Format a number with commas and fixed decimal places
 */
export const formatNumber = (value, decimals = 0) => {
  if (value == null || isNaN(value)) return '--';
  return Number(value).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
};

/**
 * Format RUL in km with appropriate units
 */
export const formatRUL = (km) => {
  if (km == null || isNaN(km)) return { value: '--', unit: 'km' };
  if (km >= 10000) {
    return { value: formatNumber(km / 1000, 1), unit: 'k km' };
  }
  return { value: formatNumber(km, 0), unit: 'km' };
};

/**
 * Format temperature value
 */
export const formatTemp = (celsius) => {
  if (celsius == null || isNaN(celsius)) return '--';
  return `${Number(celsius).toFixed(1)}°C`;
};

/**
 * Format voltage value
 */
export const formatVoltage = (volts) => {
  if (volts == null || isNaN(volts)) return '--';
  return `${Number(volts).toFixed(2)}V`;
};

/**
 * Format percentage
 */
export const formatPercent = (value, decimals = 1) => {
  if (value == null || isNaN(value)) return '--';
  return `${Number(value).toFixed(decimals)}%`;
};

/**
 * Format uptime seconds to human-readable
 */
export const formatUptime = (seconds) => {
  if (seconds == null || isNaN(seconds)) return '--';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
};

/**
 * Format timestamp to locale string
 */
export const formatTimestamp = (ts) => {
  if (!ts) return '--';
  try {
    return new Date(ts).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return '--';
  }
};

/**
 * Get health status color class
 */
export const getHealthClass = (status) => {
  switch (status?.toUpperCase()) {
    case 'HEALTHY': return 'healthy';
    case 'ADVISORY': return 'advisory';
    case 'CRITICAL': return 'critical';
    default: return '';
  }
};

/**
 * Get health status color value
 */
export const getHealthColor = (status) => {
  switch (status?.toUpperCase()) {
    case 'HEALTHY': return '#10b981';
    case 'ADVISORY': return '#f59e0b';
    case 'CRITICAL': return '#ef4444';
    default: return '#64748b';
  }
};

/**
 * Clamp a value between min and max
 */
export const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

/**
 * Map a value from one range to another
 */
export const mapRange = (value, inMin, inMax, outMin, outMax) => {
  return ((value - inMin) * (outMax - outMin)) / (inMax - inMin) + outMin;
};
