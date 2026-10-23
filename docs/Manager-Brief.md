# VAICS Change Management System: Design Brief

**Prepared by:** Krishna
**Date:** 16 October 2026 (updated: retrospective emergency changes)
**Build:** VAICS CMS v2 (React + FastAPI), runs on our own servers

## 1. Summary

You asked me to look at how ServiceNow handles change management and build a simple version that any company could run at enterprise level, with modern features that let us compete. I studied ServiceNow's change process, checked what Jira Service Management, BMC Helix and Freshservice offer, and built VAICS CMS around ServiceNow's flow. I kept the screens in the same VAICS look as our earlier CMS: white sidebar with magenta icons, the profile banner, KPI cards, and navy table headers.

The short version: **I copied ServiceNow's process, kept the setup simple, and added a few high-value features that ServiceNow either keeps in higher-priced add-ons or that need configuration work there.**

## 2. What I observed in ServiceNow change management

I based this on ServiceNow's published documentation (the "State progression for change models" and "Change types" pages).

**States.** A change moves through New → Assess → Authorize → Scheduled → Implement → Review → Closed, and can be Canceled. ServiceNow describes each state:
- New: still being drafted.
- Assess: peer review and technical approval.
- Authorize: Change Management and the CAB give final authorization.
- Scheduled: authorized and waiting for the planned start.
- Implement: the work is being done.
- Review: the requester decides whether it succeeded, and a post-implementation review can take place.
- Closed: all done.

A change cannot be canceled once it is in Review or Closed. A change moves on when conditions are met, such as an approval being granted, not just because time passes.

**Change types.**
- **Normal:** goes through every state and needs two levels of approval: peer/technical, then Change Management/CAB.
- **Standard:** pre-approved with a proven history. It skips Assess and Authorize and goes straight from New to Scheduled.
- **Emergency:** skips Assess but still has to be authorized, usually by the CAB or an Emergency CAB (ECAB).

**Approvals.** If an approver rejects, the change goes back to New. ServiceNow's Simplified Change Management lets you set Authorize approvers per risk level. Their example: a member of the assignment group for low risk and CAB members for moderate and high risk.

**Change tasks.** ServiceNow can create tasks automatically when a change enters Scheduled (check planning and resources), Implement (do the work) and Review (check the result and record lessons).

**Risk, CAB, schedule and conflicts.** These are the main supporting features: a risk assessment, CAB meetings, a change calendar, blackout and maintenance windows, and conflict detection. They are powerful, but each one needs administrators to set it up.

## 3. What I kept (core, like ServiceNow)

| Area | In VAICS CMS |
|---|---|
| States | New, Assess, Authorize, Scheduled, Implement, Review, Closed, Canceled. Same order and same rules as ServiceNow. The backend enforces them, so even the API can't skip a step. |
| Change types | Normal goes through the full flow. Standard comes from a catalog template, is pre-authorized, and goes New → Scheduled. Emergency skips Assess, needs ECAB authorization, and requires a justification. A **retrospective emergency** (ticked on the form) is implemented first – New → Implement → Review → Closed – and must pass a mandatory ECAB/CAB retrospective review before it can close. |
| Cancel rule | You can cancel from New up to Implement, with a reason. You can't cancel in Review or Closed (same as ServiceNow). |
| Rejection | Any rejection sends the change back to New with the reason recorded. |
| Approvals | Technical approval at Assess, then Change Manager / CAB at Authorize. Group approvals use "any one member" or "all members" rules. |
| Change tasks | Each change automatically gets four tasks: Planning, Implementation, Testing and Review. They control the state moves (see the diagram). |
| Risk | A 7-question risk questionnaire plus automatic risk conditions. Risk combined with impact gives the priority through a risk/impact matrix. |
| CAB | CAB Workbench with meetings, attendees, a decision per change (approve, reject or defer) and minutes. |
| Schedule | Calendar of changes, blackout windows, weekly maintenance windows and CAB meetings. |
| Conflicts | Flags a change on the same CI (including affected CIs) in an overlapping window, inside a blackout, outside a maintenance window, or when the assignee is double-booked. |
| CMDB | Configuration items with "depends on" relationships. Each change shows its Affected CIs and Impacted Services. |
| Incidents/problems | Related records on each change, marked either "resolved by this change" or "caused by this change". |
| Review (PIR) | Close codes: successful, successful with issues, unsuccessful. A PIR is required for emergency changes and anything not fully successful. |
| Change form | ServiceNow-style layout: process bar, header fields, and related-list tabs (Approvals, Change Tasks, Affected CIs, Impacted Services, Conflicts, Related Records, Activity). |
| List view | Configurable columns, filters, breadcrumb filter chips and group-by. |
| SLAs | A time target per state, for example "ECAB decision within 4 hours". Each change shows the SLA percentage used or "breached". |
| Audit | Every state move, field change (old → new value), approval, task, CAB decision and note is recorded in the Activity history. |

