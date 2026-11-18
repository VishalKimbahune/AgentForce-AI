"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import {
  Cpu,
  DollarSign,
  Activity,
  GitFork,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Network,
  Clock,
  ArrowRight,
  RefreshCw,
} from "lucide-react";

interface ModelAnalytics {
  model: string;
  provider: string;
  total_requests: number;
  avg_latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  fallback_count: number;
}

interface AnalyticsData {
  models: ModelAnalytics[];
  total_requests: number;
  total_cost_usd: number;
  total_tokens: number;
}

interface AgentHealthData {
  agent: string;
  role: string;
  total_tasks: number;
  successful_tasks: number;
  failed_tasks: number;
  success_rate: number;
  avg_latency_ms: number;
  status: "healthy" | "degraded" | "failing";
}

interface TraceSpan {
  trace_id: string;
  span_id: string;
  name: string;
  span_type: string;
  duration_ms: number;
  status: string;
  error_message?: string;
  start_time: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AnalyticsPage() {
  const { session, activeTenantId } = useAuth();
  const [activeTab, setActiveTab] = useState<"llm" | "agents" | "traces">("llm");

  const [llmData, setLlmData] = useState<AnalyticsData | null>(null);
  const [agentData, setAgentData] = useState<AgentHealthData[]>([]);
  const [tracesData, setTracesData] = useState<TraceSpan[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchAllAnalytics = () => {
    if (!session?.access_token || !activeTenantId) return;
    setLoading(true);

    const headers = {
      Authorization: `Bearer ${session.access_token}`,
      "X-Tenant-ID": activeTenantId,
    };

    // 1. LLM Analytics
    fetch(`${API_BASE}/api/v1/analytics/llm`, { headers })
      .then((res) => (res.ok ? res.json() : null))
      .then((json) => {
        if (json) setLlmData(json);
      })
      .catch((err) => console.error("Failed to load LLM analytics:", err));

    // 2. Agent Health
    fetch(`${API_BASE}/api/v1/analytics/agents`, { headers })
      .then((res) => (res.ok ? res.json() : []))
      .then((json) => {
        if (json) setAgentData(json);
      })
      .catch((err) => console.error("Failed to load agent health:", err));

    // 3. OpenTelemetry Traces
    fetch(`${API_BASE}/api/v1/analytics/traces`, { headers })
      .then((res) => (res.ok ? res.json() : { spans: [] }))
      .then((json) => {
        if (json?.spans) setTracesData(json.spans);
      })
      .catch((err) => console.error("Failed to load traces:", err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchAllAnalytics();
  }, [session, activeTenantId]);

  const totalFallbacks = llmData?.models.reduce((acc, m) => acc + m.fallback_count, 0) || 0;

  return (
    <div className="space-y-8 p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">Observability & Analytics</h2>
            <span className="text-xs px-2 py-0.5 rounded-full border border-border bg-muted text-muted-foreground font-mono">
              Screens 12 & 13
            </span>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time telemetry across multi-model routing, AI Employee health, and distributed OpenTelemetry traces.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/aiops"
            className="text-xs px-3 py-1.5 rounded-md border border-border bg-background hover:bg-muted text-foreground flex items-center gap-1.5 transition-colors"
          >
            <Activity className="w-3.5 h-3.5" /> AIOps Incidents <ArrowRight className="w-3 h-3" />
          </Link>
          <button
            onClick={fetchAllAnalytics}
            className="p-1.5 border border-border rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            title="Refresh Analytics"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-border gap-6">
        <button
          onClick={() => setActiveTab("llm")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "llm"
              ? "border-foreground text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          LLM Gateway (Screen 12)
        </button>
        <button
          onClick={() => setActiveTab("agents")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "agents"
              ? "border-foreground text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Agent Health (Screen 13)
        </button>
        <button
          onClick={() => setActiveTab("traces")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "traces"
              ? "border-foreground text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          OpenTelemetry Traces
        </button>
      </div>

      {/* TAB 1: LLM GATEWAY */}
      {activeTab === "llm" && (
        <div className="space-y-6">
          {/* Top Metric Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-5 rounded-lg border border-border bg-card flex flex-col justify-between space-y-3">
              <div className="flex items-center justify-between text-muted-foreground text-xs uppercase tracking-wider">
                <span>Total Requests</span>
                <Activity size={16} strokeWidth={1.5} />
              </div>
              <div>
                <div className="text-2xl font-semibold text-foreground tracking-tight">
                  {llmData?.total_requests ?? 0}
                </div>
                <div className="text-xs text-muted-foreground mt-1">Across Gemini, Groq, and Ollama</div>
              </div>
            </div>

            <div className="p-5 rounded-lg border border-border bg-card flex flex-col justify-between space-y-3">
              <div className="flex items-center justify-between text-muted-foreground text-xs uppercase tracking-wider">
                <span>Tokens Consumed</span>
                <Cpu size={16} strokeWidth={1.5} />
              </div>
              <div>
                <div className="text-2xl font-semibold text-foreground tracking-tight">
                  {(llmData?.total_tokens ?? 0).toLocaleString()}
                </div>
                <div className="text-xs text-muted-foreground mt-1">Prompt and completion tokens</div>
              </div>
            </div>

            <div className="p-5 rounded-lg border border-border bg-card flex flex-col justify-between space-y-3">
              <div className="flex items-center justify-between text-muted-foreground text-xs uppercase tracking-wider">
                <span>Accrued Cost</span>
                <DollarSign size={16} strokeWidth={1.5} />
              </div>
              <div>
                <div className="text-2xl font-semibold text-foreground tracking-tight">
                  ${(llmData?.total_cost_usd ?? 0).toFixed(4)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">Free tiers & local inference tracked</div>
              </div>
            </div>

            <div className="p-5 rounded-lg border border-border bg-card flex flex-col justify-between space-y-3">
              <div className="flex items-center justify-between text-muted-foreground text-xs uppercase tracking-wider">
                <span>Fallback Invocations</span>
                <GitFork size={16} strokeWidth={1.5} />
              </div>
              <div>
                <div className="text-2xl font-semibold text-foreground tracking-tight">
                  {totalFallbacks}
                </div>
                <div className="text-xs text-muted-foreground mt-1">Circuit breaker route shifts</div>
              </div>
            </div>
          </div>

          {/* Model Breakdown Table */}
          <div className="border border-border rounded-lg bg-card overflow-hidden">
            <div className="p-4 border-b border-border bg-muted/20">
              <h3 className="text-sm font-semibold text-foreground">Models & Providers Breakdown</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="p-3 font-medium">Model</th>
                    <th className="p-3 font-medium">Provider</th>
                    <th className="p-3 font-medium">Requests</th>
                    <th className="p-3 font-medium">Avg Latency</th>
                    <th className="p-3 font-medium">Total Tokens</th>
                    <th className="p-3 font-medium">Cost (USD)</th>
                    <th className="p-3 font-medium">Fallbacks</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {llmData?.models && llmData.models.length > 0 ? (
                    llmData.models.map((m, idx) => (
                      <tr key={idx} className="hover:bg-muted/30 transition-colors">
                        <td className="p-3 font-mono font-medium text-foreground">{m.model}</td>
                        <td className="p-3 uppercase text-muted-foreground font-mono">{m.provider}</td>
                        <td className="p-3 text-foreground">{m.total_requests}</td>
                        <td className="p-3 text-foreground">{m.avg_latency_ms} ms</td>
                        <td className="p-3 text-foreground">{m.total_tokens.toLocaleString()}</td>
                        <td className="p-3 font-mono text-foreground">${m.total_cost_usd.toFixed(4)}</td>
                        <td className="p-3">
                          <span
                            className={`px-2 py-0.5 rounded-full font-mono text-[11px] ${
                              m.fallback_count > 0
                                ? "bg-muted text-foreground border border-border"
                                : "text-muted-foreground"
                            }`}
                          >
                            {m.fallback_count}
                          </span>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={7} className="p-6 text-center text-muted-foreground italic">
                        No LLM telemetry records found yet. Dispatched workflow executions will appear here.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: AGENT HEALTH (Screen 13) */}
      {activeTab === "agents" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {agentData.map((agent, idx) => (
              <div key={idx} className="border border-border rounded-lg p-5 bg-card space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-base font-semibold text-foreground">{agent.agent}</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">{agent.role}</p>
                  </div>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                      agent.status === "healthy"
                        ? "bg-background text-foreground border-border"
                        : agent.status === "degraded"
                        ? "bg-muted text-foreground border-border"
                        : "bg-muted text-foreground border-foreground font-bold"
                    }`}
                  >
                    {agent.status.toUpperCase()}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 border-t border-border pt-4 text-center">
                  <div>
                    <div className="text-lg font-semibold text-foreground">{agent.total_tasks}</div>
                    <div className="text-[11px] text-muted-foreground">Total Tasks</div>
                  </div>
                  <div>
                    <div className="text-lg font-semibold text-foreground">{agent.success_rate}%</div>
                    <div className="text-[11px] text-muted-foreground">Success Rate</div>
                  </div>
                  <div>
                    <div className="text-lg font-semibold text-foreground">{agent.failed_tasks}</div>
                    <div className="text-[11px] text-muted-foreground">Failures</div>
                  </div>
                </div>

                <div className="border-t border-border pt-3 flex items-center justify-between text-xs text-muted-foreground">
                  <span>Avg Execution Latency</span>
                  <span className="font-mono text-foreground">{agent.avg_latency_ms} ms</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 3: OPENTELEMETRY TRACES */}
      {activeTab === "traces" && (
        <div className="border border-border rounded-lg bg-card overflow-hidden space-y-4">
          <div className="p-4 border-b border-border bg-muted/20 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-foreground">OpenTelemetry Distributed Spans</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                In-memory trace span buffer across API, orchestrator, agent, and tool execution boundaries.
              </p>
            </div>
            <span className="text-xs font-mono text-muted-foreground">Service: agentforce-ai</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="p-3 font-medium">Span Name</th>
                  <th className="p-3 font-medium">Layer</th>
                  <th className="p-3 font-medium">Trace ID</th>
                  <th className="p-3 font-medium">Duration</th>
                  <th className="p-3 font-medium">Status</th>
                  <th className="p-3 font-medium">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {tracesData.length > 0 ? (
                  tracesData.map((s, idx) => (
                    <tr key={idx} className="hover:bg-muted/30 transition-colors">
                      <td className="p-3 font-mono font-medium text-foreground">{s.name}</td>
                      <td className="p-3 uppercase font-mono text-[11px] text-muted-foreground">
                        {s.span_type}
                      </td>
                      <td className="p-3 font-mono text-[11px] text-muted-foreground">
                        {s.trace_id.slice(0, 12)}...
                      </td>
                      <td className="p-3 font-mono text-foreground">{s.duration_ms} ms</td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 rounded-full font-mono text-[10px] border ${
                            s.status === "ok"
                              ? "bg-background text-foreground border-border"
                              : "bg-muted text-foreground border-foreground font-bold"
                          }`}
                        >
                          {s.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="p-3 text-muted-foreground text-[11px]">
                        {s.start_time ? new Date(s.start_time).toLocaleTimeString() : "-"}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="p-6 text-center text-muted-foreground italic">
                      No distributed trace spans recorded in the current session.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
