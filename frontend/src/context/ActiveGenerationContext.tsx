import React, { createContext, useContext, useRef, useState, useCallback, useEffect } from 'react';
import { pollBatchStatus } from '../services/api';
import type { BatchStatus } from '../types';

interface ActiveGenerationState {
  batchId: string | null;
  testRunId: string;
  batchStatus: BatchStatus | null;
  running: boolean;
  setTestRunId: (id: string) => void;
  startPolling: (batchId: string) => void;
  reset: () => void;
}

const ActiveGenerationContext = createContext<ActiveGenerationState | null>(null);

const TERMINAL = ['completed', 'partial_failure', 'failed'];

export const ActiveGenerationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [batchId, setBatchId] = useState<string | null>(null);
  const [testRunId, setTestRunIdState] = useState('');
  const [batchStatus, setBatchStatus] = useState<BatchStatus | null>(null);
  const [running, setRunning] = useState(false);
  const pollTimer = useRef<any>(null);

  const clearTimer = () => {
    if (pollTimer.current) {
      clearTimeout(pollTimer.current);
      pollTimer.current = null;
    }
  };

  const startPolling = useCallback((id: string) => {
    clearTimer();
    setBatchId(id);
    setRunning(true);

    const tick = async (attempt: number) => {
      if (attempt > 60) {
        // ~2.5 min cap to avoid endless polling
        setRunning(false);
        return;
      }
      try {
        const s: BatchStatus = await pollBatchStatus(id);
        setBatchStatus(s);
        if (TERMINAL.includes(s.batch_status)) {
          setRunning(false);
          return;
        }
      } catch (e) {
        console.error('poll error', e);
      }
      pollTimer.current = setTimeout(() => tick(attempt + 1), 2500);
    };

    tick(1);
  }, []);

  const setTestRunId = useCallback((id: string) => setTestRunIdState(id), []);

  const reset = useCallback(() => {
    clearTimer();
    setBatchId(null);
    setBatchStatus(null);
    setRunning(false);
  }, []);

  // Keep polling alive for the lifetime of the provider (i.e. across tab navigation).
  useEffect(() => () => clearTimer(), []);

  return (
    <ActiveGenerationContext.Provider
      value={{ batchId, testRunId, batchStatus, running, setTestRunId, startPolling, reset }}
    >
      {children}
    </ActiveGenerationContext.Provider>
  );
};

export function useActiveGeneration() {
  const ctx = useContext(ActiveGenerationContext);
  if (!ctx) {
    throw new Error('useActiveGeneration must be used within ActiveGenerationProvider');
  }
  return ctx;
}
