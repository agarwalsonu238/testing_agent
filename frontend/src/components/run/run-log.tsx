import { cn } from "@/lib/utils";
import type { RunEvent } from "@/lib/api";

const LEVEL_STYLES: Record<RunEvent["level"], string> = {
  info: "",
  warn: "text-amber-800 dark:text-amber-300",
  error: "text-red-700 dark:text-red-300",
};

export function RunLog({ events, live }: { events: RunEvent[]; live: boolean }) {
  const shown = events.slice(-300);
  return (
    <section aria-labelledby="log-heading" className="grid gap-2">
      <h2 id="log-heading" className="text-lg font-semibold">
        Progress {live && <span className="text-sm font-normal text-muted-foreground">(live)</span>}
      </h2>
      <ol
        aria-live={live ? "polite" : undefined}
        className="grid max-h-96 gap-0.5 overflow-auto rounded-lg border bg-muted/30 p-2 font-mono text-xs"
      >
        {shown.length === 0 && <li className="text-muted-foreground">Waiting for the first event…</li>}
        {shown.map((event) => (
          <li key={event.seq} className={cn("break-words whitespace-pre-wrap", LEVEL_STYLES[event.level])}>
            <time className="text-muted-foreground" dateTime={event.at}>
              {new Date(event.at).toLocaleTimeString()}
            </time>{" "}
            <span className="text-muted-foreground">[{event.source}]</span> {event.message}
          </li>
        ))}
      </ol>
    </section>
  );
}