## 4. What I simplified and why

| ServiceNow | VAICS CMS | Why |
|---|---|---|
| Workflow Studio / business rules to design state models | One fixed, proven state model per type, built into the code | Most companies use the standard ITIL model. Fixing it removes weeks of configuration and stops people bending the process. |
| Many roles and ACLs | 5 roles (Requester, Change Manager, CAB Member, Implementer, Admin) plus an "approver" flag | Easy to understand and audit. The approver flag covers technical approvers without adding another role. |
| Separate Incident/Problem applications | Lightweight related records on the change | We need the link for impact and success scoring, not a full incident desk. It can connect to an existing ITSM later. |
| Full CMDB with discovery | Simple CIs plus "depends on" relationships | That is enough for impacted-service analysis. Discovery can come later. |
| Many risk methods (risk calculator, risk conditions, assessments) | One questionnaire plus built-in risk conditions plus a 3×4 risk/impact matrix | Gives a clear result that is easy to explain to auditors. |
| Approval rules written as scripts | An admin screen of approval policies (stage, change type, risk range, group, any/all, auto-approve) | Admins can change who approves without writing code. |

## 5. Advancements (and the problem each one solves)

1. **Auto-approval for low-risk changes.** Approvers waste time on routine work. A policy auto-approves technical review when risk is low, and it is recorded as "System (auto-approval policy)" for the audit trail. Analytics shows how many approvals were automatic and how many manual.
2. **AI risk prediction from history.** A questionnaire alone misses the CI's track record. The system looks at similar past changes (same CI, team and wording) and their outcomes, then predicts the risk with a confidence level and a failure probability. It works without any outside AI service. An LLM can be plugged in through settings.
3. **Similar past changes.** Teams repeat old mistakes. The Risk tab lists the most similar past changes and how they turned out.
4. **AI plan drafting and CAB summaries.** Writing plans is slow, and CAB members don't have time to read every change. One click drafts the implementation, backout and test plans. "AI summary" gives a 5-bullet briefing: what, why, where and when, risk and impact, and backout.
5. **Next available window.** Rescheduling around conflicts is trial and error. "Propose next available window" finds the next slots with no CI clash, no blackout and inside a maintenance window. One click reschedules.
6. **Change Success Score per team.** Managers have no simple measure of change quality. Each assignment group gets a 0-100 score from its closed changes: successful = 1, with issues = 0.7, minus points for incidents it caused and for emergencies.
7. **DevOps change API.** Pipelines deploy without a change record, or a CAB slows them down. A pipeline calls one API with a token. It creates a pre-authorized standard change, checks for blackouts (the deployment gate), and moves the change to Implement. Reporting success closes the change. Reporting failure leaves it in Review for a PIR.
8. **Slack and Microsoft Teams webhooks.** People miss emails. Every state change can post to Slack or Teams, or send signed JSON to any system.
9. **Kanban board.** Lists hide where the flow is stuck. A board view by state lets you drag a card to move it, with the same rules enforced.
10. **Approval delegation.** Approvals get stuck when someone is on leave. Approvers delegate to a colleague for a date range, and the system records who acted on whose behalf.
11. **Keyboard-first use.** Power users want speed. Shortcuts: `g d` dashboard, `g c` changes, `g a` approvals, `g b` CAB, `n` new change, `/` search, `?` help.
12. **Analytics.** Monthly trend, outcomes, team scorecard, approval automation rate, changes by source (portal vs DevOps) and most-changed CIs.

