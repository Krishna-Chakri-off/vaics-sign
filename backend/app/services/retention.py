"""Retention, deletion, tenant closure and data-subject erasure (FR-163..170, FR-195..199).
Purging removes document content, field values and signature images; the envelope row, hashes and the
hash-chained audit trail are kept as minimal evidence plus a DeletionRecord ("deletion certificate")."""
from datetime import timedelta
from ..models import Envelope, Recipient, Field, Template, DeletionRecord, Organization, User, now
from . import audit
from .storage import storage
from .workflow import org_settings

PURGE_AFTER = {"draft": "draft_days", "completed": "completed_days", "declined": "declined_days", "voided": "voided_days", "expired": "expired_days"}


def _keys(env: Envelope):
    ks = [d.storage_key for d in env.documents]
    ks += [k for k in (env.completed_key, env.certificate_key) if k]
    return ks


def purge_envelope(db, org: Organization, env: Envelope, reason: str, actor: str, req=None) -> None:
    if env.legal_hold:
        raise ValueError("legal hold")
    template_keys = {d["storage_key"] for t in db.query(Template).filter_by(org_id=org.id) for d in (t.documents or [])}
    for k in _keys(env):
        if k in template_keys: continue  # template still references the source file
        try:
            storage().delete(org.region, k)
        except Exception:  # noqa: BLE001
            pass
    for f in env.fields:
        f.value, f.default_value = None, None
    for r in env.recipients:
        r.signature_image = r.initials_image = None
        r.token_hash = r.session_hash = r.download_hash = r.code_hash = None
        r.token_revoked = True
    for d in env.documents:
        d.text = ""
    env.search_text, env.completed_key, env.certificate_key = "", None, None
    env.purged_at = now()
    if reason == "user_delete": env.deleted_at = now()
    audit.record(db, env, "purged", actor, req, f"reason={reason}; documents and field values deleted, audit evidence retained")
    db.add(DeletionRecord(org_id=org.id, envelope_public_id=env.public_id, reason=reason,
                          detail=f"{len(env.documents)} document(s); completed sha256 {env.completed_sha256 or '-'}; by {actor}"))


def run_retention(db) -> int:
    n = 0
    for org in db.query(Organization).all():
        ret = org_settings(org)["retention"]
        for status, key in PURGE_AFTER.items():
            days = ret.get(key)
            if not days or int(days) <= 0: continue
            cutoff = now() - timedelta(days=int(days))
            q = db.query(Envelope).filter(Envelope.org_id == org.id, Envelope.status == status, Envelope.purged_at.is_(None), Envelope.legal_hold.is_(False),
                                          (Envelope.completed_at if status == "completed" else Envelope.updated_at) < cutoff)
            for env in q.limit(500):
                purge_envelope(db, org, env, "retention", "system"); n += 1
        if org.status == "closed" and org.closed_at and org.closed_at < now() - timedelta(days=30):
            n += close_tenant_purge(db, org)
    db.commit()
    return n


def close_tenant_purge(db, org: Organization) -> int:
    """After the 30-day export window, purge every envelope of a closed tenant (legal holds excepted)."""
    n = 0
    for env in db.query(Envelope).filter(Envelope.org_id == org.id, Envelope.purged_at.is_(None), Envelope.legal_hold.is_(False)):
        purge_envelope(db, org, env, "tenant_closure", "system"); n += 1
    return n


def erase_subject(db, org: Organization, email: str, actor) -> dict:
    """DSR erasure: pseudonymise the person in open/draft envelopes and contacts; completed signed records are
    retained where the law requires (reported back, not silently skipped)."""
    from ..models import Contact
    email = email.lower()
    kept, scrubbed = [], 0
    for r in db.query(Recipient).join(Envelope, Envelope.id == Recipient.envelope_id).filter(Envelope.org_id == org.id, Recipient.email == email):
        env = db.get(Envelope, r.envelope_id)
        if env.status == "completed" or env.legal_hold:
            kept.append(env.public_id); continue
        r.name, r.email, r.phone = "Erased person", f"erased-{r.id}@invalid", None
        r.signature_image = r.initials_image = None
        scrubbed += 1
    c = db.query(Contact).filter_by(org_id=org.id, email=email).delete()
    return {"recipients_pseudonymised": scrubbed, "contacts_deleted": c, "retained_completed_records": kept,
            "note": "Completed signed records are retained under the organization's legal retention obligations." if kept else ""}
