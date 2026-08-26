"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";

const STATUS_COLOR: Record<string, string> = {
  completed: "text-emerald-400",
  running: "text-amber-400",
  pending: "text-slate-400",
  failed: "text-red-400",
};

const AVAILABLE_METRICS = [
  "exact_match",
  "f1",
  "answer_relevance",
  "faithfulness",
  "hallucination",
  "context_precision",
  "context_recall",
  "context_entity_recall",
  "noise_robustness",
  "toxicity",
  "coherence",
  "conciseness",
];

export default function EvalsPage() {
  const queryClient = useQueryClient();
  const { data: runs, isLoading, error } = useQuery({ queryKey: ["eval-runs"], queryFn: api.evalRuns });
  const { data: datasets } = useQuery({ queryKey: ["datasets"], queryFn: api.datasets });
  const { data: prompts } = useQuery({ queryKey: ["prompts"], queryFn: api.prompts });

  const [name, setName] = useState("eval-run");
  const [datasetId, setDatasetId] = useState("");
  const [promptId, setPromptId] = useState("");
  const [targetModel, setTargetModel] = useState("gpt-4o-mini");
  const [metrics, setMetrics] = useState<string[]>(AVAILABLE_METRICS);
  const [formError, setFormError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      api.createEvalRun({ name, dataset_id: datasetId, prompt_template_id: promptId || undefined, target_model: targetModel, metrics }),
    onSuccess: () => {
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ["eval-runs"] });
    },
    onError: (e) => setFormError((e as Error).message),
  });

  if (isLoading) return <p>Loading eval runs...</p>;
  if (error) return <p className="text-red-400">Failed to load eval runs: {(error as Error).message}</p>;

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Eval Runs</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!datasetId) {
            setFormError("Select a dataset");
            return;
          }
          create.mutate();
        }}
        className="space-y-3 rounded border border-slate-800 p-4"
      >
        <div className="flex flex-wrap gap-3">
          <input placeholder="Run name" value={name} onChange={(e) => setName(e.target.value)} className="rounded border border-slate-800 bg-slate-900 px-3 py-2" />
          <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)} required className="rounded border border-slate-800 bg-slate-900 px-3 py-2">
            <option value="">Select dataset...</option>
            {datasets?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} (v{d.version}, {d.row_count} rows)
              </option>
            ))}
          </select>
          <select value={promptId} onChange={(e) => setPromptId(e.target.value)} className="rounded border border-slate-800 bg-slate-900 px-3 py-2">
            <option value="">No prompt template</option>
            {prompts?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} v{p.version}
              </option>
            ))}
          </select>
          <input placeholder="Target model" value={targetModel} onChange={(e) => setTargetModel(e.target.value)} className="rounded border border-slate-800 bg-slate-900 px-3 py-2" />
        </div>
        <div className="flex flex-wrap gap-3 text-sm">
          {AVAILABLE_METRICS.map((m) => (
            <label key={m} className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={metrics.includes(m)}
                onChange={(e) => setMetrics(e.target.checked ? [...metrics, m] : metrics.filter((x) => x !== m))}
              />
              {m}
            </label>
          ))}
        </div>
        <button disabled={create.isPending} type="submit" className="rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-4 py-2 text-sm font-medium">
          {create.isPending ? "Starting..." : "Run eval"}
        </button>
        {formError && <p className="text-red-400 text-sm">{formError}</p>}
      </form>

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-400 border-b border-slate-800">
            <th className="py-2">Name</th>
            <th>Status</th>
            <th>Target model</th>
            <th>Rows</th>
            <th>Avg scores</th>
            <th>Cost</th>
          </tr>
        </thead>
        <tbody>
          {runs?.map((r) => (
            <tr key={r.id} className="border-b border-slate-900">
              <td className="py-2">
                <Link href={`/evals/${r.id}`} className="underline">{r.name}</Link>
              </td>
              <td className={STATUS_COLOR[r.status] || ""}>{r.status}</td>
              <td>{r.target_model}</td>
              <td>{r.summary.row_count ?? "-"}</td>
              <td>
                {r.summary.avg_scores
                  ? Object.entries(r.summary.avg_scores)
                      .map(([k, v]) => `${k}: ${v.toFixed(2)}`)
                      .join(", ")
                  : "-"}
              </td>
              <td>{r.summary.total_cost_usd != null ? `$${r.summary.total_cost_usd.toFixed(4)}` : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
