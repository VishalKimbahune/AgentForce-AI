"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  Play,
  Clock,
  CheckCircle2,
  AlertCircle,
  XCircle,
  ArrowRight,
  FileText,
  Sparkles,
  RefreshCw,
  Search,
} from "lucide-react";

interface WorkflowItem {
  id: string;
  tenant_id: string;
  input_text: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  cost_usd: number;
  tokens_used: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  tasks?: any[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const QUICK_PROMPTS = [
  "Rank these resumes for the Python JD",
  "Match recent vendor invoices to open purchase orders",
  "Generate monthly business operations report",
];

export default function WorkflowsPage() {
  const router = useRouter();
  const { session, activeTenantId } = useAuth();
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchWorkflows = async () => {
    if (!session?.access_token || !activeTenantId) return;
    setLoading(true);
    try {
      const url =
        statusFilter === "all"
          ? `${API_BASE}/api/v1/workflows`
          : `${API_BASE}/api/v1/workflows?status=${statusFilter}`;
      const res = await fetch(url, {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setWorkflows(data);
      }
    } catch (err) {
      console.error("Failed to fetch workflows:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkflows();
  }, [session, activeTenantId, statusFilter]);

  const handleLaunchWorkflow = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    if (!session?.access_token || !activeTenantId) {
      setErrorMsg("Please sign in to launch workflows.");
      return;
    }

    setSubmitting(true);
    setErrorMsg(null);

    try {
      const idemKey = `wf-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      const res = await fetch(`${API_BASE}/api/v1/workflows`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
          "Idempotency-Key": idemKey,
        },
        body: JSON.stringify({
          input: prompt,
          attachments: [],
        }),
      });

      if (res.status === 202 || res.status === 200) {
        const data = await res.json();
        router.push(`/workflows/${data.workflow_id}`);
      } else {
        const err = await res.json();
        setErrorMsg(err?.error?.message || "Failed to create workflow");
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to connect to workflow service");
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[12px] font-medium bg-muted text-foreground border border-border">
            <CheckCircle2 className="w-3.5 h-3.5 text-foreground" />
            Completed
          </span>
        );
      case "running":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[12px] font-medium bg-muted text-foreground border border-border">
            <span className="w-2 h-2 rounded-full bg-foreground animate-ping" />
            Running
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[12px] font-medium bg-muted text-foreground border border-border">
            <AlertCircle className="w-3.5 h-3.5" />
            Failed
          </span>
        );
      case "cancelled":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[12px] font-medium bg-muted text-foreground border border-border">
            <XCircle className="w-3.5 h-3.5" />
            Cancelled
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[12px] font-medium bg-muted text-foreground border border-border">
            <Clock className="w-3.5 h-3.5" />
            Pending
          </span>
        );
    }
  };

  return (
    <div className="space-y-8 max-w-6xl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-medium text-foreground tracking-tight">Workflows</h1>
          <p className="text-[14px] text-muted-foreground mt-1">
            Assign, monitor, and audit autonomous multi-agent workforce tasks.
          </p>
        </div>
        <button
          onClick={fetchWorkflows}
          className="h-9 px-3 border border-border rounded-md text-[13px] font-medium hover:bg-muted transition-colors inline-flex items-center gap-2 self-start md:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Assign Work Card */}
      <div className="p-6 border border-border rounded-lg bg-card space-y-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-foreground" />
          <h2 className="text-[16px] font-medium text-foreground">Assign work to AI workforce</h2>
        </div>

        <form onSubmit={handleLaunchWorkflow} className="space-y-4">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            placeholder="Describe the task or instructions (e.g. Rank these resumes for the Python JD)..."
            className="w-full px-3.5 py-2.5 rounded-md border border-border bg-background text-[14px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring resize-none"
          />

          {errorMsg && (
            <div className="text-[13px] text-foreground bg-muted p-2.5 rounded border border-border flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              <span>{errorMsg}</span>
            </div>
          )}

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[12px] text-muted-foreground mr-1">Suggestions:</span>
              {QUICK_PROMPTS.map((qp) => (
                <button
                  key={qp}
                  type="button"
                  onClick={() => setPrompt(qp)}
                  className="px-2.5 py-1 text-[12px] rounded border border-border bg-muted/50 hover:bg-muted text-foreground transition-colors"
                >
                  {qp}
                </button>
              ))}
            </div>

            <button
              type="submit"
              disabled={submitting || !prompt.trim()}
              className="h-9 px-4 rounded-md bg-primary text-primary-foreground text-[14px] font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center justify-center gap-2"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              {submitting ? "Launching..." : "Assign work"}
            </button>
          </div>
        </form>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2">
          {["all", "running", "completed", "cancelled"].map((filter) => (
            <button
              key={filter}
              onClick={() => setStatusFilter(filter)}
              className={`px-3 py-1 text-[13px] rounded-md capitalize transition-colors ${
                statusFilter === filter
                  ? "bg-primary text-primary-foreground font-medium"
                  : "text-muted-foreground hover:bg-muted"
              }`}
            >
              {filter}
            </button>
          ))}
        </div>
        <span className="text-[13px] text-muted-foreground">
          {workflows.length} {workflows.length === 1 ? "workflow" : "workflows"}
        </span>
      </div>

      {/* Workflows List Table */}
      <div className="border border-border rounded-lg bg-card overflow-hidden">
        {loading && workflows.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground text-[14px]">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />
            Loading workflows...
          </div>
        ) : workflows.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <FileText className="w-8 h-8 text-muted-foreground mx-auto stroke-[1.5]" />
            <p className="text-[14px] text-foreground font-medium">No workflows found</p>
            <p className="text-[13px] text-muted-foreground max-w-sm mx-auto">
              Assign a work request above to watch your autonomous AI agents coordinate in real time.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-muted-foreground font-medium">
                  <th className="py-3 px-4">Task / Instruction</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Tokens & Cost</th>
                  <th className="py-3 px-4">Started</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {workflows.map((wf) => (
                  <tr key={wf.id} className="hover:bg-muted/20 transition-colors">
                    <td className="py-3.5 px-4 font-medium text-foreground max-w-md">
                      <Link
                        href={`/workflows/${wf.id}`}
                        className="hover:underline flex items-center gap-2 truncate"
                      >
                        <span className="truncate">{wf.input_text}</span>
                      </Link>
                    </td>
                    <td className="py-3.5 px-4">{getStatusBadge(wf.status)}</td>
                    <td className="py-3.5 px-4 text-muted-foreground">
                      {wf.tokens_used > 0 ? (
                        <span>
                          {wf.tokens_used.toLocaleString()} tok · ${wf.cost_usd.toFixed(4)}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-muted-foreground whitespace-nowrap">
                      {wf.started_at ? new Date(wf.started_at).toLocaleTimeString() : "—"}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <Link
                        href={`/workflows/${wf.id}`}
                        className="inline-flex items-center gap-1 text-[12px] font-medium text-foreground hover:underline"
                      >
                        Timeline
                        <ArrowRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
