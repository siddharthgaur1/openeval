"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export default function DatasetsPage() {
  const queryClient = useQueryClient();
  const { data: datasets, isLoading, error } = useQuery({ queryKey: ["datasets"], queryFn: api.datasets });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const createFromCsv = useMutation({
    mutationFn: async () => {
      if (!name) throw new Error("Name is required");
      if (file) return api.uploadDataset(name, file);
      return api.createDataset(name, []);
    },
    onSuccess: () => {
      setName("");
      setFile(null);
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
    onError: (e) => setFormError((e as Error).message),
  });

  if (isLoading) return <p>Loading datasets...</p>;
  if (error) return <p className="text-red-400">Failed to load datasets: {(error as Error).message}</p>;

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Datasets</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          createFromCsv.mutate();
        }}
        className="flex flex-wrap items-end gap-3 rounded border border-slate-800 p-4"
      >
        <div>
          <label className="block text-xs text-slate-400 mb-1">Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} required className="rounded border border-slate-800 bg-slate-900 px-3 py-2" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">CSV/JSONL file (optional)</label>
          <input type="file" accept=".csv,.jsonl" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm" />
        </div>
        <button disabled={createFromCsv.isPending} type="submit" className="rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-4 py-2 text-sm font-medium">
          {createFromCsv.isPending ? "Creating..." : "Create dataset"}
        </button>
        {formError && <p className="text-red-400 text-sm">{formError}</p>}
      </form>

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-400 border-b border-slate-800">
            <th className="py-2">Name</th>
            <th>Version</th>
            <th>Rows</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {datasets?.map((d) => (
            <tr key={d.id} className="border-b border-slate-900">
              <td className="py-2">{d.name}</td>
              <td>v{d.version}</td>
              <td>{d.row_count}</td>
              <td>
                <button className="underline text-indigo-400" onClick={() => setSelectedId(selectedId === d.id ? null : d.id)}>
                  {selectedId === d.id ? "Hide rows" : "View rows"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selectedId && <DatasetDetail datasetId={selectedId} />}
    </div>
  );
}

function DatasetDetail({ datasetId }: { datasetId: string }) {
  const queryClient = useQueryClient();
  const { data: rows, isLoading } = useQuery({ queryKey: ["dataset-rows", datasetId], queryFn: () => api.datasetRows(datasetId) });
  const [mode, setMode] = useState<"variation" | "adversarial">("variation");
  const [count, setCount] = useState(10);

  const generate = useMutation({
    mutationFn: () => api.generateDatasetRows(datasetId, mode, count),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["datasets"] }),
  });

  return (
    <div className="space-y-4 rounded border border-slate-800 p-4">
      <div className="flex items-center gap-3">
        <h2 className="font-medium">Rows</h2>
        <select value={mode} onChange={(e) => setMode(e.target.value as "variation" | "adversarial")} className="rounded border border-slate-800 bg-slate-900 px-2 py-1 text-sm">
          <option value="variation">Variation</option>
          <option value="adversarial">Adversarial</option>
        </select>
        <input
          type="number"
          min={1}
          max={100}
          value={count}
          onChange={(e) => setCount(Number(e.target.value))}
          className="w-20 rounded border border-slate-800 bg-slate-900 px-2 py-1 text-sm"
        />
        <button disabled={generate.isPending} onClick={() => generate.mutate()} className="rounded bg-slate-800 hover:bg-slate-700 px-3 py-1 text-sm">
          {generate.isPending ? "Generating..." : "Generate synthetic rows (new version)"}
        </button>
      </div>
      {generate.isError && <p className="text-red-400 text-sm">{(generate.error as Error).message}</p>}

      {isLoading ? (
        <p>Loading rows...</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-400 border-b border-slate-800">
              <th className="py-2">Input</th>
              <th>Expected output</th>
              <th>Context</th>
            </tr>
          </thead>
          <tbody>
            {rows?.map((r) => (
              <tr key={r.id} className="border-b border-slate-900 align-top">
                <td className="py-2 max-w-xs whitespace-pre-wrap">{r.input}</td>
                <td className="max-w-xs whitespace-pre-wrap">{r.expected_output ?? "-"}</td>
                <td className="max-w-xs whitespace-pre-wrap">{r.context ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
