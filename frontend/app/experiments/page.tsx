"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";

export default function ExperimentsPage() {
  const queryClient = useQueryClient();
  const { data: experiments, isLoading, error } = useQuery({ queryKey: ["experiments"], queryFn: api.experiments });
  const { data: runs } = useQuery({ queryKey: ["eval-runs"], queryFn: api.evalRuns });
  const [name, setName] = useState("");
  const [runIds, setRunIds] = useState<string[]>([]);
  const [baselineRunId, setBaselineRunId] = useState<string>("");
  const [formError, setFormError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => api.createExperiment(name, runIds, baselineRunId || undefined),
    onSuccess: () => {
      setName("");
      setRunIds([]);
      setBaselineRunId("");
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ["experiments"] });
    },
    onError: (e) => setFormError((e as Error).message),
  });

  if (isLoading) return <p>Loading experiments...</p>;
  if (error) return <p className="text-red-400">Failed to load experiments: {(error as Error).message}</p>;

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Experiments</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
        className="space-y-3 rounded border border-slate-800 p-4"
      >
        <input placeholder="Experiment name" value={name} onChange={(e) => setName(e.target.value)} required className="w-full rounded border border-slate-800 bg-slate-900 px-3 py-2" />
        <div>
          <label className="block text-xs text-slate-400 mb-1">Eval runs to compare (ctrl/cmd-click for multiple)</label>
          <select multiple value={runIds} onChange={(e) => setRunIds([...e.target.selectedOptions].map((o) => o.value))} className="w-full rounded border border-slate-800 bg-slate-900 px-3 py-2 h-32">
            {runs?.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} ({r.status})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Baseline run (optional, must be in the list above)</label>
          <select value={baselineRunId} onChange={(e) => setBaselineRunId(e.target.value)} className="w-full rounded border border-slate-800 bg-slate-900 px-3 py-2">
            <option value="">None</option>
            {runIds.map((id) => {
              const run = runs?.find((r) => r.id === id);
              return (
                <option key={id} value={id}>
                  {run?.name ?? id}
                </option>
              );
            })}
          </select>
        </div>
        <button disabled={create.isPending} type="submit" className="rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-4 py-2 text-sm font-medium">
          {create.isPending ? "Creating..." : "Create experiment"}
        </button>
        {formError && <p className="text-red-400 text-sm">{formError}</p>}
      </form>

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-400 border-b border-slate-800">
            <th className="py-2">Name</th>
            <th>Runs</th>
            <th>Baseline</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {experiments?.map((e) => (
            <tr key={e.id} className="border-b border-slate-900">
              <td className="py-2">{e.name}</td>
              <td>{e.run_ids.length}</td>
              <td>{e.baseline_run_id ? "set" : "-"}</td>
              <td>
                <Link href={`/experiments/${e.id}`} className="underline text-indigo-400">
                  Compare
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
