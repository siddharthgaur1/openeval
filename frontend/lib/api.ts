const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("openeval_token");
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}/api${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export type Project = {
  id: string;
  organization_id: string;
  name: string;
  trace_quota_per_month: number;
  eval_run_quota_per_month: number;
  created_at: string;
};

export type Trace = {
  id: string;
  project_id: string;
  name: string;
  model: string;
  prompt: string;
  response: string;
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
  tags: Record<string, unknown>;
  created_at: string;
};

export type TraceStats = {
  count: number;
  total_cost_usd: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
};

export type EvalRun = {
  id: string;
  project_id: string;
  name: string;
  dataset_id: string;
  target_model: string;
  judge_model: string;
  metrics: string[];
  status: string;
  total_rows: number;
  completed_rows: number;
  failed_rows: number;
  summary: {
    row_count?: number;
    avg_scores?: Record<string, number>;
    total_cost_usd?: number;
    p50_latency_ms?: number;
    p95_latency_ms?: number;
    p99_latency_ms?: number;
  };
  error: string | null;
  created_at: string;
  finished_at: string | null;
};

// Every project-scoped resource requires a project_id - resolved once (the
// caller's default/personal project, auto-provisioned server-side on register)
// and cached for the tab's lifetime. A project switcher can call api.myProjects()
// and override this via setActiveProjectId() when multi-project support is needed.
let cachedProjectId: string | null = null;

export function setActiveProjectId(projectId: string) {
  cachedProjectId = projectId;
}

async function activeProjectId(): Promise<string> {
  if (cachedProjectId) return cachedProjectId;
  const project = await apiFetch<Project>("/projects/default");
  cachedProjectId = project.id;
  return project.id;
}

export const api = {
  login: (email: string, password: string) =>
    apiFetch<{ access_token: string }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string) =>
    apiFetch<{ access_token: string }>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  myProjects: () => apiFetch<Project[]>("/projects"),
  defaultProject: () => apiFetch<Project>("/projects/default"),
  traces: async () => apiFetch<Trace[]>(`/traces?project_id=${await activeProjectId()}`),
  traceStats: async () => apiFetch<TraceStats>(`/traces/stats?project_id=${await activeProjectId()}`),
  evalRuns: async () => apiFetch<EvalRun[]>(`/evals?project_id=${await activeProjectId()}`),
  evalRun: (id: string) => apiFetch<EvalRun>(`/evals/${id}`),
  compareRuns: (runIds: string[]) =>
    apiFetch("/evals/compare", { method: "POST", body: JSON.stringify({ run_ids: runIds }) }),
};
