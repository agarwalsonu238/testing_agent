"use client";

import { useRef, useState } from "react";

import { Tag } from "@/components/badges";
import { agentLabel } from "@/components/finding-card";
import { AgentResultCard } from "@/components/run/agent-result-card";
import { Button } from "@/components/ui/button";
import { approveRun, type RunDetail, type TestCase } from "@/lib/api";
import { cn } from "@/lib/utils";

export type StageKey = "plan" | "review" | "run" | "report";
type StageState = "done" | "active" | "pending";

export const STAGES: { key: StageKey; title: string; hint: string }[] = [
  { key: "plan", title: "1 · Plan", hint: "QA Lead writes the test cases" },
  { key: "review", title: "2 · Review", hint: "A second agent checks the cases" },
  { key: "run", title: "3 · Run", hint: "Agents execute the approved cases" },
  { key: "report", title: "4 · Report", hint: "Findings and the final summary" },
];

/**
 * Where each tab stands. A running run reports its own stage; for finished runs (and runs saved
 * before stages existed) it is worked out from what the run produced.
 */
export function stageStates(run: RunDetail): Record<StageKey, StageState> {
  const planned = Boolean(run.plan_summary) || run.test_cases.length > 0;
  // The reviewer runs right before the cases are stored, so stored cases mean the review is done.
  const reviewed = run.test_cases.length > 0;
  const reported = run.agents.length > 0;
  if (run.status === "finished") {
    return {
      plan: planned ? "done" : "pending",
      review: reviewed ? "done" : "pending",
      run: reported ? "done" : "pending",
      report: reported ? "done" : "pending",
    };
  }
  switch (run.stage) {
    case "planning":
      return { plan: "active", review: "pending", run: "pending", report: "pending" };
    case "reviewing":
    case "awaiting_approval":
      return { plan: "done", review: "active", run: "pending", report: "pending" };
    case "running":
      return { plan: "done", review: "done", run: "active", report: "pending" };
    case "reporting":
    case "done":
      return { plan: "done", review: "done", run: "done", report: "active" };
    default:
      // No stage reported (an older run): infer it.
      if (!planned) return { plan: "active", review: "pending", run: "pending", report: "pending" };
      if (!reviewed) return { plan: "done", review: "active", run: "pending", report: "pending" };
      return { plan: "done", review: "done", run: "active", report: "pending" };
  }
}

/** The tab to show by default: the stage in progress, or the last stage a finished run reached. */
export function defaultStage(run: RunDetail): StageKey {
  const states = stageStates(run);
  const active = STAGES.find((s) => states[s.key] === "active");
  if (active) return active.key;
  return [...STAGES].reverse().find((s) => states[s.key] === "done")?.key ?? "plan";
}

const STATE_MARK: Record<StageState, string> = { done: "✓", active: "●", pending: "○" };
const STATE_LABEL: Record<StageState, string> = { done: "done", active: "in progress", pending: "not started" };

export function StageTabs({
  run,
  selected,
  onSelect,
}: {
  run: RunDetail;
  selected: StageKey;
  onSelect: (key: StageKey) => void;
}) {
  const states = stageStates(run);
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  function onKeyDown(e: React.KeyboardEvent, index: number) {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = STAGES[(index + step + STAGES.length) % STAGES.length].key;
    onSelect(next);
    refs.current[next]?.focus();
  }

  return (
    <div role="tablist" aria-label="Pipeline stages" className="-mx-1 flex gap-1 overflow-x-auto border-b px-1 pb-2">
      {STAGES.map((stage, i) => {
        const active = stage.key === selected;
        return (
          <button
            key={stage.key}
            ref={(el) => {
              refs.current[stage.key] = el;
            }}
            type="button"
            role="tab"
            id={`stage-tab-${stage.key}`}
            aria-selected={active}
            aria-controls={`stage-panel-${stage.key}`}
            tabIndex={active ? 0 : -1}
            onClick={() => onSelect(stage.key)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cn(
              "grid gap-0.5 rounded-md px-3 py-1.5 text-left text-sm whitespace-nowrap outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50",
              active && "bg-muted font-medium",
            )}
          >
            <span>
              <span aria-hidden>{STATE_MARK[states[stage.key]]} </span>
              {stage.title}
              <span className="sr-only"> ({STATE_LABEL[states[stage.key]]})</span>
            </span>
            <span className="text-xs font-normal text-muted-foreground">{stage.hint}</span>
          </button>
        );
      })}
    </div>
  );
}