I left out features that would hurt simplicity, such as a visual workflow designer, a full incident desk, CMDB discovery and multi-step custom forms.

## 6. Comparison with ServiceNow and competitors

The competitor details below come only from public sources I checked on 14 Oct 2026 (vendor docs and 2026 comparison articles). "Not verified" means I didn't confirm it, not that the product lacks it.

| Capability | VAICS CMS | ServiceNow | Jira Service Management | BMC Helix ITSM | Freshservice |
|---|---|---|---|---|---|
| ITIL state model by change type | Yes. Normal, Standard and Emergency with ServiceNow's state rules | Yes. Normal goes through all states; Standard skips Assess/Authorize; Emergency skips Assess | Leaner and highly configurable by default | Change models closely follow ITIL 4 | Follows the ITIL textbook; standard/normal/emergency workflows |
| CAB / ECAB | CAB Workbench with auto-built agenda, decisions and minutes; ECAB for emergencies | CAB / ECAB authorization | Suits "no CAB meeting unless the risk score is high" | CAB management | Template-driven CAB workflows |
| Risk scoring | Questionnaire, conditions and a risk/impact matrix | Risk assessment; approvers set by risk level | AI risk scoring (Premium/Enterprise) | Risk scoring; AI-driven change impact analysis | Risk and impact assessment |
| Conflict detection / calendar | CI, blackout, maintenance and assignee conflicts, plus next-window proposal | Calendar and conflict detection | Change calendar | Change calendars and blackout windows | Conflict detection against the calendar |
| CI/CD deployment gating | DevOps API: create, gate, auto-close | Not verified | Yes. Deployment gating with Bitbucket / GitHub; auto-creates change records from Bitbucket deployments | Not verified | Reported to lack native CI/CD deployment gating |
| History-based risk prediction | Yes, built in, no extra licence | Not verified | AI risk scoring (Premium) | AI-driven change impact analysis | Not verified |
| Team change success score | Yes | Not verified | Not verified | Not verified | Not verified |
| Hosting | Our own servers or cloud, SQLite or PostgreSQL | SaaS | Cloud (Atlassian) | Cloud, on-premise or hybrid | Cloud only |
| Licence | Owned by VAICS (no per-agent fee) | Commercial | Change management on Premium/Enterprise tiers | Commercial (price not disclosed) | Commercial, tiered per agent |

**Where we stand.** We match ServiceNow on the process core. We match JSM's DevOps strength (pipeline gating) without needing the Atlassian ecosystem. We offer BMC/JSM-style AI risk features built in. And we are easier to set up and own than any of them.

## 7. Role model

| Role | What they do |
|---|---|
| Requester | Raises changes, edits them while New, submits, cancels while New/Assess/Authorize, and can close in Review (decides success, like ServiceNow). Sees only their own changes. |
| Implementer (assignee) | A member of the assignment group. Closes planning, implementation and testing tasks, and moves Scheduled → Implement → Review. |
| Change Manager | Runs the process. Authorizes (by policy), chairs the CAB, edits any open change, closes, and cancels. |
| CAB Member | Approves or rejects at Authorize (CAB/ECAB groups) and attends CAB meetings. Cannot raise changes. |
| Admin | Users, groups, approval policies, the standard change catalog, windows, SLAs and webhooks. |
| Approver (flag) | Any user marked as an approver can be put in approval groups, for example a senior engineer giving technical approval at Assess. |

## 8. Workflow

