from . import sign_models  # noqa
"""Seed realistic demo data: python -m app.seed  (--reset wipes and recreates)."""
import sys
from datetime import timedelta
from .database import SessionLocal, Base, engine as db_engine
from . import models, engine, insights
from .models import now
from .security import hash_password

USERS = [  # email, name, role, approver, title
    ("admin@vaics.com", "Asha Admin", "admin", False, "Platform Administrator"),
    ("manager@vaics.com", "Manoj Manager", "change_manager", True, "Change Manager"),
    ("cab@vaics.com", "Chitra CAB", "cab_member", True, "CAB Member - Infrastructure"),
    ("cab2@vaics.com", "Kiran CAB", "cab_member", True, "CAB Member - Applications"),
    ("approver@vaics.com", "Tara Tech", "implementer", True, "Senior Engineer (Technical Approver)"),
    ("implementer@vaics.com", "Imran Implementer", "implementer", False, "Systems Engineer"),
    ("requester@vaics.com", "Riya Requester", "requester", False, "Application Analyst"),
]


def seed(reset=False):
    if reset:
        Base.metadata.drop_all(db_engine)
    Base.metadata.create_all(db_engine)
    db = SessionLocal()
    if db.query(models.User).count():
        print("Database already seeded (use --reset to recreate)."); return
    db.add(models.Organization(id=1, name="VAICS Consulting"))
    pw = hash_password("Demo@123")
    U = {}
    for e, n, r, a, t in USERS:
        U[e.split("@")[0]] = models.User(email=e, full_name=n, role=r, is_approver=a, title=t, password_hash=pw); db.add(U[e.split("@")[0]])
    db.flush()
    G = {}
    for name, kind, members in [("Infrastructure Ops", "assignment", ["implementer", "approver"]), ("Application Support", "assignment", ["implementer", "approver"]),
                                ("Network Team", "assignment", ["approver"]), ("Technical Approvers", "approval", ["approver"]),
                                ("Change Management", "approval", ["manager"]), ("CAB", "cab", ["cab", "cab2"]), ("ECAB", "cab", ["manager", "cab"])]:
        G[name] = models.Group(name=name, kind=kind, member_ids=[U[m].id for m in members]); db.add(G[name])
    db.flush()
    C = {}
    for n, t, o, env, crit, g in [
        ("Online Banking", "business_service", "Digital", "production", "critical", None), ("HR Self-Service", "business_service", "HR IT", "production", "high", None),
        ("Corporate Email", "business_service", "IT", "production", "high", None), ("Web-Portal", "application", "Web Team", "production", "high", "Application Support"),
        ("HRMS-App", "application", "HR IT", "production", "medium", "Application Support"), ("ERP-DB-01", "database", "DBA Team", "production", "critical", "Infrastructure Ops"),
        ("Core-Switch-A", "network", "Network Team", "production", "critical", "Network Team"), ("Mail-Gateway", "server", "Infra Team", "production", "medium", "Infrastructure Ops"),
        ("APP-VM-07", "server", "Infra Team", "production", "medium", "Infrastructure Ops"), ("QA-K8s-Cluster", "cluster", "DevOps", "staging", "low", "Application Support")]:
        C[n] = models.ConfigurationItem(name=n, ci_type=t, owner=o, environment=env, criticality=crit, support_group_id=G[g].id if g else None); db.add(C[n])
    db.flush()
    for p, c in [("Online Banking", "Web-Portal"), ("Online Banking", "ERP-DB-01"), ("HR Self-Service", "HRMS-App"), ("HRMS-App", "ERP-DB-01"),
                 ("Corporate Email", "Mail-Gateway"), ("Web-Portal", "APP-VM-07"), ("APP-VM-07", "Core-Switch-A"), ("Mail-Gateway", "Core-Switch-A")]:
        db.add(models.CIRelationship(parent_id=C[p].id, child_id=C[c].id))
    T = [models.ChangeTemplate(name="OS security patching (monthly)", category="Patching", risk="low", description="Apply monthly OS security patches",
                               implementation_plan="1. Snapshot VM\n2. Apply patches\n3. Reboot\n4. Verify services", backout_plan="Revert to snapshot", test_plan="Service health checks"),
         models.ChangeTemplate(name="SSL certificate renewal", category="Security", risk="low", implementation_plan="Install renewed certificate and reload the web server",
                               backout_plan="Restore previous certificate", test_plan="Verify HTTPS and expiry date"),
         models.ChangeTemplate(name="Pipeline deployment (DevOps)", category="Release", risk="low", implementation_plan="Automated deployment by CI/CD pipeline",
                               backout_plan="Pipeline rollback to previous artifact", test_plan="Automated smoke tests")]
    db.add_all(T)
    t0 = now().replace(minute=0, second=0, microsecond=0)
    db.add(models.BlackoutWindow(name="Quarter-end financial freeze", start=t0 + timedelta(days=25), end=t0 + timedelta(days=28), reason="Financial close"))
    db.add(models.MaintenanceWindow(name="Weeknight window (Mon-Thu 18:00-23:00 UTC)", weekdays=[0, 1, 2, 3], start_hour=18, end_hour=23))
    db.add(models.MaintenanceWindow(name="Weekend window (Sat 00:00-12:00 UTC)", weekdays=[5], start_hour=0, end_hour=12))
    for i, (n, st, ct, mn, mx, g, ag, rule, auto) in enumerate([
        ("Technical approval (assignment group peer)", "assess", "normal", "moderate", "very_high", None, True, "any", False),
        ("Low-risk auto technical approval", "assess", "normal", "low", "low", None, False, "any", True),
        ("Change Manager authorization", "authorize", "normal", "low", "very_high", "Change Management", False, "any", False),
        ("CAB authorization (high risk)", "authorize", "normal", "high", "very_high", "CAB", False, "any", False),
        ("ECAB authorization (emergency)", "authorize", "emergency", "low", "very_high", "ECAB", False, "any", False)]):
        db.add(models.ApprovalPolicy(name=n, stage=st, change_type=ct, min_risk=mn, max_risk=mx, group_id=G[g].id if g else None,
                                     use_assignment_group=ag, rule=rule, auto_approve=auto, order=(i + 1) * 10))
    for n, ct, st, h in [("Assess within 2 business days", "*", "assess", 48), ("Authorize within 3 days", "normal", "authorize", 72),
                         ("ECAB decision within 4 hours", "emergency", "authorize", 4), ("PIR within 5 days", "*", "review", 120),
                         ("Implement within window + 24h", "*", "implement", 24)]:
        db.add(models.SLADefinition(name=n, change_type=ct, state=st, target_hours=h))
    db.flush()

    req, mgr, imp, apv = U["requester"], U["manager"], U["implementer"], U["approver"]

    def mk(title, typ, ci, group, day, hours=2, tpl=None, desc="", answers=None, by=req, affected=()):
        start = t0 + timedelta(days=day, hours=19 - t0.hour)
        c = models.Change(title=title, description=desc or f"{title}.", justification="Business requirement / service improvement", type=typ, category="Infrastructure",
                          configuration_item_id=C[ci].id, template_id=T[tpl].id if tpl is not None else None, assignment_group_id=G[group].id,
                          assigned_to_id=imp.id, planned_start=start, planned_end=start + timedelta(hours=hours),
                          implementation_plan=(T[tpl].implementation_plan if tpl is not None else "1. Pre-checks and backup\n2. Apply the change\n3. Validate"),
                          backout_plan="Restore from pre-change backup", test_plan="Smoke tests and monitoring for 30 minutes",
                          requester_id=by.id, risk=T[tpl].risk if tpl is not None else "moderate", created_at=start - timedelta(days=6))
        db.add(c); db.flush()
        c.number = f"CHG{1000000 + c.id:07d}"
        for a in affected:
            db.add(models.ChangeCI(change_id=c.id, ci_id=C[a].id))
        engine.create_default_tasks(db, c)
        db.flush()
        if tpl is None:
            insights.compute_risk(db, c, answers or {}, by)
        engine.log(db, c, by, "created", "Change created", to="new")
        return c

    def close_tasks(c, types):
        for t in db.query(models.ChangeTask).filter(models.ChangeTask.change_id == c.id, models.ChangeTask.task_type.in_(types)):
            t.state, t.close_notes, t.closed_at = "closed", "Done", now()
        db.flush()

    def approve_all(c, stage, who):
        for a in db.query(models.Approval).filter_by(change_id=c.id, stage=stage, state="requested").all():
            if a.state == "requested":
                engine.act_on_approval(db, db.get(models.User, a.approver_id), a, "approve", "Reviewed - OK")
                db.flush()

    def run(c, upto, code=None):
        path = engine.PATHS[c.type]
        for s in path[1:path.index(upto) + 1]:
            if c.state == upto:
                break
            if c.state in ("assess", "authorize"):
                approve_all(c, c.state, None); continue
            if c.state == "scheduled":
                close_tasks(c, ["planning"])
            if c.state == "implement":
                close_tasks(c, ["implementation", "testing"])
            if c.state == "review":
                close_tasks(c, ["review"]); c.close_code = code or "successful"; c.close_notes = "Completed as planned"
                c.pir_notes = "PIR held; lessons recorded" if c.close_code != "successful" or c.type == "emergency" else None
            engine.move(db, c, mgr if c.state == "review" else (req if c.state == "new" else imp), engine.next_state(c),
                        "Submitted for review" if c.state == "new" else None)
            db.flush()
        return c

    hi = {"affects_production": True, "service_outage": True, "untested": False, "no_backout": False, "many_users": True, "multiple_teams": True}
    run(mk("Upgrade ERP database to PostgreSQL 16", "normal", "ERP-DB-01", "Infrastructure Ops", 9, 4, answers=hi, affected=["HRMS-App"]), "new")
    run(mk("Add firewall rule for partner VPN", "normal", "Core-Switch-A", "Network Team", 6, answers={"affects_production": True}), "assess")
    a1 = run(mk("Migrate HRMS reporting to new VM", "normal", "HRMS-App", "Application Support", 5, 3, answers=hi), "authorize")
    a2 = run(mk("Replace load balancer on Online Banking", "normal", "Web-Portal", "Infrastructure Ops", 7, 3, answers=hi, affected=["APP-VM-07"]), "authorize")
    run(mk("Monthly OS patching - APP-VM-07", "standard", "APP-VM-07", "Infrastructure Ops", 2, tpl=0), "scheduled")
    run(mk("Mail gateway spam-filter upgrade", "normal", "Mail-Gateway", "Infrastructure Ops", 0, 3, answers={"affects_production": True}), "implement")
    run(mk("Emergency fix: Core-Switch-A line card", "emergency", "Core-Switch-A", "Network Team", -1, desc="Line card failure causing packet loss"), "review")
    for title, typ, ci, grp, day, code, tpl in [
        ("Renew SSL certificate for Web-Portal", "standard", "Web-Portal", "Application Support", -12, "successful", 1),
        ("HRMS payroll module release 2.4", "normal", "HRMS-App", "Application Support", -20, "successful_with_issues", None),
        ("Scale QA cluster nodes", "normal", "QA-K8s-Cluster", "Application Support", -15, "unsuccessful", None),
        ("Patch ERP-DB-01 kernel", "normal", "ERP-DB-01", "Infrastructure Ops", -30, "successful", None),
        ("Core switch firmware upgrade", "normal", "Core-Switch-A", "Network Team", -25, "successful", None),
        ("Monthly OS patching - Mail-Gateway", "standard", "Mail-Gateway", "Infrastructure Ops", -8, "successful", 0)]:
        run(mk(title, typ, ci, grp, day, tpl=tpl), "closed", code)
    cx = mk("Decommission legacy FTP server", "normal", "APP-VM-07", "Infrastructure Ops", 14)
    engine.move(db, cx, req, "canceled", "No longer required")
    rej = run(mk("Upgrade Web-Portal framework (major)", "normal", "Web-Portal", "Application Support", 10, 6, answers=hi), "assess")
    a = db.query(models.Approval).filter_by(change_id=rej.id, state="requested").first()
    engine.act_on_approval(db, db.get(models.User, a.approver_id), a, "reject", "Needs a tested backout and a smaller window")
    scale = db.query(models.Change).filter_by(title="Scale QA cluster nodes").first()
    db.add(models.RelatedRecord(kind="incident", number="INC0012045", short_description="QA cluster pods crash-looping after node scale-out", priority="3 - Moderate", change_id=scale.id, relation="caused_by"))
    sw = db.query(models.Change).filter(models.Change.title.like("Emergency fix%")).first()
    db.add(models.RelatedRecord(kind="incident", number="INC0012101", short_description="Packet loss on core network", priority="1 - Critical", change_id=sw.id, relation="fixes"))
    db.add(models.RelatedRecord(kind="problem", number="PRB0004012", short_description="Recurring line-card failures on Core-Switch-A", change_id=sw.id, relation="fixes"))
    m = models.CabMeeting(title="Weekly CAB", start=t0 + timedelta(days=1, hours=10 - t0.hour), end=t0 + timedelta(days=1, hours=11 - t0.hour), location="Teams / Board room",
                          chair_id=mgr.id, attendee_ids=[mgr.id, U["cab"].id, U["cab2"].id, apv.id])
    db.add(m); db.flush()
    for i, c in enumerate([a1, a2], 1):
        db.add(models.CabAgendaItem(meeting_id=m.id, change_id=c.id, order=i))
    # retrospective emergency: implemented first, justification submitted, waiting for ECAB retrospective review
    rt = mk("Emergency restore: Mail-Gateway expired TLS certificate", "emergency", "Mail-Gateway", "Infrastructure Ops", -1, 1,
            desc="Outbound and inbound mail stopped after the gateway TLS certificate expired")
    rt.retrospective, rt.verbal_auth_by, rt.verbal_auth_notes = True, "Manoj Manager", "Phone approval at 07:10 IST; ECAB could not convene in time"
    engine.move(db, rt, imp, "implement", "Implemented first (retrospective emergency)")
    close_tasks(rt, ["implementation", "testing"])
    engine.move(db, rt, imp, "review", "Mail flow restored")
    for k, v in {"retro_why_emergency": "Corporate Email was down for all users; waiting for the next CAB would have kept mail down for days.",
                 "retro_business_impact": "About 400 users without email; customer and supplier communication stopped.",
                 "retro_actions_taken": "Installed a renewed certificate on Mail-Gateway and restarted the mail service.",
                 "retro_timeline": "06:55 alert; 07:05 cause found; 07:10 verbal approval; 07:25 certificate installed; 07:40 mail flow verified.",
                 "retro_outcome": "Successful - mail flow restored, queued mail delivered.",
                 "retro_root_cause": "Certificate expiry was not monitored. Related incident INC0012230.",
                 "retro_preventive_actions": "Add certificate-expiry monitoring (30/7-day alerts); move renewals to the standard SSL catalog item."}.items():
        setattr(rt, k, v)
    rt.retro_status = "draft"
    engine.submit_retro(db, req, rt)
    db.add(models.RelatedRecord(kind="incident", number="INC0012230", short_description="Corporate email down - TLS certificate expired", priority="1 - Critical", change_id=rt.id, relation="fixes"))
    db.add(models.CabAgendaItem(meeting_id=m.id, change_id=rt.id, order=3))
    db.add(models.Note(change_id=sw.id, user_id=imp.id, body="Line card replaced; traffic stable."))
    db.commit()
    print("Seeded. Demo logins (password Demo@123): " + ", ".join(e for e, *_ in USERS))


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
