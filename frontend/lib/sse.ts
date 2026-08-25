"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type EvalProgress = {
  status: string;
  total_rows: number;
  completed_rows: number;
  failed_rows: number;
  summary?: Record<string, unknown>;
};

export function useEvalProgress(evalRunId: string | undefined, enabled: boolean): EvalProgress | null {
  const [progress, setProgress] = useState<EvalProgress | null>(null);

  useEffect(() => {
    if (!evalRunId || !enabled) return;
    const token = typeof window !== "undefined" ? window.localStorage.getItem("openeval_token") : null;
    const url = `${API_URL}/api/evals/${evalRunId}/status${token ? `?token=${encodeURIComponent(token)}` : ""}`;
    const source = new EventSource(url, { withCredentials: false });

    source.onmessage = (event) => {
      const data = JSON.parse(event.data) as EvalProgress;
      setProgress(data);
      if (data.status === "completed" || data.status === "failed") {
        source.close();
      }
    };
    source.onerror = () => source.close();

    return () => source.close();
  }, [evalRunId, enabled]);

  return progress;
}
