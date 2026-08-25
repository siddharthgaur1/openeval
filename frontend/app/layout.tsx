import "./globals.css";
import type { Metadata } from "next";
import { Providers } from "@/lib/providers";
import { NavBar } from "@/components/NavBar";

export const metadata: Metadata = {
  title: "OpenEval",
  description: "LLM evaluation & observability platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 min-h-screen">
        <Providers>
          <NavBar />
          <main className="p-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
