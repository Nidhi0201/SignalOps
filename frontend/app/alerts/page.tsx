"use client";

import axios from "axios";
import { useEffect, useState } from "react";
import Link from "next/link";

type AlertRule = {
  id: number;
  name: string;
  service: string | null;
  level: string;
  window_minutes: number;
  threshold_count: number;
  enabled: boolean;
  created_at: string;
};

type Incident = {
  id: number;
  alert_rule_id: number;
  start_time: string;
  end_time: string | null;
  status: string;
  log_count: number;
  ai_summary: string | null;
  ai_root_cause: string | null;
  ai_next_steps: string | null;
  created_at: string;
  alert_rule?: AlertRule;
};

export default function AlertsPage() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newRule, setNewRule] = useState({
    name: "",
    service: "",
    level: "ERROR",
    window_minutes: 5,
    threshold_count: 10,
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [rulesRes, incidentsRes] = await Promise.all([
        axios.get<AlertRule[]>("http://localhost:8000/alerts"),
        axios.get<Incident[]>("http://localhost:8000/alerts/incidents"),
      ]);
      setRules(rulesRes.data);
      setIncidents(incidentsRes.data);
    } catch (err) {
      console.error("Failed to load alerts:", err);
    } finally {
      setLoading(false);
    }
  };

  const createRule = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await axios.post("http://localhost:8000/alerts", {
        ...newRule,
        service: newRule.service || null,
      });
      setShowCreateForm(false);
      setNewRule({
        name: "",
        service: "",
        level: "ERROR",
        window_minutes: 5,
        threshold_count: 10,
      });
      loadData();
    } catch (err) {
      console.error("Failed to create rule:", err);
    }
  };

  const toggleRule = async (id: number) => {
    try {
      await axios.post(`http://localhost:8000/alerts/${id}/toggle`);
      loadData();
    } catch (err) {
      console.error("Failed to toggle rule:", err);
    }
  };

  const resolveIncident = async (id: number) => {
    try {
      await axios.post(`http://localhost:8000/alerts/incidents/${id}/resolve`);
      loadData();
    } catch (err) {
      console.error("Failed to resolve incident:", err);
    }
  };

  if (loading) {
    return <div className="p-6 text-slate-400">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-50">Alerts & Incidents</h1>
        <Link
          href="/"
          className="text-sm text-slate-400 hover:text-slate-200"
        >
          ← Back to Logs
        </Link>
      </div>

      {/* Alert Rules */}
      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-100">Alert Rules</h2>
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="rounded-md bg-emerald-500 px-3 py-1.5 text-sm font-medium text-emerald-950 hover:bg-emerald-400"
          >
            {showCreateForm ? "Cancel" : "+ New Rule"}
          </button>
        </div>

        {showCreateForm && (
          <form onSubmit={createRule} className="mb-4 space-y-3 rounded-md border border-slate-700 bg-slate-950/60 p-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="text-xs text-slate-400">Name</label>
                <input
                  value={newRule.name}
                  onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
                  required
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-50"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400">Service (optional)</label>
                <input
                  value={newRule.service}
                  onChange={(e) => setNewRule({ ...newRule, service: e.target.value })}
                  placeholder="payment-service"
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-50"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400">Level</label>
                <select
                  value={newRule.level}
                  onChange={(e) => setNewRule({ ...newRule, level: e.target.value })}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-50"
                >
                  <option value="ERROR">ERROR</option>
                  <option value="FATAL">FATAL</option>
                  <option value="WARN">WARN</option>
                  <option value="INFO">INFO</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-400">Window (minutes)</label>
                <input
                  type="number"
                  value={newRule.window_minutes}
                  onChange={(e) => setNewRule({ ...newRule, window_minutes: parseInt(e.target.value) })}
                  min="1"
                  required
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-50"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400">Threshold Count</label>
                <input
                  type="number"
                  value={newRule.threshold_count}
                  onChange={(e) => setNewRule({ ...newRule, threshold_count: parseInt(e.target.value) })}
                  min="1"
                  required
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-50"
                />
              </div>
            </div>
            <button
              type="submit"
              className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-emerald-950 hover:bg-emerald-400"
            >
              Create Rule
            </button>
          </form>
        )}

        <div className="space-y-2">
          {rules.length === 0 ? (
            <p className="text-sm text-slate-500">No alert rules yet. Create one above.</p>
          ) : (
            rules.map((rule) => (
              <div
                key={rule.id}
                className="flex items-center justify-between rounded-md border border-slate-800 bg-slate-950/60 p-3"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-100">{rule.name}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] uppercase ${
                        rule.enabled
                          ? "bg-emerald-500/20 text-emerald-300"
                          : "bg-slate-700 text-slate-400"
                      }`}
                    >
                      {rule.enabled ? "Enabled" : "Disabled"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">
                    Alert if {rule.level} logs {rule.service ? `from ${rule.service} ` : ""}
                    exceed {rule.threshold_count} in {rule.window_minutes} minutes
                  </p>
                </div>
                <button
                  onClick={() => toggleRule(rule.id)}
                  className="rounded-md bg-slate-700 px-3 py-1.5 text-xs hover:bg-slate-600"
                >
                  {rule.enabled ? "Disable" : "Enable"}
                </button>
              </div>
            ))
          )}
        </div>
      </section>

      {/* Incidents */}
      <section className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
        <h2 className="mb-4 text-sm font-semibold text-slate-100">Incidents ({incidents.length})</h2>
        <div className="space-y-2">
          {incidents.length === 0 ? (
            <p className="text-sm text-slate-500">No incidents yet.</p>
          ) : (
            incidents.map((incident) => (
              <div
                key={incident.id}
                className="rounded-md border border-slate-800 bg-slate-900/60 p-4"
              >
                <div className="mb-2 flex items-center justify-between">
                  <div>
                    <span className="font-medium text-slate-100">
                      {incident.alert_rule?.name || `Alert Rule #${incident.alert_rule_id}`}
                    </span>
                    <span
                      className={`ml-2 rounded-full px-2 py-0.5 text-[10px] uppercase ${
                        incident.status === "open"
                          ? "bg-red-500/20 text-red-300"
                          : incident.status === "acknowledged"
                          ? "bg-amber-500/20 text-amber-300"
                          : "bg-emerald-500/20 text-emerald-300"
                      }`}
                    >
                      {incident.status}
                    </span>
                  </div>
                  {incident.status === "open" && (
                    <button
                      onClick={() => resolveIncident(incident.id)}
                      className="rounded-md bg-emerald-500 px-3 py-1.5 text-xs font-medium text-emerald-950 hover:bg-emerald-400"
                    >
                      Resolve
                    </button>
                  )}
                </div>
                <p className="text-xs text-slate-400">
                  {incident.log_count} matching logs • Started {new Date(incident.start_time).toLocaleString()}
                </p>
                {incident.ai_summary && (
                  <div className="mt-3 space-y-2 rounded-md bg-slate-950/60 p-3 text-xs">
                    <div>
                      <span className="font-semibold text-emerald-400">Summary:</span>
                      <p className="mt-1 text-slate-300">{incident.ai_summary}</p>
                    </div>
                    {incident.ai_root_cause && (
                      <div>
                        <span className="font-semibold text-amber-400">Root Cause:</span>
                        <p className="mt-1 text-slate-300">{incident.ai_root_cause}</p>
                      </div>
                    )}
                    {incident.ai_next_steps && (
                      <div>
                        <span className="font-semibold text-blue-400">Next Steps:</span>
                        <div className="mt-1 text-slate-300 whitespace-pre-line">{incident.ai_next_steps}</div>
                      </div>
                    )}
                  </div>
                )}
                {!incident.ai_summary && incident.status === "open" && (
                  <button
                    onClick={async () => {
                      try {
                        await axios.post(`http://localhost:8000/alerts/incidents/${incident.id}/summarize`);
                        loadData();
                      } catch (err) {
                        console.error("Failed to summarize:", err);
                      }
                    }}
                    className="mt-2 rounded-md bg-blue-500/20 px-2 py-1 text-[10px] text-blue-300 hover:bg-blue-500/30"
                  >
                    Generate AI Summary
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
