"""Reports (FR-171..175): volume, turnaround, completion/decline rates by user, template and period; CSV export."""
import csv, io
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from ..core.db import get_db
from ..models import Envelope, User, Template, now
from .deps import Principal, perm

router = APIRouter(prefix="/reports", tags=["reports"])


def _rows(db, p: Principal, start: datetime, end: datetime):
    q = db.query(Envelope).filter(Envelope.org_id == p.org.id, Envelope.sent_at.isnot(None), Envelope.sent_at >= start, Envelope.sent_at < end, Envelope.is_sandbox.is_(False))
    if not p.can("reports.view_all") and not p.can("envelopes.view_all"):
        q = q.filter(Envelope.owner_id == p.user.id)
    return q.all()


def _agg(envs):
    sent = len(envs)
    done = [e for e in envs if e.status == "completed"]
    tat = [(e.completed_at - e.sent_at).total_seconds() / 3600 for e in done if e.completed_at]
    return {"sent": sent, "completed": len(done), "declined": sum(e.status == "declined" for e in envs), "voided": sum(e.status == "voided" for e in envs),
            "expired": sum(e.status == "expired" for e in envs), "in_progress": sum(e.status in ("sent", "delivered", "partially_signed") for e in envs),
            "completion_rate": round(len(done) / sent * 100, 1) if sent else 0.0,
            "decline_rate": round(sum(e.status == "declined" for e in envs) / sent * 100, 1) if sent else 0.0,
            "avg_turnaround_hours": round(sum(tat) / len(tat), 1) if tat else None}


@router.get("/summary")
def summary(days: int = Query(30, ge=1, le=3650), group_by: str = Query("period", pattern="^(period|user|template)$"),
            p: Principal = Depends(perm("reports.view")), db: Session = Depends(get_db)):
    end = now(); start = end - timedelta(days=days)
    envs = _rows(db, p, start, end)
    groups = defaultdict(list)
    for e in envs:
        if group_by == "period": k = e.sent_at.strftime("%Y-%m-%d" if days <= 62 else "%Y-%m")
        elif group_by == "user": k = (db.get(User, e.owner_id).email)
        else: k = db.get(Template, e.template_id).name if e.template_id and db.get(Template, e.template_id) else "(no template)"
        groups[k].append(e)
    return {"from": start, "to": end, "total": _agg(envs), "groups": [{"key": k, **_agg(v)} for k, v in sorted(groups.items())]}


@router.get("/summary.csv")
def summary_csv(days: int = 30, group_by: str = "period", p: Principal = Depends(perm("reports.view")), db: Session = Depends(get_db)):
    data = summary(days, group_by, p, db)
    b = io.StringIO(); w = csv.writer(b)
    cols = ["key", "sent", "completed", "declined", "voided", "expired", "in_progress", "completion_rate", "decline_rate", "avg_turnaround_hours"]
    w.writerow(cols)
    for g in data["groups"]: w.writerow([g[c] for c in cols])
    w.writerow(["TOTAL"] + [data["total"][c] for c in cols[1:]])
    return Response(b.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="vaics-sign-report-{group_by}-{days}d.csv"'})
