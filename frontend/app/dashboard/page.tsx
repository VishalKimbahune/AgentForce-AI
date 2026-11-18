import { ArrowUpRight, CheckCircle2, Clock, Cpu, Play, ShieldAlert } from "lucide-react";

export default function DashboardPage() {
  const metrics = [
    { label: "Running workflows", value: "3", change: "+1 from yesterday", icon: Play },
    { label: "Pending approvals", value: "2", change: "Requires review", icon: ShieldAlert },
    { label: "Hours saved", value: "148h", change: "This month", icon: Clock },
    { label: "Cost this month", value: "$4.18", change: "Under budget ($50)", icon: ArrowUpRight },
  ];

  const recentWorkflows = [
    {
      id: "wf-101",
      name: "Screen 15 resumes for senior python developer",
      agent: "HR employee",
      status: "Waiting for approval",
      statusType: "warning",
      started: "12m ago",
    },
    {
      id: "wf-102",
      name: "Vendor invoice matching and anomaly check",
      agent: "Finance employee",
      status: "Running",
      statusType: "info",
      started: "28m ago",
    },
    {
      id: "wf-103",
      name: "Monthly business performance report generation",
      agent: "Operations employee",
      status: "Completed",
      statusType: "success",
      started: "2h ago",
    },
  ];

  return (
    <div className="space-y-8">
      {/* Overview header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-[24px] font-medium text-foreground tracking-tight">Overview</h2>
          <p className="text-[14px] text-muted-foreground mt-1">
            Monitor active digital employees, running workflows, and pending human approvals.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="h-9 px-4 rounded-md border border-border hover:bg-muted text-[14px] text-foreground transition-colors duration-theme">
            View traces
          </button>
          <button className="h-9 px-4 rounded-md bg-primary text-primary-foreground hover:opacity-90 text-[14px] font-medium transition-opacity">
            Assign work
          </button>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map((m) => {
          const Icon = m.icon;
          return (
            <div
              key={m.label}
              className="p-5 rounded-lg border border-border bg-card flex flex-col justify-between space-y-3"
            >
              <div className="flex items-center justify-between text-muted-foreground">
                <span className="text-[13px]">{m.label}</span>
                <Icon size={16} strokeWidth={1.5} />
              </div>
              <div>
                <div className="text-[28px] font-medium text-foreground tracking-tight leading-none">
                  {m.value}
                </div>
                <div className="text-[12px] text-muted-foreground mt-2">{m.change}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Active workflows section */}
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="p-5 border-b border-border flex items-center justify-between">
          <div>
            <h3 className="text-[15px] font-medium text-foreground">Recent workflows</h3>
            <p className="text-[12px] text-muted-foreground mt-0.5">
              Workflows coordinated across specialized AI employees.
            </p>
          </div>
          <button className="text-[13px] text-muted-foreground hover:text-foreground transition-colors">
            View all
          </button>
        </div>

        <div className="divide-y divide-border">
          {recentWorkflows.map((wf) => (
            <div
              key={wf.id}
              className="p-4 flex items-center justify-between hover:bg-muted/50 transition-colors duration-theme"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[12px] text-muted-foreground">{wf.id}</span>
                  <span className="text-[14px] font-medium text-foreground">{wf.name}</span>
                </div>
                <div className="text-[12px] text-muted-foreground">
                  Assigned to <span className="text-foreground">{wf.agent}</span> • Started {wf.started}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] border border-border bg-muted/40 text-foreground">
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      wf.statusType === "success"
                        ? "bg-success"
                        : wf.statusType === "warning"
                        ? "bg-warning"
                        : "bg-foreground"
                    }`}
                  />
                  <span>{wf.status}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Health status bar */}
      <div className="p-4 rounded-lg border border-border bg-muted/30 flex items-center justify-between text-[13px]">
        <div className="flex items-center gap-2">
          <CheckCircle2 size={16} className="text-success" strokeWidth={1.5} />
          <span className="text-foreground font-medium">All platform services healthy</span>
          <span className="text-muted-foreground">— LiteLLM gateway, Policy engine, and Vector store ready.</span>
        </div>
        <span className="font-mono text-[12px] text-muted-foreground">v0.1.0</span>
      </div>
    </div>
  );
}

