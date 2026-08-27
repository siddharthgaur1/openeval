"use client";

import { useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, KappaResult } from "@/lib/api";

export default function AnnotationsPage() {
  return (
    <div className="space-y-10">
      <h1 className="text-xl font-semibold">Human Evaluation</h1>
      <AssignForm />
      <MyQueue />
      <KappaCalculator />
    </div>
  );
}

function AssignForm() {
  const [traceId, setTraceId] = useState("");
  const [userId, setUserId] = useState("");
  const [criteria, setCriteria] = useState("coherence, toxicity");
  const [ok, setOk] = useState(false);
  const { data: members } = useQuery({ queryKey: ["org-members"], queryFn: api.orgMembers });

  const assign = useMutation({
    mutationFn: () => api.assignAnnotation(traceId, userId, { criteria: criteria.split(",").map((c) => c.trim()).filter(Boolean) }),
    onSuccess: () => {
      setOk(true);
      setTraceId("");
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        setOk(false);
        assign.mutate();
      }}
      className="flex flex-wrap items-end gap-3 rounded border border-slate-800 p-4"
    >
      <div>
        <label className="block text-xs text-slate-400 mb-1">Trace ID</label>
        <input value={traceId} onChange={(e) => setTraceId(e.target.value)} required className="rounded border border-slate-800 bg-slate-900 px-3 py-2 w-72" />
      </div>
      <div>
        <label className="block text-xs text-slate-400 mb-1">Assign to</label>
        <select value={userId} onChange={(e) => setUserId(e.target.value)} required className="rounded border border-slate-800 bg-slate-900 px-3 py-2 w-72">
          <option value="" disabled>
            Select a teammate...
          </option>
          {members?.map((m) => (
            <option key={m.user_id} value={m.user_id}>
              {m.email} ({m.role})
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-xs text-slate-400 mb-1">Rubric criteria (comma-separated)</label>
        <input value={criteria} onChange={(e) => setCriteria(e.target.value)} className="rounded border border-slate-800 bg-slate-900 px-3 py-2 w-72" />
      </div>
      <button disabled={assign.isPending} type="submit" className="rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-4 py-2 text-sm font-medium">
        {assign.isPending ? "Assigning..." : "Assign for review"}
      </button>
      {ok && <span className="text-emerald-400 text-sm">Assigned.</span>}
      {assign.isError && <span className="text-red-400 text-sm">{(assign.error as Error).message}</span>}
    </form>
  );
}

function MyQueue() {
  const queryClient = useQueryClient();
  const { data: queue, isLoading, error } = useQuery({ queryKey: ["annotation-queue"], queryFn: api.annotationQueue });

  const traceQueries = useQueries({
    queries: (queue ?? []).map((item) => ({
      queryKey: ["trace", item.trace_id],
      queryFn: () => api.trace(item.trace_id),
      enabled: !!queue,
    })),
  });

  if (isLoading) return <p>Loading queue...</p>;
  if (error) return <p className="text-red-400">Failed to load queue: {(error as Error).message}</p>;

  return (
    <div className="space-y-4">
      <h2 className="font-medium">My review queue</h2>
      {queue?.length === 0 && <p className="text-slate-400 text-sm">Nothing assigned to you.</p>}
      {queue?.map((item, i) => (
        <AnnotationItem key={item.id} item={item} trace={traceQueries[i]?.data} onDone={() => queryClient.invalidateQueries({ queryKey: ["annotation-queue"] })} />
      ))}
    </div>
  );
}

function AnnotationItem({
  item,
  trace,
  onDone,
}: {
  item: { id: string; trace_id: string; rubric: Record<string, unknown>; status: string };
  trace?: { prompt: string; response: string };
  onDone: () => void;
}) {
  const criteria = (item.rubric.criteria as string[] | undefined) ?? ["overall"];
  const [scores, setScores] = useState<Record<string, number>>({});
  const [comment, setComment] = useState("");

  const submit = useMutation({
    mutationFn: () => api.submitAnnotation(item.id, scores, comment || undefined),
    onSuccess: onDone,
  });

  return (
    <div className="space-y-3 rounded border border-slate-800 p-4">
      <div className="text-xs text-slate-500">Trace {item.trace_id}</div>
      {trace && (
        <div className="grid grid-cols-2 gap-4 text-sm">
          <pre className="whitespace-pre-wrap rounded bg-slate-900 p-2">{trace.prompt}</pre>
          <pre className="whitespace-pre-wrap rounded bg-slate-900 p-2">{trace.response}</pre>
        </div>
      )}
      {item.status === "completed" ? (
        <p className="text-emerald-400 text-sm">Submitted.</p>
      ) : (
        <div className="flex flex-wrap items-end gap-3">
          {criteria.map((c) => (
            <div key={c}>
              <label className="block text-xs text-slate-400 mb-1">{c} (1-5)</label>
              <input
                type="number"
                min={1}
                max={5}
                value={scores[c] ?? ""}
                onChange={(e) => setScores({ ...scores, [c]: Number(e.target.value) })}
                className="w-20 rounded border border-slate-800 bg-slate-900 px-2 py-1"
              />
            </div>
          ))}
          <input placeholder="Comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} className="flex-1 rounded border border-slate-800 bg-slate-900 px-3 py-2" />
          <button disabled={submit.isPending} onClick={() => submit.mutate()} className="rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-4 py-2 text-sm font-medium">
            Submit
          </button>
        </div>
      )}
    </div>
  );
}

function KappaCalculator() {
  const [criterion, setCriterion] = useState("coherence");
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [result, setResult] = useState<KappaResult | null>(null);
  const { data: members } = useQuery({ queryKey: ["org-members"], queryFn: api.orgMembers });

  const compute = useMutation({
    mutationFn: () => api.kappa(criterion, a, b),
    onSuccess: setResult,
  });

  return (
    <div className="space-y-3 rounded border border-slate-800 p-4">
      <h2 className="font-medium">Inter-annotator agreement (Cohen's kappa)</h2>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Criterion</label>
          <input value={criterion} onChange={(e) => setCriterion(e.target.value)} className="rounded border border-slate-800 bg-slate-900 px-3 py-2" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Annotator A</label>
          <select value={a} onChange={(e) => setA(e.target.value)} className="rounded border border-slate-800 bg-slate-900 px-3 py-2 w-64">
            <option value="">Select...</option>
            {members?.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.email}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Annotator B</label>
          <select value={b} onChange={(e) => setB(e.target.value)} className="rounded border border-slate-800 bg-slate-900 px-3 py-2 w-64">
            <option value="">Select...</option>
            {members?.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.email}
              </option>
            ))}
          </select>
        </div>
        <button disabled={compute.isPending} onClick={() => compute.mutate()} className="rounded bg-slate-800 hover:bg-slate-700 px-4 py-2 text-sm">
          Compute
        </button>
      </div>
      {result && (
        <p className="text-sm">
          κ = {result.kappa.toFixed(3)} across {result.n_shared_items} shared items
        </p>
      )}
      {compute.isError && <p className="text-red-400 text-sm">{(compute.error as Error).message}</p>}
    </div>
  );
}
