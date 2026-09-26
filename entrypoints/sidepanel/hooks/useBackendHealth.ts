import { useCallback, useEffect, useRef, useState } from 'react';
import { pingHealth } from '../lib/api';

const POLL_INTERVAL_MS = 4000;
const FAILURES_BEFORE_OFFLINE = 2;

export interface BackendHealth {
  isOnline: boolean;
  isChecking: boolean;
  checkNow: () => void;
}

export function useBackendHealth(): BackendHealth {
  const [isOnline, setIsOnline] = useState(true);
  const [isChecking, setIsChecking] = useState(false);
  const failuresRef = useRef(0);
  const inFlightRef = useRef(false);
  const mountedRef = useRef(false);

  const probe = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setIsChecking(true);
    try {
      const reachable = await pingHealth();
      if (!mountedRef.current) return;
      if (reachable) {
        failuresRef.current = 0;
        setIsOnline(true);
      } else {
        failuresRef.current += 1;
        if (failuresRef.current >= FAILURES_BEFORE_OFFLINE) {
          setIsOnline(false);
        }
      }
    } finally {
      inFlightRef.current = false;
      if (mountedRef.current) setIsChecking(false);
    }
  }, []);

  const checkNow = useCallback(() => {
    void probe();
  }, [probe]);

  useEffect(() => {
    mountedRef.current = true;
    const onWake = () => {
      if (!document.hidden) void probe();
    };

    void probe();
    const interval = setInterval(onWake, POLL_INTERVAL_MS);
    document.addEventListener('visibilitychange', onWake);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onWake);
    };
  }, [probe]);

  return { isOnline, isChecking, checkNow };
}

export default useBackendHealth;
