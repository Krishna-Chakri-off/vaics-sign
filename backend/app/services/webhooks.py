"""Outgoing webhooks: HMAC-SHA256 signed (header X-VAICS-Signature: t=<unix>,v1=<hex>), retried with exponential back-off, logged."""
import hashlib, hmac, json, time
from datetime import timedelta
from ..models import Webhook, WebhookDelivery, now

BACKOFF_MIN = [1, 5, 30, 120, 720]  # minutes; then failed


def sign(secret: str, body: bytes, ts: int) -> str:
    return hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()


def emit(db, org_id: int, event: str, data: dict):
    for wh in db.query(Webhook).filter_by(org_id=org_id, active=True).all():
        if wh.events and event not in wh.events and "*" not in wh.events:
            continue
        db.add(WebhookDelivery(webhook_id=wh.id, org_id=org_id, event=event, payload={"event": event, "data": data}, next_attempt_at=now()))


def deliver_due(db, client=None, limit: int = 100) -> int:
    import httpx
    client = client or httpx.Client(timeout=10)
    n = 0
    for d in db.query(WebhookDelivery).filter(WebhookDelivery.status.in_(("pending", "retrying")), WebhookDelivery.next_attempt_at <= now()).limit(limit):
        wh = db.get(Webhook, d.webhook_id)
        body = json.dumps({**d.payload, "delivery_id": d.id}, separators=(",", ":")).encode()
        ts = int(time.time())
        d.attempts += 1
        try:
            r = client.post(wh.url, content=body, headers={"Content-Type": "application/json", "X-VAICS-Event": d.event,
                                                           "X-VAICS-Signature": f"t={ts},v1={sign(wh.secret, body, ts)}"})
            d.response_code = r.status_code
            ok = 200 <= r.status_code < 300
            d.error = None if ok else f"HTTP {r.status_code}"
        except Exception as ex:  # noqa: BLE001
            ok, d.error = False, str(ex)[:300]
        if ok:
            d.status = "delivered"
        elif d.attempts > len(BACKOFF_MIN):
            d.status = "failed"
        else:
            d.status, d.next_attempt_at = "retrying", now() + timedelta(minutes=BACKOFF_MIN[d.attempts - 1])
        n += 1
    db.commit()
    return n
