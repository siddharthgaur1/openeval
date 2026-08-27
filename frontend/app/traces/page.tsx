"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, Trace } from "@/lib/api";

export default function TracesPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [modelFilter, setModelFilter] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Debounced so search filters server-side (across the whole project, not just
  // the current page) without firing a request per keystroke.
  useEffect(() => {
    const id = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(id);
  }, [search]);

  const { data: traces, isLoading, error } = useQuery({
    queryKey: ["traces", debouncedSearch, modelFilter],
    queryFn: () => api.traces({ search: debouncedSearch || undefined, model: modelFilter || undefined }),
  });
  const { data: stats } = useQuery({ queryKey: ["trace-stats"], queryFn: api.traceStats });
  // Unfiltered fetch just to populate the model dropdown's options.
  const { data: allTraces } = useQuery({ queryKey: ["traces", "__all__"], queryFn: () => api.traces({}) });

  const models = useMemo(() => [...new Set((allTraces ?? []).map((t) => t.model))], [allTraces]);
  const filtered = traces ?? [];

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

      <div className="flex gap-3">
        <input
          placeholder="Search prompt/response..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 rounded border border-slate-800 bg-slate-900 px-3 py-2 text-sm"
        />
        <select value={modelFilter} onChange={(e) => setModelFilter(e.target.value)} className="rounded border border-slate-800 bg-slate-900 px-3 py-2 text-sm">
          <option value="">All models</option>
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-400 border-b border-slate-800">
            <th className="py-2">Model</th>
            <th>Latency</th>
            <th>Tokens</th>
            <th>Cost</th>
            <th>Feedback</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((t) => (
            <TraceRow key={t.id} trace={t} expanded={expandedId === t.id} onToggle={() => setExpandedId(expandedId === t.id ? null : t.id)} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TraceRow({ trace, expanded, onToggle }: { trace: Trace; expanded: boolean; onToggle: () => void }) {
  const queryClient = useQueryClient();
  const [comment, setComment] = useState("");

  const feedback = useMutation({
    mutationFn: (score: number) => api.submitFeedback(trace.id, score, comment || undefined),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["traces"], exact: false }),
  });

  const existingFeedback = trace.tags?.feedback;

  return (
    <>
      <tr className={`border-b border-slate-900 cursor-pointer ${trace.error ? "text-red-400" : ""}`} onClick={onToggle}>
        <td className="py-2">{trace.model}</td>
        <td>{trace.latency_ms.toFixed(0)}ms</td>
        <td>{trace.prompt_tokens + trace.completion_tokens}</td>
        <td>${trace.cost_usd.toFixed(4)}</td>
        <td>{existingFeedback ? (existingFeedback.score > 0 ? "👍" : "👎") : "-"}</td>
        <td>{new Date(trace.created_at).toLocaleString()}</td>
      </tr>
      {expanded && (
        <tr className="border-b border-slate-900 bg-slate-900/40">
          <td colSpan={6} className="p-4 space-y-3">
            {trace.error && <p className="text-red-400 font-mono text-xs whitespace-pre-wrap">{trace.error}</p>}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-slate-400 mb-1">Prompt</div>
                <pre className="whitespace-pre-wrap rounded bg-slate-950 p-2 text-xs">{trace.prompt}</pre>
              </div>
              <div>
                <div className="text-xs text-slate-400 mb-1">Response</div>
                <pre className="whitespace-pre-wrap rounded bg-slate-950 p-2 text-xs">{trace.response}</pre>
              </div>
            </div>
            <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
              <button onClick={() => feedback.mutate(1)} className="rounded bg-slate-800 hover:bg-slate-700 px-3 py-1 text-sm">
                👍
              </button>
              <button onClick={() => feedback.mutate(-1)} className="rounded bg-slate-800 hover:bg-slate-700 px-3 py-1 text-sm">
                👎
              </button>
              <input
                placeholder="Comment (optional)"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                className="flex-1 rounded border border-slate-800 bg-slate-900 px-3 py-1 text-sm"
              />
              {existingFeedback && <span className="text-xs text-slate-500">Last: {existingFeedback.comment ?? "no comment"}</span>}
            </div>
          </td>
        </tr>
      )}
    </>
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
