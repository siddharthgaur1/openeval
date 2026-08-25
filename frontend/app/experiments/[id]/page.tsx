"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

export default function ExperimentComparePage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({ queryKey: ["experiment-compare", id], queryFn: () => api.compareExperiment(id) });

  if (isLoading) return <p>Loading comparison...</p>;
  if (error) return <p className="text-red-400">Failed to load comparison: {(error as Error).message}</p>;
  if (!data || data.runs.length === 0) return <p>Nothing to compare yet.</p>;

  const metrics = [...new Set(data.runs.flatMap((r) => Object.keys(r.delta_vs_baseline)))];

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Experiment comparison</h1>

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-400 border-b border-slate-800">
            <th className="py-2">Run</th>
            {metrics.map((m) => (
              <th key={m}>{m}</th>
            ))}
            <th>Regressions</th>
          </tr>
        </thead>
        <tbody>
          {data.runs.map((r) => (
            <tr key={r.eval_run_id} className="border-b border-slate-900">
              <td className="py-2">
                {r.name}
                {r.eval_run_id === data.baseline_run_id && <span className="ml-2 rounded bg-slate-800 px-2 py-0.5 text-xs">baseline</span>}
              </td>
              {metrics.map((m) => {
                const delta = r.delta_vs_baseline[m];
                const sig = r.significance_vs_baseline[m];
                return (
                  <td key={m} className={delta == null ? "" : delta < 0 ? "text-red-400" : delta > 0 ? "text-emerald-400" : ""}>
                    {delta != null ? `${delta >= 0 ? "+" : ""}${delta.toFixed(3)}` : "-"}
                    {sig?.p_value != null && sig.p_value < 0.05 && <span className="ml-1 text-xs text-amber-400">*</span>}
                  </td>
                );
              })}
              <td>{r.regressions.length > 0 ? r.regressions.join(", ") : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-slate-500">* statistically significant vs baseline (Welch's t-test, p &lt; 0.05)</p>

      {data.runs.map(
        (r) =>
          r.row_diffs.length > 0 && (
            <div key={r.eval_run_id} className="space-y-3">
              <h2 className="font-medium">Row-level changes: {r.name}</h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-400 border-b border-slate-800">
                    <th className="py-2">Baseline output</th>
                    <th>Candidate output</th>
                    <th>Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {r.row_diffs.map((d) => (
                    <tr key={d.dataset_row_id} className="border-b border-slate-900 align-top">
                      <td className="py-2 max-w-sm whitespace-pre-wrap">{d.baseline_output}</td>
                      <td className="max-w-sm whitespace-pre-wrap">{d.candidate_output}</td>
                      <td>
                        {Object.entries(d.delta).map(([m, v]) => (
                          <div key={m} className={v < 0 ? "text-red-400" : v > 0 ? "text-emerald-400" : ""}>
                            {m}: {v >= 0 ? "+" : ""}
                            {v.toFixed(3)}
                          </div>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ),
      )}
    </div>
  );
}
