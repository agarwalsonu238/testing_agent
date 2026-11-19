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
      let run: RunDetail;
      if (variant.kind === "quick-scan") {
        run = await startQuickScan(mode);
      } else if (variant.kind === "check-change") {
        run = await startCheckChange({
          mode,
          base_ref: baseRef.trim() || undefined,
          flow: text.trim() || undefined,
        });
      } else {
        run = await startAgentRun({
          agent: variant.agent,
          task: text.trim(),
          route: route.trim() || undefined,
          mode,
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

      {/* Mode is meaningless for the two static-analysis agents — neither opens a browser. */}
      {variant.kind !== "agent" || !["code-reviewer", "api-checker"].includes(variant.agent) ? (
        <ModePicker value={mode} onChange={setMode} disabled={busy} />
      ) : null}

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
