"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { fieldClass, labelClass } from "@/components/form-styles";
import { Button } from "@/components/ui/button";
import { saveAsTest } from "@/lib/api";

export function SaveTestForm({ runId }: { runId: string }) {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [folder, setFolder] = useState<"isolated" | "live">("isolated");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const id = useId();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const run = await saveAsTest(runId, { title: title.trim() || undefined, folder });
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-3 rounded-xl border p-4" aria-labelledby={`${id}-h`}>
      <div>
        <h2 id={`${id}-h`} className="font-semibold">
          Save as test
        </h2>
        <p className="text-sm text-muted-foreground">
          The flow passed. The Test writer turns it into a Playwright test with the next test ID, on a new branch in a
          separate worktree, and opens a PR. Your uncommitted work isn&apos;t touched.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-[1fr_12rem]">
        <div className="grid gap-1">
          <label htmlFor={`${id}-title`} className={labelClass}>
            Test title (optional)
          </label>
          <input
            id={`${id}-title`}
            className={fieldClass}
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Pricing yearly toggle"
          />
        </div>
        <div className="grid gap-1">
          <label htmlFor={`${id}-folder`} className={labelClass}>
            Folder
          </label>
          <select
            id={`${id}-folder`}
            className={fieldClass}
            value={folder}
            onChange={(e) => setFolder(e.target.value as "isolated" | "live")}
          >
            <option value="isolated">Isolated tests</option>
            <option value="live">Live tests</option>
          </select>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={busy}>
          {busy ? "Starting…" : "Save as test"}
        </Button>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </div>
    </form>
  );
}
