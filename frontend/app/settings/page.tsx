"use client";

import { useEffect, useState } from "react";
import { ThemeToggle } from "@/components/theme-toggle";
import { useAuth } from "@/lib/auth-context";
import { Shield, UserPlus, Check, AlertCircle } from "lucide-react";

interface Member {
  membership_id: string;
  user_id: string;
  email: string;
  name?: string;
  role: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SettingsPage() {
  const { session, memberships, activeTenantId, appUser } = useAuth();
  const activeMembership = memberships.find((m) => m.tenant_id === activeTenantId) || memberships[0];
  const org = activeMembership?.organization;

  const [members, setMembers] = useState<Member[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviteName, setInviteName] = useState("");
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [inviting, setInviting] = useState(false);

  const fetchMembers = async () => {
    if (!session?.access_token || !activeTenantId) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/org/members`, {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setMembers(data);
      }
    } catch (err) {
      console.error("Failed to load members:", err);
    }
  };

  useEffect(() => {
    fetchMembers();
  }, [session, activeTenantId]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session?.access_token || !activeTenantId) return;
    setInviting(true);
    setMsg(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/org/members/invitations`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
        body: JSON.stringify({
          email: inviteEmail,
          role: inviteRole,
          name: inviteName || undefined,
        }),
      });

      if (res.ok) {
        setMsg({ type: "success", text: `Successfully invited ${inviteEmail} as ${inviteRole}` });
        setInviteEmail("");
        setInviteName("");
        await fetchMembers();
      } else {
        const errData = await res.json();
        setMsg({ type: "error", text: errData.error?.message || "Failed to invite member" });
      }
    } catch (err: any) {
      setMsg({ type: "error", text: err.message || "Failed to invite member" });
    } finally {
      setInviting(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-[24px] font-medium text-foreground tracking-tight">Settings</h2>
        <p className="text-[14px] text-muted-foreground mt-1">
          Manage workspace organization, team members, roles, and appearance.
        </p>
      </div>

      {/* Appearance Section */}
      <div className="p-6 border border-border rounded-lg bg-card space-y-4">
        <h3 className="text-[15px] font-medium text-foreground">Appearance</h3>
        <p className="text-[12px] text-muted-foreground">
          Switch between light and dark themes. Persisted across sessions in local storage.
        </p>
        <div className="flex items-center gap-3 pt-1">
          <ThemeToggle />
          <span className="text-[14px] text-foreground">Toggle theme mode</span>
        </div>
      </div>

      {/* Organization Details Section */}
      <div className="p-6 border border-border rounded-lg bg-card space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-[15px] font-medium text-foreground">Organization details</h3>
            <p className="text-[12px] text-muted-foreground mt-0.5">
              Workspace configuration and token allowances.
            </p>
          </div>
          <div className="px-2.5 py-1 rounded-full text-[12px] border border-border bg-muted/40 font-mono text-foreground flex items-center gap-1.5">
            <Shield size={12} strokeWidth={1.5} />
            <span>Role: {activeMembership?.role || "member"}</span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          <div>
            <label className="text-[12px] text-muted-foreground block mb-1">Organization name</label>
            <input
              type="text"
              readOnly
              value={org?.name || "Acme Workforce Corp"}
              className="w-full h-9 px-3 rounded-md border border-border bg-muted/30 text-[14px] text-foreground"
            />
          </div>
          <div>
            <label className="text-[12px] text-muted-foreground block mb-1">Plan</label>
            <input
              type="text"
              readOnly
              value={org?.plan || "starter"}
              className="w-full h-9 px-3 rounded-md border border-border bg-muted/30 text-[14px] text-foreground"
            />
          </div>
          <div>
            <label className="text-[12px] text-muted-foreground block mb-1">Daily token budget</label>
            <input
              type="text"
              readOnly
              value={org ? `${org.daily_token_budget.toLocaleString()} tokens` : "500,000 tokens"}
              className="w-full h-9 px-3 rounded-md border border-border bg-muted/30 text-[14px] text-foreground"
            />
          </div>
        </div>
      </div>

      {/* Members & RBAC Section */}
      <div className="p-6 border border-border rounded-lg bg-card space-y-6">
        <div>
          <h3 className="text-[15px] font-medium text-foreground">Team members and roles</h3>
          <p className="text-[12px] text-muted-foreground mt-0.5">
            Role-based access control (owner, manager, approver, member, auditor).
          </p>
        </div>

        {/* Invite Form (only for owner/manager) */}
        {activeMembership?.role === "owner" || activeMembership?.role === "manager" ? (
          <form onSubmit={handleInvite} className="p-4 rounded-md border border-border bg-muted/20 space-y-3">
            <h4 className="text-[13px] font-medium text-foreground flex items-center gap-1.5">
              <UserPlus size={14} strokeWidth={1.5} />
              <span>Invite member</span>
            </h4>

            {msg && (
              <div
                className={`p-2.5 rounded text-[12px] flex items-center gap-2 border ${
                  msg.type === "success"
                    ? "border-success/40 bg-success/10 text-success"
                    : "border-danger/40 bg-danger/10 text-danger"
                }`}
              >
                {msg.type === "success" ? <Check size={14} /> : <AlertCircle size={14} />}
                <span>{msg.text}</span>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <input
                type="email"
                required
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="colleague@acme.com"
                className="h-9 px-3 rounded-md border border-border bg-background text-[13px] text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
              <input
                type="text"
                value={inviteName}
                onChange={(e) => setInviteName(e.target.value)}
                placeholder="Full name (optional)"
                className="h-9 px-3 rounded-md border border-border bg-background text-[13px] text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className="h-9 px-3 rounded-md border border-border bg-background text-[13px] text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="member">Member</option>
                <option value="approver">Approver</option>
                <option value="manager">Manager</option>
                {activeMembership?.role === "owner" && <option value="owner">Owner</option>}
                <option value="auditor">Auditor (read-only)</option>
              </select>
              <button
                type="submit"
                disabled={inviting}
                className="h-9 px-4 rounded-md bg-primary text-primary-foreground text-[13px] font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
              >
                {inviting ? "Inviting..." : "Send invite"}
              </button>
            </div>
          </form>
        ) : null}

        {/* Members Table */}
        <div className="rounded-md border border-border overflow-hidden">
          <table className="w-full text-left text-[13px]">
            <thead className="border-b border-border bg-muted/40 text-[12px] text-muted-foreground">
              <tr>
                <th className="py-2.5 px-4 font-normal">Member</th>
                <th className="py-2.5 px-4 font-normal">Email</th>
                <th className="py-2.5 px-4 font-normal">Role</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {members.length > 0 ? (
                members.map((m) => (
                  <tr key={m.membership_id} className="hover:bg-muted/30 transition-colors">
                    <td className="py-2.5 px-4 font-medium text-foreground">
                      {m.name || m.email.split("@")[0]}
                    </td>
                    <td className="py-2.5 px-4 font-mono text-[12px] text-muted-foreground">{m.email}</td>
                    <td className="py-2.5 px-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] border border-border bg-muted/60 capitalize text-foreground">
                        {m.role}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={3} className="py-4 px-4 text-center text-muted-foreground text-[13px]">
                    {activeMembership ? "1 member in workspace." : "Sign in to view workspace members."}
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
