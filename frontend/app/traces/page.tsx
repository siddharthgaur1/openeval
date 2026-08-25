"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export default function TracesPage() {
  const { data: traces, isLoading, error } = useQuery({ queryKey: ["traces"], queryFn: api.traces });
  const { data: stats } = useQuery({ queryKey: ["trace-stats"], queryFn: api.traceStats });

  if (isLoading) return <p>Loading traces...</p>;
  if (error) return <p className="text-red-400">Failed to load traces: {(error as Error).message}</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Traces</h1>

      {stats && (
        <div className="grid grid-cols-5 gap-4">
          <Stat label="Count" value={stats.count} />
          <Stat label="Total cost" value={`$${stats.total_cost_usd.toFixed(4)}`} />
          <Stat label="p50 latency" value={`${stats.p50_latency_ms.toFixed(0)}ms`} />
          <Stat label="p95 latency" value={`${stats.p95_latency_ms.toFixed(0)}ms`} />
          <Stat label="p99 latency" value={`${stats.p99_latency_ms.toFixed(0)}ms`} />
        </div>
      )}

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-400 border-b border-slate-800">
            <th className="py-2">Model</th>
            <th>Latency</th>
            <th>Tokens</th>
            <th>Cost</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {traces?.map((t) => (
            <tr key={t.id} className="border-b border-slate-900">
              <td className="py-2">{t.model}</td>
              <td>{t.latency_ms.toFixed(0)}ms</td>
              <td>{t.prompt_tokens + t.completion_tokens}</td>
              <td>${t.cost_usd.toFixed(4)}</td>
              <td>{new Date(t.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded border border-slate-800 p-4">
      <div className="text-slate-400 text-xs">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
