"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  Layers,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Activity,
  Cpu,
  Calendar,
  CreditCard,
  FileSpreadsheet,
  Bell,
  UserCheck,
} from "lucide-react";

interface IntegrationItem {
  id: string;
  name: string;
  category: string;
  description: string;
  status: string;
  version: string;
  third_party_oauth: boolean;
  capabilities: string[];
}

interface TestResult {
  status: string;
  latency_ms: number;
  test_detail: string;
  tested_at: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const ICON_MAP: Record<string, any> = {
  mock_calendar: Calendar,
  mock_ats: UserCheck,
  mock_erp: FileSpreadsheet,
  mock_payment: CreditCard,
  notifications: Bell,
};

export default function IntegrationsPage() {
  const { session, activeTenantId } = useAuth();
  const [integrations, setIntegrations] = useState<IntegrationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});

  const fetchIntegrations = async () => {
    if (!session?.access_token) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations`, {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId || "",
        },
      });
      if (res.ok) {
        const data = await res.json();
        setIntegrations(data);
      }
    } catch (err) {
      console.error("Failed to load integrations catalog:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIntegrations();
  }, [session, activeTenantId]);

  const runConnectivityTest = async (id: string) => {
    if (!session?.access_token) return;
    setTestingId(id);
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations/${id}/test`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId || "",
        },
      });
      if (res.ok) {
        const result = await res.json();
        setTestResults((prev) => ({
          ...prev,
          [id]: {
            status: result.status,
            latency_ms: result.latency_ms,
            test_detail: result.test_detail,
            tested_at: result.tested_at,
          },
        }));
      }
    } catch (err) {
      console.error(`Failed to test connectivity for ${id}:`, err);
    } finally {
      setTestingId(null);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-foreground" />
            <h1 className="text-[20px] font-medium text-foreground tracking-tight">
              Built-in Integrations & Services
            </h1>
          </div>
          <p className="text-[13px] text-muted-foreground mt-1">
            AgentForce AI connects to internal mock adapters for calendar scheduling, candidate tracking, ERP data, payment disbursements, and push alerts without third-party OAuth.
          </p>
        </div>

        <button
          onClick={fetchIntegrations}
          disabled={loading}
          className="h-8 px-3 border border-border rounded-md text-[13px] font-medium hover:bg-muted text-foreground transition-colors self-start md:self-auto inline-flex items-center gap-1.5"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Grid of Built-in Services */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {integrations.map((item) => {
          const IconComponent = ICON_MAP[item.id] || Cpu;
          const result = testResults[item.id];
          const isTesting = testingId === item.id;

          return (
            <div
              key={item.id}
              className="p-5 rounded-lg border border-border bg-card flex flex-col justify-between space-y-4"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div className="w-9 h-9 rounded-md bg-muted border border-border flex items-center justify-center text-foreground">
                    <IconComponent className="w-4 h-4" />
                  </div>
                  <div className="flex items-center gap-1.5 text-[12px] font-mono text-muted-foreground">
                    <span className="w-2 h-2 rounded-full bg-foreground" />
                    <span>Active v{item.version}</span>
                  </div>
                </div>

                <div>
                  <h3 className="text-[15px] font-medium text-foreground">{item.name}</h3>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground border border-border/50 inline-block mt-1">
                    {item.category}
                  </span>
                  <p className="text-[12px] text-muted-foreground mt-2 line-clamp-3">
                    {item.description}
                  </p>
                </div>

                {/* Capabilities list */}
                <div className="space-y-1.5 pt-1 border-t border-border/50">
                  <span className="text-[11px] font-medium text-foreground">Capabilities:</span>
                  <div className="flex flex-wrap gap-1">
                    {item.capabilities.map((cap) => (
                      <span
                        key={cap}
                        className="text-[10px] px-1.5 py-0.5 rounded bg-muted/60 text-muted-foreground border border-border/30"
                      >
                        {cap}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Probe Test Section */}
              <div className="pt-3 border-t border-border space-y-2">
                {result && (
                  <div className="p-2 rounded bg-muted/40 border border-border text-[11px] space-y-1">
                    <div className="flex items-center justify-between font-mono">
                      <span className="text-foreground font-medium flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3 text-foreground" />
                        {result.status.toUpperCase()}
                      </span>
                      <span className="text-muted-foreground">{result.latency_ms} ms</span>
                    </div>
                    <p className="text-[10px] text-muted-foreground truncate">
                      {result.test_detail}
                    </p>
                  </div>
                )}

                <button
                  onClick={() => runConnectivityTest(item.id)}
                  disabled={isTesting}
                  className="w-full h-8 border border-border rounded-md text-[12px] font-medium hover:bg-muted text-foreground transition-colors flex items-center justify-center gap-1.5"
                >
                  {isTesting ? (
                    <>
                      <RefreshCw className="w-3 h-3 animate-spin" />
                      Probing service...
                    </>
                  ) : (
                    <>
                      <Activity className="w-3 h-3" />
                      Test Connectivity
                    </>
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

