"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";

// The hosted backend is on Render's free tier and sleeps when idle; measured cold
// starts are 1.5-4 min. Poll /health with backoff and give up after this long.
const GIVE_UP_MS = 6 * 60 * 1000;
// Only show the banner if /health is still unanswered after this, so a warm backend never flashes it.
const SHOW_AFTER_MS = 3000;

export function WakeBanner() {
  const [state, setState] = useState<"checking" | "up" | "down">("checking");
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const start = Date.now();
    const slowTimer = setTimeout(() => setSlow(true), SHOW_AFTER_MS);

    async function poll(delay: number) {
      try {
        const res = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(15000) });
        if (res.ok) {
          if (!stopped) setState("up");
          return;
        }
      } catch {
        // network error or timeout while the backend boots - retry below
      }
      if (stopped) return;
      if (Date.now() - start > GIVE_UP_MS) {
        setState("down");
        return;
      }
      timer = setTimeout(() => poll(Math.min(delay * 2, 30000)), delay);
    }
    poll(2000);

    return () => {
      stopped = true;
      clearTimeout(timer);
      clearTimeout(slowTimer);
    };
  }, []);

  if (state === "up" || !slow) return null;
  return (
    <div role="status" className="border-b border-amber-800 bg-amber-950 px-6 py-2 text-sm text-amber-200">
      {state === "down"
        ? "Backend still isn't responding after several minutes. Try reloading, or check back later."
        : "Backend on a free tier is waking up — first load can take a few minutes."}
    </div>
  );
}
