"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  Users,
  Plus,
  Shield,
  CheckCircle2,
  Cpu,
  Sparkles,
  ArrowRight,
  RefreshCw,
  Sliders,
  Check,
} from "lucide-react";

interface Agent {
  id: string;
  name: string;
  type: string;
  system_prompt: string;
  model_policy?: any;
  allowed_tools: string[];
  status: "active" | "paused";
  template_id?: string;
  created_at: string;
}

interface Template {
  id: string;
  name: string;
  type: string;
  description: string;
  default_config?: any;
  required_integrations: string[];
  published: boolean;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function EmployeesPage() {
  const { session, activeTenantId, memberships } = useAuth();
  const activeMembership = memberships.find((m) => m.tenant_id === activeTenantId) || memberships[0];
  const isManagerOrOwner = activeMembership?.role === "owner" || activeMembership?.role === "manager";

  const [activeTab, setActiveTab] = useState<"installed" | "marketplace">("installed");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [installingId, setInstallingId] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const fetchEmployeesData = async () => {
    if (!session?.access_token || !activeTenantId) return;
    setLoading(true);

    const headers = {
      Authorization: `Bearer ${session.access_token}`,
      "X-Tenant-ID": activeTenantId,
    };

    try {
      // Fetch installed agents
      const aRes = await fetch(`${API_BASE}/api/v1/agents`, { headers });
      if (aRes.ok) setAgents(await aRes.json());

      // Fetch marketplace templates
      const tRes = await fetch(`${API_BASE}/api/v1/marketplace/templates`, { headers });
      if (tRes.ok) setTemplates(await tRes.json());
    } catch (e) {
      console.error("Failed to load employees:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmployeesData();
  }, [session, activeTenantId]);

  const handleInstall = async (templateId: string) => {
    if (!session?.access_token || !activeTenantId) return;
    setInstallingId(templateId);
    setStatusMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/marketplace/templates/${templateId}/install`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
      });
      if (res.ok) {
        setStatusMsg("AI Employee installed successfully into your workspace.");
        await fetchEmployeesData();
        setActiveTab("installed");
      }
    } catch (e) {
      console.error("Installation failed:", e);
    } finally {
      setInstallingId(null);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">AI Employees & Marketplace</h1>
            <span className="text-xs px-2 py-0.5 rounded-full border border-border bg-muted text-muted-foreground font-mono">
              Screen 8
            </span>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Deploy specialized, governed autonomous employees to handle recruitment, finance, reporting, and operations.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setActiveTab(activeTab === "installed" ? "marketplace" : "installed")}
            className="text-xs px-3 py-2 rounded-md bg-foreground text-background font-medium hover:opacity-90 flex items-center gap-1.5 transition-opacity"
          >
            {activeTab === "installed" ? (
              <>
                <Plus className="w-3.5 h-3.5" /> Browse Marketplace
              </>
            ) : (
              <>
                <Users className="w-3.5 h-3.5" /> View Installed ({agents.length})
              </>
            )}
          </button>
        </div>
      </div>

      {statusMsg && (
        <div className="p-4 rounded-md border border-border bg-muted/40 text-xs text-foreground flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-foreground" />
          <span>{statusMsg}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-border gap-6">
        <button
          onClick={() => setActiveTab("installed")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "installed"
              ? "border-foreground text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Installed AI Employees ({agents.length})
        </button>
        <button
          onClick={() => setActiveTab("marketplace")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "marketplace"
              ? "border-foreground text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Marketplace Templates ({templates.length})
        </button>
      </div>

      {/* TAB 1: INSTALLED EMPLOYEES */}
      {activeTab === "installed" && (
        <div className="space-y-6">
          {agents.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {agents.map((agent) => (
                <div key={agent.id} className="border border-border rounded-lg p-6 bg-card space-y-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-base font-semibold text-foreground">{agent.name}</h3>
                      <span className="text-xs font-mono uppercase text-muted-foreground">{agent.type} employee</span>
                    </div>
                    <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono border border-border bg-muted text-foreground uppercase">
                      {agent.status}
                    </span>
                  </div>

                  <p className="text-xs text-muted-foreground line-clamp-3">
                    {agent.system_prompt}
                  </p>

                  <div className="border-t border-border pt-3 space-y-2">
                    <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
                      Allowed Controlled Tools
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {agent.allowed_tools && agent.allowed_tools.length > 0 ? (
                        agent.allowed_tools.map((t, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 rounded text-[10px] font-mono bg-muted text-muted-foreground border border-border"
                          >
                            {t}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-muted-foreground italic">Standard platform tools</span>
                      )}
                    </div>
                  </div>

                  <div className="border-t border-border pt-3 flex items-center justify-between text-xs text-muted-foreground font-mono">
                    <span>Deployed</span>
                    <span>{new Date(agent.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="border border-border rounded-lg p-12 bg-card text-center space-y-4">
              <Users className="w-10 h-10 text-muted-foreground mx-auto" />
              <h3 className="text-base font-semibold text-foreground">No AI Employees installed yet</h3>
              <p className="text-xs text-muted-foreground max-w-md mx-auto">
                Explore pre-configured AI Employee templates from the marketplace and install them with one click.
              </p>
              <button
                onClick={() => setActiveTab("marketplace")}
                className="text-xs px-4 py-2 rounded-md bg-foreground text-background font-medium hover:opacity-90 transition-opacity"
              >
                Browse Marketplace Templates
              </button>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: MARKETPLACE TEMPLATES */}
      {activeTab === "marketplace" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map((tpl) => {
            const isInstalled = agents.some((a) => a.type === tpl.type);
            return (
              <div key={tpl.id} className="border border-border rounded-lg p-6 bg-card flex flex-col justify-between space-y-4">
                <div className="space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-base font-semibold text-foreground">{tpl.name}</h3>
                      <span className="text-xs font-mono uppercase text-muted-foreground">{tpl.type} template</span>
                    </div>
                    {isInstalled && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-mono border border-border bg-muted text-foreground flex items-center gap-1">
                        <Check className="w-3 h-3" /> Installed
                      </span>
                    )}
                  </div>

                  <p className="text-xs text-muted-foreground leading-relaxed">{tpl.description}</p>

                  <div className="space-y-1.5 pt-1">
                    <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
                      Required Mock Integrations
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {tpl.required_integrations && tpl.required_integrations.length > 0 ? (
                        tpl.required_integrations.map((intg, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 rounded text-[10px] font-mono bg-muted text-muted-foreground border border-border uppercase"
                          >
                            {intg}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-muted-foreground italic">None required</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="border-t border-border pt-4">
                  <button
                    onClick={() => handleInstall(tpl.id)}
                    disabled={installingId === tpl.id || !isManagerOrOwner}
                    className="w-full text-xs px-4 py-2 rounded-md border border-border bg-background hover:bg-muted text-foreground font-medium flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                  >
                    {installingId === tpl.id ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Installing...
                      </>
                    ) : (
                      <>
                        <Plus className="w-3.5 h-3.5" /> Install Employee
                      </>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
