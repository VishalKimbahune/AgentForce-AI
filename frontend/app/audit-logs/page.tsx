"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  FileText,
  Download,
  Filter,
  Search,
  RefreshCw,
  ShieldCheck,
  Calendar,
  User,
  Bot,
} from "lucide-react";

interface AuditLogItem {
  id: string;
  tenant_id: string;
  actor_type: string;
  actor_id: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  details_redacted?: any;
  ip?: string;
  correlation_id?: string;
  created_at: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AuditLogsPage() {
  const { session, activeTenantId } = useAuth();
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);

  // Filters
  const [actorTypeFilter, setActorTypeFilter] = useState<string>("");
  const [actionSearch, setActionSearch] = useState<string>("");

  const fetchAuditLogs = async () => {
    if (!session?.access_token || !activeTenantId) return;
    setLoading(true);

    const params = new URLSearchParams();
    if (actorTypeFilter) params.append("actor_type", actorTypeFilter);
    if (actionSearch) params.append("action", actionSearch);
    params.append("limit", "100");

    try {
      const res = await fetch(`${API_BASE}/api/v1/audit-logs?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
      });
      if (res.ok) {
        setLogs(await res.json());
      }
    } catch (e) {
      console.error("Failed to fetch audit logs:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditLogs();
  }, [session, activeTenantId, actorTypeFilter]);

  const handleExportCSV = async () => {
    if (!session?.access_token || !activeTenantId) return;
    setDownloading(true);

    const params = new URLSearchParams();
    params.append("export", "csv");
    if (actorTypeFilter) params.append("actor_type", actorTypeFilter);
    if (actionSearch) params.append("action", actionSearch);

    try {
      const res = await fetch(`${API_BASE}/api/v1/audit-logs?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
      });

      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `agentforce_audit_logs_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      }
    } catch (e) {
      console.error("Failed to export audit CSV:", e);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">Compliance & Audit Trail</h1>
            <span className="text-xs px-2 py-0.5 rounded-full border border-border bg-muted text-muted-foreground font-mono">
              Screen 15
            </span>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Immutable, append-only security logs of sensitive actions, approvals, tool calls, and configuration changes.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleExportCSV}
            disabled={downloading}
            className="text-xs px-3 py-2 rounded-md bg-foreground text-background font-medium hover:opacity-90 flex items-center gap-1.5 transition-opacity disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            {downloading ? "Exporting..." : "Export CSV (RFC 4180)"}
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 border border-border rounded-lg bg-card">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground font-medium">Actor Type:</span>
            <select
              value={actorTypeFilter}
              onChange={(e) => setActorTypeFilter(e.target.value)}
              className="px-2.5 py-1.5 text-xs rounded-md border border-border bg-background text-foreground focus:outline-none"
            >
              <option value="">All Actors</option>
              <option value="user">User</option>
              <option value="agent">AI Agent</option>
              <option value="system">System</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="text"
              value={actionSearch}
              onChange={(e) => setActionSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") fetchAuditLogs();
              }}
              placeholder="Search action or resource..."
              className="px-3 py-1.5 text-xs rounded-md border border-border bg-background text-foreground w-64 focus:outline-none"
            />
            <button
              onClick={fetchAuditLogs}
              className="px-3 py-1.5 text-xs rounded-md border border-border hover:bg-muted text-foreground transition-colors"
            >
              Search
            </button>
          </div>
        </div>

        <button
          onClick={fetchAuditLogs}
          title="Refresh Audit Logs"
          className="p-1.5 border border-border rounded-md hover:bg-muted text-muted-foreground hover:text-foreground self-end sm:self-auto transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Audit Log Table */}
      <div className="border border-border rounded-lg bg-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-border text-muted-foreground bg-muted/20">
                <th className="p-3 font-medium">Timestamp (UTC)</th>
                <th className="p-3 font-medium">Actor</th>
                <th className="p-3 font-medium">Action</th>
                <th className="p-3 font-medium">Target Resource</th>
                <th className="p-3 font-medium">Resource ID</th>
                <th className="p-3 font-medium">Correlation ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {logs.length > 0 ? (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-muted/30 transition-colors">
                    <td className="p-3 font-mono text-muted-foreground">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="p-3">
                      <div className="flex items-center gap-1.5">
                        {log.actor_type === "agent" ? (
                          <Bot className="w-3.5 h-3.5 text-muted-foreground" />
                        ) : (
                          <User className="w-3.5 h-3.5 text-muted-foreground" />
                        )}
                        <span className="font-mono uppercase text-[11px] font-medium text-foreground">
                          {log.actor_type}
                        </span>
                      </div>
                    </td>
                    <td className="p-3 font-mono font-medium text-foreground">{log.action}</td>
                    <td className="p-3 font-mono uppercase text-muted-foreground text-[11px]">
                      {log.resource_type}
                    </td>
                    <td className="p-3 font-mono text-muted-foreground text-[11px]">
                      {log.resource_id ? `${log.resource_id.slice(0, 16)}...` : "-"}
                    </td>
                    <td className="p-3 font-mono text-muted-foreground text-[11px]">
                      {log.correlation_id ? `${log.correlation_id.slice(0, 12)}...` : "-"}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-muted-foreground italic">
                    No audit records match the selected filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

