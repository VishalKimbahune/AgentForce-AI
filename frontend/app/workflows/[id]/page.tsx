"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  AlertCircle,
  XCircle,
  RefreshCw,
  StopCircle,
  UserCheck,
  Cpu,
  Layers,
  Sparkles,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  FileText,
  MessageSquare,
  CreditCard,
  FileSpreadsheet,
  Download,
} from "lucide-react";

interface WorkflowEvent {
  type: string;
  workflow_id: string;
  task_id?: string;
  agent: string;
  message: string;
  timestamp: string;
  correlation_id: string;
  data?: any;
}

interface AgentTraceMessage {
  id: string;
  workflow_id: string;
  tenant_id: string;
  source_agent: string;
  destination_agent: string;
  payload: any;
  correlation_id: string;
  created_at: string;
}

interface CandidateRanking {
  candidate_name: string;
  email?: string;
  score: number;
  matched_skills: string[];
  missing_skills: string[];
  experience_years?: number;
  summary: string;
  rationale: string;
}

interface FinanceDeliverable {
  summary: string;
  clean_invoices: Array<{
    invoice_number: string;
    vendor: string;
    po_number?: string;
    amount: number;
    due_date: string;
    description: string;
    department?: string;
  }>;
  flagged_invoices: Array<{
    invoice_number: string;
    vendor: string;
    po_number?: string;
    amount: number;
    flags: string[];
    po_expected_amount?: number;
    department?: string;
  }>;
  payment_batch: {
    batch_id: string;
    total_amount: number;
    invoice_count: number;
    status: string;
  };
  audit_stats: {
    total_invoices: number;
    clean_count: number;
    flagged_count: number;
    clean_amount: number;
    flagged_amount: number;
    duplicates?: number;
    anomalies?: number;
  };
}

interface OperationsDeliverable {
  period: string;
  filename: string;
  file_path: string;
  summary: string;
  metrics: {
    gross_revenue: number;
    total_expenses: number;
    net_income: number;
    operating_margin_pct: number;
    workforce_hours_saved: number;
    automated_tasks_count: number;
    sla_uptime_pct: number;
    department_breakdown?: Record<string, { budget: number; spent: number; [k: string]: any }>;
  };
}

interface WorkflowDetail {
  id: string;
  tenant_id: string;
  input_text: string;
  status: "pending" | "running" | "waiting_approval" | "completed" | "failed" | "cancelled";
  plan?: {
    title?: string;
    tasks?: Array<{ id: string; name: string; agent: string; depends_on: string[] }>;
  };
  cost_usd: number;
  tokens_used: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  tasks?: Array<{
    id: string;
    name: string;
    status: string;
    output?: any;
  }>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function WorkflowDetailPage() {
  const params = useParams();
  const id = params?.id as string;
  const { session, activeTenantId } = useAuth();

  const [workflow, setWorkflow] = useState<WorkflowDetail | null>(null);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [traces, setTraces] = useState<AgentTraceMessage[]>([]);
  const [rankings, setRankings] = useState<CandidateRanking[]>([]);
  const [financeData, setFinanceData] = useState<FinanceDeliverable | null>(null);
  const [opsData, setOpsData] = useState<OperationsDeliverable | null>(null);
  const [activeTab, setActiveTab] = useState<"timeline" | "deliverables" | "trace" | "raw">("timeline");
  const [cancelling, setCancelling] = useState(false);
  const [expandedPayload, setExpandedPayload] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);

