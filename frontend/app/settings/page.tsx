"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { data: keys, isLoading, error } = useQuery({ queryKey: ["api-keys"], queryFn: api.apiKeys });
  const [name, setName] = useState("");
  const [scope, setScope] = useState<"read" | "write" | "admin">("write");
  const [justCreated, setJustCreated] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => api.createApiKey(name, scope),
    onSuccess: (key) => {
      setJustCreated(key.key);
      setName("");
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const revoke = useMutation({
    mutationFn: (id: string) => api.revokeApiKey(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["api-keys"] }),
  });

  return (
    <div className="space-y-8 max-w-2xl">
      <h1 className="text-xl font-semibold">API keys</h1>
      <p className="text-sm text-slate-400">
        Used by the SDK, LiteLLM proxy, and CI to authenticate instead of your login session.
        A <code>read</code> key can only fetch data; <code>write</code> can also ingest traces and trigger
        evals; <code>admin</code> can additionally manage other API keys.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
        className="flex flex-wrap items-end gap-3 rounded border border-slate-800 p-4"
      >
        <div>
          <label className="block text-xs text-slate-400 mb-1">Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="ci-pipeline"
            className="rounded border border-slate-800 bg-slate-900 px-3 py-2"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Scope</label>
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value as "read" | "write" | "admin")}
            className="rounded border border-slate-800 bg-slate-900 px-2 py-2"
          >
            <option value="read">read</option>
            <option value="write">write</option>
            <option value="admin">admin</option>
          </select>
        </div>
        <button disabled={create.isPending} type="submit" className="rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-4 py-2 text-sm font-medium">
          {create.isPending ? "Creating..." : "Create key"}
        </button>
      </form>

      {justCreated && (
        <div className="rounded border border-amber-700 bg-amber-950/40 p-4 text-sm">
          <p className="mb-2 text-amber-300">
            Copy this key now - it will not be shown again.
          </p>
          <code className="break-all">{justCreated}</code>
        </div>
      )}

      {isLoading ? (
        <p>Loading keys...</p>
      ) : error ? (
        <p className="text-red-400">Failed to load API keys: {(error as Error).message}</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-400 border-b border-slate-800">
              <th className="py-2">Name</th>
              <th>Prefix</th>
              <th>Scope</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {keys?.map((k) => (
              <tr key={k.id} className="border-b border-slate-900">
                <td className="py-2">{k.name}</td>
                <td className="font-mono text-slate-400">{k.prefix}…</td>
                <td>{k.scope}</td>
                <td>
                  <button
                    onClick={() => revoke.mutate(k.id)}
                    disabled={revoke.isPending}
                    className="text-red-400 hover:text-red-300 disabled:opacity-50"
                  >
                    Revoke
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
