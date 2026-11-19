"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Loaded<T> = { key: string; data?: T; error?: string };

export type ApiData<T> = {
  data: T | undefined;
  error: string | undefined;
  loading: boolean;
  reload: () => void;
};

const message = (err: unknown) => (err instanceof Error ? err.message : String(err));

/**
 * Load data for `key` (null = don't load). With `intervalMs`, it refreshes after each load finishes,
 * which is how run pages follow a run live. The last good data stays visible while refreshing.
 */
export function useApiData<T>(
  key: string | null,
  load: (signal: AbortSignal) => Promise<T>,
  intervalMs?: number,
): ApiData<T> {
  const [state, setState] = useState<Loaded<T>>({ key: "" });
  const [tick, setTick] = useState(0);
  const loadRef = useRef(load);

  useEffect(() => {
    loadRef.current = load;
  });

  useEffect(() => {
    if (key === null) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;

    const run = () => {
      loadRef
        .current(controller.signal)
        .then((data) => setState({ key, data }))
        .catch((err: unknown) => {
          if (!controller.signal.aborted) setState((prev) => ({ ...prev, key, error: message(err) }));
        })
        .finally(() => {
          if (intervalMs && !controller.signal.aborted) timer = setTimeout(run, intervalMs);
        });
    };
    run();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [key, tick, intervalMs]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  const current = state.key === key;
  return {
    data: state.data,
    error: current ? state.error : undefined,
    loading: key !== null && !current,
    reload,
  };
}
