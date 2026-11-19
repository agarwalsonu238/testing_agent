import { runFileUrl, type Evidence } from "@/lib/api";

/** Screenshots and designs collapsed behind a toggle; console, network, code and log text below. */
export function EvidenceView({ runId, evidence }: { runId: string; evidence: Evidence[] }) {
  const images = evidence.filter((e) => e.path && (e.kind === "screenshot" || e.kind === "design"));
  const files = evidence.filter((e) => e.path && e.kind !== "screenshot" && e.kind !== "design");
  const texts = evidence.filter((e) => !e.path && e.text);
  if (evidence.length === 0) return null;

  return (
    <div className="grid gap-2">
      {images.length > 0 && (
        <details className="group">
          <summary className="inline-flex w-fit cursor-pointer list-none items-center gap-1 rounded-md px-1.5 py-1 text-sm text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none">
            <span aria-hidden className="transition-transform group-open:rotate-90">
              ▸
            </span>
            {images.length === 1 ? "Show screenshot" : `Show screenshots (${images.length})`}
          </summary>
          <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {images.map((item) => {
              const url = runFileUrl(runId, item.path as string);
              return (
                <figure key={`${item.kind}-${item.path}`} className="min-w-0">
                  <figcaption className="mb-1 text-xs text-muted-foreground">
                    {item.kind === "design" ? "Design" : "Page"} · {item.label}
                  </figcaption>
                  {/* Thumbnail only — click through for the full-size original. */}
                  <a href={url} target="_blank" rel="noreferrer" className="block rounded-md border focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none">
                    {/* eslint-disable-next-line @next/next/no-img-element -- local run evidence served by the QA backend, sizes unknown */}
                    <img src={url} alt={`${item.kind} ${item.label}`} loading="lazy" className="max-h-36 w-full rounded-md object-contain object-top" />
                  </a>
                </figure>
              );
            })}
          </div>
        </details>
      )}
      {files.map((item) => (
        <a key={item.path} href={runFileUrl(runId, item.path as string)} className="text-sm underline underline-offset-4">
          {item.label}
        </a>
      ))}
      {texts.map((item, i) => (
        <pre
          key={`${item.kind}-${i}`}
          className="max-h-60 overflow-auto rounded-md border bg-muted/50 p-2 font-mono text-xs whitespace-pre-wrap break-words"
        >
          <span className="text-muted-foreground">{item.label}: </span>
          {item.text}
        </pre>
      ))}
    </div>
  );
}
