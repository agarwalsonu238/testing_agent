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
          The QA Lead plans test case scenarios first — the normal path plus edge cases, from your diff and
          anything you describe — then the Functionality tester runs every one of them before the (optional)
          Design and Code review. Functionality is always checked, even with no local diff. Runs use your own
          Claude plan; run Quick Scan first.
        </p>
      </div>
      <StartRunForm variant={{ kind: "check-change" }} />
    </section>
  );
}
