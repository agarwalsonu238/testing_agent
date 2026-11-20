"use client";

import { Copy, ExternalLink, RotateCw } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Tag, VerdictBadge } from "@/components/badges";
import { FindingCard } from "@/components/finding-card";
import { ApiReferenceView } from "@/components/run/api-reference-view";
import { AgentResultCard } from "@/components/run/agent-result-card";
import { RunLog } from "@/components/run/run-log";
import { Button } from "@/components/ui/button";
import { useApiData } from "@/hooks/use-api-data";
import {
  cancelRun,
  getRun,
  getRunEvents,
  runFileUrl,
  startAgentRun,
  startCheckChange,
  startQuickScan,
  type RunDetail,
} from "@/lib/api";

const POLL_MS = 1500;

const KIND_LABELS: Record<RunDetail["kind"], string> = {
  "quick-scan": "Quick Scan",
  "check-change": "Check my change",
  agent: "Agent run",
  "save-test": "Save as test",
  "saved-test": "Saved test",
};

function duration(run: RunDetail) {
  if (!run.finished_at) return null;
  const seconds = Math.round((Date.parse(run.finished_at) - Date.parse(run.started_at)) / 1000);
  return seconds < 90 ? `${seconds} s` : `${Math.round(seconds / 60)} min`;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      size="sm"
      variant="outline"
      onClick={() =>
        navigator.clipboard.writeText(text).then(
          () => setCopied(true),
          () => setCopied(false),
        )
      }
    >
      <Copy aria-hidden /> {copied ? "Copied" : "Copy"}
    </Button>
  );
}

