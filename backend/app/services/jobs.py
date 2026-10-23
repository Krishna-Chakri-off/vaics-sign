"""Background jobs. Run once with `python -m app.jobs` (cron/K8s CronJob) or as a loop with RUN_SCHEDULER=true."""
import logging, threading, time
from datetime import timedelta
from ..core.config import settings
from ..core.db import SessionLocal
from ..models import Envelope, Organization, User, now
from . import workflow as wf, notify, audit, webhooks, retention

log = logging.getLogger("vaics.jobs")


def reminders(db) -> int:
    n = 0
    for env in db.query(Envelope).filter(Envelope.status.in_(wf.OPEN)):
        org = db.get(Organization, env.org_id)
        wf.check_expiry(db, env)
        if env.status not in wf.OPEN: continue
        if not env.reminder_first_days: continue
        for r in wf.current_step(env):
            if not r.notified_at or r.status in ("completed", "declined"): continue
            last = r.last_reminded_at
            due = (r.notified_at + timedelta(days=env.reminder_first_days)) if not last else (last + timedelta(days=max(1, env.reminder_every_days or 1)))
            if due <= now() and r.reminders_sent < 10:
                n += wf.remind(db, org, env, r, None, "system")
    db.commit()
    return n


def expiry_warnings(db) -> int:
    n = 0
    soon = now() + timedelta(days=3)
    for env in db.query(Envelope).filter(Envelope.status.in_(wf.OPEN), Envelope.expires_at.isnot(None), Envelope.expires_at <= soon, Envelope.expiry_warned.is_(False)):
        org = db.get(Organization, env.org_id); owner = db.get(User, env.owner_id)
        notify.send_email(db, org=org, to=owner.email, kind="expiry_warning", envelope=env, subject=f"Expiring soon: {env.title}",
                          body=f"\"{env.title}\" expires on {env.expires_at:%d %b %Y %H:%M} UTC and is not complete. Extend it from the envelope page if needed.",
                          link=f"{settings.PUBLIC_APP_URL}/envelopes/{env.id}")
        for r in wf.current_step(env):
            notify.send_email(db, org=org, to=r.email, kind="expiry_warning", envelope=env, subject=f"Action needed before {env.expires_at:%d %b %Y}: {env.title}",
                              body=f"Hello {r.name},\n\n\"{env.title}\" expires on {env.expires_at:%d %b %Y}. Use the link from your earlier email to complete it.")
        env.expiry_warned = True; audit.record(db, env, "expiry_warning_sent", "system"); n += 1
    db.commit()
    return n


def expire(db) -> int:
    n = 0
    for env in db.query(Envelope).filter(Envelope.status.in_(wf.OPEN), Envelope.expires_at.isnot(None), Envelope.expires_at < now()):
        wf.check_expiry(db, env); n += 1
    return n


def billing(db) -> int:
    n = 0
    for org in db.query(Organization).filter(Organization.status == "trial", Organization.trial_ends_at.isnot(None)):
        admin = db.query(User).filter_by(org_id=org.id, role="org_admin", is_active=True).first()
        if not org.trial_reminded and org.trial_ends_at - now() <= timedelta(days=3) and admin:
            notify.send_email(db, org=org, to=admin.email, kind="trial_ending", subject="Your VAICS Sign trial ends soon",
                              body=f"Your trial ends on {org.trial_ends_at:%d %b %Y}. Choose a plan to keep sending documents.", link=f"{settings.PUBLIC_APP_URL}/admin/billing")
            org.trial_reminded = True; n += 1
        if org.trial_ends_at < now():
            from ..models import Plan
            free = db.query(Plan).filter_by(code="free").first()
            org.plan_id, org.status = free.id, "active"
            audit.admin_log(db, org.id, "system", "billing.trial_ended", org.slug, after={"plan": "free"}); n += 1
    for org in db.query(Organization).filter(Organization.status == "past_due", Organization.grace_until.isnot(None), Organization.grace_until < now()):
        org.status = "restricted"
        audit.admin_log(db, org.id, "system", "billing.restricted", org.slug, after={"reason": "payment grace period ended"}); n += 1
    for org in db.query(Organization).filter(Organization.status == "active", Organization.current_period_end.isnot(None), Organization.current_period_end < now()):
        org.status, org.grace_until = "past_due", now() + timedelta(days=7)
        audit.admin_log(db, org.id, "system", "billing.renewal_due", org.slug); n += 1
    db.commit()
    return n


def run_all() -> dict:
    db = SessionLocal()
    try:
        out = {"reminders": reminders(db), "expiry_warnings": expiry_warnings(db), "expired": expire(db), "billing": billing(db),
               "webhooks": webhooks.deliver_due(db), "purged": retention.run_retention(db)}
        db.commit()
        return out
    finally:
        db.close()


def start_scheduler(interval: int = 300):
    def loop():
        while True:
            try:
                log.info("jobs %s", run_all())
            except Exception:  # noqa: BLE001
                log.exception("job run failed")
            time.sleep(interval)
    threading.Thread(target=loop, daemon=True, name="vaics-jobs").start()
