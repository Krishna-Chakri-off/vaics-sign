from ..models import Envelope, User
from ..services.workflow import current_step

R_KEYS = ("id", "role_name", "type", "name", "email", "phone", "order", "language", "private_message", "auth_method", "sender_set_code", "host_user_id",
          "status", "notified_at", "completed_at", "completed_ip", "decline_reason", "code_locked", "code_attempts", "reminders_sent", "email_status", "signature_type")
F_KEYS = ("id", "document_id", "recipient_id", "type", "page", "x", "y", "w", "h", "required", "read_only", "reason_required", "label", "tooltip", "default_value",
          "options", "validation", "regex", "font_size", "group_name", "condition", "formula", "value", "reason", "signed_at", "field_hash")


def envelope_out(db, env: Envelope, full: bool = False) -> dict:
    owner = db.get(User, env.owner_id)
    step = {r.id for r in current_step(env)} if env.status in ("sent", "delivered", "partially_signed") else set()
    out = {k: getattr(env, k) for k in ("id", "public_id", "title", "message", "status", "visibility", "group_id", "labels", "folder", "template_id", "template_version",
                                         "bulk_job_id", "language", "expires_at", "sent_at", "completed_at", "created_at", "updated_at", "version_hash", "completed_sha256",
                                         "sealed", "void_reason", "legal_hold", "is_sandbox", "reminder_first_days", "reminder_every_days", "sender_notify", "brand", "purged_at")}
    out["owner"] = {"id": owner.id, "name": owner.full_name, "email": owner.email} if owner else None
    out["recipients"] = [{**{k: getattr(r, k) for k in R_KEYS}, "current": r.id in step} for r in env.recipients]
    out["documents"] = [{"id": d.id, "order": d.order, "name": d.name, "source_name": d.source_name, "source_type": d.source_type, "sha256": d.sha256,
                         "source_sha256": d.source_sha256, "size": d.size, "pages": d.pages} for d in env.documents]
    if full:
        out["fields"] = [{k: getattr(f, k) for k in F_KEYS} for f in env.fields]
    else:
        out["field_count"] = len(env.fields)
    return out
