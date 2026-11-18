"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Clock,
  UserCheck,
  Calendar,
  DollarSign,
  AlertTriangle,
  RefreshCw,
  Send,
  UserPlus,
  ArrowRight,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

interface ApprovalItem {
  id: string;
  tenant_id: string;
  workflow_id: string;
  task_id?: string;
  requested_by_agent: string;
  action_type: string;
  action_payload: any;
  risk_level: "low" | "medium" | "high" | "critical";
  reason: string;
  status: "pending" | "approved" | "rejected" | "expired" | "cancelled";
  required_role: string;
  level: number;
  expires_at?: string;
  decided_by?: string;
  decided_at?: string;
  decision_note?: string;
  created_at: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ApprovalsPage() {
  const { session, activeTenantId, memberships } = useAuth();
  const activeMembership = memberships.find((m) => m.tenant_id === activeTenantId) || memberships[0];
  const userRole = activeMembership?.role || "owner";

  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("pending");
  const [activeActionId, setActiveActionId] = useState<string | null>(null);
  const [actionType, setActionType] = useState<"approve" | "reject" | "delegate" | null>(null);
  const [decisionNote, setDecisionNote] = useState("");
  const [delegateToUser, setDelegateToUser] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [expandedPayload, setExpandedPayload] = useState<string | null>(null);

  const fetchApprovals = async () => {
    if (!session?.access_token || !activeTenantId) return;
    setLoading(true);
    try {
      const url =
        statusFilter === "all"
          ? `${API_BASE}/api/v1/approvals`
          : `${API_BASE}/api/v1/approvals?status=${statusFilter}`;
      const res = await fetch(url, {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setApprovals(data);
      }
    } catch (err) {
      console.error("Failed to load approvals:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
  }, [session, activeTenantId, statusFilter]);

  const handleDecision = async (approvalId: string, decision: "approve" | "reject") => {
    if (!session?.access_token || !activeTenantId) return;
    setSubmitting(true);
    setErrorMsg(null);

    try {
      const endpoint = `${API_BASE}/api/v1/approvals/${approvalId}/${decision}`;
      const res = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
        body: JSON.stringify({ note: decisionNote }),
      });

      if (res.ok) {
        setActiveActionId(null);
        setActionType(null);
        setDecisionNote("");
        await fetchApprovals();
      } else {
        const err = await res.json();
        setErrorMsg(err?.detail || `Failed to ${decision} request`);
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to connect to approval service");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelegate = async (approvalId: string) => {
    if (!session?.access_token || !activeTenantId || !delegateToUser.trim()) return;
    setSubmitting(true);
    setErrorMsg(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/approvals/${approvalId}/delegate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
        body: JSON.stringify({ to_user_id: delegateToUser.trim() }),
      });

      if (res.ok) {
        setActiveActionId(null);
        setActionType(null);
        setDelegateToUser("");
        await fetchApprovals();
      } else {
        const err = await res.json();
        setErrorMsg(err?.detail || "Failed to delegate request");
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to delegate request");
    } finally {
      setSubmitting(false);
    }
  };

  const getRiskBadge = (level: string) => {
    switch (level) {
      case "critical":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium border border-border bg-foreground text-background">
            CRITICAL RISK
          </span>
        );
      case "high":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium border border-border bg-muted text-foreground">
            HIGH RISK
          </span>
        );
      case "medium":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium border border-border bg-muted text-foreground">
            MEDIUM RISK
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium border border-border text-muted-foreground">
            LOW RISK
          </span>
        );
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "approved":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[12px] font-medium bg-muted text-foreground border border-border">
            <CheckCircle2 className="w-3.5 h-3.5" /> Approved
          </span>
        );
      case "rejected":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[12px] font-medium bg-muted text-foreground border border-border">
            <XCircle className="w-3.5 h-3.5" /> Rejected
          </span>
        );
      case "expired":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[12px] font-medium bg-muted text-foreground border border-border">
            <Clock className="w-3.5 h-3.5" /> Expired
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[12px] font-medium bg-muted text-foreground border border-border">
            <span className="w-2 h-2 rounded-full bg-foreground animate-ping" /> Pending Review
          </span>
        );
    }
  };

  return (
    <div className="space-y-8 max-w-6xl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-medium text-foreground tracking-tight">Approval Center</h1>
          <p className="text-[14px] text-muted-foreground mt-1">
            Human-in-the-loop review for sensitive workforce actions flagged by the policy engine.
          </p>
        </div>
        <button
          onClick={fetchApprovals}
          className="h-9 px-3 border border-border rounded-md text-[13px] font-medium hover:bg-muted transition-colors inline-flex items-center gap-2 self-start md:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2">
          {["pending", "approved", "rejected", "all"].map((filter) => (
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
          {approvals.length} {approvals.length === 1 ? "request" : "requests"}
        </span>
      </div>

      {/* Approvals List */}
      <div className="space-y-4">
        {loading && approvals.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground text-[14px] border border-border rounded-lg bg-card">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />
            Loading approval requests...
          </div>
        ) : approvals.length === 0 ? (
          <div className="p-12 text-center space-y-3 border border-border rounded-lg bg-card">
            <CheckCircle2 className="w-8 h-8 text-muted-foreground mx-auto stroke-[1.5]" />
            <p className="text-[14px] text-foreground font-medium">No {statusFilter} approvals</p>
            <p className="text-[13px] text-muted-foreground max-w-sm mx-auto">
              All workforce tasks within your organization policy threshold are running smoothly.
            </p>
          </div>
        ) : (
          approvals.map((req) => {
            const isActing = activeActionId === req.id;
            const isExpanded = expandedPayload === req.id;

            return (
              <div
                key={req.id}
                className="p-6 border border-border rounded-lg bg-card space-y-4 transition-all"
              >
                {/* Header Row */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-3">
                  <div className="flex items-center gap-2.5">
                    <ShieldAlert className="w-4 h-4 text-foreground flex-shrink-0" />
                    <span className="text-[14px] font-medium font-mono text-foreground uppercase">
                      {req.action_type}
                    </span>
                    {getRiskBadge(req.risk_level)}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-[11px] font-mono text-muted-foreground">
                      Required Role: {req.required_role}
                    </span>
                    {getStatusBadge(req.status)}
                  </div>
                </div>

                {/* Reason and Details */}
                <div className="space-y-1.5">
                  <p className="text-[14px] text-foreground font-medium">{req.reason}</p>
                  <div className="flex flex-wrap items-center gap-4 text-[12px] font-mono text-muted-foreground">
                    <span>Requested by: {req.requested_by_agent} employee</span>
                    <span>Created: {new Date(req.created_at).toLocaleTimeString()}</span>
                    {req.expires_at && <span>Expires: {new Date(req.expires_at).toLocaleTimeString()}</span>}
                    <Link
                      href={`/workflows/${req.workflow_id}`}
                      className="hover:underline text-foreground inline-flex items-center gap-1"
                    >
                      View workflow <ArrowRight className="w-3 h-3" />
                    </Link>
                  </div>
                </div>

                {/* Structured Payload Preview (Candidates / Payment) */}
                {req.action_payload?.candidates && (
                  <div className="p-3.5 rounded-md border border-border bg-background space-y-2">
                    <span className="text-[12px] font-mono text-muted-foreground uppercase tracking-wider">
                      Proposed Interview Candidates:
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {req.action_payload.candidates.map((c: any, idx: number) => (
                        <div
                          key={idx}
                          className="p-2.5 rounded bg-muted/30 border border-border text-[12px] space-y-0.5"
                        >
                          <div className="font-medium text-foreground flex items-center justify-between">
                            <span>{c.name}</span>
                            <span className="font-mono text-[11px]">{c.score}% match</span>
                          </div>
                          <div className="text-[11px] font-mono text-muted-foreground">
                            {c.email || "No email"} · Slot: {c.slot || "2026-11-05 14:00 UTC"}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Expandable JSON Inspector */}
                <div>
                  <button
                    onClick={() => setExpandedPayload(isExpanded ? null : req.id)}
                    className="text-[12px] text-muted-foreground hover:text-foreground inline-flex items-center gap-1 font-mono"
                  >
                    {isExpanded ? (
                      <>
                        <ChevronDown className="w-3 h-3" /> Hide action payload
                      </>
                    ) : (
                      <>
                        <ChevronRight className="w-3 h-3" /> Inspect structured action payload JSON
                      </>
                    )}
                  </button>

                  {isExpanded && (
                    <pre className="mt-2 p-3 rounded bg-muted/60 border border-border text-[11px] font-mono text-foreground overflow-x-auto max-h-48">
                      {JSON.stringify(req.action_payload, null, 2)}
                    </pre>
                  )}
                </div>

                {/* Decision / Resolution Note if decided */}
                {req.status !== "pending" && (
                  <div className="p-3 rounded bg-muted/40 border border-border text-[12px] font-mono space-y-1">
                    <div className="flex items-center justify-between text-muted-foreground">
                      <span>Decided by: {req.decided_by || "Reviewer"}</span>
                      <span>Decided at: {req.decided_at ? new Date(req.decided_at).toLocaleString() : "—"}</span>
                    </div>
                    {req.decision_note && (
                      <p className="text-foreground font-sans">{req.decision_note}</p>
                    )}
                  </div>
                )}

                {/* Interactive Action Forms (Approve / Reject / Delegate) */}
                {req.status === "pending" && (
                  <div className="border-t border-border pt-4 space-y-3">
                    {errorMsg && activeActionId === req.id && (
                      <div className="text-[13px] text-foreground bg-muted p-2.5 rounded border border-border flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4" />
                        <span>{errorMsg}</span>
                      </div>
                    )}

                    {isActing ? (
                      <div className="p-4 rounded-md border border-border bg-background space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-[13px] font-medium text-foreground capitalize">
                            {actionType} Action Request
                          </span>
                          <button
                            onClick={() => {
                              setActiveActionId(null);
                              setActionType(null);
                            }}
                            className="text-[12px] text-muted-foreground hover:text-foreground"
                          >
                            Cancel
                          </button>
                        </div>

                        {actionType === "delegate" ? (
                          <div className="space-y-1.5">
                            <label className="text-[12px] text-muted-foreground font-mono">
                              Delegate to User ID:
                            </label>
                            <input
                              type="text"
                              value={delegateToUser}
                              onChange={(e) => setDelegateToUser(e.target.value)}
                              placeholder="e.g. user_uuid_12345"
                              className="w-full px-3 py-1.5 rounded border border-border bg-background text-[13px] focus:outline-none focus:ring-1 focus:ring-ring"
                            />
                          </div>
                        ) : (
                          <div className="space-y-1.5">
                            <label className="text-[12px] text-muted-foreground font-mono">
                              Decision Note (optional):
                            </label>
                            <input
                              type="text"
                              value={decisionNote}
                              onChange={(e) => setDecisionNote(e.target.value)}
                              placeholder={`Rationale for ${actionType}ing this action...`}
                              className="w-full px-3 py-1.5 rounded border border-border bg-background text-[13px] focus:outline-none focus:ring-1 focus:ring-ring"
                            />
                          </div>
                        )}

                        <div className="flex justify-end gap-2 pt-1">
                          {actionType === "approve" && (
                            <button
                              onClick={() => handleDecision(req.id, "approve")}
                              disabled={submitting}
                              className="h-8 px-4 rounded bg-primary text-primary-foreground text-[13px] font-medium hover:opacity-90 disabled:opacity-50"
                            >
                              {submitting ? "Approving..." : "Confirm & Resume Workflow"}
                            </button>
                          )}
                          {actionType === "reject" && (
                            <button
                              onClick={() => handleDecision(req.id, "reject")}
                              disabled={submitting}
                              className="h-8 px-4 rounded bg-primary text-primary-foreground text-[13px] font-medium hover:opacity-90 disabled:opacity-50"
                            >
                              {submitting ? "Rejecting..." : "Confirm Rejection"}
                            </button>
                          )}
                          {actionType === "delegate" && (
                            <button
                              onClick={() => handleDelegate(req.id)}
                              disabled={submitting || !delegateToUser.trim()}
                              className="h-8 px-4 rounded bg-primary text-primary-foreground text-[13px] font-medium hover:opacity-90 disabled:opacity-50"
                            >
                              {submitting ? "Delegating..." : "Confirm Delegation"}
                            </button>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="text-[12px] text-muted-foreground">
                          Action requires <span className="font-bold text-foreground">{req.required_role}</span> role or higher.
                        </div>

                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => {
                              setActiveActionId(req.id);
                              setActionType("delegate");
                              setErrorMsg(null);
                            }}
                            className="h-8 px-3 border border-border rounded-md text-[13px] font-medium hover:bg-muted text-foreground transition-colors inline-flex items-center gap-1.5"
                          >
                            <UserPlus className="w-3.5 h-3.5" /> Delegate
                          </button>
                          <button
                            onClick={() => {
                              setActiveActionId(req.id);
                              setActionType("reject");
                              setErrorMsg(null);
                            }}
                            className="h-8 px-3 border border-border rounded-md text-[13px] font-medium hover:bg-muted text-foreground transition-colors inline-flex items-center gap-1.5"
                          >
                            <XCircle className="w-3.5 h-3.5" /> Reject
                          </button>
                          <button
                            onClick={() => {
                              setActiveActionId(req.id);
                              setActionType("approve");
                              setErrorMsg(null);
                            }}
                            className="h-8 px-4 rounded-md bg-primary text-primary-foreground text-[13px] font-medium hover:opacity-90 transition-opacity inline-flex items-center gap-1.5"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" /> Approve
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
