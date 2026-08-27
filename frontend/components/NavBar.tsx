"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

const LINKS = [
  { href: "/traces", label: "Traces" },
  { href: "/datasets", label: "Datasets" },
  { href: "/prompts", label: "Prompts" },
  { href: "/evals", label: "Eval Runs" },
  { href: "/experiments", label: "Experiments" },
  { href: "/annotations", label: "Annotations" },
  { href: "/analytics", label: "Analytics" },
  { href: "/settings", label: "Settings" },
];

export function NavBar() {
  const pathname = usePathname();
  const router = useRouter();

  if (pathname === "/login") return null;

  function logout() {
    window.localStorage.removeItem("openeval_token");
    router.push("/login");
  }

  return (
    <nav className="border-b border-slate-800 px-6 py-4 flex items-center gap-6 overflow-x-auto">
      <Link href="/" className="font-semibold shrink-0">OpenEval</Link>
      {LINKS.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={`shrink-0 text-slate-300 hover:text-white ${pathname?.startsWith(l.href) ? "text-white" : ""}`}
        >
          {l.label}
        </Link>
      ))}
      <button onClick={logout} className="ml-auto shrink-0 text-slate-400 hover:text-white text-sm">
        Log out
      </button>
    </nav>
  );
}
