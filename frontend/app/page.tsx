import Link from "next/link";

export default function Home() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Welcome to OpenEval</h1>
      <p className="text-slate-400">Self-hostable LLM evaluation & observability.</p>
      <div className="flex gap-4">
        <Link href="/traces" className="underline">View traces</Link>
        <Link href="/evals" className="underline">View eval runs</Link>
      </div>
    </div>
  );
}
