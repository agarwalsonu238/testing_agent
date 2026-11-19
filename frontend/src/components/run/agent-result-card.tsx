import { CircleCheck, CircleMinus, CircleX } from "lucide-react";

import { VerdictBadge } from "@/components/badges";
import { agentLabel } from "@/components/finding-card";
import { runFileUrl, type AgentResult, type Step } from "@/lib/api";

const STEP_ICON: Record<Step["status"], React.ReactNode> = {
  pass: <CircleCheck className="size-4 text-emerald-600" aria-label="pass" />,
  fail: <CircleX className="size-4 text-red-600" aria-label="fail" />,
  skipped: <CircleMinus className="size-4 text-muted-foreground" aria-label="skipped" />,
};

export function AgentResultCard({ runId, result }: { runId: string; result: AgentResult }) {
  return (
    <article className="grid gap-3 rounded-xl border bg-card p-4">
      <header className="flex flex-wrap items-center gap-2">
        <h3 className="font-medium">{agentLabel(result.agent)}</h3>
        <VerdictBadge verdict={result.verdict} />
        {result.duration_s != null && (
          <span className="text-xs text-muted-foreground">{Math.round(result.duration_s)} s</span>
        )}
      </header>
      {result.blocked_reason && <p className="text-sm text-amber-800 dark:text-amber-300">{result.blocked_reason}</p>}
      {result.summary && <p className="text-sm">{result.summary}</p>}
      <details className="text-sm">
        <summary className="cursor-pointer text-muted-foreground">Task</summary>
        <p className="mt-1 whitespace-pre-wrap">{result.task}</p>
      </details>

      {result.steps.length > 0 && (
        <section aria-label="Steps" className="grid gap-2">
          <h4 className="text-sm font-medium">Steps (as reported by the agent)</h4>
          <ol className="grid gap-2">
            {result.steps.map((step) => (
              <li key={step.index} className="grid gap-2 rounded-lg border p-2 text-sm sm:grid-cols-[1fr_10rem]">
                <div className="flex items-start gap-2">
                  {STEP_ICON[step.status]}
                  <div>
                    <p>
                      {step.index}. {step.description}
                    </p>
                    {step.note && <p className="text-muted-foreground">{step.note}</p>}
                  </div>
                </div>
                {step.screenshot && (
                  <a href={runFileUrl(runId, step.screenshot)} target="_blank" rel="noreferrer" className="block rounded border">
                    {/* eslint-disable-next-line @next/next/no-img-element -- local run evidence served by the QA backend */}
                    <img
                      src={runFileUrl(runId, step.screenshot)}
                      alt={`Step ${step.index} screenshot`}
                      loading="lazy"
                      className="max-h-28 w-full object-cover object-top"
                    />
                  </a>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}

      {result.checks.length > 0 && (
        <section aria-label="Recorded checks" className="grid gap-1">
          <h4 className="text-sm font-medium">Checks recorded by Playwright (these decide the verdict)</h4>
          <ul className="grid gap-1 text-sm">
            {result.checks.map((check) => (
              <li key={`${check.source}-${check.detail}`} className="flex items-start gap-2">
                {check.passed ? STEP_ICON.pass : STEP_ICON.fail}
                <span className="break-words">
                  <span className="text-muted-foreground">{check.source}:</span> {check.detail}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
