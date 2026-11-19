import type { Metadata } from "next";

import { BackendStatus } from "@/components/backend-status";
import { SetupChecklist } from "@/components/setup-checklist";

export const metadata: Metadata = { title: "Setup check" };

export default function SetupPage() {
  return (
    <section className="grid gap-6" aria-labelledby="setup-heading">
      <div>
        <h1 id="setup-heading" className="text-2xl font-semibold tracking-tight">
          Setup check
        </h1>
        <p className="text-muted-foreground">
          Claude Code, your login, the browser and the app must be ready before agents run.
        </p>
      </div>
      <BackendStatus />
      <SetupChecklist />
    </section>
  );
}
