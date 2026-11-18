# 05 — Users, Features, Screens and Expected Output

> Defines who uses the product, what they see, and what "done" looks like.

## 1. Final users and roles

| Role | Who | Can do |
|---|---|---|
| Org owner / admin | CEO, IT head | Everything: members, roles, integrations, budgets, delete data |
| Department manager | HR head, finance manager, ops lead | Create and configure employees for their department, assign work, approve actions in their scope |
| Approver | Senior manager | Approve or reject pending actions, delegate approvals |
| Operator / member | Recruiter, analyst, support lead | Assign work, view results, upload documents |
| Auditor (read-only) | Compliance, auditor | View workflows, traces, audit logs, no actions |

### Primary personas

1. **Priya, HR manager.** Wants resumes screened and interviews scheduled without spending days. Needs to review before invitations go out.
2. **Rahul, finance manager.** Wants invoices matched to purchase orders and anomalies flagged. Must personally approve every payment.
3. **Anita, operations lead.** Wants monthly reports and deadline follow-ups generated and sent to management.
4. **Vikram, platform admin.** Wants to see agent health, cost per workflow, and failures, with suggested fixes.

## 2. Product screens

| # | Screen | Purpose | Key elements |
|---|---|---|---|
| 1 | Login and org setup | Sign in, create or join organization | Supabase email/password or magic-link login, optional MFA, workspace selector |
| 2 | Dashboard | Overview | Running workflows, pending approvals, hours saved, cost this month, agent health |
| 3 | AI Employees | List and manage | Cards with name, role, status, success rate; "Add employee" |
| 4 | Marketplace | Install templates | Template cards (HR, Finance, Support, Legal), description, required integrations, Install |
| 5 | Employee configuration | Configure one agent | Name, instructions, model, tools and permissions, knowledge sources, approval rules |
| 6 | Assign work | Main interaction | Large input ("Describe the work"), attach files, mic button, employee picker (optional) |
| 7 | Workflow builder | Visual or form-based flow | Steps list, dependencies, conditions, approval points |
| 8 | Live workflow | Real-time execution | Step timeline with status, current agent, logs, cancel button |
| 9 | Agent traces | Debug | Message-by-message trace, tool calls, token and cost per step |
| 10 | Approval center | Human-in-the-loop | Pending list; each item shows action, reason, risk level, data involved, Approve / Reject / Delegate |
| 11 | Knowledge base | Documents | Upload, status (processing, ready), tags, permissions, delete |
| 12 | LLM analytics | Gateway usage | Requests by model, latency, fallback count, tokens, cost |
| 13 | Observability | Agent health | Success/failure rate, completion time, retries |
| 14 | AIOps | Incidents | Detected anomalies, root-cause hypothesis, recommended fix, approve remediation |
| 15 | Audit logs | Compliance | Filter by user, agent, action, date; export CSV |
| 16 | Integrations | View built-in services | Mock Calendar, ATS, HRMS, ERP and CRM service status; no third-party account connection required |
| 17 | Voice | Speak commands | Push-to-talk and continuous modes, live captions, interrupt button |
| 18 | Settings | Org config | Members, roles, budgets, approval thresholds, theme |

All screens follow `02_DESIGN_SYSTEM.md` (monochrome, light/dark toggle in header).

## 3. Core user journeys

### Journey A: Recruitment automation (Priya)
1. Priya types: "Find the top 20 candidates for our Python developer role and schedule interviews." (or speaks it).
2. Intent agent detects `recruitment`, asks which JD if more than one exists.
3. Knowledge agent retrieves the JD. HR agent parses uploaded resumes and ranks them.
4. Compliance agent checks the hiring policy.
5. HR agent proposes interview slots using the local mock calendar service.
6. Policy engine flags "send external emails" as needing approval.
7. Priya sees an approval card with the candidate list and draft email, then approves.
8. Notification agent creates in-app interview invitations after approval.
9. Verifier checks all 20 were handled. Priya gets a completion report (ranked table, slots, emails sent).

