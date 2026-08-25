"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, PlaygroundResult, PromptTemplate } from "@/lib/api";
import { lineDiff } from "@/lib/diff";

export default function PromptsPage() {
  const queryClient = useQueryClient();
  const { data: prompts, isLoading, error } = useQuery({ queryKey: ["prompts"], queryFn: api.prompts });
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [template, setTemplate] = useState("");
  const [variables, setVariables] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const latestByName = useMemo(() => {
    const map = new Map<string, PromptTemplate>();
    for (const p of prompts ?? []) {
      const existing = map.get(p.name);
      if (!existing || p.version > existing.version) map.set(p.name, p);
    }
    return [...map.values()];
  }, [prompts]);

  const create = useMutation({
    mutationFn: () =>
      api.createPrompt(
        name,
        template,
        variables.split(",").map((v) => v.trim()).filter(Boolean),
      ),
    onSuccess: () => {
      setName("");
      setTemplate("");
      setVariables("");
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
    },
    onError: (e) => setFormError((e as Error).message),
  });

  if (isLoading) return <p>Loading prompts...</p>;
  if (error) return <p className="text-red-400">Failed to load prompts: {(error as Error).message}</p>;

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Prompts</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
        className="space-y-3 rounded border border-slate-800 p-4"
      >
        <div className="flex gap-3">
          <input placeholder="Prompt name" value={name} onChange={(e) => setName(e.target.value)} required className="rounded border border-slate-800 bg-slate-900 px-3 py-2" />
          <input placeholder="Variables (comma-separated)" value={variables} onChange={(e) => setVariables(e.target.value)} className="flex-1 rounded border border-slate-800 bg-slate-900 px-3 py-2" />
        </div>
        <textarea
          placeholder="Template, e.g. Answer using $context: $question"
          value={template}
          onChange={(e) => setTemplate(e.target.value)}
          required
          rows={4}
          className="w-full rounded border border-slate-800 bg-slate-900 px-3 py-2 font-mono text-sm"
        />
        <button disabled={create.isPending} type="submit" className="rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-4 py-2 text-sm font-medium">
          {create.isPending ? "Saving..." : "Save new prompt / version"}
        </button>
        {formError && <p className="text-red-400 text-sm">{formError}</p>}
      </form>

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-400 border-b border-slate-800">
            <th className="py-2">Name</th>
            <th>Latest version</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {latestByName.map((p) => (
            <tr key={p.name} className="border-b border-slate-900">
              <td className="py-2">{p.name}</td>
              <td>v{p.version}</td>
              <td>
                <StatusBadge status={p.status} />
              </td>
              <td>
                <button className="underline text-indigo-400" onClick={() => setSelectedName(selectedName === p.name ? null : p.name)}>
                  {selectedName === p.name ? "Hide" : "Versions & playground"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selectedName && <PromptDetail name={selectedName} />}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color = status === "production" ? "bg-emerald-900 text-emerald-300" : status === "staging" ? "bg-amber-900 text-amber-300" : "bg-slate-800 text-slate-300";
  return <span className={`rounded px-2 py-0.5 text-xs ${color}`}>{status}</span>;
}

function PromptDetail({ name }: { name: string }) {
  const queryClient = useQueryClient();
  const { data: versions, isLoading } = useQuery({ queryKey: ["prompt-versions", name], queryFn: () => api.promptVersions(name) });
  const [diffPair, setDiffPair] = useState<[number, number] | null>(null);
  const [playgroundVersionId, setPlaygroundVersionId] = useState<string | null>(null);
  const [model, setModel] = useState("gpt-4o-mini");
  const [varsJson, setVarsJson] = useState("{}");
  const [result, setResult] = useState<PlaygroundResult | null>(null);
  const [playgroundError, setPlaygroundError] = useState<string | null>(null);

  const promote = useMutation({
    mutationFn: (versionId: string) => api.promotePrompt(versionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompt-versions", name] });
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
    },
  });

  const runPlayground = useMutation({
    mutationFn: async () => {
      if (!playgroundVersionId) throw new Error("Select a version first");
      let vars: Record<string, string>;
      try {
        vars = JSON.parse(varsJson);
      } catch {
        throw new Error("Variables must be valid JSON, e.g. {\"question\": \"...\"}");
      }
      return api.runPlayground(playgroundVersionId, model, vars);
    },
    onSuccess: (r) => {
      setResult(r);
      setPlaygroundError(null);
    },
    onError: (e) => setPlaygroundError((e as Error).message),
  });

  if (isLoading) return <p>Loading versions...</p>;

  const versionA = diffPair ? versions?.find((v) => v.version === diffPair[0]) : null;
  const versionB = diffPair ? versions?.find((v) => v.version === diffPair[1]) : null;

  return (
    <div className="space-y-6 rounded border border-slate-800 p-4">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-400 border-b border-slate-800">
            <th className="py-2">Version</th>
            <th>Status</th>
            <th>Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {versions?.map((v) => (
            <tr key={v.id} className="border-b border-slate-900">
              <td className="py-2">v{v.version}</td>
              <td>
                <StatusBadge status={v.status} />
              </td>
              <td>{new Date(v.created_at).toLocaleString()}</td>
              <td className="space-x-3">
                <button
                  className="underline text-indigo-400"
                  disabled={promote.isPending || v.status === "production"}
                  onClick={() => promote.mutate(v.id)}
                >
                  Promote
                </button>
                <button className="underline text-indigo-400" onClick={() => setPlaygroundVersionId(v.id)}>
                  Playground
                </button>
                <button
                  className="underline text-slate-400"
                  onClick={() => setDiffPair(v.version > 1 ? [v.version - 1, v.version] : null)}
                >
                  Diff vs prev
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {versionA && versionB && <DiffView left={versionA.template} right={versionB.template} leftLabel={`v${versionA.version}`} rightLabel={`v${versionB.version}`} />}

      {playgroundVersionId && (
        <div className="space-y-3 rounded border border-slate-800 p-4">
          <h3 className="font-medium">Playground</h3>
          <div className="flex gap-3">
            <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="Model (e.g. gpt-4o-mini)" className="rounded border border-slate-800 bg-slate-900 px-3 py-2" />
          </div>
          <textarea
            value={varsJson}
            onChange={(e) => setVarsJson(e.target.value)}
            rows={3}
            className="w-full rounded border border-slate-800 bg-slate-900 px-3 py-2 font-mono text-sm"
          />
          <button disabled={runPlayground.isPending} onClick={() => runPlayground.mutate()} className="rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-4 py-2 text-sm font-medium">
            {runPlayground.isPending ? "Running..." : "Run"}
          </button>
          {playgroundError && <p className="text-red-400 text-sm">{playgroundError}</p>}
          {result && (
            <div className="space-y-2 text-sm">
              <div>
                <span className="text-slate-400">Rendered prompt:</span>
                <pre className="whitespace-pre-wrap rounded bg-slate-900 p-2">{result.rendered_prompt}</pre>
              </div>
              <div>
                <span className="text-slate-400">Output:</span>
                <pre className="whitespace-pre-wrap rounded bg-slate-900 p-2">{result.output}</pre>
              </div>
              <div className="text-slate-400">
                {result.latency_ms.toFixed(0)}ms · ${result.cost_usd.toFixed(5)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DiffView({ left, right, leftLabel, rightLabel }: { left: string; right: string; leftLabel: string; rightLabel: string }) {
  const lines = lineDiff(left, right);
  return (
    <div className="space-y-1 rounded border border-slate-800 p-3 font-mono text-xs">
      <div className="text-slate-400">
        {leftLabel} → {rightLabel}
      </div>
      {lines.map((l, i) => (
        <div key={i} className={l.type === "add" ? "bg-emerald-950 text-emerald-300" : l.type === "remove" ? "bg-red-950 text-red-300" : "text-slate-400"}>
          {l.type === "add" ? "+ " : l.type === "remove" ? "- " : "  "}
          {l.text}
        </div>
      ))}
    </div>
  );
}
