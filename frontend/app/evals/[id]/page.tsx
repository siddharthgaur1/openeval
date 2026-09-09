"use client";

import { useState } from "react";
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
  const [expanded, setExpanded] = useState<string | null>(null);
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

      {run.results.length > 0 && (
        <div className="space-y-3">
          <h2 className="font-medium">Rows</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-800">
                <th className="py-2">#</th>
                <th>Output</th>
                <th>Scores</th>
                <th>Latency</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {run.results.map((result, i) => (
                <tr key={result.id} className="border-b border-slate-900 align-top">
                  <td className="py-2 text-slate-500">{i + 1}</td>
                  <td className="max-w-sm whitespace-pre-wrap">{result.output}</td>
                  <td className="space-y-1">
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(result.scores).map(([metric, score]) => {
                        // score_details is null on rows written before evaluators explained themselves.
                        const detail = result.score_details?.[metric];
                        const key = `${result.id}:${metric}`;
                        const chip = `${metric} ${score.toFixed(3)}`;
                        return detail ? (
                          <button
                            key={metric}
                            type="button"
                            onClick={() => setExpanded(expanded === key ? null : key)}
                            className="rounded bg-slate-800 hover:bg-slate-700 px-2 py-0.5 text-xs underline decoration-dotted"
                          >
                            {chip} {expanded === key ? "▾" : "▸"}
                          </button>
                        ) : (
                          <span key={metric} className="rounded bg-slate-800 px-2 py-0.5 text-xs">
                            {chip}
                          </span>
                        );
                      })}
                    </div>
                    {Object.entries(result.score_details ?? {}).map(([metric, detail]) =>
                      expanded === `${result.id}:${metric}` ? (
                        <div key={metric} className="rounded border border-slate-800 p-2 text-xs space-y-1">
                          {detail.reasoning && <p className="text-slate-300">{detail.reasoning}</p>}
                          {detail.evidence.length > 0 && (
                            <p className="text-slate-500">Evidence: steps {detail.evidence.join(", ")}</p>
                          )}
                        </div>
                      ) : null,
                    )}
                  </td>
                  <td>{result.latency_ms.toFixed(0)}ms</td>
                  <td>${result.cost_usd.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
