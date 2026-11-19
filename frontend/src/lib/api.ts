/**
 * Typed client for the QA agent backend (FastAPI, `/api/v1`).
 * NEXT_PUBLIC_BACKEND_URL is inlined at build time (see Dockerfile build args).
 * Shapes mirror backend/src/app/schemas/{runs,setup}.py — keep both sides in sync.
 */
export const BACKEND_URL = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8400").replace(/\/$/, "");
export const API_BASE = `${BACKEND_URL}/api/v1`;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** The backend's `{"detail": ...}` error body, as one readable line. */
function detailMessage(body: unknown): string | null {
  if (!body || typeof body !== "object" || !("detail" in body)) return null;
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown };
    if (typeof first?.msg === "string") return first.msg.replace(/^Value error, /, "");
  }
  return null;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const fallback = `${init?.method ?? "GET"} ${path} failed with ${res.status}`;
    const body: unknown = await res.json().catch(() => null);
    throw new ApiError(res.status, detailMessage(body) ?? fallback);
  }
  return (await res.json()) as T;
}

const post = <T>(path: string, body: unknown = {}, init?: RequestInit) =>
  apiFetch<T>(path, { ...init, method: "POST", body: JSON.stringify(body) });

// --- Types ---

export type Verdict = "PASS" | "FAILING" | "BLOCKED";
export type Severity = "High" | "Medium" | "Warning";
export type FailureCategory =
  | "approved change"
  | "needs approval"
  | "regression"
  | "automation issue"
  | "environment";
export type RunKind = "quick-scan" | "check-change" | "agent" | "save-test" | "saved-test";
export type RunMode = "mocked" | "real";
export type FindingStatus = "open" | "accepted" | "ignored";
export type EvidenceKind = "screenshot" | "design" | "console" | "network" | "code" | "log" | "trace";

export type Evidence = { kind: EvidenceKind; label: string; path: string | null; text: string | null };

export type Finding = {
  id: string;
  agent: string;
  title: string;
  severity: Severity;
  category: FailureCategory;
  location: string;
  expected: string;
  actual: string;
  suggested_fix: string | null;
  evidence: Evidence[];
  status: FindingStatus;
  ignore_reason: string | null;
  fingerprint: string;
};

export type FindingItem = Finding & { run_id: string; run_title: string; run_started_at: string };

export type Step = {
  index: number;
  description: string;
  status: "pass" | "fail" | "skipped";
  screenshot: string | null;
  note: string | null;
};

export type Check = { source: string; passed: boolean; detail: string };

export type AgentResult = {
  agent: string;
  task: string;
  verdict: Verdict;
  summary: string;
  blocked_reason: string | null;
  steps: Step[];
  checks: Check[];
  duration_s: number | null;
};

export type Artifact = { label: string; path: string; kind: EvidenceKind };

export type SavedTestInfo = {
  test_id: string;
  file: string;
  branch: string;
  commit: string | null;
  pr_url: string | null;
  pushed: boolean;
};

export type RunParams = {
  mode: RunMode;
  agent: string | null;
  task: string | null;
  route: string | null;
  flow: string | null;
  base_ref: string | null;
  source_run_id: string | null;
  test_id: string | null;
};

export type RunCounts = { open: number; total: number };

export type RunSummary = {
  id: string;
  kind: RunKind;
  title: string;
  status: "running" | "finished";
  verdict: Verdict | null;
  started_at: string;
  finished_at: string | null;
  mode: RunMode;
  counts: RunCounts;
};

export type RunDetail = Omit<RunSummary, "mode"> & {
  blocked_reason: string | null;
  params: RunParams;
  plan_summary: string | null;
  agents: AgentResult[];
  findings: Finding[];
  artifacts: Artifact[];
  saved_test: SavedTestInfo | null;
  counts: RunCounts;
  report_summary: string;
  can_save_as_test: boolean;
};

export type RunEvent = {
  seq: number;
  at: string;
  level: "info" | "warn" | "error";
  source: string;
  message: string;
};

export type SetupItem = {
  key: string;
  label: string;
  status: "pass" | "warn" | "fail" | "skip";
  detail: string;
  fix: string | null;
};

export type SetupCheck = { ready: boolean; items: SetupItem[] };

export type AgentInfo = { name: string; description: string };

export type QaConfigSummary = {
  app_url: string;
  app_repo_path: string | null;
  pages: string[];
  viewports: string[];
  agents: AgentInfo[];
  designs: string[];
};

export type SavedTest = {
  id: string;
  title: string;
  file: string;
  folder: string | null;
  created_at: string | null;
  source_run_id: string | null;
};

// --- Calls ---

export type HealthResponse = { status: string; environment: string };
export const getHealth = (init?: RequestInit) => apiFetch<HealthResponse>("/health", init);

export const getSetupCheck = (live: boolean, init?: RequestInit) =>
  apiFetch<SetupCheck>(`/setup-check?live=${live}`, init);
export const getQaConfig = (init?: RequestInit) => apiFetch<QaConfigSummary>("/qa-config", init);

export const listRuns = (init?: RequestInit) => apiFetch<RunSummary[]>("/runs", init);
export const getRun = (id: string, init?: RequestInit) =>
  apiFetch<RunDetail>(`/runs/${encodeURIComponent(id)}`, init);
export const getRunEvents = (id: string, after: number, init?: RequestInit) =>
  apiFetch<{ events: RunEvent[]; done: boolean }>(
    `/runs/${encodeURIComponent(id)}/events?after=${after}`,
    init,
  );
export const cancelRun = (id: string) => post<RunDetail>(`/runs/${encodeURIComponent(id)}/cancel`);

export const startQuickScan = (mode: RunMode) => post<RunDetail>("/runs/quick-scan", { mode });
export const startCheckChange = (body: { mode: RunMode; base_ref?: string; flow?: string }) =>
  post<RunDetail>("/runs/check-change", body);
export const startAgentRun = (body: { agent: string; task: string; route?: string; mode: RunMode }) =>
  post<RunDetail>("/runs/agent", body);
export const saveAsTest = (runId: string, body: { title?: string; folder?: "isolated" | "live" }) =>
  post<RunDetail>(`/runs/${encodeURIComponent(runId)}/save-test`, body);

export const listFindings = (filter: { status?: FindingStatus; agent?: string }, init?: RequestInit) => {
  const params = new URLSearchParams();
  if (filter.status) params.set("status", filter.status);
  if (filter.agent) params.set("agent", filter.agent);
  const query = params.toString();
  return apiFetch<FindingItem[]>(`/findings${query ? `?${query}` : ""}`, init);
};
export const decideFinding = (
  runId: string,
  findingId: string,
  body: { decision: "accept" | "ignore"; reason?: string },
) =>
  post<Finding>(
    `/runs/${encodeURIComponent(runId)}/findings/${encodeURIComponent(findingId)}/decision`,
    body,
  );

export const listSavedTests = (init?: RequestInit) => apiFetch<SavedTest[]>("/saved-tests", init);
export const runSavedTest = (testId: string) =>
  post<RunDetail>(`/saved-tests/${encodeURIComponent(testId)}/run`);

/** URL of a file inside a run folder (screenshots, designs, traces, logs). */
export const runFileUrl = (runId: string, path: string) =>
  `${API_BASE}/runs/${encodeURIComponent(runId)}/files/${path.split("/").map(encodeURIComponent).join("/")}`;
