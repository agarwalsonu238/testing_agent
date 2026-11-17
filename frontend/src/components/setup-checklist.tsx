"use client";

import { CircleCheck, CircleExclamationPoint, CircleMinus, CircleX } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useApiData } from "@/hooks/use-api-data";
import { getSetupCheck, type SetupItem } from "@/lib/api";

const ICONS: Record<SetupItem["status"], React.ReactNode> = {
  pass: <CircleCheck className="size-5 text-emerald-600" aria-label="Ready" />,
  warn: <CircleExclamationPoint className="size-5 text-amber-600" aria-label="Warning" />,
  fail: <CircleX className="size-5 text-red-600" aria-label="Not ready" />,
  skip: <CircleMinus className="size-5 text-muted-foreground" aria-label="Not checked" />,
};

export function SetupChecklist() {
  const [run, setRun] = useState({ live: false, n: 0 });
  const check = useApiData(`setup:${run.live}:${run.n}`, (signal) => getSetupCheck(run.live, { signal }));

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" onClick={() => setRun((r) => ({ live: false, n: r.n + 1 }))} disabled={check.loading}>
          Check again
        </Button>
        <Button onClick={() => setRun((r) => ({ live: true, n: r.n + 1 }))} disabled={check.loading}>
          Run a test on my login
        </Button>
        <p className="text-xs text-muted-foreground">The login test makes one tiny Claude Code call on your plan.</p>
      </div>

      {check.loading && <p className="text-muted-foreground" role="status">Checking…</p>}
      {check.error && (
        <p role="alert" className="text-sm text-destructive">
          Couldn&apos;t reach the QA agent backend: {check.error}
        </p>
      )}
      {check.data && !check.loading && (
        <>
          <p role="status" className="font-medium">
            {check.data.ready ? "Ready: everything needed is green." : "Not ready yet: fix the red items below."}
          </p>
          <ul className="grid gap-2">
            {check.data.items.map((item) => (
              <li key={item.key} className="flex items-start gap-3 rounded-xl border p-3">
                <span className="mt-0.5">{ICONS[item.status]}</span>
                <div className="min-w-0">
                  <p className="font-medium">{item.label}</p>
                  <p className="text-sm break-words text-muted-foreground">{item.detail}</p>
                  {item.fix && <p className="mt-1 text-sm">Fix: {item.fix}</p>}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
