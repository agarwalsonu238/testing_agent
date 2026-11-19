import type { Metadata } from "next";
import { Suspense } from "react";

import { AgentRunPanel } from "@/components/agent-run-panel";

export const metadata: Metadata = { title: "Run one agent" };

export default function AgentPage() {
  return (
    <Suspense fallback={<p className="text-muted-foreground">Loading agent…</p>}>
      <AgentRunPanel />
    </Suspense>
  );
}
