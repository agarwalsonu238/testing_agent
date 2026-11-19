"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { agentLabel } from "@/components/finding-card";
import { StartRunForm } from "@/components/start-run-form";
import { useApiData } from "@/hooks/use-api-data";
import { getQaConfig } from "@/lib/api";

/** Agents that only run as part of another flow. */
const NOT_STANDALONE: Record<string, { text: string; href: string; link: string }> = {
  "qa-lead": { text: "The QA Lead plans the checks for your diff.", href: "/check", link: "Check my change" },
  "test-writer": {
    text: "The Test writer runs from Save as test on a passing Functionality tester report.",
    href: "/runs",
    link: "Runs",
  },
};

export function AgentRunPanel() {
  const { name } = useParams<{ name: string }>();
  const config = useApiData("qa-config", (signal) => getQaConfig({ signal }));
  const agent = config.data?.agents.find((a) => a.name === name);
  const other = NOT_STANDALONE[name];

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
      {agent && other && (
        <p className="text-sm">
          {other.text}{" "}
          <Link href={other.href} className="underline underline-offset-4">
            {other.link}
          </Link>
        </p>
      )}
      {agent && !other && (
        <StartRunForm variant={{ kind: "agent", agent: name, needsRoute: name === "design-reviewer" }} />
      )}
    </section>
  );
}
