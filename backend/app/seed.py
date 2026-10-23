"""Seed plans (always) and, with `python -m app.seed --demo`, a platform admin and Krishna's demo organization.
Demo passwords come from DEMO_PASSWORD (env); nothing secret is hard-coded."""
import os, sys
from datetime import timedelta
from .core.db import SessionLocal, Base, engine
from .core.security import hash_password
from .models import Plan, Organization, User, now

ALL = ["api", "webhooks", "branding", "parallel_routing", "sms_otp", "bulk_send", "templates", "powerforms", "in_person", "groups",
       "advanced_roles", "reminders", "overage_billing", "combine_templates", "top_ups"]


def feats(*on):
    return {f: f in on for f in ALL}


PLANS = [
    dict(code="free", name="Free", description="For individuals trying VAICS Sign", features=feats("reminders"),
         limits={"envelopes_per_month": 3, "seats": 1, "templates": 0, "sms_per_month": 0, "api_calls_per_month": 0, "api_calls_per_min": 30, "bulk_max_rows": 0, "storage_mb": 500},
         prices={"INR": {"monthly": 0, "annual": 0}, "USD": {"monthly": 0, "annual": 0}, "EUR": {"monthly": 0, "annual": 0}}),
    dict(code="standard", name="Standard", description="Small teams", features=feats("reminders", "templates", "branding", "groups", "top_ups"),
         limits={"envelopes_per_month": 100, "seats": 10, "templates": 25, "sms_per_month": 0, "api_calls_per_month": 0, "api_calls_per_min": 60, "bulk_max_rows": 0, "storage_mb": 10000},
         prices={"INR": {"monthly": 799, "annual": 7990}, "USD": {"monthly": 15, "annual": 150}, "EUR": {"monthly": 14, "annual": 140}}),
    dict(code="business", name="Business", description="Growing businesses with automation",
         features=feats("reminders", "templates", "branding", "groups", "parallel_routing", "sms_otp", "bulk_send", "powerforms", "in_person", "api", "webhooks",
                        "advanced_roles", "combine_templates", "top_ups"),
         limits={"envelopes_per_month": 500, "seats": 100, "templates": -1, "sms_per_month": 500, "api_calls_per_month": 50000, "api_calls_per_min": 120, "bulk_max_rows": 1000, "storage_mb": 100000},
         prices={"INR": {"monthly": 1999, "annual": 19990}, "USD": {"monthly": 40, "annual": 400}, "EUR": {"monthly": 37, "annual": 370}}),
    dict(code="enterprise", name="Enterprise", description="Contracted plan, invoice billing, overage", features=feats(*ALL),
         limits={"envelopes_per_month": -1, "seats": -1, "templates": -1, "sms_per_month": 5000, "api_calls_per_month": -1, "api_calls_per_min": 600, "bulk_max_rows": 10000, "storage_mb": -1},
         prices={"INR": {"monthly": 0, "annual": 0}, "USD": {"monthly": 0, "annual": 0}, "EUR": {"monthly": 0, "annual": 0}}, is_public=False, is_custom=True),
    dict(code="sandbox", name="Developer sandbox", description="Free API sandbox; documents are watermarked and not legally binding",
         features=feats("api", "webhooks", "templates", "parallel_routing", "bulk_send", "powerforms", "in_person", "reminders", "groups"),
         limits={"envelopes_per_month": 50, "seats": 3, "templates": 10, "sms_per_month": 0, "api_calls_per_month": 10000, "api_calls_per_min": 60, "bulk_max_rows": 50, "storage_mb": 1000},
         prices={"INR": {"monthly": 0, "annual": 0}, "USD": {"monthly": 0, "annual": 0}, "EUR": {"monthly": 0, "annual": 0}}, is_public=False),
]


def ensure_plans(db=None):
    own = db is None
    db = db or SessionLocal()
    try:
        for p in PLANS:
            x = db.query(Plan).filter_by(code=p["code"]).first()
            if not x:
                db.add(Plan(**p))
        db.commit()
    finally:
        if own: db.close()


def demo(db, password: str):
    biz = db.query(Plan).filter_by(code="business").first()
    if not db.query(User).filter_by(email="platform@example.com").first():
        db.add(User(org_id=None, email="platform@example.com", full_name="VAICS Platform Admin", role="platform_admin", password_hash=hash_password(password),
                    email_verified=True, password_changed_at=now()))
    org = db.query(Organization).filter_by(slug="vaics-consulting").first()
    if not org:
        org = Organization(name="VAICS Consulting", slug="vaics-consulting", country="IN", region="in", status="active", plan_id=biz.id, seats=10, currency="INR",
                           current_period_end=now() + timedelta(days=30), billing_state_code="36")
        db.add(org); db.flush()
    people = [("krishna@example.com", "Krishna", "org_admin"), ("sender@example.com", "Demo Sender", "sender"),
              ("auditor@example.com", "Demo Auditor", "auditor"), ("templates@example.com", "Template Manager", "template_manager")]
    for email, name, role in people:
        if not db.query(User).filter_by(email=email).first():
            db.add(User(org_id=org.id, email=email, full_name=name, role=role, password_hash=hash_password(password), email_verified=True, password_changed_at=now()))
    db.commit()


if __name__ == "__main__":
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    ensure_plans(db)
    if "--demo" in sys.argv:
        pw = os.environ.get("DEMO_PASSWORD")
        if not pw:
            sys.exit("Set DEMO_PASSWORD (min 12 chars) to create demo users")
        demo(db, pw)
        print("Demo users: platform@example.com, krishna@example.com, sender@example.com, auditor@example.com, templates@example.com (password = $DEMO_PASSWORD)")
    print("Seed complete")
