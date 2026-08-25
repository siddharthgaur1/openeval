"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { useEvalProgress } from "@/lib/sse";

export default function EvalRunDetailPage() {
  const params = useParams<{ id: string }>();
  const { data: run, isLoading, error } = useQuery({
    queryKey: ["eval-run", params.id],
    queryFn: () => api.evalRun(params.id),
    refetchInterval: (query) => (query.state.data?.status === "running" || query.state.data?.status === "pending" ? 2000 : false),
  });
  const progress = useEvalProgress(params.id, run?.status === "running" || run?.status === "pending");

  if (isLoading) return <p>Loading...</p>;
  if (error) return <p className="text-red-400">Failed to load run: {(error as Error).message}</p>;
  if (!run) return null;

  const totalRows = progress?.total_rows ?? run.total_rows;
  const completedRows = progress?.completed_rows ?? run.completed_rows;
  const failedRows = progress?.failed_rows ?? run.failed_rows;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{run.name}</h1>
      <p>
        Status: <span className="font-mono">{progress?.status ?? run.status}</span>
      </p>
      {(run.status === "running" || run.status === "pending") && totalRows > 0 && (
        <div className="space-y-1">
          <div className="h-2 w-full rounded bg-slate-800 overflow-hidden">
            <div
              className="h-full bg-emerald-500 transition-all"
              style={{ width: `${((completedRows + failedRows) / totalRows) * 100}%` }}
            />
          </div>
          <div className="text-xs text-slate-400">
            {completedRows + failedRows} / {totalRows} rows ({failedRows} failed)
          </div>
        </div>
      )}
      {run.error && <p className="text-red-400">{run.error}</p>}

      {run.summary.avg_scores && (
        <div className="grid grid-cols-3 gap-4">
          {Object.entries(run.summary.avg_scores).map(([metric, score]) => (
            <div key={metric} className="rounded border border-slate-800 p-4">
              <div className="text-slate-400 text-xs">{metric}</div>
              <div className="text-lg font-semibold">{score.toFixed(3)}</div>
            </div>
          ))}
        </div>
      )}

      <div className="text-sm text-slate-400">
        p50/p95/p99 latency: {run.summary.p50_latency_ms?.toFixed(0)}ms / {run.summary.p95_latency_ms?.toFixed(0)}ms /{" "}
        {run.summary.p99_latency_ms?.toFixed(0)}ms · total cost ${run.summary.total_cost_usd?.toFixed(4)}
      </div>
    </div>
  );
}
