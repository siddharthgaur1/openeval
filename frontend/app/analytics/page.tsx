"use client";

import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";

export default function AnalyticsPage() {
  const { data: cost, isLoading: costLoading, error: costError } = useQuery({ queryKey: ["analytics-cost"], queryFn: api.costAnalytics });
  const { data: latency, isLoading: latencyLoading, error: latencyError } = useQuery({ queryKey: ["analytics-latency"], queryFn: api.latencyAnalytics });

  if (costLoading || latencyLoading) return <p>Loading analytics...</p>;
  if (costError || latencyError) return <p className="text-red-400">Failed to load analytics: {((costError ?? latencyError) as Error).message}</p>;

  const costByDay = Object.entries(cost?.by_day ?? {}).map(([day, usd]) => ({ day, usd }));
  const costByModel = Object.entries(cost?.by_model ?? {}).map(([model, usd]) => ({ model, usd }));
  const latencyByModel = Object.entries(latency?.by_model ?? {}).map(([model, v]) => ({ model, ...v }));

  return (
    <div className="space-y-10">
      <h1 className="text-xl font-semibold">Cost & Latency Analytics</h1>

      <div className="grid grid-cols-3 gap-4">
        <Stat label="Total cost" value={`$${cost?.total_usd.toFixed(4) ?? "0"}`} />
        <Stat label="Projected monthly cost" value={`$${cost?.projected_monthly_usd.toFixed(2) ?? "0"}`} />
        <Stat label="Models tracked" value={costByModel.length} />
      </div>

      <section className="space-y-3">
        <h2 className="font-medium">Daily cost trend</h2>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={costByDay}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="day" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} />
              <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }} />
              <Line type="monotone" dataKey="usd" stroke="#818cf8" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="font-medium">Cost by model</h2>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={costByModel}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="model" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} />
              <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }} />
              <Bar dataKey="usd" fill="#818cf8" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="font-medium">Latency by model (ms)</h2>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={latencyByModel}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="model" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} />
              <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }} />
              <Bar dataKey="p50" fill="#38bdf8" name="p50" />
              <Bar dataKey="p95" fill="#818cf8" name="p95" />
              <Bar dataKey="p99" fill="#f472b6" name="p99" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
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
