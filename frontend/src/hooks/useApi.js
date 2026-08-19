import { useState, useCallback } from 'react';

/**
 * Hook for one-off API requests with loading/error state
 */
export function useApi(apiFn) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const execute = useCallback(async (...args) => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiFn(...args);
      const responseData = result.data || result;
      setData(responseData);
      setLoading(false);
      return responseData;
    } catch (err) {
      const errorMessage = err.response?.data?.detail || err.message || 'Request failed';
      setError(errorMessage);
      setLoading(false);
      throw err;
    }
  }, [apiFn]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, error, loading, execute, reset };
}

export default useApi;
