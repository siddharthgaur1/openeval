import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import { Providers } from "@/lib/providers";

export const metadata: Metadata = {
  title: "OpenEval",
  description: "LLM evaluation & observability platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 min-h-screen">
        <Providers>
          <nav className="border-b border-slate-800 px-6 py-4 flex gap-6">
            <span className="font-semibold">OpenEval</span>
            <Link href="/traces" className="text-slate-300 hover:text-white">Traces</Link>
            <Link href="/evals" className="text-slate-300 hover:text-white">Eval Runs</Link>
          </nav>
          <main className="p-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
