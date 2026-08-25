"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ResponsiveContainer, Line, LineChart } from "recharts";
import { api } from "@/lib/api";

export default function Home() {
  const { data: traces, isLoading: tracesLoading } = useQuery({ queryKey: ["traces"], queryFn: api.traces });
  const { data: stats, isLoading: statsLoading } = useQuery({ queryKey: ["trace-stats"], queryFn: api.traceStats });
  const { data: cost } = useQuery({ queryKey: ["analytics-cost"], queryFn: api.costAnalytics });
  const { data: runs } = useQuery({ queryKey: ["eval-runs"], queryFn: api.evalRuns });

  if (tracesLoading || statsLoading) return <p>Loading overview...</p>;

  const now = Date.now();
  const day = 24 * 60 * 60 * 1000;
  const today = (traces ?? []).filter((t) => now - new Date(t.created_at).getTime() < day);
  const week = (traces ?? []).filter((t) => now - new Date(t.created_at).getTime() < 7 * day);
  const errorRate = traces?.length ? (traces.filter((t) => t.error).length / traces.length) * 100 : 0;

  const modelCounts = new Map<string, number>();
  for (const t of traces ?? []) modelCounts.set(t.model, (modelCounts.get(t.model) ?? 0) + 1);
  const topModels = [...modelCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);

  const costTrend = Object.entries(cost?.by_day ?? {}).map(([day, usd]) => ({ day, usd }));

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-2xl font-semibold">OpenEval</h1>
        <p className="text-slate-400">Self-hostable LLM evaluation & observability.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Traces today" value={today.length} />
        <Stat label="Traces this week" value={week.length} />
        <Stat label="Error rate" value={`${errorRate.toFixed(1)}%`} />
        <Stat label="p95 latency" value={`${stats?.p95_latency_ms.toFixed(0) ?? 0}ms`} />
      </div>

      <section className="space-y-3">
        <h2 className="font-medium">Cost trend</h2>
        <div className="h-40">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={costTrend}>
              <Line type="monotone" dataKey="usd" stroke="#818cf8" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <Link href="/analytics" className="text-indigo-400 underline text-sm">
          Full cost & latency analytics →
        </Link>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="space-y-3">
          <h2 className="font-medium">Top models by usage</h2>
          <ul className="text-sm space-y-1">
            {topModels.map(([model, count]) => (
              <li key={model} className="flex justify-between border-b border-slate-900 py-1">
                <span>{model}</span>
                <span className="text-slate-400">{count}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="space-y-3">
          <h2 className="font-medium">Recent eval runs</h2>
          <ul className="text-sm space-y-1">
            {(runs ?? []).slice(0, 5).map((r) => (
              <li key={r.id} className="flex justify-between border-b border-slate-900 py-1">
                <Link href={`/evals/${r.id}`} className="underline">
                  {r.name}
                </Link>
                <span className="text-slate-400">{r.status}</span>
              </li>
            ))}
            {(runs ?? []).length === 0 && <li className="text-slate-500">No eval runs yet.</li>}
          </ul>
        </div>
      </section>

      <div className="flex gap-4 text-sm">
        <Link href="/traces" className="underline">View traces</Link>
        <Link href="/evals" className="underline">View eval runs</Link>
      </div>
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
