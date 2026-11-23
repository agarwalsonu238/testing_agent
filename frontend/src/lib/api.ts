/**
 * Typed client for the QA agent backend (FastAPI, `/api/v1`).
 * NEXT_PUBLIC_BACKEND_URL is inlined at build time (see Dockerfile build args).
 * Shapes mirror backend/src/app/schemas/{runs,setup}.py — keep both sides in sync.
 */
export const BACKEND_URL = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8400").replace(/\/$/, "");
export const API_BASE = `${BACKEND_URL}/api/v1`;
// Only set once the backend has API_AUTH_TOKEN configured (a deployed backend); empty locally.
const API_KEY = process.env.NEXT_PUBLIC_QA_API_KEY ?? "";

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
    headers: {
      "Content-Type": "application/json",
      ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
      ...init?.headers,
    },
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

export type ApiField = { key: string; type: string; example: string };
export type ApiParam = {
  name: string;
  value: string;
  effect: "changes result" | "changes order" | "no visible effect" | "rejected" | "error";
  detail: string;
};
export type ApiReference = {
  url: string;
  status: number | null;
  content_type: string;
  time_ms: number | null;
  size_bytes: number | null;
  is_json: boolean;
  error: string | null;
  item_count: number | null;
  total: number | null;
  fields: ApiField[];
  params: ApiParam[];
  raw_file: string | null;
};

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
  app_url: string | null;
  app_repo_path: string | null;
  agent: string | null;
  task: string | null;
  route: string | null;
  flow: string | null;
  base_ref: string | null;
  source_run_id: string | null;
  test_id: string | null;
  approve_plan: boolean;
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

export type TestCase = {
  id: string;
  title: string;
  agent: string;
  steps: string[];
  expected: string;
  status: "planned" | "pass" | "fail" | "blocked" | "skipped";
  note: string | null;
  /** What the test-case reviewer changed (rewritten) — null when approved unchanged or rejected. */
  review_note: string | null;
  /** The reviewer's decision; null when no review ran (older runs). */
  review_status: "approved" | "rewritten" | "rejected" | null;
};

/** Where a Check my change / agent run is in its pipeline; null for runs that have none. */
export type RunStageName = "planning" | "reviewing" | "awaiting_approval" | "running" | "reporting" | "done";

export type RunDetail = Omit<RunSummary, "mode"> & {
  stage: RunStageName | null;
  /** One line on what the run is doing right now. */
  activity: string | null;
  /** Paused until the developer approves the reviewed test cases. */
  awaiting_approval: boolean;
  /** Who reviewed the test cases, e.g. "Gemini (gemini-2.5-pro)"; null when nobody did. */
  reviewer: string | null;
  blocked_reason: string | null;
  params: RunParams;
  plan_summary: string | null;
  test_cases: TestCase[];
  agents: AgentResult[];
  findings: Finding[];
  artifacts: Artifact[];
  api_references: ApiReference[];
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

/** `standalone` is false for roles that only run inside another flow (QA Lead, reviewer, reporter…). */
export type AgentInfo = { name: string; description: string; standalone: boolean };

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
/** Let a run that is waiting go ahead; `skip` lists test case IDs the developer chose not to run. */
export const approveRun = (id: string, skip: string[]) =>
  post<RunDetail>(`/runs/${encodeURIComponent(id)}/approve`, { skip });

/** Which project to test. Omitted fields fall back to the server's APP_URL / APP_REPO_PATH. */
export type RunTarget = { app_url?: string; app_repo_path?: string };

export const startQuickScan = (mode: RunMode, target: RunTarget = {}) =>
  post<RunDetail>("/runs/quick-scan", { mode, ...target });
export const startCheckChange = (
  body: { mode: RunMode; base_ref?: string; flow?: string; approve_plan?: boolean } & RunTarget,
) => post<RunDetail>("/runs/check-change", body);
export const startAgentRun = (
  body: { agent: string; task: string; route?: string; mode: RunMode; approve_plan?: boolean } & RunTarget,
) => post<RunDetail>("/runs/agent", body);
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
export const runFileUrl = (runId: string, path: string) => {
  const url = `${API_BASE}/runs/${encodeURIComponent(runId)}/files/${path.split("/").map(encodeURIComponent).join("/")}`;
  // <img>/<a> can't set a custom header, so the key goes in the query string here instead —
  // the backend accepts either. Only relevant once API_AUTH_TOKEN is configured.
  return API_KEY ? `${url}?key=${encodeURIComponent(API_KEY)}` : url;
};
