import { runFileUrl, type ApiParam, type ApiReference } from "@/lib/api";

const EFFECT_LABEL: Record<ApiParam["effect"], { text: string; tone: string }> = {
  "changes result": { text: "Works: it changes the results", tone: "text-emerald-700 dark:text-emerald-400" },
  "changes order": { text: "Works: it changes the order", tone: "text-emerald-700 dark:text-emerald-400" },
  "no visible effect": { text: "Nothing changed", tone: "text-muted-foreground" },
  rejected: { text: "The API refused it", tone: "text-amber-700 dark:text-amber-400" },
  error: { text: "Could not be tested", tone: "text-amber-700 dark:text-amber-400" },
};

const PARAM_MEANING: Record<string, string> = {
  page: "Page number",
  limit: "How many items per page",
  pageSize: "How many items per page",
  per_page: "How many items per page",
  offset: "How many items to skip",
  sort: "Sort the list",
  sortBy: "Sort the list",
  order: "Sort direction (asc / desc)",
  search: "Search by text",
  q: "Search by text",
  query: "Search by text",
  name: "Filter by name",
  category: "Filter by category",
  categoryId: "Filter by category",
  tag: "Filter by tag",
  minPrice: "Lowest price",
  maxPrice: "Highest price",
  isAvailable: "Only available items",
};

const TYPE_LABEL: Record<string, string> = {
  string: "Text",
  integer: "Whole number",
  number: "Number",
  boolean: "Yes / No",
  object: "Group of fields",
  array: "List",
  null: "Empty",
};

/** "string or null" -> "Text (can be empty)". */
function typeLabel(type: string) {
  const parts = type.split(" or ");
  const empty = parts.includes("null");
  const main = parts.filter((p) => p !== "null").map((p) => TYPE_LABEL[p] ?? p);
  if (main.length === 0) return "Empty";
  return `${main.join(" or ")}${empty ? " (can be empty)" : ""}`;
}

/** "data[].price" -> "data → each item → price". */
function keyLabel(key: string) {
  return key.replace(/\[\]/g, " (each item)").split(".").join(" › ");
}

function Row({ children }: { children: React.ReactNode }) {
  return <tr className="border-t align-top">{children}</tr>;
}

export function ApiReferenceView({ runId, reference }: { runId: string; reference: ApiReference }) {
  const ok = reference.status != null && reference.status < 400;
  const working = reference.params.filter((p) => p.effect.startsWith("changes"));
  const other = reference.params.filter((p) => !p.effect.startsWith("changes"));
  return (
    <article className="grid gap-5 rounded-xl border bg-card p-4">
      <header className="grid gap-2">
        <p className="text-sm text-muted-foreground">API address (read-only GET request)</p>
        <p className="font-mono text-sm break-all">{reference.url}</p>
        {reference.error ? (
          <p role="alert" className="text-sm text-destructive">
            Could not reach this address: {reference.error}
          </p>
        ) : (
          <ul className="flex flex-wrap gap-2 text-sm">
            <li className={`rounded-full border px-2 py-0.5 ${ok ? "text-emerald-700 dark:text-emerald-400" : "text-destructive"}`}>
              {ok ? "Working" : "Problem"} · status {reference.status}
            </li>
            {reference.time_ms != null && <li className="rounded-full border px-2 py-0.5">{reference.time_ms} ms</li>}
            {reference.item_count != null && (
              <li className="rounded-full border px-2 py-0.5">
                {reference.item_count} items returned{reference.total != null ? ` of ${reference.total} in total` : ""}
              </li>
            )}
            {reference.raw_file && (
              <li>
                <a className="underline underline-offset-4" href={runFileUrl(runId, reference.raw_file)} target="_blank" rel="noreferrer">
                  See the full raw response
                </a>
              </li>
            )}
          </ul>
        )}
      </header>

      {reference.params.length > 0 && (
        <section className="grid gap-2">
          <h3 className="font-medium">What you can ask for (filters, search, paging)</h3>
          <p className="text-xs text-muted-foreground">
            Each option was tried once against the live API. &quot;Nothing changed&quot; means this exact name and value made
            no difference; the API may use a different name for it.
          </p>
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="p-2 font-medium">Option</th>
                  <th className="p-2 font-medium">What it is for</th>
                  <th className="p-2 font-medium">Tried with</th>
                  <th className="p-2 font-medium">Result</th>
                </tr>
              </thead>
              <tbody>
                {[...working, ...other].map((p) => (
                  <Row key={p.name}>
                    <td className="p-2 font-mono">{p.name}</td>
                    <td className="p-2">{PARAM_MEANING[p.name] ?? "—"}</td>
                    <td className="p-2 font-mono">{p.value}</td>
                    <td className={`p-2 ${EFFECT_LABEL[p.effect].tone}`}>
                      {EFFECT_LABEL[p.effect].text}
                      {p.detail && <span className="block text-xs text-muted-foreground">{p.detail}</span>}
                    </td>
                  </Row>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {reference.fields.length > 0 && (
        <section className="grid gap-2">
          <h3 className="font-medium">What the answer contains ({reference.fields.length} fields)</h3>
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="p-2 font-medium">Field</th>
                  <th className="p-2 font-medium">Kind of value</th>
                  <th className="p-2 font-medium">Example</th>
                </tr>
              </thead>
              <tbody>
                {reference.fields.map((f) => (
                  <Row key={f.key}>
                    <td className="p-2">{keyLabel(f.key)}</td>
                    <td className="p-2">{typeLabel(f.type)}</td>
                    <td className="p-2 text-muted-foreground">{f.example || "—"}</td>
                  </Row>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {!reference.error && !reference.is_json && (
        <p className="text-sm text-muted-foreground">This address did not answer with JSON, so there are no fields to list.</p>
      )}
    </article>
  );
}
