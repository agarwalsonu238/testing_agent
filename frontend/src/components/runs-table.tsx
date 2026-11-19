"use client";

import Link from "next/link";

import { VerdictBadge } from "@/components/badges";
import { useApiData } from "@/hooks/use-api-data";
import { listRuns } from "@/lib/api";

export function RunsTable() {
  const runs = useApiData("runs", (signal) => listRuns({ signal }), 5000);

  if (runs.error && !runs.data) {
    return (
      <p role="alert" className="text-sm text-destructive">
        Couldn&apos;t load runs: {runs.error}
      </p>
    );
  }
  if (!runs.data) return <p className="text-muted-foreground">Loading runs…</p>;
  if (runs.data.length === 0) {
    return (
      <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
        No runs yet. Start with a <Link className="underline underline-offset-4" href="/scan">Quick Scan</Link>.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border">
      <table className="w-full text-sm">
        <caption className="sr-only">The last 20 runs, newest first</caption>
        <thead className="bg-muted/50 text-left text-muted-foreground">
          <tr>
            <th scope="col" className="p-2 font-medium">Run</th>
            <th scope="col" className="p-2 font-medium">Verdict</th>
            <th scope="col" className="p-2 font-medium">Open / total</th>
            <th scope="col" className="p-2 font-medium">Mode</th>
            <th scope="col" className="p-2 font-medium">Started</th>
          </tr>
        </thead>
        <tbody>
          {runs.data.map((run) => (
            <tr key={run.id} className="border-t">
              <td className="p-2">
                <Link href={`/runs/${run.id}`} className="font-medium underline-offset-4 hover:underline">
                  {run.title}
                </Link>
              </td>
              <td className="p-2">
                <VerdictBadge verdict={run.status === "running" ? null : run.verdict} />
              </td>
              <td className="p-2 tabular-nums">
                {run.counts.open} / {run.counts.total}
              </td>
              <td className="p-2">{run.mode}</td>
              <td className="p-2 whitespace-nowrap">
                <time dateTime={run.started_at}>{new Date(run.started_at).toLocaleString()}</time>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