### Journey B: Finance automation (Rahul)
1. Rahul uploads invoices and says "Process this month's vendor invoices."
2. Finance agent extracts fields (OCR/LLM), verifies vendor, matches purchase orders, checks duplicates and anomalies.
3. Clean invoices are grouped. Flagged ones show the reason.
4. Rahul gets an approval request per payment batch. No payment executes without his approval.
5. After approval, the (mock) payment API is called, audit trail written, summary report generated.

### Journey C: Operations report (Anita)
1. Anita says "Generate a monthly business report and send it to management."
2. Operations and Finance agents pull data from the mock ERP and internal task tracker.
3. Report agent builds a PDF or PPT. Verifier checks the numbers against the sources.
4. Anita approves the email to leadership. Notification agent sends it.

### Journey D: Admin monitoring (Vikram)
1. Dashboard shows "Recruitment agent failure rate up 20%".
2. AIOps agent shows a root-cause hypothesis from traces and logs (for example, an unavailable mock integration or expired LLM provider key).
3. Recommended fix appears. Vikram approves or applies it manually. System verifies recovery.

## 4. Expected output of the finished project

### Must work in the demo (MVP)
- [ ] Sign up, create organization, invite a member with a role.
- [ ] Install or create at least **three AI employees**: HR, Finance, Operations.
- [ ] Type or speak a task and see a **live workflow timeline** update in real time.
- [ ] Orchestrator splits the task, runs agents in sequence and in parallel, shows agent-to-agent messages in the trace view.
- [ ] Upload documents to the knowledge base and get cited answers (RAG).
- [ ] Parse resumes, rank against a JD, propose interview slots using the mock calendar, and create in-app interview invitations.
- [ ] Process sample invoices against mock purchase orders, flag duplicates and anomalies.
- [ ] **Approval center** pauses the workflow, and resume happens only after an authorized human approves.
- [ ] Rejecting or letting an approval expire stops the action. It never auto-approves.
- [ ] LLM gateway routes by task type, falls back when a provider fails, tracks tokens and cost.
- [ ] Guardrails block a prompt-injection test and mask PII in logs.
- [ ] Observability dashboard shows success rate, latency, token cost, and full trace of a workflow.
- [ ] Voice: push-to-talk, transcription shown, spoken reply, same approvals as text.
- [ ] Light and dark theme toggle works on every page and persists.
- [ ] Audit log records every sensitive action with who, what, when.
- [ ] Tenant isolation test passes (Org A cannot see Org B data).

### Nice to have
- Marketplace with installable agent templates.
- AIOps agent with anomaly detection and suggested fixes.
- Multi-level approval and delegation.
- Kubernetes manifests and CI pipeline.

### Success metrics to display
Workflows completed, automation success rate, human approval rate, average completion time, hours saved (estimated), cost per completed workflow.

## 5. Non-functional requirements

| Area | Requirement |
|---|---|
| Performance | Dashboard loads under 2s; first live-workflow event under 1s after submit; voice reply starts under 3s on a normal connection |
| Reliability | Workflow resumes after backend restart from the last checkpoint |
| Security | JWT with refresh rotation, RBAC, tenant filter on every query, secrets never in logs |
| Privacy | PII masked in logs and telemetry; documents deletable with propagation to vectors |
| Auditability | Immutable audit records for approvals, tool calls, config changes |
| Accessibility | WCAG AA contrast, keyboard navigation, captions for voice |
| Responsiveness | Works on desktop and tablet; mobile usable for approvals |

## 6. Sample data to seed

- 1 organization, 4 users (admin, HR manager, finance manager, auditor).
- 15 fake resumes (PDF/DOCX) and 2 job descriptions (Python developer, data engineer).
- 12 fake invoices (include 1 duplicate, 1 over-budget, 1 unknown vendor) and matching purchase orders.
- 5 policy documents (hiring policy, expense policy, data privacy, leave policy, approval matrix).
- 30 days of mock operations data for report generation.
