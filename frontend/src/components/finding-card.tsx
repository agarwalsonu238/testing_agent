"use client";

import { useId, useState } from "react";

import { SeverityBadge, Tag } from "@/components/badges";
import { EvidenceView } from "@/components/evidence-view";
import { fieldClass } from "@/components/form-styles";
import { Button } from "@/components/ui/button";
import { decideFinding, type Finding } from "@/lib/api";

const AGENT_LABELS: Record<string, string> = {
  "quick-scan": "Quick Scan",
  "qa-lead": "QA Lead",
  "design-reviewer": "Design reviewer",
  "functionality-tester": "Functionality tester",
  "code-reviewer": "Code reviewer",
  "api-checker": "API checker",
  "test-writer": "Test writer",
  "saved-test": "Saved test",
};

export const agentLabel = (name: string) => AGENT_LABELS[name] ?? name;

type Props = {
  runId: string;
  finding: Finding;
  onDecided?: (finding: Finding) => void;
  /** Read-only while the run is still writing its results. */
  locked?: boolean;
};

export function FindingCard({ runId, finding, onDecided, locked }: Props) {
  const [current, setCurrent] = useState(finding);
  const [ignoring, setIgnoring] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reasonId = useId();
  const errorId = useId();

  async function decide(decision: "accept" | "ignore") {
    if (decision === "ignore" && !reason.trim()) {
      setError("Add a one-line reason so the same finding is skipped next time.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await decideFinding(runId, current.id, {
        decision,
        reason: decision === "ignore" ? reason.trim() : undefined,
      });
      setCurrent(updated);
      setIgnoring(false);
      onDecided?.(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="grid gap-3 rounded-xl border bg-card p-4 text-card-foreground" aria-labelledby={`${reasonId}-title`}>
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">
            {agentLabel(current.agent)} · {current.location}
          </p>
          <h3 id={`${reasonId}-title`} className="font-medium break-words">
            {current.title}
          </h3>
        </div>
        <div className="flex flex-wrap gap-1">
          <SeverityBadge severity={current.severity} />
          <Tag>{current.category}</Tag>
        </div>
      </header>

      {(current.expected || current.actual) && (
        <dl className="grid gap-1 text-sm sm:grid-cols-[6rem_1fr]">
          {current.expected && (
            <>
              <dt className="text-muted-foreground">Expected</dt>
              <dd className="break-words">{current.expected}</dd>
            </>
          )}
          {current.actual && (
            <>
              <dt className="text-muted-foreground">Happened</dt>
              <dd className="break-words">{current.actual}</dd>
            </>
          )}
        </dl>
      )}

      {current.suggested_fix && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground">Suggested fix (nothing applied)</summary>
          <pre className="mt-1 overflow-auto rounded-md border bg-muted/50 p-2 font-mono text-xs whitespace-pre-wrap">
            {current.suggested_fix}
          </pre>
        </details>
      )}

      <EvidenceView runId={runId} evidence={current.evidence} />

      <footer className="grid gap-2">
        {current.status === "open" && !ignoring && (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => decide("accept")} disabled={busy || locked}>
              Accept
            </Button>
            <Button size="sm" variant="outline" onClick={() => setIgnoring(true)} disabled={busy || locked}>
              Ignore
            </Button>
          </div>
        )}
        {current.status === "open" && ignoring && (
          <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void decide("ignore");
            }}
          >
            <div className="grid min-w-56 flex-1 gap-1">
              <label htmlFor={reasonId} className="text-sm">
                Why ignore it?
              </label>
              <input
                id={reasonId}
                className={fieldClass}
                value={reason}
                maxLength={300}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Third-party widget, tracked in #123"
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? errorId : undefined}
                autoFocus
              />
            </div>
            <Button size="sm" type="submit" disabled={busy}>
              Ignore finding
            </Button>
            <Button size="sm" variant="ghost" type="button" onClick={() => setIgnoring(false)} disabled={busy}>
              Cancel
            </Button>
          </form>
        )}
        {current.status === "accepted" && <p className="text-sm">Accepted: a bug to fix.</p>}
        {current.status === "ignored" && (
          <p className="text-sm text-muted-foreground">Ignored: {current.ignore_reason}</p>
        )}
        {error && (
          <p id={errorId} role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </footer>
    </article>
  );
}
