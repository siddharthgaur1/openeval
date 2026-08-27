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
  if (res.status === 401 && typeof window !== "undefined") {
    window.localStorage.removeItem("openeval_token");
    if (window.location.pathname !== "/login") window.location.href = "/login";
  }
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

export type OrgMember = {
  id: string;
  user_id: string;
  email: string;
  role: string;
};

export type ApiKey = {
  id: string;
  name: string;
  key: string | null;
  prefix: string;
  scope: "read" | "write" | "admin";
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
  tags: Record<string, unknown> & { feedback?: { score: number; comment: string | null } };
  error: string | null;
  created_at: string;
};

export type Dataset = {
  id: string;
  project_id: string;
  name: string;
  version: number;
  row_count: number;
};

export type DatasetRow = {
  id: string;
  input: string;
  expected_output: string | null;
  context: string | null;
  tags: Record<string, unknown>;
};

export type PromptTemplate = {
  id: string;
  project_id: string;
  name: string;
  version: number;
  template: string;
  variables: string[];
  status: string;
  created_at: string;
};

export type PlaygroundResult = {
  rendered_prompt: string;
  output: string;
  latency_ms: number;
  cost_usd: number;
};

export type Experiment = {
  id: string;
  project_id: string;
  name: string;
  baseline_run_id: string | null;
  run_ids: string[];
  notes: string | null;
  created_at: string;
};

export type ExperimentComparison = {
  baseline_run_id: string | null;
  runs: {
    eval_run_id: string;
    name: string;
    summary: Record<string, unknown>;
    delta_vs_baseline: Record<string, number>;
    significance_vs_baseline: Record<string, { statistic: number | null; p_value: number | null }>;
    regressions: string[];
    row_diffs: { dataset_row_id: string; baseline_output: string; candidate_output: string; delta: Record<string, number> }[];
  }[];
};

export type AnnotationQueueItem = {
  id: string;
  trace_id: string;
  assigned_to_user_id: string;
  rubric: Record<string, unknown>;
  status: string;
  created_at: string;
};

export type KappaResult = {
  criterion: string;
  n_shared_items: number;
  kappa: number;
};

export type CostAnalytics = {
  by_model: Record<string, number>;
  by_day: Record<string, number>;
  total_usd: number;
  projected_monthly_usd: number;
};

