import csv, io, json
from ..models import AuditEvent, AdminAuditLog, now
from ..core.security import sha256_hex


def client_ip(req) -> str | None:
    if req is None:
        return None
    fwd = req.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else None)


def entry_hash(e: AuditEvent) -> str:
    return sha256_hex(json.dumps([e.org_id, e.envelope_id, e.event, e.actor, e.recipient_id, e.ip, e.user_agent, e.detail,
                                  e.doc_hash, e.prev_hash, e.created_at.isoformat()], ensure_ascii=False))


def record(db, env, event: str, actor: str, req=None, detail: str = "", recipient=None) -> AuditEvent:
    prev = db.query(AuditEvent).filter_by(envelope_id=env.id).order_by(AuditEvent.id.desc()).first()
    e = AuditEvent(org_id=env.org_id, envelope_id=env.id, event=event, actor=actor or "system", recipient_id=recipient.id if recipient else None,
                   ip=client_ip(req), user_agent=(req.headers.get("user-agent", "")[:300] if req else None),
                   location=(req.headers.get("cf-ipcountry") or req.headers.get("x-geo-country")) if req else None,
                   detail=detail[:4000], doc_hash=env.completed_sha256 or env.version_hash, prev_hash=prev.entry_hash if prev else None,
                   created_at=now())
    e.entry_hash = entry_hash(e)
    db.add(e); db.flush()
    try:
        from .webhooks import emit
        emit(db, env.org_id, f"envelope.{event}", {"envelope_id": env.public_id, "event": event, "actor": actor, "at": e.created_at.isoformat() + "Z"})
    except Exception:
        pass
    return e


def verify_chain(events: list[AuditEvent]) -> tuple[bool, int | None]:
    prev = None
    for e in events:
        if e.prev_hash != prev or entry_hash(e) != e.entry_hash:
            return False, e.id
        prev = e.entry_hash
    return True, None


def admin_log(db, org_id, actor, action: str, target: str = "", before=None, after=None, req=None):
    db.add(AdminAuditLog(org_id=org_id, actor_id=getattr(actor, "id", None), actor_email=getattr(actor, "email", str(actor)),
                         action=action, target=target, before=before, after=after, ip=client_ip(req), created_at=now()))


def events_csv(events) -> str:
    b = io.StringIO(); w = csv.writer(b)
    w.writerow(["id", "utc_time", "event", "actor", "recipient_id", "ip", "user_agent", "location", "detail", "doc_hash", "prev_hash", "entry_hash"])
    for e in events:
        w.writerow([e.id, e.created_at.isoformat() + "Z", e.event, e.actor, e.recipient_id or "", e.ip or "", e.user_agent or "", e.location or "", e.detail, e.doc_hash or "", e.prev_hash or "", e.entry_hash])
    return b.getvalue()
