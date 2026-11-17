import type { Metadata } from "next";
import { Suspense } from "react";

import { RunReport } from "@/components/run/run-report";

export const metadata: Metadata = { title: "Run report" };

export default function RunPage() {
  return (
    <Suspense fallback={<p className="text-muted-foreground">Loading run…</p>}>
      <RunReport />
    </Suspense>
  );
}
