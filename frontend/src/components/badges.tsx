import { cn } from "@/lib/utils";
import type { Severity, Verdict } from "@/lib/api";

const pill = "inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-semibold tracking-wide";

const VERDICT_STYLES: Record<Verdict | "RUNNING", string> = {
  PASS: "border-emerald-600/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300",
  FAILING: "border-red-600/30 bg-red-500/10 text-red-800 dark:text-red-300",
  BLOCKED: "border-amber-600/30 bg-amber-500/10 text-amber-900 dark:text-amber-300",
  RUNNING: "border-sky-600/30 bg-sky-500/10 text-sky-800 dark:text-sky-300",
};

export function VerdictBadge({ verdict }: { verdict: Verdict | null }) {
  const value = verdict ?? "RUNNING";
  return <span className={cn(pill, VERDICT_STYLES[value])}>{value}</span>;
}

const SEVERITY_STYLES: Record<Severity, string> = {
  High: "border-red-600/30 bg-red-500/10 text-red-800 dark:text-red-300",
  Medium: "border-amber-600/30 bg-amber-500/10 text-amber-900 dark:text-amber-300",
  Warning: "border-border bg-muted text-muted-foreground",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <span className={cn(pill, "font-medium", SEVERITY_STYLES[severity])}>{severity}</span>;
}

export function Tag({ children }: { children: React.ReactNode }) {
  return <span className={cn(pill, "border-border font-normal text-muted-foreground")}>{children}</span>;
}
