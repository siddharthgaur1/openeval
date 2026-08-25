"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { access_token } = mode === "login" ? await api.login(email, password) : await api.register(email, password);
      window.localStorage.setItem("openeval_token", access_token);
      router.push("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-sm mx-auto mt-16 space-y-6">
      <h1 className="text-xl font-semibold">{mode === "login" ? "Log in" : "Create an account"}</h1>
      <form onSubmit={submit} className="space-y-4">
        <input
          type="email"
          placeholder="Email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded border border-slate-800 bg-slate-900 px-3 py-2"
        />
        <input
          type="password"
          placeholder="Password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded border border-slate-800 bg-slate-900 px-3 py-2"
        />
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <button disabled={busy} type="submit" className="w-full rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 py-2 font-medium">
          {busy ? "Please wait..." : mode === "login" ? "Log in" : "Register"}
        </button>
      </form>
      <button className="text-sm text-slate-400 underline" onClick={() => setMode(mode === "login" ? "register" : "login")}>
        {mode === "login" ? "Need an account? Register" : "Already have an account? Log in"}
      </button>
    </div>
  );
}
