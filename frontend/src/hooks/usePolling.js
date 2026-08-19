import { useEffect, useRef, useCallback, useState } from 'react';

/**
 * Generic polling hook with configurable interval and auto-cleanup
 */
export function usePolling(fetchFn, intervalMs = 1000, enabled = true) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef(null);
  const mountedRef = useRef(true);

  const execute = useCallback(async () => {
    try {
      const result = await fetchFn();
      if (mountedRef.current) {
        setData(result.data || result);
        setError(null);
        setLoading(false);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err);
        setLoading(false);
      }
    }
  }, [fetchFn]);

  useEffect(() => {
    mountedRef.current = true;

    if (!enabled) {
      setLoading(false);
      return;
    }

    // Execute immediately on mount
    execute();

    // Set up polling interval
    intervalRef.current = setInterval(execute, intervalMs);

    return () => {
      mountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [execute, intervalMs, enabled]);

  const refetch = useCallback(() => {
    setLoading(true);
    execute();
  }, [execute]);

  return { data, error, loading, refetch };
}

export default usePolling;