export type LatencyAnalytics = {
  by_model: Record<string, { p50: number; p95: number; p99: number }>;
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

  orgMembers: async () => {
    const project = await api.defaultProject();
    return apiFetch<OrgMember[]>(`/organizations/${project.organization_id}/members`);
  },

  apiKeys: () => apiFetch<ApiKey[]>("/auth/api-keys"),
  createApiKey: (name: string, scope: "read" | "write" | "admin") =>
    apiFetch<ApiKey>("/auth/api-keys", { method: "POST", body: JSON.stringify({ name, scope }) }),
  revokeApiKey: (id: string) => apiFetch<void>(`/auth/api-keys/${id}`, { method: "DELETE" }),

  traces: async (filters: { search?: string; model?: string; hasError?: boolean; limit?: number } = {}) => {
    const params = new URLSearchParams({ project_id: await activeProjectId(), limit: String(filters.limit ?? 200) });
    if (filters.search) params.set("search", filters.search);
    if (filters.model) params.set("model", filters.model);
    if (filters.hasError) params.set("has_error", "true");
    return apiFetch<Trace[]>(`/traces?${params}`);
  },
  traceStats: async () => apiFetch<TraceStats>(`/traces/stats?project_id=${await activeProjectId()}`),
  trace: (id: string) => apiFetch<Trace>(`/traces/${id}`),
  submitFeedback: (id: string, score: number, comment?: string) =>
    apiFetch<Trace>(`/traces/${id}/feedback`, { method: "POST", body: JSON.stringify({ score, comment }) }),

  evalRuns: async () => apiFetch<EvalRun[]>(`/evals?project_id=${await activeProjectId()}`),
  evalRun: (id: string) => apiFetch<EvalRun>(`/evals/${id}`),
  createEvalRun: (payload: { name: string; dataset_id: string; prompt_template_id?: string; target_model: string; judge_model?: string; metrics?: string[] }) =>
    apiFetch<EvalRun>("/evals", { method: "POST", body: JSON.stringify(payload) }),
  compareRuns: (runIds: string[]) =>
    apiFetch<ExperimentComparison>("/evals/compare", { method: "POST", body: JSON.stringify({ run_ids: runIds }) }),

  datasets: async () => apiFetch<Dataset[]>(`/datasets?project_id=${await activeProjectId()}`),
  datasetRows: (id: string) => apiFetch<DatasetRow[]>(`/datasets/${id}/rows`),
  createDataset: async (name: string, rows: { input: string; expected_output?: string; context?: string }[]) =>
    apiFetch<Dataset>("/datasets", { method: "POST", body: JSON.stringify({ project_id: await activeProjectId(), name, rows }) }),
  uploadDataset: async (name: string, file: File) => {
    const projectId = await activeProjectId();
    const form = new FormData();
    form.append("file", file);
    const token = getToken();
    const res = await fetch(`${API_URL}/api/datasets/upload?name=${encodeURIComponent(name)}&project_id=${projectId}`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
    return res.json() as Promise<Dataset>;
  },
  generateDatasetRows: (id: string, mode: "variation" | "adversarial", count: number) =>
    apiFetch<Dataset>(`/datasets/${id}/generate`, { method: "POST", body: JSON.stringify({ mode, count }) }),

  prompts: async () => apiFetch<PromptTemplate[]>(`/prompts?project_id=${await activeProjectId()}`),
  promptVersions: async (name: string) => apiFetch<PromptTemplate[]>(`/prompts/${encodeURIComponent(name)}/versions?project_id=${await activeProjectId()}`),
  createPrompt: async (name: string, template: string, variables: string[]) =>
    apiFetch<PromptTemplate>("/prompts", { method: "POST", body: JSON.stringify({ project_id: await activeProjectId(), name, template, variables }) }),
  promotePrompt: (versionId: string) => apiFetch<PromptTemplate>(`/prompts/${versionId}/promote`, { method: "POST" }),
  runPlayground: (versionId: string, model: string, variables: Record<string, string>) =>
    apiFetch<PlaygroundResult>(`/prompts/${versionId}/playground`, { method: "POST", body: JSON.stringify({ model, variables }) }),

  experiments: async () => apiFetch<Experiment[]>(`/experiments?project_id=${await activeProjectId()}`),
  createExperiment: async (name: string, runIds: string[], baselineRunId?: string) =>
    apiFetch<Experiment>("/experiments", {
      method: "POST",
      body: JSON.stringify({ project_id: await activeProjectId(), name, run_ids: runIds, baseline_run_id: baselineRunId }),
    }),
  compareExperiment: (id: string, regressionThreshold = 0.05) =>
    apiFetch<ExperimentComparison>(`/experiments/${id}/compare?regression_threshold=${regressionThreshold}`),
  setBaseline: (id: string, runId: string) =>
    apiFetch<Experiment>(`/experiments/${id}/baseline`, { method: "POST", body: JSON.stringify({ run_id: runId }) }),

  annotationQueue: () => apiFetch<AnnotationQueueItem[]>("/annotations/queue"),
  assignAnnotation: (traceId: string, assignedToUserId: string, rubric: Record<string, unknown>) =>
    apiFetch("/annotations/assign", { method: "POST", body: JSON.stringify({ trace_id: traceId, assigned_to_user_id: assignedToUserId, rubric }) }),
  submitAnnotation: (itemId: string, scores: Record<string, unknown>, comment?: string) =>
    apiFetch(`/annotations/queue/${itemId}/submit`, { method: "POST", body: JSON.stringify({ scores, comment }) }),
  kappa: (criterion: string, annotatorAId: string, annotatorBId: string) =>
    apiFetch<KappaResult>("/annotations/kappa", {
      method: "POST",
      body: JSON.stringify({ criterion, annotator_a_id: annotatorAId, annotator_b_id: annotatorBId }),
    }),

  costAnalytics: async () => apiFetch<CostAnalytics>(`/analytics/cost?project_id=${await activeProjectId()}`),
  latencyAnalytics: async () => apiFetch<LatencyAnalytics>(`/analytics/latency?project_id=${await activeProjectId()}`),
};
