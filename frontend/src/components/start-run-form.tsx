"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { fieldClass, labelClass } from "@/components/form-styles";
import { MicButton } from "@/components/mic-button";
import { ModePicker } from "@/components/mode-picker";
import { Button } from "@/components/ui/button";
import {
  startAgentRun,
  startCheckChange,
  startQuickScan,
  type RunDetail,
  type RunMode,
} from "@/lib/api";

type Variant =
  | { kind: "quick-scan" }
  | { kind: "check-change" }
  | { kind: "agent"; agent: string; needsRoute: boolean };

const SUBMIT_LABEL: Record<Variant["kind"], string> = {
  "quick-scan": "Run Quick Scan",
  "check-change": "Check my change",
  agent: "Run agent",
};

/** Start a run and open its live report. Errors (another run active, API key set…) stay on the form. */
export function StartRunForm({ variant }: { variant: Variant }) {
  const router = useRouter();
  const id = useId();
  const [mode, setMode] = useState<RunMode>("mocked");
  const [text, setText] = useState("");
  const [route, setRoute] = useState("");
  const [baseRef, setBaseRef] = useState("");
  const [appUrl, setAppUrl] = useState("");
  const [repoPath, setRepoPath] = useState("");
  const [approvePlan, setApprovePlan] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function appendDictated(chunk: string) {
    setText((prev) => (prev.trim() ? `${prev.replace(/\s+$/, "")} ${chunk}` : chunk));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const target = {
        app_url: appUrl.trim() || undefined,
        app_repo_path: repoPath.trim() || undefined,
      };
      let run: RunDetail;
      if (variant.kind === "quick-scan") {
        run = await startQuickScan(mode, target);
      } else if (variant.kind === "check-change") {
        run = await startCheckChange({
          mode,
          base_ref: baseRef.trim() || undefined,
          flow: text.trim() || undefined,
          approve_plan: approvePlan,
          ...target,
        });
      } else {
        run = await startAgentRun({
          agent: variant.agent,
          task: text.trim(),
          route: route.trim() || undefined,
          mode,
          approve_plan: approvePlan,
          ...target,
        });
      }
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  const errorId = `${id}-error`;
  return (
    <form onSubmit={submit} className="grid max-w-2xl gap-5" aria-describedby={error ? errorId : undefined}>
      <fieldset className="grid gap-3 rounded-lg border p-4">
        <legend className="px-1 text-sm font-medium">Project to test (optional)</legend>
        <div className="grid gap-1">
          <label htmlFor={`${id}-app-url`} className={labelClass}>
            App URL
          </label>
          <input
            id={`${id}-app-url`}
            className={`${fieldClass} font-mono`}
            value={appUrl}
            maxLength={500}
            pattern="https?://\S+"
            onChange={(e) => setAppUrl(e.target.value)}
            placeholder="https://my-app.example.com"
          />
        </div>
        <div className="grid gap-1">
          <label htmlFor={`${id}-repo`} className={labelClass}>
            Project folder
          </label>
          <input
            id={`${id}-repo`}
            className={`${fieldClass} font-mono`}
            value={repoPath}
            maxLength={1000}
            onChange={(e) => setRepoPath(e.target.value)}
            placeholder="/Users/you/Desktop/GitHub/my-project"
          />
        </div>
        <p className="text-xs text-muted-foreground">
          Any project, any stack. Leave both empty to use the server&apos;s default (APP_URL and APP_REPO_PATH).
        </p>
      </fieldset>

      {variant.kind === "check-change" && (
        <>
          <div className="grid gap-1">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label htmlFor={`${id}-flow`} className={labelClass}>
                Flow to test (optional)
              </label>
              <MicButton onText={appendDictated} label="Dictate" />
            </div>
            <textarea
              id={`${id}-flow`}
              className={`${fieldClass} min-h-36 font-mono`}
              value={text}
              maxLength={4000}
              onChange={(e) => setText(e.target.value)}
              placeholder={
                "Describe what to test, in your own words — the QA Lead turns it into test case scenarios (the normal path plus edge cases) before anything runs. For example:\nCheck that booking the same pet for the same date twice cancels the first booking."
              }
            />
            <p className="text-xs text-muted-foreground">
              The QA Lead always writes test case scenarios first, then tests each one — from this description, or from your diff when you leave it empty. Works even with no local changes to diff against.
            </p>
          </div>
          <div className="grid gap-1">
            <label htmlFor={`${id}-base`} className={labelClass}>
              Compare against (optional)
            </label>
            <input
              id={`${id}-base`}
              className={`${fieldClass} font-mono`}
              value={baseRef}
              maxLength={200}
              onChange={(e) => setBaseRef(e.target.value)}
              placeholder="origin/main"
            />
          </div>
        </>
      )}

      {variant.kind === "agent" && (
        <>
          <div className="grid gap-1">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label htmlFor={`${id}-task`} className={labelClass}>
                What should it check?
              </label>
              <MicButton onText={appendDictated} label="Dictate" />
            </div>
            <textarea
              id={`${id}-task`}
              className={`${fieldClass} min-h-36`}
              value={text}
              required
              minLength={3}
              maxLength={4000}
              onChange={(e) => setText(e.target.value)}
              placeholder={
                variant.agent === "functionality-tester"
                  ? "1. Open the home page.\n2. …\nExpected: no console errors and no failed API calls."
                  : variant.agent === "api-checker"
                    ? "Paste an endpoint to test, e.g. GET https://api.example.com/v1/products\nor describe the API change to check. Works for any project."
                    : "Describe what to check"
              }
            />
          </div>
          <div className="grid gap-1">
            <label htmlFor={`${id}-route`} className={labelClass}>
              Route{variant.needsRoute ? "" : " (optional)"}
            </label>
            <input
              id={`${id}-route`}
              className={`${fieldClass} font-mono`}
              value={route}
              required={variant.needsRoute}
              pattern="/\S*"
              maxLength={300}
              onChange={(e) => setRoute(e.target.value)}
              placeholder="/pricing"
            />
          </div>
        </>
      )}

      {/* Mode is meaningless for the two agents that never open the app in a browser. */}
      {variant.kind !== "agent" || !["code-reviewer", "api-checker"].includes(variant.agent) ? (
        <ModePicker value={mode} onChange={setMode} disabled={busy} />
      ) : null}

      {variant.kind !== "quick-scan" && (
        <label className="flex max-w-2xl items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-1"
            checked={approvePlan}
            disabled={busy}
            onChange={(e) => setApprovePlan(e.target.checked)}
          />
          <span>
            Let me approve the test cases before they run
            <span className="block text-xs text-muted-foreground">
              The run writes and reviews the cases, then waits for your go-ahead. You can untick any case. Nothing is tested until
              you approve.
            </span>
          </span>
        </label>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" size="lg" disabled={busy}>
          {busy ? "Starting…" : SUBMIT_LABEL[variant.kind]}
        </Button>
        {error && (
          <p id={errorId} role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </div>
    </form>
  );
}
