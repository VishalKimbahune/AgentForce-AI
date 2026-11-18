"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import {
  Activity,
  AlertTriangle,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Clock,
  ArrowRight,
  RefreshCw,
  Zap,
  Check,
  RotateCw,
} from "lucide-react";

interface Incident {
  id: string;
  tenant_id: string;
  severity: "critical" | "high" | "medium" | "low";
  summary: string;
  root_cause_hypothesis?: string;
  recommendation?: string;
  status: "open" | "remediating" | "resolved";
  created_at: string;
  resolved_at?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AIOpsPage() {
  const { session, activeTenantId, memberships } = useAuth();
  const activeMembership = memberships.find((m) => m.tenant_id === activeTenantId) || memberships[0];
  const userRole = activeMembership?.role || "owner";

  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchIncidents = () => {
    if (!session?.access_token || !activeTenantId) return;
    setLoading(true);
    setErrorMsg(null);

    fetch(`${API_BASE}/api/v1/aiops/incidents`, {
      headers: {
        Authorization: `Bearer ${session.access_token}`,
        "X-Tenant-ID": activeTenantId,
      },
    })
      .then((res) => (res.ok ? res.json() : []))
      .then((data: Incident[]) => {
        setIncidents(data);
        if (data.length > 0 && !selectedIncident) {
          setSelectedIncident(data[0]);
        }
      })
      .catch((err) => {
        console.error("Failed to load incidents:", err);
        setErrorMsg("Failed to connect to AIOps service.");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchIncidents();
  }, [session, activeTenantId]);

  const handleScan = async () => {
    if (!session?.access_token || !activeTenantId) return;
    setScanning(true);
    setActionMessage(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/aiops/scan`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
      });
      if (res.ok) {
        const newIncidents = await res.json();
        setActionMessage(
          newIncidents.length > 0
            ? `Scan complete: detected ${newIncidents.length} new incident(s).`
            : "Scan complete: all employee agents operating within healthy parameters."
        );
        fetchIncidents();
      }
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to trigger scan.");
    } finally {
      setScanning(false);
    }
  };

  const handleSimulateFailure = async () => {
    if (!session?.access_token || !activeTenantId) return;
    setSimulating(true);
    setActionMessage(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/aiops/simulate-failure`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          agent_name: "recruitment",
          error_reason: "ATS integration endpoint http://localhost:8101 timed out after 30 seconds",
        }),
      });
      if (res.ok) {
        const inc = await res.json();
        setActionMessage("Forced failure triggered: AIOps diagnosed anomaly and created incident.");
        setSelectedIncident(inc);
        fetchIncidents();
      }
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to simulate failure.");
    } finally {
      setSimulating(false);
    }
  };

  const handleRemediate = async (incidentId: string) => {
    if (!session?.access_token || !activeTenantId) return;
    setActionMessage(null);
    setErrorMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/aiops/incidents/${incidentId}/remediate`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setActionMessage(
          "Remediation request submitted to Approval Center! Review and approve in Approvals tab to apply fix."
        );
        fetchIncidents();
      } else {
        const err = await res.json();
        setErrorMsg(err?.detail || "Failed to request remediation.");
      }
    } catch (e: any) {
      setErrorMsg(e.message || "Remediation request failed.");
    }
  };

  const handleResolve = async (incidentId: string) => {
    if (!session?.access_token || !activeTenantId) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/aiops/incidents/${incidentId}/resolve`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
      });
      if (res.ok) {
        setActionMessage("Incident resolved successfully.");
        fetchIncidents();
      }
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to resolve incident.");
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">AIOps Incident Center</h1>
            <span className="text-xs px-2 py-0.5 rounded-full border border-border bg-muted text-muted-foreground font-mono">
              Screen 14
            </span>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Autonomous site reliability: anomaly detection, root-cause hypothesis generation, and governed human-in-the-loop remediation.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleScan}
            disabled={scanning}
            className="text-xs px-3 py-2 rounded-md border border-border bg-background hover:bg-muted text-foreground flex items-center gap-1.5 transition-colors disabled:opacity-50"
          >
            <RotateCw className={`w-3.5 h-3.5 ${scanning ? "animate-spin" : ""}`} />
            Run Anomaly Scan
          </button>
          <button
            onClick={handleSimulateFailure}
            disabled={simulating}
            className="text-xs px-3 py-2 rounded-md bg-foreground text-background font-medium hover:opacity-90 flex items-center gap-1.5 transition-opacity disabled:opacity-50"
          >
            <Zap className="w-3.5 h-3.5" />
            Simulate Failure & Scan (Demo)
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="p-4 rounded-md border border-border bg-muted/40 text-xs text-foreground flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-foreground" />
            <span>{actionMessage}</span>
          </div>
          <Link href="/approvals" className="font-semibold underline flex items-center gap-1">
            Open Approvals <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      )}

      {errorMsg && (
        <div className="p-4 rounded-md border border-border bg-muted/30 text-xs text-foreground flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-foreground shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Main Grid: Incidents List & Diagnostic Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Incidents List */}
        <div className="border border-border rounded-lg bg-card overflow-hidden">
          <div className="p-4 border-b border-border bg-muted/20 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">Detected Incidents</h2>
            <span className="text-xs font-mono text-muted-foreground">{incidents.length} total</span>
          </div>

          <div className="divide-y divide-border max-h-[600px] overflow-y-auto">
            {incidents.length > 0 ? (
              incidents.map((inc) => (
                <div
                  key={inc.id}
                  onClick={() => setSelectedIncident(inc)}
                  className={`p-4 cursor-pointer transition-colors text-xs space-y-2 ${
                    selectedIncident?.id === inc.id ? "bg-muted/50" : "hover:bg-muted/20"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase font-semibold border ${
                        inc.severity === "critical"
                          ? "bg-foreground text-background border-foreground"
                          : inc.severity === "high"
                          ? "bg-muted text-foreground border-border"
                          : "text-muted-foreground border-border"
                      }`}
                    >
                      {inc.severity}
                    </span>
                    <span className="text-[11px] font-mono text-muted-foreground uppercase">
                      {inc.status}
                    </span>
                  </div>

                  <p className="font-medium text-foreground text-sm line-clamp-2">{inc.summary}</p>
                  <p className="text-muted-foreground text-[11px]">
                    {inc.created_at ? new Date(inc.created_at).toLocaleString() : ""}
                  </p>
                </div>
              ))
            ) : (
              <div className="p-8 text-center text-xs text-muted-foreground italic">
                No active incidents found. Click "Simulate Failure & Scan" to test Journey D.
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Diagnostic & Remediation Card */}
        <div className="lg:col-span-2 space-y-6">
          {selectedIncident ? (
            <div className="border border-border rounded-lg p-6 bg-card space-y-6">
              <div className="flex items-start justify-between border-b border-border pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase font-semibold border ${
                        selectedIncident.severity === "critical"
                          ? "bg-foreground text-background border-foreground"
                          : "bg-muted text-foreground border-border"
                      }`}
                    >
                      {selectedIncident.severity}
                    </span>
                    <span className="text-xs font-mono text-muted-foreground">
                      ID: {selectedIncident.id.slice(0, 8)}
                    </span>
                  </div>
                  <h3 className="text-lg font-semibold text-foreground mt-2">
                    {selectedIncident.summary}
                  </h3>
                </div>

                <span className="px-3 py-1 rounded-full text-xs font-mono uppercase border border-border bg-muted text-foreground">
                  Status: {selectedIncident.status}
                </span>
              </div>

              {/* Root-Cause Hypothesis Box */}
              <div className="space-y-2">
                <span className="text-xs uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5" /> Root-Cause Hypothesis (AIOps Diagnosis)
                </span>
                <div className="p-4 rounded-md border border-border bg-muted/20 text-xs font-mono leading-relaxed text-foreground">
                  {selectedIncident.root_cause_hypothesis || "Analyzing system telemetry and stack traces..."}
                </div>
              </div>

              {/* Recommended Fix Box */}
              <div className="space-y-2">
                <span className="text-xs uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1.5">
                  <ShieldAlert className="w-3.5 h-3.5" /> Recommended Remediation
                </span>
                <div className="p-4 rounded-md border border-border bg-muted/20 text-xs font-mono leading-relaxed text-foreground">
                  {selectedIncident.recommendation || "No action required."}
                </div>
              </div>

              {/* Governance & Actions */}
              <div className="border-t border-border pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <p className="text-xs text-muted-foreground max-w-sm">
                  Policy rule: Automated remediation requires manager approval before executing infrastructure changes.
                </p>

                <div className="flex items-center gap-3">
                  {selectedIncident.status === "open" && (
                    <button
                      onClick={() => handleRemediate(selectedIncident.id)}
                      className="text-xs px-4 py-2 rounded-md bg-foreground text-background font-medium hover:opacity-90 flex items-center gap-1.5 transition-opacity"
                    >
                      Remediate (Request Approval) <ArrowRight className="w-3 h-3" />
                    </button>
                  )}

                  {selectedIncident.status === "remediating" && (
                    <Link
                      href="/approvals"
                      className="text-xs px-4 py-2 rounded-md border border-border bg-muted hover:bg-muted/80 text-foreground flex items-center gap-1.5"
                    >
                      Pending in Approvals <ArrowRight className="w-3 h-3" />
                    </Link>
                  )}

                  {selectedIncident.status !== "resolved" && (
                    <button
                      onClick={() => handleResolve(selectedIncident.id)}
                      className="text-xs px-3 py-2 rounded-md border border-border hover:bg-muted text-foreground flex items-center gap-1 transition-colors"
                    >
                      <Check className="w-3.5 h-3.5" /> Mark Resolved
                    </button>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="border border-border rounded-lg p-12 bg-card text-center text-xs text-muted-foreground italic">
              Select an incident from the list to view the AIOps root-cause hypothesis and remediation plan.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

