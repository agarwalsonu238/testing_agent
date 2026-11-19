"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { FindingCard } from "@/components/finding-card";
import { useApiData } from "@/hooks/use-api-data";
import { cn } from "@/lib/utils";
import { listFindings, type FindingItem } from "@/lib/api";

export const REVIEW_TABS = [
  { key: "", label: "To review" },
  { key: "design-reviewer", label: "Design" },
  { key: "functionality-tester", label: "Functionality" },
  { key: "code-reviewer", label: "Code review" },
  { key: "quick-scan", label: "Quick Scan" },
] as const;

const tabClass =
  "rounded-md px-2.5 py-1 text-sm whitespace-nowrap outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50";

/** Group findings by run, newest run first (the API already sorts them). */
function byRun(items: FindingItem[]) {
  const groups = new Map<string, FindingItem[]>();
  for (const item of items) groups.set(item.run_id, [...(groups.get(item.run_id) ?? []), item]);
  return [...groups.values()];
}

export function FindingsBoard() {
  const agent = useSearchParams().get("agent") ?? "";
  const { data, error, loading, reload } = useApiData(`findings:${agent}`, (signal) =>
    listFindings({ status: "open", agent: agent || undefined }, { signal }),
  );
  const [decided, setDecided] = useState<Set<string>>(new Set());
  const items = (data ?? []).filter((f) => !decided.has(`${f.run_id}/${f.id}`));

  return (
    <section className="grid gap-4" aria-labelledby="review-heading">
      <div>
        <h1 id="review-heading" className="text-2xl font-semibold tracking-tight">
          To review
        </h1>
        <p className="text-muted-foreground">
          {loading ? "Loading findings…" : `${items.length} open finding${items.length === 1 ? "" : "s"}`}
        </p>
      </div>

      <nav aria-label="Filter findings" className="-mx-1 flex gap-1 overflow-x-auto border-b px-1 pb-2">
        {REVIEW_TABS.map((tab) => {
          const active = tab.key === agent;
          return (
            <Link
              key={tab.key || "all"}
              href={tab.key ? `/?agent=${tab.key}` : "/"}
              aria-current={active ? "page" : undefined}
              className={cn(tabClass, active && "bg-muted font-medium")}
            >
              {tab.label}
            </Link>
          );
        })}
        <Link href="/runs" className={cn(tabClass, "text-muted-foreground")}>
          Runs
        </Link>
        <Link href="/guide" className={cn(tabClass, "text-muted-foreground")}>
          Guide
        </Link>
      </nav>

      {error && (
        <div role="alert" className="rounded-lg border border-destructive/40 p-3 text-sm">
          <p>Couldn&apos;t load findings: {error}</p>
          <button type="button" onClick={reload} className="mt-1 underline underline-offset-4">
            Try again
          </button>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
          <p>Nothing to review.</p>
          <p>
            Run a <Link className="underline underline-offset-4" href="/scan">Quick Scan</Link> or{" "}
            <Link className="underline underline-offset-4" href="/check">Check my change</Link>.
          </p>
        </div>
      )}

      {byRun(items).map((group) => (
        <section key={group[0].run_id} className="grid gap-3" aria-label={group[0].run_title}>
          <h2 className="text-sm text-muted-foreground">
            <Link href={`/runs/${group[0].run_id}`} className="underline-offset-4 hover:underline">
              {group[0].run_title}
            </Link>{" "}
            · {new Date(group[0].run_started_at).toLocaleString()}
          </h2>
          {group.map((finding) => (
            <FindingCard
              key={`${finding.run_id}/${finding.id}`}
              runId={finding.run_id}
              finding={finding}
              onDecided={() =>
                setDecided((prev) => new Set(prev).add(`${finding.run_id}/${finding.id}`))
              }
            />
          ))}
        </section>
      ))}
    </section>
  );
}
