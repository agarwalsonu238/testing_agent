import type { Metadata } from "next";

import { RunsTable } from "@/components/runs-table";

export const metadata: Metadata = { title: "Runs" };

export default function RunsPage() {
  return (
    <section className="grid gap-4" aria-labelledby="runs-heading">
      <div>
        <h1 id="runs-heading" className="text-2xl font-semibold tracking-tight">
          Runs
        </h1>
        <p className="text-muted-foreground">The last 20 runs. Each one is a folder on this machine.</p>
      </div>
      <RunsTable />
    </section>
  );
}
