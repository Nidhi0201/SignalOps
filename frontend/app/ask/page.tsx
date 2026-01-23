"use client";

import axios from "axios";
import { useState, FormEvent, useEffect } from "react";
import Link from "next/link";

type Citation = {
  log_id: string;
  timestamp: string;
  service: string;
  level: string;
  message: string;
};

type ChatMessage = {
  question: string;
  answer: string;
  citations: Citation[];
  timestamp: Date;
};

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [services, setServices] = useState<string[]>([]);
  const [loadingServices, setLoadingServices] = useState(true);
  const [filters, setFilters] = useState({
    service: "",
    level: "",
    from: "",
    to: "",
    useDateFilter: false,
  });

  // Fetch available services on mount
  useEffect(() => {
    const fetchServices = async () => {
      try {
        const res = await axios.get<string[]>("http://localhost:8000/logs/services");
        setServices(res.data);
      } catch (err) {
        console.error("Failed to fetch services:", err);
      } finally {
        setLoadingServices(false);
      }
    };
    fetchServices();
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!question.trim() || loading) return;

    const currentQuestion = question;
    setQuestion("");
    setLoading(true);

    try {
      const payload: any = { question: currentQuestion };
      if (filters.service?.trim()) payload.service = filters.service.trim();
      if (filters.level?.trim()) payload.level = filters.level.trim();
      // Only send date filters if date filter is enabled AND both dates are provided
      if (filters.useDateFilter && filters.from?.trim() && filters.to?.trim()) {
        const fromDate = new Date(filters.from);
        const toDate = new Date(filters.to);
        if (!isNaN(fromDate.getTime()) && !isNaN(toDate.getTime())) {
          payload.from_ts = fromDate.toISOString();
          payload.to_ts = toDate.toISOString();
        }
      }

      const res = await axios.post("http://localhost:8000/logs/ask", payload);

      setMessages([
        ...messages,
        {
          question: currentQuestion,
          answer: res.data.answer,
          citations: res.data.citations || [],
          timestamp: new Date(),
        },
      ]);
    } catch (err) {
      console.error("Failed to get answer:", err);
      setMessages([
        ...messages,
        {
          question: currentQuestion,
          answer: "Sorry, I couldn't process your question. Make sure the backend is running and try again.",
          citations: [],
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen flex-col">
      <div className="border-b border-slate-800 bg-slate-900/40 px-6 py-4">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-50">Ask My Logs</h1>
            <p className="text-xs text-slate-400">Ask questions about your logs using AI</p>
          </div>
          <Link
            href="/"
            className="text-sm text-slate-400 hover:text-slate-200"
          >
            ← Back to Logs
          </Link>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Filters Sidebar */}
        <div className="w-64 border-r border-slate-800 bg-slate-950/40 p-4 overflow-y-auto">
          <h2 className="mb-3 text-sm font-semibold text-slate-100">Filters</h2>
          <div className="space-y-4">
            {/* Service Filter */}
            <div>
              <label className="text-xs font-medium text-slate-300 mb-1 block">
                Service {filters.service && <span className="text-emerald-400">●</span>}
              </label>
              <select
                value={filters.service}
                onChange={(e) => setFilters({ ...filters, service: e.target.value })}
                className="w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-50 focus:border-emerald-500 focus:outline-none"
                disabled={loadingServices}
              >
                <option value="">All Services</option>
                {services.map((svc) => (
                  <option key={svc} value={svc}>
                    {svc}
                  </option>
                ))}
              </select>
              {loadingServices && (
                <p className="mt-1 text-[10px] text-slate-500">Loading services...</p>
              )}
            </div>

            {/* Level Filter */}
            <div>
              <label className="text-xs font-medium text-slate-300 mb-1 block">
                Level {filters.level && <span className="text-emerald-400">●</span>}
              </label>
              <select
                value={filters.level}
                onChange={(e) => setFilters({ ...filters, level: e.target.value })}
                className="w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-50 focus:border-emerald-500 focus:outline-none"
              >
                <option value="">All Levels</option>
                <option value="ERROR">ERROR</option>
                <option value="FATAL">FATAL</option>
                <option value="WARN">WARN</option>
                <option value="INFO">INFO</option>
                <option value="DEBUG">DEBUG</option>
              </select>
            </div>

            {/* Date Filter Toggle */}
            <div className="border-t border-slate-700 pt-3">
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-medium text-slate-300">
                  Date Range {filters.useDateFilter && <span className="text-emerald-400">●</span>}
                </label>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={filters.useDateFilter}
                    onChange={(e) =>
                      setFilters({ ...filters, useDateFilter: e.target.checked, from: "", to: "" })
                    }
                    className="sr-only peer"
                  />
                  <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-600"></div>
                </label>
              </div>
              {filters.useDateFilter ? (
                <div className="space-y-2 mt-2">
                  <div>
                    <label className="text-[10px] text-slate-400 mb-1 block">From</label>
                    <input
                      type="datetime-local"
                      value={filters.from}
                      onChange={(e) => setFilters({ ...filters, from: e.target.value })}
                      className="w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-50 focus:border-emerald-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-400 mb-1 block">To</label>
                    <input
                      type="datetime-local"
                      value={filters.to}
                      onChange={(e) => setFilters({ ...filters, to: e.target.value })}
                      className="w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-50 focus:border-emerald-500 focus:outline-none"
                    />
                  </div>
                  {(!filters.from || !filters.to) && (
                    <p className="text-[10px] text-amber-400">
                      ⚠ Both dates required for filter
                    </p>
                  )}
                </div>
              ) : (
                <div className="mt-2 p-2 rounded-md bg-slate-900/50 border border-slate-700">
                  <p className="text-[10px] text-slate-400 text-center">
                    All dates (no filter)
                  </p>
                </div>
              )}
            </div>

            {/* Active Filters Summary */}
            {(filters.service || filters.level || filters.useDateFilter) && (
              <div className="border-t border-slate-700 pt-3">
                <p className="text-[10px] font-medium text-slate-400 mb-1">Active Filters:</p>
                <div className="space-y-1">
                  {filters.service && (
                    <div className="text-[10px] text-slate-300">
                      Service: <span className="text-emerald-400">{filters.service}</span>
                    </div>
                  )}
                  {filters.level && (
                    <div className="text-[10px] text-slate-300">
                      Level: <span className="text-emerald-400">{filters.level}</span>
                    </div>
                  )}
                  {filters.useDateFilter && filters.from && filters.to && (
                    <div className="text-[10px] text-slate-300">
                      Date: <span className="text-emerald-400">Set</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Clear Filters Button */}
            <div className="pt-2 border-t border-slate-700">
              <button
                type="button"
                onClick={() =>
                  setFilters({
                    service: "",
                    level: "",
                    from: "",
                    to: "",
                    useDateFilter: false,
                  })
                }
                className="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700 transition-colors"
              >
                Clear All Filters
              </button>
            </div>
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex flex-1 flex-col">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-6">
            <div className="mx-auto max-w-3xl space-y-6">
              {messages.length === 0 && (
                <div className="text-center text-slate-500">
                  <p className="mb-2 text-lg">Ask a question about your logs</p>
                  <p className="text-sm">Examples:</p>
                  <ul className="mt-2 space-y-1 text-sm">
                    <li>"Why did checkout fail in the last 30 minutes?"</li>
                    <li>"What errors occurred in payment-service?"</li>
                    <li>"Show me timeout issues"</li>
                  </ul>
                </div>
              )}

              {messages.map((msg, idx) => (
                <div key={idx} className="space-y-3">
                  {/* Question */}
                  <div className="flex justify-end">
                    <div className="max-w-[80%] rounded-lg bg-emerald-500/20 px-4 py-2">
                      <p className="text-sm text-slate-100">{msg.question}</p>
                    </div>
                  </div>

                  {/* Answer */}
                  <div className="flex justify-start">
                    <div className="max-w-[80%] rounded-lg bg-slate-800 px-4 py-3">
                      <p className="whitespace-pre-line text-sm text-slate-200">{msg.answer}</p>
                      
                      {/* Citations */}
                      {msg.citations.length > 0 && (
                        <div className="mt-3 border-t border-slate-700 pt-3">
                          <p className="mb-2 text-xs font-semibold text-slate-400">Citations:</p>
                          <div className="space-y-2">
                            {msg.citations.slice(0, 5).map((cite, citeIdx) => (
                              <div
                                key={citeIdx}
                                className="rounded-md border border-slate-700 bg-slate-900/60 p-2 text-xs"
                              >
                                <div className="flex items-center gap-2">
                                  <span className="text-slate-500">[{cite.level}]</span>
                                  <span className="text-slate-400">{cite.service}</span>
                                  <span className="text-slate-500">
                                    {new Date(cite.timestamp).toLocaleTimeString()}
                                  </span>
                                </div>
                                <p className="mt-1 text-slate-300">{cite.message}</p>
                                <p className="mt-1 text-[10px] text-slate-500">ID: {cite.log_id}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="rounded-lg bg-slate-800 px-4 py-3">
                    <p className="text-sm text-slate-400">Thinking...</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Input */}
          <div className="border-t border-slate-800 bg-slate-900/40 p-4">
            <form onSubmit={handleSubmit} className="mx-auto max-w-3xl">
              <div className="flex gap-2">
                <input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Ask a question about your logs..."
                  className="flex-1 rounded-md border border-slate-700 bg-slate-950 px-4 py-2 text-sm text-slate-50 placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none"
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading || !question.trim()}
                  className="rounded-md bg-emerald-500 px-6 py-2 text-sm font-medium text-emerald-950 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Ask
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