/** Start the same run again with the same prompt and settings. Not offered for runs built from another run. */
function RerunButton({ run }: { run: RunDetail }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const p = run.params;
  const target = { app_url: p.app_url ?? undefined, app_repo_path: p.app_repo_path ?? undefined };
  const start = () => {
    if (run.kind === "agent" && p.agent && p.task) {
      return startAgentRun({ agent: p.agent, task: p.task, route: p.route ?? undefined, mode: p.mode, ...target });
    }
    if (run.kind === "check-change") {
      return startCheckChange({ mode: p.mode, base_ref: p.base_ref ?? undefined, flow: p.flow ?? undefined, ...target });
    }
    if (run.kind === "quick-scan") return startQuickScan(p.mode, target);
    return null;
  };
  if (!["agent", "check-change", "quick-scan"].includes(run.kind)) return null;
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        size="sm"
        disabled={busy}
        onClick={() => {
          const request = start();
          if (!request) return;
          setBusy(true);
          setError(null);
          request.then(
            (next) => router.push(`/runs/${next.id}`),
            (err: unknown) => {
              setError(err instanceof Error ? err.message : String(err));
              setBusy(false);
            },
          );
        }}
      >
        <RotateCw aria-hidden /> {busy ? "Starting…" : "Run again"}
      </Button>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

function Artifacts({ run }: { run: RunDetail }) {
  const shots = run.artifacts.filter((a) => a.kind === "screenshot");
  const files = run.artifacts.filter((a) => a.kind !== "screenshot");
  if (run.artifacts.length === 0) return null;
  return (
    <section aria-labelledby="artifacts-heading" className="grid gap-3">
      <h2 id="artifacts-heading" className="text-lg font-semibold">
        Evidence
      </h2>
      {shots.length > 0 && (
        <ul className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {shots.map((a) => (
            <li key={a.path} className="min-w-0">
              <a href={runFileUrl(run.id, a.path)} target="_blank" rel="noreferrer" className="block rounded-md border">
                {/* eslint-disable-next-line @next/next/no-img-element -- local run evidence served by the QA backend */}
                <img src={runFileUrl(run.id, a.path)} alt={a.label} loading="lazy" className="h-32 w-full rounded-md object-cover object-top" />
              </a>
              <p className="mt-1 truncate text-xs text-muted-foreground">{a.label}</p>
            </li>
          ))}
        </ul>
      )}
      {files.length > 0 && (
        <ul className="grid gap-1 text-sm">
          {files.map((a) => (
            <li key={a.path}>
              <a className="underline underline-offset-4" href={runFileUrl(run.id, a.path)}>
                {a.label}
              </a>
              {a.kind === "trace" && (
                <span className="text-muted-foreground"> · open with <code>npx playwright show-trace &lt;file&gt;</code></span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function RunReport() {
  const { id } = useParams<{ id: string }>();
  const [cancelError, setCancelError] = useState<string | null>(null);
  // Poll while the run is running; when it finishes the interval changes, which triggers one
  // final load of both the run and its events, then polling stops.
  const [finished, setFinished] = useState<string | null>(null);
  const interval = finished === id ? undefined : POLL_MS;
  const run = useApiData(`run:${id}`, (signal) => getRun(id, { signal }), interval);
  const events = useApiData(`events:${id}`, (signal) => getRunEvents(id, 0, { signal }), interval);

  const data = run.data;
  const isFinished = data?.id === id && data.status === "finished";
  if (isFinished && finished !== id) setFinished(id);

  if (run.error && !data) {
    return (
      <div role="alert" className="grid gap-2">
        <h1 className="text-2xl font-semibold">Run not available</h1>
        <p className="text-muted-foreground">{run.error}</p>
        <Link href="/runs" className="underline underline-offset-4">
          Back to runs
        </Link>
      </div>
    );
  }
  if (!data) return <p className="text-muted-foreground">Loading run…</p>;

  const running = data.status === "running";
  const findings = [...data.findings].sort((a, b) => Number(a.status !== "open") - Number(b.status !== "open"));

  return (
    <div className="grid gap-8">
      <header className="grid gap-2">
        <p className="text-sm text-muted-foreground">
          <Link href="/runs" className="underline-offset-4 hover:underline">
            Runs
          </Link>{" "}
          / {KIND_LABELS[data.kind]}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{data.title}</h1>
          <VerdictBadge verdict={running ? null : data.verdict} />
          <Tag>{data.params.mode} mode</Tag>
        </div>
        <p className="text-sm text-muted-foreground">
          Started {new Date(data.started_at).toLocaleString()}
          {duration(data) && ` · took ${duration(data)}`} · {data.counts.open} open of {data.counts.total} finding
          {data.counts.total === 1 ? "" : "s"}
        </p>
        {!running && <RerunButton run={data} />}
        {running && (
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                cancelRun(data.id).then(
                  () => run.reload(),
                  (err: unknown) => setCancelError(err instanceof Error ? err.message : String(err)),
                )
              }
            >
              Cancel run
            </Button>
            {cancelError && (
              <p role="alert" className="text-sm text-destructive">
                {cancelError}
              </p>
            )}
          </div>
        )}
        {data.blocked_reason && (
          <p role="status" className="rounded-lg border border-amber-600/30 bg-amber-500/10 p-3 text-sm">
            <strong>BLOCKED:</strong> {data.blocked_reason}
          </p>
        )}
      </header>

      {data.plan_summary && (
        <section aria-labelledby="plan-heading" className="grid gap-1">
          <h2 id="plan-heading" className="text-lg font-semibold">
            QA Lead plan
          </h2>
          <p className="text-sm whitespace-pre-wrap">{data.plan_summary}</p>
        </section>
      )}

      {data.test_cases.length > 0 && (
        <section aria-labelledby="cases-heading" className="grid gap-2">
          <h2 id="cases-heading" className="text-lg font-semibold">
            Test cases (planned first, {data.test_cases.length})
          </h2>
          <ul className="grid gap-2">
            {data.test_cases.map((c) => (
              <li key={c.id} className="rounded-lg border p-3 text-sm">
                <p className="font-medium">
                  {c.id} · {c.title} <Tag>{c.status}</Tag>
                </p>
                <p className="text-muted-foreground">{c.agent}</p>
                {c.steps.length > 0 && (
                  <ol className="ml-5 list-decimal">
                    {c.steps.map((st, i) => (
                      <li key={i}>{st}</li>
                    ))}
                  </ol>
                )}
                {c.expected && <p>Expected: {c.expected}</p>}
                {c.note && <p className="text-muted-foreground">{c.note}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.saved_test && (
        <section aria-labelledby="saved-heading" className="grid gap-1 rounded-xl border p-4 text-sm">
          <h2 id="saved-heading" className="font-semibold">
            Saved test {data.saved_test.test_id}
          </h2>
          <p>
            <code>{data.saved_test.file}</code> on branch <code>{data.saved_test.branch}</code>
            {data.saved_test.commit && ` (commit ${data.saved_test.commit.slice(0, 8)})`}
          </p>
          {data.saved_test.pr_url ? (
            <a href={data.saved_test.pr_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 underline underline-offset-4">
              Open the PR <ExternalLink className="size-3" aria-hidden />
            </a>
          ) : (
            !running && <p className="text-muted-foreground">Not pushed. See the progress log for why.</p>
          )}
        </section>
      )}

      {data.api_references.length > 0 && (
        <section aria-labelledby="api-heading" className="grid gap-3">
          <h2 id="api-heading" className="text-lg font-semibold">
            API in plain words
          </h2>
          {data.api_references.map((ref) => (
            <ApiReferenceView key={ref.url} runId={data.id} reference={ref} />
          ))}
        </section>
      )}

      {data.agents.length > 0 && (
        <section aria-labelledby="agents-heading" className="grid gap-3">
          <h2 id="agents-heading" className="text-lg font-semibold">
            Agents
          </h2>
          {data.agents.map((result, i) => (
            <AgentResultCard key={`${result.agent}-${i}`} runId={data.id} result={result} />
          ))}
        </section>
      )}

      <section aria-labelledby="findings-heading" className="grid gap-3">
        <h2 id="findings-heading" className="text-lg font-semibold">
          Findings
        </h2>
        {findings.length === 0 && (
          <p className="text-sm text-muted-foreground">{running ? "None yet." : "No findings."}</p>
        )}
        {findings.map((finding) => (
          <FindingCard key={finding.id} runId={data.id} finding={finding} locked={running} onDecided={() => run.reload()} />
        ))}
      </section>

      <Artifacts run={data} />

      {!running && (
        <section aria-labelledby="summary-heading" className="grid gap-2">
          <div className="flex items-center justify-between gap-2">
            <h2 id="summary-heading" className="text-lg font-semibold">
              Summary for the PR description
            </h2>
            <CopyButton text={data.report_summary} />
          </div>
          <pre className="overflow-auto rounded-lg border bg-muted/30 p-3 font-mono text-xs whitespace-pre-wrap">
            {data.report_summary}
          </pre>
        </section>
      )}

      <RunLog events={events.data?.events ?? []} live={running} />
    </div>
  );
}
