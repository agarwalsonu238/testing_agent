"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

import { agentLabel } from "@/components/finding-card";
import { StartRunForm } from "@/components/start-run-form";
import { useApiData } from "@/hooks/use-api-data";
import { getQaConfig } from "@/lib/api";

export function AgentRunPanel() {
  const { name } = useParams<{ name: string }>();
  const config = useApiData("qa-config", (signal) => getQaConfig({ signal }));
  const agent = config.data?.agents.find((a) => a.name === name);
  const router = useRouter();
  // QA Lead, the reviewer, the reporter and the Test writer only run inside another flow, so they
  // have no page of their own: send an old link to the flow that uses them.
  const pipelineOnly = agent !== undefined && !agent.standalone;
  useEffect(() => {
    if (pipelineOnly) router.replace(name === "test-writer" ? "/runs" : "/check");
  }, [pipelineOnly, name, router]);

  return (
    <section className="grid gap-6" aria-labelledby="agent-heading">
      <div className="grid gap-1">
        <h1 id="agent-heading" className="text-2xl font-semibold tracking-tight">
          {agentLabel(name)}
        </h1>
        {config.error && (
          <p role="alert" className="text-sm text-destructive">
            Couldn&apos;t load the agent list: {config.error}
          </p>
        )}
        {config.data && !agent && <p className="text-muted-foreground">No agent called “{name}”.</p>}
        {agent && <p className="max-w-2xl text-muted-foreground">{agent.description}</p>}
      </div>
      {agent && !pipelineOnly && (
        <StartRunForm variant={{ kind: "agent", agent: name, needsRoute: name === "design-reviewer" }} />
      )}
    </section>
  );
}
