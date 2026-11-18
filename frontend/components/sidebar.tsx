"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  GitBranch,
  ShieldAlert,
  BookOpen,
  BarChart3,
  Layers,
  Mic,
  Activity,
  FileText,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Employees", href: "/employees", icon: Users },
  { name: "Workflows", href: "/workflows", icon: GitBranch },
  { name: "Voice", href: "/voice", icon: Mic },
  { name: "Approvals", href: "/approvals", icon: ShieldAlert },
  { name: "AIOps", href: "/aiops", icon: Activity },
  { name: "Knowledge", href: "/knowledge", icon: BookOpen },
  { name: "Integrations", href: "/integrations", icon: Layers },
  { name: "Analytics", href: "/analytics", icon: BarChart3 },
  { name: "Audit Logs", href: "/audit-logs", icon: FileText },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { memberships, activeTenantId } = useAuth();
  const activeMembership = memberships.find((m) => m.tenant_id === activeTenantId) || memberships[0];
  const orgName = activeMembership?.organization?.name || "Acme Corp";

  return (
    <aside className="w-[240px] border-r border-border bg-background flex flex-col shrink-0 h-screen sticky top-0">
      {/* Brand header */}
      <div className="h-14 px-6 flex items-center border-b border-border">
        <Link href="/dashboard" className="flex items-center gap-2 font-medium text-foreground tracking-tight">
          <div className="w-4 h-4 bg-foreground rounded-[2px]" />
          <span className="text-[15px] font-medium">AgentForce AI</span>
        </Link>
      </div>

      {/* Navigation list */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navigation.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-[14px] transition-colors duration-theme",
                isActive
                  ? "bg-muted text-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
              )}
            >
              <Icon size={18} strokeWidth={1.5} />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* Bottom organization indicator */}
      <div className="p-4 border-t border-border">
        <div className="px-2 py-1 text-xs text-muted-foreground">
          <p className="font-medium text-foreground truncate">{orgName}</p>
          <p className="text-[11px] truncate">Organization Workspace</p>
        </div>
      </div>
    </aside>
  );
}

