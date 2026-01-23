"use client";

import axios from "axios";
import { FormEvent, useState } from "react";

type Log = {
  id: string;
  timestamp: string;
  service: string;
  level: string;
  message: string;
  trace_id?: string | null;
  metadata?: Record<string, unknown>;
};

export default function HomePage() {
  const [service, setService] = useState("");
  const [level, setLevel] = useState("");
  const [q, setQ] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const params: Record<string, string> = {};
      if (service) params.service = service;
      if (level) params.level = level;
      if (q) params.q = q;
      // Convert datetime-local to ISO format
      if (from) params.from = new Date(from).toISOString();
      if (to) params.to = new Date(to).toISOString();

      const res = await axios.get<Log[]>("http://localhost:8000/logs/search", {
        params
      });
      setLogs(res.data);
    } catch (err) {
      console.error(err);
      setError("Failed to fetch logs. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-50">Log Search</h1>
        <div className="flex gap-4">
          <a
            href="/alerts"
            className="text-sm text-emerald-400 hover:text-emerald-300"
          >
            Alerts & Incidents →
          </a>
          <a
            href="/ask"
            className="text-sm text-blue-400 hover:text-blue-300"
          >
            Ask My Logs →
          </a>
        </div>
      </div>
      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-slate-100">
          Log Search
        </h2>
        <form
          onSubmit={handleSearch}
          className="grid gap-3 md:grid-cols-5 md:items-end"
        >
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">Service</label>
            <input
              value={service}
              onChange={(e) => setService(e.target.value)}
              placeholder="payment-service"
              className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-50 outline-none ring-0 focus:border-emerald-500"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">Level</label>
            <select
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-50 outline-none ring-0 focus:border-emerald-500"
            >
              <option value="">Any</option>
              <option value="DEBUG">DEBUG</option>
              <option value="INFO">INFO</option>
              <option value="WARN">WARN</option>
              <option value="ERROR">ERROR</option>
              <option value="FATAL">FATAL</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">Query</label>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="timeout OR payment failed"
              className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-50 outline-none ring-0 focus:border-emerald-500"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">From (ISO)</label>
            <input
              type="datetime-local"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-50 outline-none ring-0 focus:border-emerald-500"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">To (ISO)</label>
            <input
              type="datetime-local"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-50 outline-none ring-0 focus:border-emerald-500"
            />
          </div>
          <div className="md:col-span-5 flex justify-end pt-1">
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-md bg-emerald-500 px-3 py-1.5 text-sm font-medium text-emerald-950 shadow hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Searching..." : "Search Logs"}
            </button>
          </div>
        </form>
      </section>

      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-200">
          {error}
        </div>
      )}

      <section className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-100">
            Results ({logs.length})
          </h2>
        </div>
        <div className="max-h-[480px] space-y-1 overflow-auto text-xs font-mono">
          {logs.length === 0 && (
            <p className="text-slate-500">
              No logs yet. Try ingesting some logs via the API.
            </p>
          )}
          {logs.map((log) => (
            <div
              key={log.id}
              className="rounded-md border border-slate-800 bg-slate-900/60 p-2"
            >
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="text-[11px] text-slate-400">
                  {new Date(log.timestamp).toISOString()}
                </span>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-200">
                    {log.service}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide ${
                      log.level === "ERROR" || log.level === "FATAL"
                        ? "bg-red-500/20 text-red-300"
                        : log.level === "WARN"
                        ? "bg-amber-500/20 text-amber-300"
                        : "bg-emerald-500/20 text-emerald-300"
                    }`}
                  >
                    {log.level}
                  </span>
                </div>
              </div>
              <p className="text-slate-100">{log.message}</p>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
                <span className="truncate">id: {log.id}</span>
                {log.trace_id && <span>trace: {log.trace_id}</span>}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

