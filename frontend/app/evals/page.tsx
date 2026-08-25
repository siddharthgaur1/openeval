"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";

const STATUS_COLOR: Record<string, string> = {
  completed: "text-emerald-400",
  running: "text-amber-400",
  pending: "text-slate-400",
  failed: "text-red-400",
};

export default function EvalsPage() {
  const { data: runs, isLoading, error } = useQuery({ queryKey: ["eval-runs"], queryFn: api.evalRuns });

  if (isLoading) return <p>Loading eval runs...</p>;
  if (error) return <p className="text-red-400">Failed to load eval runs: {(error as Error).message}</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Eval Runs</h1>
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
