"use client";

import { useEffect, useState } from "react";

import { API_BASE, getHealth, type HealthResponse } from "@/lib/api";

type State =
  | { kind: "loading" }
  | { kind: "ok"; data: HealthResponse }
  | { kind: "error"; message: string };

export function BackendStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    getHealth({ signal: controller.signal })
      .then((data) => setState({ kind: "ok", data }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setState({ kind: "error", message: err instanceof Error ? err.message : String(err) });
      });
    return () => controller.abort();
  }, []);

  return (
    <div className="rounded-lg border p-4 text-sm">
      <p className="font-medium">Backend</p>
      <p className="text-muted-foreground font-mono text-xs">{API_BASE}</p>
      <p className="mt-2" role="status">
        {state.kind === "loading" && "Checking…"}
        {state.kind === "ok" && `✅ ${state.data.status} (${state.data.environment})`}
        {state.kind === "error" && `❌ ${state.message}`}
      </p>
    </div>
  );
}
