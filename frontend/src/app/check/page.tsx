import type { Metadata } from "next";

import { StartRunForm } from "@/components/start-run-form";

export const metadata: Metadata = { title: "Check my change" };

export default function CheckChangePage() {
  return (
    <section className="grid gap-6" aria-labelledby="check-heading">
      <div className="grid gap-1">
        <h1 id="check-heading" className="text-2xl font-semibold tracking-tight">
          Check my change
        </h1>
        <p className="max-w-2xl text-muted-foreground">
          The QA Lead reads your diff and runs the right agents: UI files → Design reviewer, logic or API →
          Functionality tester, every change → Code reviewer. Runs use your own Claude plan; run Quick Scan first.
        </p>
      </div>
      <StartRunForm variant={{ kind: "check-change" }} />
    </section>
  );
}
