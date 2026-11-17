"use client";

import {
  Bot,
  CircleCheck,
  CircleExclamationPoint,
  Clock,
  FlaskConical,
  Inbox,
  Play,
  ScanSearch,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { agentLabel } from "@/components/finding-card";
import { useApiData } from "@/hooks/use-api-data";
import { cn } from "@/lib/utils";
import { getQaConfig, listFindings } from "@/lib/api";

const linkClass =
  "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none hover:bg-sidebar-accent focus-visible:ring-3 focus-visible:ring-ring/50";

function NavLink({
  href,
  icon,
  children,
  active,
  badge,
}: {
  href: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  active: boolean;
  badge?: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(linkClass, active && "bg-sidebar-accent font-medium")}
    >
      <span aria-hidden className="text-muted-foreground [&_svg]:size-4">
        {icon}
      </span>
      <span className="flex-1">{children}</span>
      {badge}
    </Link>
  );
}

export function AppSidebar() {
  const pathname = usePathname();
  // Refresh the counts when the developer moves between pages.
  const findings = useApiData(`sidebar-findings:${pathname}`, (signal) =>
    listFindings({ status: "open" }, { signal }),
  );
  const config = useApiData("qa-config", (signal) => getQaConfig({ signal }));
  const open = findings.data?.length;

  return (
    <aside className="border-b bg-sidebar text-sidebar-foreground md:sticky md:top-0 md:h-screen md:w-64 md:shrink-0 md:overflow-y-auto md:border-r md:border-b-0">
      <div className="flex flex-col gap-4 p-3">
        <div className="px-2">
          <Link href="/" className="font-semibold tracking-tight">
            QA Testing Agent
          </Link>
          <p className="truncate text-xs text-muted-foreground" title={config.data?.app_url}>
            testing {config.data?.app_url.replace(/^https?:\/\//, "") ?? "…"}
          </p>
        </div>

        <nav aria-label="Main" className="grid gap-0.5">
          <NavLink href="/check" icon={<Play />} active={pathname === "/check"}>
            Check my change
          </NavLink>
          <NavLink href="/scan" icon={<ScanSearch />} active={pathname === "/scan"}>
            Quick Scan
          </NavLink>
          <NavLink
            href="/"
            icon={<Inbox />}
            active={pathname === "/"}
            badge={
              open ? (
                <span className="rounded-full bg-primary px-1.5 text-xs text-primary-foreground" aria-label={`${open} open`}>
                  {open}
                </span>
              ) : null
            }
          >
            To review
          </NavLink>
          <NavLink href="/runs" icon={<Clock />} active={pathname.startsWith("/runs")}>
            Runs
          </NavLink>
          <NavLink href="/saved-tests" icon={<FlaskConical />} active={pathname === "/saved-tests"}>
            Saved tests
          </NavLink>
          <NavLink href="/setup" icon={<ShieldCheck />} active={pathname === "/setup"}>
            Setup check
          </NavLink>
        </nav>

        <nav aria-label="Agents" className="grid gap-0.5">
          <p className="px-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">Agents</p>
          {config.error && (
            <p className="flex items-center gap-1 px-2 text-xs text-destructive">
              <CircleExclamationPoint className="size-3" aria-hidden /> Backend unreachable
            </p>
          )}
          {config.data?.agents.map((agent) => (
            <NavLink
              key={agent.name}
              href={`/agents/${agent.name}`}
              icon={agent.name === "qa-lead" ? <CircleCheck /> : <Bot />}
              active={pathname === `/agents/${agent.name}`}
            >
              {agentLabel(agent.name)}
            </NavLink>
          ))}
        </nav>
      </div>
    </aside>
  );
}
