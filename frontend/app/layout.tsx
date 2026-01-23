import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "SignalOps",
  description: "Mini Datadog/ELK for logs, alerts, and AI incidents"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-slate-50">
        <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-6">
          <header className="mb-6 flex items-center justify-between">
            <h1 className="text-xl font-semibold text-slate-50">
              SignalOps
            </h1>
            <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
              Phase 1 · Log Search
            </span>
          </header>
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}

