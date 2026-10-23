"""Plan entitlements, metering and quota enforcement (warnings at 80% and 100%)."""
from fastapi import HTTPException
from sqlalchemy import func
from ..models import UsageRecord, Credit, User, now
from . import notify

METRIC_LIMIT = {"envelopes": "envelopes_per_month", "sms": "sms_per_month", "api_calls": "api_calls_per_month",
                "aadhaar": "aadhaar_per_month", "dsc": "dsc_per_month", "idv": "idv_per_month"}


def period() -> str:
    return now().strftime("%Y-%m")


def feature(org, name: str) -> bool:
    return bool(org.plan and (org.plan.features or {}).get(name))


def require_feature(org, name: str, label: str | None = None):
    if not feature(org, name):
        raise HTTPException(402, {"code": "upgrade_required", "feature": name, "message": f"{label or name} is not included in your plan. Upgrade to use it."})


def used(db, org_id: int, metric: str, per: str | None = None) -> int:
    return int(db.query(func.coalesce(func.sum(UsageRecord.quantity), 0)).filter_by(org_id=org_id, metric=metric, period=per or period()).scalar() or 0)


def credits(db, org_id: int, metric: str) -> int:
    return int(db.query(func.coalesce(func.sum(Credit.quantity), 0)).filter_by(org_id=org_id, metric=metric).scalar() or 0)


def limit_of(org, metric: str):
    lim = (org.plan.limits or {}).get(METRIC_LIMIT.get(metric, metric)) if org.plan else 0
    return None if lim in (None, -1) else int(lim)


def check_and_record(db, org, metric: str, qty: int = 1):
    """Raise 402 if the quota (+ purchased credits, or allowed overage) would be exceeded; else record usage and warn at 80%/100%."""
    lim = limit_of(org, metric)
    cur = used(db, org.id, metric)
    if lim is not None:
        allowance = lim + credits(db, org.id, metric)
        overage = bool((org.plan.features or {}).get("overage_billing")) and org.settings.get("allow_overage")
        if cur + qty > allowance and not overage:
            raise HTTPException(402, {"code": "quota_exceeded", "metric": metric, "limit": allowance, "used": cur,
                                      "message": f"Monthly {metric} limit reached ({cur}/{allowance}). Upgrade or buy credits."})
    db.add(UsageRecord(org_id=org.id, metric=metric, quantity=qty, period=period()))
    if lim:
        before, after = cur / lim, (cur + qty) / lim
        for th in (0.8, 1.0):
            if before < th <= after:
                for admin in db.query(User).filter_by(org_id=org.id, role="org_admin", is_active=True):
                    notify.notify_user(db, admin.id, f"Usage warning: {int(th * 100)}% of monthly {metric} quota used ({cur + qty}/{lim}).")
                    notify.send_email(db, org=org, to=admin.email, kind="usage_warning", subject=f"{int(th * 100)}% of your {metric} quota used",
                                      body=f"Your organization has used {cur + qty} of {lim} {metric} this month.")


def summary(db, org) -> dict:
    out = {}
    for m in ("envelopes", "sms", "api_calls", "aadhaar", "dsc", "idv"):
        lim = limit_of(org, m); u = used(db, org.id, m)
        out[m] = {"used": u, "limit": lim, "credits": credits(db, org.id, m), "pct": round(100 * u / lim) if lim else None}
    seats = db.query(User).filter_by(org_id=org.id, is_active=True).count()
    out["seats"] = {"used": seats, "limit": org.seats}
    return out
