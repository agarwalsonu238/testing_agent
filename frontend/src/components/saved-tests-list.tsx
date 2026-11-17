"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useApiData } from "@/hooks/use-api-data";
import { listSavedTests, runSavedTest } from "@/lib/api";

export function SavedTestsList() {
  const router = useRouter();
  const tests = useApiData("saved-tests", (signal) => listSavedTests({ signal }));
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(testId: string) {
    setStarting(testId);
    setError(null);
    try {
      const started = await runSavedTest(testId);
      router.push(`/runs/${started.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStarting(null);
    }
  }

  if (tests.error) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {tests.error}
      </p>
    );
  }
  if (!tests.data) return <p className="text-muted-foreground">Loading saved tests…</p>;
  if (tests.data.length === 0) {
    return (
      <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
        No saved tests in the registry yet. When a Functionality tester flow passes, use{" "}
        <strong>Save as test</strong> on its report.
      </p>
    );
  }

  return (
    <div className="grid gap-3">
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <ul className="grid gap-2">
        {tests.data.map((test) => (
          <li key={test.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3">
            <div className="min-w-0">
              <p className="font-medium">
                {test.id} · {test.title}
              </p>
              <p className="truncate font-mono text-xs text-muted-foreground">{test.file}</p>
              {test.source_run_id && (
                <Link href={`/runs/${test.source_run_id}`} className="text-xs underline underline-offset-4">
                  Recorded in run {test.source_run_id}
                </Link>
              )}
            </div>
            <Button size="sm" variant="outline" disabled={starting !== null} onClick={() => run(test.id)}>
              {starting === test.id ? "Starting…" : "Run (no AI)"}
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