export function StagePanel({ stage, children }: { stage: StageKey; children: React.ReactNode }) {
  return (
    <div role="tabpanel" id={`stage-panel-${stage}`} aria-labelledby={`stage-tab-${stage}`} className="grid min-w-0 grid-cols-1 gap-6">
      {children}
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">{children}</p>;
}

/** Stage 1: what the QA Lead decided to test, as first written. */
export function PlanStage({ run }: { run: RunDetail }) {
  const running = run.status === "running";
  return (
    <>
      {run.plan_summary && (
        <section aria-labelledby="plan-heading" className="grid gap-1">
          <h2 id="plan-heading" className="text-lg font-semibold">
            QA Lead plan
          </h2>
          <p className="text-sm whitespace-pre-wrap break-words">{run.plan_summary}</p>
        </section>
      )}
      <section aria-labelledby="cases-heading" className="grid grid-cols-1 gap-2">
        <h2 id="cases-heading" className="text-lg font-semibold">
          Test cases ({run.test_cases.length})
        </h2>
        {run.test_cases.length === 0 && (
          <Empty>{running ? "The QA Lead is still writing the test cases…" : "No test cases were written for this run."}</Empty>
        )}
        <ul className="grid grid-cols-1 gap-2">
          {run.test_cases.map((c) => (
            <li key={c.id} className="min-w-0 rounded-lg border p-3 text-sm">
              <p className="font-medium break-words">
                {c.id} · {c.title}
              </p>
              <p className="text-muted-foreground">{agentLabel(c.agent)}</p>
              {c.steps.length > 0 && (
                <ol className="ml-5 list-decimal break-words">
                  {c.steps.map((st, i) => (
                    <li key={i}>{st}</li>
                  ))}
                </ol>
              )}
              {c.expected && <p className="break-words">Expected: {c.expected}</p>}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

const REVIEW_LABEL = { approved: "Approved as written", rewritten: "Rewritten", rejected: "Rejected" } as const;

/** The reviewer's decision. Runs saved before `review_status` existed only carry a note for rewrites. */
function reviewStatus(c: TestCase): TestCase["review_status"] {
  return c.review_status ?? (c.review_note ? "rewritten" : null);
}

function reviewLabel(c: TestCase) {
  const status = reviewStatus(c);
  return status ? REVIEW_LABEL[status] : "Review not recorded";
}

/** Stage 2: what the test-case reviewer decided about each case, and (when asked) your go-ahead. */
export function ReviewStage({ run, onApproved }: { run: RunDetail; onApproved?: () => void }) {
  const running = run.status === "running";
  const waiting = run.awaiting_approval;
  const [skipped, setSkipped] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const counts = { approved: 0, rewritten: 0, rejected: 0 };
  for (const c of run.test_cases) {
    const status = reviewStatus(c);
    if (status) counts[status] += 1;
  }
  const runnable = run.test_cases.filter((c) => c.status === "planned");
  const toRun = runnable.filter((c) => !skipped.has(c.id));

  function toggle(id: string) {
    setSkipped((prev) => {
      const next = new Set(prev);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  }

  function approve() {
    setBusy(true);
    setError(null);
    approveRun(run.id, [...skipped]).then(
      () => {
        setBusy(false);
        onApproved?.();
      },
      (err: unknown) => {
        setError(err instanceof Error ? err.message : String(err));
        setBusy(false);
      },
    );
  }

  return (
    <section aria-labelledby="review-stage-heading" className="grid grid-cols-1 gap-3">
      <h2 id="review-stage-heading" className="text-lg font-semibold">
        Test case review
      </h2>
      {waiting && (
        <div role="status" className="grid gap-2 rounded-xl border border-sky-600/30 bg-sky-500/10 p-4 text-sm">
          <p className="font-medium">The run is paused for you.</p>
          <p>
            Untick any case you don&apos;t want to run, then approve. Nothing is tested until you do. Cancel run (at the top) stops
            it instead.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm" onClick={approve} disabled={busy || toRun.length === 0}>
              {busy ? "Starting…" : `Approve and run ${toRun.length} case${toRun.length === 1 ? "" : "s"}`}
            </Button>
            {toRun.length === 0 && <span className="text-muted-foreground">Tick at least one case, or cancel the run.</span>}
            {error && (
              <span role="alert" className="text-destructive">
                {error}
              </span>
            )}
          </div>
        </div>
      )}
      {run.reviewer && (
        <p className="text-sm">
          Reviewed by <strong>{run.reviewer}</strong>
          {!run.reviewer.startsWith("Claude") && <span className="text-muted-foreground"> (a different AI from the one that wrote the cases)</span>}
        </p>
      )}
      {run.test_cases.length === 0 ? (
        <Empty>{running ? "Waiting for the plan before the cases can be reviewed…" : "No test cases to review."}</Empty>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            {counts.approved} approved as written · {counts.rewritten} rewritten · {counts.rejected} rejected. Only approved
            and rewritten cases go on to run.
          </p>
          <ul className="grid grid-cols-1 gap-2">
            {run.test_cases.map((c) => (
              <li key={c.id} className="min-w-0 rounded-lg border p-3 text-sm">
                <p className="font-medium break-words">
                  {waiting && c.status === "planned" && (
                    <input
                      type="checkbox"
                      className="mr-2 align-middle"
                      checked={!skipped.has(c.id)}
                      onChange={() => toggle(c.id)}
                      aria-label={`Run ${c.id}`}
                    />
                  )}
                  {c.id} · {c.title} <Tag>{reviewLabel(c)}</Tag>
                </p>
                {reviewStatus(c) === "rejected" && c.note && <p className="break-words">Why: {c.note}</p>}
                {reviewStatus(c) === "rewritten" && c.review_note && <p className="break-words">What changed: {c.review_note}</p>}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

const AGENT_ORDER = ["functionality-tester", "code-reviewer", "design-reviewer", "api-checker"];

type GroupState = "waiting" | "running" | "executed" | "not-run";
const GROUP_LABEL: Record<GroupState, string> = {
  waiting: "Waiting",
  running: "Running now",
  executed: "Executed",
  "not-run": "Not run",
};

/** Stage 3: each agent in turn, with its cases (and its report once stage 4 has written it). */
export function AgentSteps({ run }: { run: RunDetail }) {
  const finished = run.status === "finished";
  const names = [...new Set([...run.test_cases.map((c) => c.agent), ...run.agents.map((a) => a.agent)])].sort(
    (a, b) => (AGENT_ORDER.indexOf(a) + 1 || 99) - (AGENT_ORDER.indexOf(b) + 1 || 99),
  );
  const groups = names
    .map((name) => {
      const cases = run.test_cases.filter((c) => c.agent === name && c.review_status !== "rejected");
      const results = run.agents.filter((a) => a.agent === name);
      return { name, cases, results };
    })
    .filter((g) => g.cases.length > 0 || g.results.length > 0);

  if (groups.length === 0) {
    return <Empty>{finished ? "No agent ran." : "No agent has started yet."}</Empty>;
  }
  return (
    <section aria-labelledby="agent-steps-heading" className="grid grid-cols-1 gap-4">
      <h2 id="agent-steps-heading" className="text-lg font-semibold">
        Agents, one at a time
      </h2>
      {groups.map(({ name, cases, results }) => {
        const executed = cases.length > 0 && cases.every((c) => c.status !== "planned");
        const state: GroupState = executed
          ? "executed"
          : run.stage === "running" && run.activity?.startsWith(`${name} `)
            ? "running"
            : finished
              ? "not-run"
              : "waiting";
        return (
          <div key={name} className="grid min-w-0 grid-cols-1 gap-2 rounded-xl border p-4">
            <h3 className="flex flex-wrap items-center gap-2 font-medium">
              {agentLabel(name)} <Tag>{GROUP_LABEL[state]}</Tag>
            </h3>
            {state === "running" && run.activity && <p className="text-sm text-muted-foreground">{run.activity}</p>}
            <ul className="grid grid-cols-1 gap-2">
              {cases.map((c) => (
                <li key={c.id} className="min-w-0 rounded-lg border p-3 text-sm">
                  <p className="font-medium break-words">
                    {c.id} · {c.title} <Tag>{c.status}</Tag>
                  </p>
                  {c.note && <p className="break-words">{c.note}</p>}
                </li>
              ))}
            </ul>
            {results.map((result, i) => (
              <AgentResultCard key={`${result.agent}-${i}`} runId={run.id} result={result} />
            ))}
          </div>
        );
      })}
    </section>
  );
}