```
NORMAL     New ──submit──▶ Assess ──technical approval──▶ Authorize ──CM / CAB approval──▶ Scheduled
                                (auto if low risk)                                          │
                                                                    planning task closed ──▶ Implement
                                                     implementation + testing tasks closed ──▶ Review
                                             review task + close code (+ PIR if needed) ──▶ Closed

STANDARD   New ──(catalog template, pre-authorized)──▶ Scheduled ──▶ Implement ──▶ Review ──▶ Closed
EMERGENCY  New ──justification──▶ Authorize (ECAB) ──▶ Scheduled ──▶ Implement ──▶ Review ──▶ Closed
RETRO EMERGENCY  New ──justification (+ optional verbal authorization)──▶ Implement (first)
                 ──impl. + testing tasks closed──▶ Retrospective Review: owner submits 7-part justification
                 ──ECAB/CAB: accept / accept with actions / request info (back to owner) / reject & escalate──▶ Closed

Any rejection at Assess/Authorize ──▶ back to New (reason recorded)
Cancel allowed: New, Assess, Authorize, Scheduled, Implement   (not Review / Closed)
DevOps API: New ──▶ Scheduled ──▶ Implement ──(success)──▶ Review ──▶ Closed automatically
```

### Retrospective emergency changes (new)

Sometimes an outage has to be fixed before anyone can meet. ServiceNow handles this with retrospective (expedited) emergency changes, and so do we:

- On an Emergency change the requester ticks **Retrospective emergency**. They can record an optional **verbal authorization** (who, notes). Plans and window are optional; justification, CI and assignment group are required.
- **Submit goes straight to Implement.** There are no approvals beforehand; the planning task is cancelled as not applicable, and the timeline records that a retrospective review is now mandatory.
- After implementation the change enters **Review**, shown on the progress bar as **Retrospective Review (ECAB)** with a magenta "Retrospective emergency path" banner.
- The owner (requester, assignee or change manager) fills the **Retrospective Review** tab: why it was an emergency, business impact if not done, what was done, timeline of actions, outcome, root cause / related incident, preventive actions. All seven are required to submit.
- Submitting notifies ECAB/CAB members and puts the change on the **CAB Workbench** agenda. Reviewers (CAB members, change managers, admins, ECAB/CAB group members – never the requester) can **Accept**, **Accept with actions**, **Request more info** (sends it back to the owner) or **Reject & escalate** (notifies change managers, fires a webhook, sets Approval = rejected).
- **Closing is blocked** until the justification is submitted and ECAB/CAB has decided. The dashboard shows a count and list of emergency changes awaiting retrospective review, and every step is in the audit trail.

**Likely questions.** *Doesn't this let people bypass approval?* No – it is recorded as an emergency, with mandatory justification, the requester can't review their own change, and nothing closes without an ECAB/CAB decision; rejections are escalated and visible in analytics. *What does "rejected" do?* It records that the emergency was not justified and escalates to change management; the change can then be closed (normally with a close code that reflects it), so the record is never left open. *Is the classic emergency still available?* Yes – untick the box and ECAB authorizes before work starts.

## 9. Verification

- 11 automated backend tests pass (including two for retrospective emergencies). They cover:
  - the full Normal lifecycle (New → Assess → Authorize → Scheduled → Implement → Review → Closed), with task gates, close codes and PIR;
  - Standard changes skipping approvals, and Emergency changes going through ECAB;
  - rejection back to New, low-risk auto-approval, and delegation;
  - role checks, conflicts, next window, impacted services and the CAB decision;
  - the DevOps API, AI assist, analytics and SLAs.
- The frontend production build passes.
- I ran the full lifecycle live against the running servers.
- Demo data covers every state, a rejected change, related incidents and problems, and a scheduled CAB meeting.

## 10. Roadmap

1. Single sign-on (Azure AD / SAML) and mapping roles from groups.
2. Email approvals (approve or reject by replying), plus a Teams approval card.
3. Connectors that create changes from GitHub/GitLab/Azure DevOps deployments without any scripting.
4. Import CMDB data from discovery tools or spreadsheets.
5. Better risk prediction as our change history grows (moving from rules to a trained model).
6. Multi-tenant hosting for clients (the data model already has an organization ID).
7. Attachments on changes and tasks, and PDF export of CAB minutes.