  // 1. Fetch Workflow details and initial messages
  const loadWorkflowData = async () => {
    if (!session?.access_token || !id) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/workflows/${id}`, {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId || "",
        },
      });
      if (res.ok) {
        const data: WorkflowDetail = await res.json();
        setWorkflow(data);

        // Check task outputs for deliverables
        if (data.tasks) {
          for (const t of data.tasks) {
            if (t.output) {
              if (Array.isArray(t.output.rankings)) {
                setRankings(t.output.rankings);
              }
              if (t.output.clean_invoices) {
                setFinanceData(t.output);
              }
              if (t.output.file_path && t.output.metrics) {
                setOpsData(t.output);
              }
            }
          }
        }
      }
    } catch (err) {
      console.error("Failed to load workflow detail:", err);
    }
  };

  const loadTraceMessages = async () => {
    if (!session?.access_token || !id) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/workflows/${id}/messages`, {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId || "",
        },
      });
      if (res.ok) {
        const data = await res.json();
        setTraces(data);
      }
    } catch (err) {
      console.error("Failed to load trace messages:", err);
    }
  };

  // 2. Setup Server-Sent Events (SSE) Stream
  useEffect(() => {
    if (!id || !session?.access_token) return;

    loadWorkflowData();
    loadTraceMessages();

    // Initialize EventSource
    const sseUrl = `${API_BASE}/api/v1/workflows/${id}/events?token=${encodeURIComponent(
      session.access_token
    )}`;
    const es = new EventSource(sseUrl);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const parsed: WorkflowEvent = JSON.parse(event.data);
        setEvents((prev) => {
          if (
            prev.some(
              (p) =>
                p.timestamp === parsed.timestamp &&
                p.message === parsed.message &&
                p.agent === parsed.agent
            )
          ) {
            return prev;
          }
          return [...prev, parsed];
        });

        if (parsed.data?.rankings && Array.isArray(parsed.data.rankings)) {
          setRankings(parsed.data.rankings);
        }
        if (parsed.data?.clean_invoices) {
          setFinanceData(parsed.data);
        }
        if (parsed.data?.file_path && parsed.data?.metrics) {
          setOpsData(parsed.data);
        }

        if (
          parsed.type === "workflow.completed" ||
          parsed.type === "workflow.failed" ||
          parsed.type === "workflow.cancelled"
        ) {
          loadWorkflowData();
          loadTraceMessages();
        }
      } catch (err) {
        console.error("Error parsing SSE event:", err);
      }
    };

    es.onerror = () => {
      es.close();
      loadWorkflowData();
    };

    return () => {
      es.close();
    };
  }, [id, session?.access_token, activeTenantId]);

  const handleCancel = async () => {
    if (!session?.access_token || !id) return;
    setCancelling(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/workflows/${id}/cancel`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId || "",
        },
      });
      if (res.ok) {
        loadWorkflowData();
      }
    } catch (err) {
      console.error("Failed to cancel workflow:", err);
    } finally {
      setCancelling(false);
    }
  };

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case "completed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] font-medium bg-muted text-foreground border border-border">
            <CheckCircle2 className="w-3.5 h-3.5 text-foreground" /> Completed
          </span>
        );
      case "running":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] font-medium bg-muted text-foreground border border-border">
            <span className="w-2 h-2 rounded-full bg-foreground animate-pulse" /> Running
          </span>
        );
      case "waiting_approval":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] font-medium bg-muted text-foreground border border-border">
            <AlertCircle className="w-3.5 h-3.5 text-foreground" /> Waiting Approval
          </span>
        );
      case "cancelled":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] font-medium bg-muted text-muted-foreground border border-border">
            <StopCircle className="w-3.5 h-3.5 text-muted-foreground" /> Cancelled
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] font-medium bg-muted text-muted-foreground border border-border">
            <XCircle className="w-3.5 h-3.5" /> Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] font-medium bg-muted text-muted-foreground border border-border">
            <Clock className="w-3.5 h-3.5" /> Pending
          </span>
        );
    }
  };

  // Determine intent / specialized employee
  const inputText = (workflow?.input_text || "").toLowerCase();
  const isFinance =
    financeData !== null ||
    inputText.includes("invoice") ||
    inputText.includes("po") ||
    inputText.includes("payment") ||
    inputText.includes("expense");
  const isOps =
    opsData !== null ||
    inputText.includes("report") ||
    inputText.includes("operations") ||
    inputText.includes("monthly");

  const specializedAgentName = isFinance
    ? "Finance AI Employee"
    : isOps
    ? "Operations AI Employee"
    : "HR AI Employee";
  const specializedAgentRole = isFinance
    ? "Audit vendor invoices, match ERP POs, assemble payment batch"
    : isOps
    ? "Aggregate ERP operational KPIs and compile PDF business report"
    : "Parse candidate resumes and match JD criteria";
  const specializedAgentKey = isFinance ? "finance" : isOps ? "ops" : "hr";

  const timelineSteps = [
    {
      id: "intent",
      agent: "intent_agent",
      name: "Intent Classification",
      role: "Analyze user request and categorize workflow domain",
    },
    {
      id: "planner",
      agent: "planner",
      name: "Autonomous Planner",
      role: "Decompose into structured tasks and inter-agent directives",
    },
    {
      id: "orchestrator",
      agent: "orchestrator",
      name: "Orchestration & Limits",
      role: "Enforce safety boundaries, step limit (30 max)",
    },
    {
      id: specializedAgentKey,
      agent: specializedAgentKey,
      name: specializedAgentName,
      role: specializedAgentRole,
    },
    {
      id: "verifier",
      agent: "verifier",
      name: "Quality Verification",
      role: "Audit deliverables against enterprise constraints",
    },
  ];

  const deliverablesCount =
    rankings.length > 0
      ? rankings.length
      : financeData
      ? financeData.audit_stats.total_invoices
      : opsData
      ? 1
      : 0;

  const deliverablesLabel = isFinance
    ? "Invoices & Payments"
    : isOps
    ? "Operations Report"
    : "Candidate Rankings";

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Back button and Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-4">
        <div className="space-y-1.5">
          <Link
            href="/workflows"
            className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to workflows
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-[20px] font-medium text-foreground tracking-tight">
              {workflow?.input_text || "Workflow Execution"}
            </h1>
            {getStatusBadge(workflow?.status)}
          </div>
          <p className="text-[12px] font-mono text-muted-foreground">ID: {id}</p>
        </div>

        {/* Action Controls & Telemetry */}
        <div className="flex items-center gap-3 self-start md:self-auto">
          {workflow && (workflow.status === "pending" || workflow.status === "running") && (
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="h-8 px-3 border border-border rounded-md text-[13px] font-medium hover:bg-muted text-foreground transition-colors inline-flex items-center gap-1.5"
            >
              <StopCircle className="w-3.5 h-3.5" />
              {cancelling ? "Cancelling..." : "Cancel"}
            </button>
          )}

          <div className="px-3 py-1 rounded border border-border bg-card text-[12px] font-mono text-muted-foreground">
            {workflow?.tokens_used || 0} tokens · ${(workflow?.cost_usd || 0).toFixed(4)}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-border pb-2 text-[13px]">
        <button
          onClick={() => setActiveTab("timeline")}
          className={`px-3 py-1.5 rounded-md transition-colors ${
            activeTab === "timeline"
              ? "bg-primary text-primary-foreground font-medium"
              : "text-muted-foreground hover:bg-muted"
          }`}
        >
          Live Timeline ({events.length})
        </button>
        <button
          onClick={() => setActiveTab("deliverables")}
          className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-1.5 ${
            activeTab === "deliverables"
              ? "bg-primary text-primary-foreground font-medium"
              : "text-muted-foreground hover:bg-muted"
          }`}
        >
          {isFinance ? (
            <CreditCard className="w-3.5 h-3.5" />
          ) : isOps ? (
            <FileSpreadsheet className="w-3.5 h-3.5" />
          ) : (
            <UserCheck className="w-3.5 h-3.5" />
          )}
          {deliverablesLabel} {deliverablesCount > 0 && `(${deliverablesCount})`}
        </button>
        <button
          onClick={() => setActiveTab("trace")}
          className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-1.5 ${
            activeTab === "trace"
              ? "bg-primary text-primary-foreground font-medium"
              : "text-muted-foreground hover:bg-muted"
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          Agent Message Trace ({traces.length})
        </button>
        <button
          onClick={() => setActiveTab("raw")}
          className={`px-3 py-1.5 rounded-md transition-colors ${
            activeTab === "raw"
              ? "bg-primary text-primary-foreground font-medium"
              : "text-muted-foreground hover:bg-muted"
          }`}
        >
          Raw SSE Stream
        </button>
      </div>

      {/* TAB 1: Live Timeline View */}
      {activeTab === "timeline" && (
        <div className="space-y-4">
          <div className="p-4 rounded-lg border border-border bg-card">
            <h3 className="text-[14px] font-medium text-foreground mb-3">
              LangGraph StateGraph Progression
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              {timelineSteps.map((step, idx) => {
                const stepEvents = events.filter((e) => e.agent === step.agent);
                const isStarted = stepEvents.some((e) => e.type === "task.started");
                const isCompleted =
                  stepEvents.some(
                    (e) => e.type === "task.completed" || e.type === "workflow.completed"
                  ) || workflow?.status === "completed";

                return (
                  <div
                    key={step.id}
                    className={`p-3.5 rounded-md border transition-all ${
                      isCompleted
                        ? "border-border bg-muted/30"
                        : isStarted
                        ? "border-foreground bg-muted/60"
                        : "border-border/50 opacity-60"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-[11px] font-mono text-muted-foreground">
                        0{idx + 1}
                      </span>
                      {isCompleted ? (
                        <CheckCircle2 className="w-4 h-4 text-foreground" />
                      ) : isStarted ? (
                        <span className="w-2 h-2 rounded-full bg-foreground animate-ping" />
                      ) : (
                        <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                      )}
                    </div>
                    <p className="text-[13px] font-medium text-foreground">{step.name}</p>
                    <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
                      {step.role}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Chronological Event Timeline */}
          <div className="border border-border rounded-lg bg-card overflow-hidden">
            <div className="px-4 py-3 border-b border-border bg-muted/30 flex items-center justify-between">
              <span className="text-[13px] font-medium text-foreground">
                Realtime Event Timeline
              </span>
              <span className="text-[12px] text-muted-foreground">
                {events.length} events logged
              </span>
            </div>

            <div className="divide-y divide-border">
              {events.length === 0 ? (
                <div className="p-8 text-center text-[13px] text-muted-foreground">
                  <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2" />
                  Connecting to live SSE event bus...
                </div>
              ) : (
                events.map((evt, idx) => (
                  <div key={idx} className="p-3.5 flex items-start gap-3 hover:bg-muted/10">
                    <div className="mt-0.5">
                      {evt.type === "workflow.completed" ? (
                        <ShieldCheck className="w-4 h-4 text-foreground" />
                      ) : evt.type.includes("completed") ? (
                        <CheckCircle2 className="w-4 h-4 text-foreground" />
                      ) : (
                        <Sparkles className="w-4 h-4 text-muted-foreground" />
                      )}
                    </div>

                    <div className="flex-1 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[12px] font-mono px-2 py-0.5 rounded bg-muted border border-border text-foreground">
                          {evt.agent}
                        </span>
                        <span className="text-[11px] text-muted-foreground font-mono">
                          {new Date(evt.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="text-[13px] text-foreground">{evt.message}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: Deliverables (HR Rankings, Finance Invoices, or Ops Report) */}
      {activeTab === "deliverables" && (
        <div className="space-y-6">
          {/* DELIVERABLE A: Finance Invoice Audit & Payment Batch */}
          {financeData && (
            <div className="border border-border rounded-lg bg-card p-6 space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-4">
                <div>
                  <h3 className="text-[16px] font-medium text-foreground">
                    Accounts Payable & Invoice Audit Report
                  </h3>
                  <p className="text-[13px] text-muted-foreground mt-0.5">
                    {financeData.summary}
                  </p>
                </div>
                <div className="text-[12px] font-mono px-3 py-1 rounded bg-muted border border-border">
                  Batch ID: {financeData.payment_batch.batch_id}
                </div>
              </div>

              {/* KPI metrics */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-3 rounded border border-border bg-muted/20">
                  <span className="text-[11px] text-muted-foreground">Clean Invoices</span>
                  <p className="text-[18px] font-medium font-mono text-foreground mt-0.5">
                    {financeData.audit_stats.clean_count}
                  </p>
                  <span className="text-[11px] text-muted-foreground">
                    ${financeData.audit_stats.clean_amount.toLocaleString()}
                  </span>
                </div>
                <div className="p-3 rounded border border-border bg-muted/20">
                  <span className="text-[11px] text-muted-foreground">Flagged Anomalies</span>
                  <p className="text-[18px] font-medium font-mono text-foreground mt-0.5">
                    {financeData.audit_stats.flagged_count}
                  </p>
                  <span className="text-[11px] text-muted-foreground">
                    ${financeData.audit_stats.flagged_amount.toLocaleString()}
                  </span>
                </div>
                <div className="p-3 rounded border border-border bg-muted/20">
                  <span className="text-[11px] text-muted-foreground">Payment Batch Total</span>
                  <p className="text-[18px] font-medium font-mono text-foreground mt-0.5">
                    ${financeData.payment_batch.total_amount.toLocaleString()}
                  </p>
                  <span className="text-[11px] text-muted-foreground capitalize">
                    Status: {financeData.payment_batch.status.replace("_", " ")}
                  </span>
                </div>
                <div className="p-3 rounded border border-border bg-muted/20">
                  <span className="text-[11px] text-muted-foreground">Policy Gate</span>
                  <p className="text-[15px] font-medium text-foreground mt-1">
                    Finance Manager Sign-off
                  </p>
                  <span className="text-[11px] text-muted-foreground">
                    {workflow?.status === "completed" ? "Approved & Disbursed" : "Paused for Approval"}
                  </span>
                </div>
              </div>

              {/* Clean Invoices Table */}
              <div className="space-y-2">
                <h4 className="text-[14px] font-medium text-foreground">
                  Approved Invoices (Scheduled for Payment Batch)
                </h4>
                <div className="overflow-x-auto border border-border rounded-md">
                  <table className="w-full text-left border-collapse text-[13px]">
                    <thead>
                      <tr className="border-b border-border bg-muted/40 text-muted-foreground font-medium">
                        <th className="py-2.5 px-3">Invoice #</th>
                        <th className="py-2.5 px-3">Vendor</th>
                        <th className="py-2.5 px-3">PO Number</th>
                        <th className="py-2.5 px-3">Amount</th>
                        <th className="py-2.5 px-3">Due Date</th>
                        <th className="py-2.5 px-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {financeData.clean_invoices.map((inv) => (
                        <tr key={inv.invoice_number} className="hover:bg-muted/10">
                          <td className="py-2.5 px-3 font-mono font-medium">{inv.invoice_number}</td>
                          <td className="py-2.5 px-3">{inv.vendor}</td>
                          <td className="py-2.5 px-3 font-mono text-muted-foreground">{inv.po_number || "—"}</td>
                          <td className="py-2.5 px-3 font-mono font-medium">${inv.amount.toLocaleString()}</td>
                          <td className="py-2.5 px-3 text-muted-foreground">{inv.due_date}</td>
                          <td className="py-2.5 px-3">
                            <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-muted border border-border">
                              Matched & Clean
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Flagged Invoices Table */}
              <div className="space-y-2">
                <h4 className="text-[14px] font-medium text-foreground">
                  Flagged Invoices (Anomalies & Duplicate Detection)
                </h4>
                <div className="overflow-x-auto border border-border rounded-md">
                  <table className="w-full text-left border-collapse text-[13px]">
                    <thead>
                      <tr className="border-b border-border bg-muted/40 text-muted-foreground font-medium">
                        <th className="py-2.5 px-3">Invoice #</th>
                        <th className="py-2.5 px-3">Vendor</th>
                        <th className="py-2.5 px-3">Billed vs PO</th>
                        <th className="py-2.5 px-3">Anomaly Reason</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {financeData.flagged_invoices.map((inv) => (
                        <tr key={inv.invoice_number} className="hover:bg-muted/10">
                          <td className="py-2.5 px-3 font-mono font-medium">{inv.invoice_number}</td>
                          <td className="py-2.5 px-3">{inv.vendor}</td>
                          <td className="py-2.5 px-3 font-mono">
                            ${inv.amount.toLocaleString()}
                            {inv.po_expected_amount && (
                              <span className="text-[11px] text-muted-foreground block">
                                PO: ${inv.po_expected_amount.toLocaleString()}
                              </span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 max-w-md">
                            {inv.flags.map((f, fIdx) => (
                              <div
                                key={fIdx}
                                className="text-[11px] px-2 py-0.5 rounded bg-muted text-foreground border border-border mb-1"
                              >
                                {f}
                              </div>
                            ))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* DELIVERABLE B: Operations Executive Report */}
          {opsData && (
            <div className="border border-border rounded-lg bg-card p-6 space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-4">
                <div>
                  <h3 className="text-[16px] font-medium text-foreground">
                    Executive Operations & Performance Report
                  </h3>
                  <p className="text-[13px] text-muted-foreground mt-0.5">
                    {opsData.period} · Compiled with ReportLab PDF Generator
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono px-2 py-1 rounded bg-muted border border-border">
                    {opsData.filename}
                  </span>
                </div>
              </div>

              {/* KPI Indicators */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-3 rounded border border-border bg-muted/20">
                  <span className="text-[11px] text-muted-foreground">Gross Revenue</span>
                  <p className="text-[18px] font-medium font-mono text-foreground mt-0.5">
                    ${opsData.metrics.gross_revenue.toLocaleString()}
                  </p>
                  <span className="text-[11px] text-muted-foreground">Monthly billing cycle</span>
                </div>
                <div className="p-3 rounded border border-border bg-muted/20">
                  <span className="text-[11px] text-muted-foreground">Net Operating Income</span>
                  <p className="text-[18px] font-medium font-mono text-foreground mt-0.5">
                    ${opsData.metrics.net_income.toLocaleString()}
                  </p>
                  <span className="text-[11px] text-muted-foreground">
                    {opsData.metrics.operating_margin_pct.toFixed(2)}% margin
                  </span>
                </div>
                <div className="p-3 rounded border border-border bg-muted/20">
                  <span className="text-[11px] text-muted-foreground">Hours Saved</span>
                  <p className="text-[18px] font-medium font-mono text-foreground mt-0.5">
                    {opsData.metrics.workforce_hours_saved.toLocaleString()} hrs
                  </p>
                  <span className="text-[11px] text-muted-foreground">Autonomous agents</span>
                </div>
                <div className="p-3 rounded border border-border bg-muted/20">
                  <span className="text-[11px] text-muted-foreground">SLA Availability</span>
                  <p className="text-[18px] font-medium font-mono text-foreground mt-0.5">
                    {opsData.metrics.sla_uptime_pct}%
                  </p>
                  <span className="text-[11px] text-muted-foreground">99.9% target SLA</span>
                </div>
              </div>

              {/* Executive Summary Callout */}
              <div className="p-4 rounded-md border border-border bg-muted/30 space-y-1">
                <span className="text-[12px] font-medium text-foreground uppercase tracking-wide">
                  Executive Narrative
                </span>
                <p className="text-[13px] text-foreground leading-relaxed">
                  {opsData.summary}
                </p>
              </div>

              {/* Department Breakdown */}
              {opsData.metrics.department_breakdown && (
                <div className="space-y-2">
                  <h4 className="text-[14px] font-medium text-foreground">
                    Departmental Resource & Throughput
                  </h4>
                  <div className="overflow-x-auto border border-border rounded-md">
                    <table className="w-full text-left border-collapse text-[13px]">
                      <thead>
                        <tr className="border-b border-border bg-muted/40 text-muted-foreground font-medium">
                          <th className="py-2.5 px-3">Department</th>
                          <th className="py-2.5 px-3">Budget</th>
                          <th className="py-2.5 px-3">Spend</th>
                          <th className="py-2.5 px-3">Utilization</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {Object.entries(opsData.metrics.department_breakdown).map(([dept, info]) => {
                          const util = (info.spent / info.budget) * 100;
                          return (
                            <tr key={dept} className="hover:bg-muted/10">
                              <td className="py-2.5 px-3 font-medium">{dept}</td>
                              <td className="py-2.5 px-3 font-mono">${info.budget.toLocaleString()}</td>
                              <td className="py-2.5 px-3 font-mono">${info.spent.toLocaleString()}</td>
                              <td className="py-2.5 px-3 font-mono">{util.toFixed(1)}%</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* DELIVERABLE C: HR Candidate Rankings */}
          {rankings.length > 0 && (
            <div className="border border-border rounded-lg bg-card p-6 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-4">
                <div>
                  <h3 className="text-[16px] font-medium text-foreground">
                    Candidate Screening & Match Report
                  </h3>
                  <p className="text-[13px] text-muted-foreground mt-0.5">
                    Evaluated against Python Backend Developer requirements.
                  </p>
                </div>
                <div className="text-[13px] font-medium px-3 py-1 rounded bg-muted border border-border">
                  {rankings.length} Candidates Screened
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-[13px]">
                  <thead>
                    <tr className="border-b border-border bg-muted/40 text-muted-foreground font-medium">
                      <th className="py-2.5 px-3">Rank</th>
                      <th className="py-2.5 px-3">Candidate</th>
                      <th className="py-2.5 px-3">Match Score</th>
                      <th className="py-2.5 px-3">Matched Skills</th>
                      <th className="py-2.5 px-3">Missing Skills</th>
                      <th className="py-2.5 px-3">Recommendation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {rankings.map((c, idx) => (
                      <tr key={idx} className="hover:bg-muted/10 transition-colors">
                        <td className="py-3 px-3 font-mono text-[12px] font-medium text-foreground">
                          #{idx + 1}
                        </td>
                        <td className="py-3 px-3">
                          <div className="font-medium text-foreground">{c.candidate_name}</div>
                          {c.email && (
                            <div className="text-[11px] font-mono text-muted-foreground">
                              {c.email}
                            </div>
                          )}
                        </td>
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-2">
                            <span className="font-medium font-mono text-[13px]">{c.score}%</span>
                            <div className="w-16 h-2 rounded-full bg-muted overflow-hidden border border-border">
                              <div
                                className="h-full bg-foreground"
                                style={{ width: `${c.score}%` }}
                              />
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-3">
                          <div className="flex flex-wrap gap-1 max-w-xs">
                            {c.matched_skills.map((s) => (
                              <span
                                key={s}
                                className="px-1.5 py-0.5 text-[11px] rounded bg-muted text-foreground border border-border font-mono capitalize"
                              >
                                {s}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="py-3 px-3">
                          <div className="flex flex-wrap gap-1 max-w-xs">
                            {c.missing_skills.length > 0 ? (
                              c.missing_skills.map((s) => (
                                <span
                                  key={s}
                                  className="px-1.5 py-0.5 text-[11px] rounded border border-border/80 text-muted-foreground font-mono capitalize"
                                >
                                  {s}
                                </span>
                              ))
                            ) : (
                              <span className="text-[12px] text-muted-foreground">—</span>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-3 max-w-sm">
                          <p className="text-[12px] text-foreground font-medium">{c.summary}</p>
                          <p className="text-[11px] text-muted-foreground mt-0.5">{c.rationale}</p>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {!financeData && !opsData && rankings.length === 0 && (
            <div className="p-8 text-center text-muted-foreground text-[13px] border border-border rounded-lg bg-card">
              No deliverables produced yet. Deliverables will appear once the specialized agent finishes processing.
            </div>
          )}
        </div>
      )}

      {/* TAB 3: Inter-Agent Message Trace */}
      {activeTab === "trace" && (
        <div className="border border-border rounded-lg bg-card p-6 space-y-4">
          <div className="border-b border-border pb-3">
            <h3 className="text-[16px] font-medium text-foreground">
              Inter-Agent Message Traces
            </h3>
            <p className="text-[13px] text-muted-foreground mt-0.5">
              Payloads dispatched between Planner, Orchestrator, and specialized AI Employees.
            </p>
          </div>

          {traces.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground text-[13px]">
              No inter-agent messages recorded for this workflow yet.
            </div>
          ) : (
            <div className="space-y-3">
              {traces.map((m) => {
                const isExpanded = expandedPayload === m.id;
                return (
                  <div
                    key={m.id}
                    className="p-4 rounded-md border border-border bg-background space-y-3"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-[13px] font-medium">
                        <span className="font-mono px-2 py-0.5 rounded bg-muted border border-border">
                          {m.source_agent}
                        </span>
                        <span className="text-muted-foreground">→</span>
                        <span className="font-mono px-2 py-0.5 rounded bg-muted border border-border">
                          {m.destination_agent}
                        </span>
                      </div>
                      <span className="text-[11px] font-mono text-muted-foreground">
                        {new Date(m.created_at).toLocaleTimeString()} · CID: {m.correlation_id}
                      </span>
                    </div>

                    <p className="text-[13px] text-foreground">
                      {m.payload?.task_description || "Coordinated subtask execution"}
                    </p>

                    <button
                      onClick={() => setExpandedPayload(isExpanded ? null : m.id)}
                      className="text-[12px] text-muted-foreground hover:text-foreground inline-flex items-center gap-1 font-mono"
                    >
                      {isExpanded ? (
                        <>
                          <ChevronDown className="w-3 h-3" /> Hide structured payload
                        </>
                      ) : (
                        <>
                          <ChevronRight className="w-3 h-3" /> Inspect structured payload JSON
                        </>
                      )}
                    </button>

                    {isExpanded && (
                      <pre className="p-3 rounded bg-muted/60 border border-border text-[11px] font-mono text-foreground overflow-x-auto max-h-64">
                        {JSON.stringify(m.payload, null, 2)}
                      </pre>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB 4: Raw SSE Stream Output */}
      {activeTab === "raw" && (
        <div className="border border-border rounded-lg bg-card p-6 space-y-3">
          <h3 className="text-[16px] font-medium text-foreground">
            Server-Sent Events (SSE) Audit Log
          </h3>
          <div className="bg-muted/40 p-4 rounded-md border border-border font-mono text-[11px] space-y-2 max-h-96 overflow-y-auto">
            {events.map((e, idx) => (
              <div key={idx} className="text-foreground/90 pb-1 border-b border-border/40">
                <span className="text-muted-foreground">[{e.timestamp}]</span>{" "}
                <span className="font-bold text-foreground">{e.type}</span> ({e.agent}):{" "}
                {e.message}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
