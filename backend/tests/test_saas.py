import hashlib, hmac, io, json
from datetime import timedelta
import pyotp
from .conftest import signup, login, draft, link_and_code, sign, outbox, make_pdf, PW
from app.core.db import SessionLocal
from app.core.config import settings
from app import models

ONE = [{"name": "Ravi", "email": "ravi@example.com", "order": 1, "auth_method": "none"}]


def test_tenant_isolation(client):
    a = signup(client, "a@example.com", "Org A")
    b = signup(client, "b@example.com", "Org B")
    env = draft(client, a, ONE)
    assert client.get(f"/api/v1/envelopes/{env['id']}", headers=b).status_code == 404
    assert client.get(f"/api/v1/envelopes/{env['id']}/documents/{env['documents'][0]['id']}/file", headers=b).status_code == 404
    assert client.post(f"/api/v1/envelopes/{env['id']}/send", headers=b).status_code == 404
    assert all(e["id"] != env["id"] for e in client.get("/api/v1/envelopes", headers=b).json()["items"])
    assert client.get("/api/v1/org/users", headers=b).json()[0]["email"] == "b@example.com"


def test_unverified_cannot_send_and_login_lockout(client):
    h = signup(client, verify=False)
    env = draft(client, h, ONE)
    assert client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h).status_code == 403
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json={"email": "krishna@example.com", "password": "wrong-password-x"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "krishna@example.com", "password": PW}).status_code == 423


def test_weak_password_rejected(client):
    r = client.post("/api/v1/auth/signup", json={"full_name": "X Y", "email": "x@example.com", "password": "password", "organization": "Org", "country": "IN", "accept_terms": True})
    assert r.status_code == 422


def test_mfa_and_password_reset(client):
    h = signup(client)
    sec = client.post("/api/v1/auth/mfa/setup", headers=h).json()["secret"]
    r = client.post("/api/v1/auth/mfa/enable", json={"code": pyotp.TOTP(sec).now()}, headers=h)
    assert r.status_code == 200, r.text
    assert client.post("/api/v1/auth/login", json={"email": "krishna@example.com", "password": PW}).json() == {"mfa_required": True}
    ok = client.post("/api/v1/auth/login", json={"email": "krishna@example.com", "password": PW, "totp": pyotp.TOTP(sec).now()})
    assert ok.status_code == 200 and ok.json()["access_token"]
    client.post("/api/v1/auth/password/forgot", json={"email": "krishna@example.com"})
    tok = outbox("reset_password", "krishna@example.com")[-1].link.rsplit("/", 1)[1]
    new = "Another-Strong-Pass-77"
    assert client.post("/api/v1/auth/password/reset", json={"token": tok, "password": new}).status_code == 200
    assert client.post("/api/v1/auth/password/reset", json={"token": tok, "password": new + "x"}).status_code == 400


def test_invitations_roles_and_seats(client):
    h = signup(client)
    assert client.post("/api/v1/org/invitations", json={"email": "viewer@example.com", "role": "viewer"}, headers=h).status_code == 201
    tok = outbox("invitation", "viewer@example.com")[-1].link.rsplit("/", 1)[1]
    assert client.post("/api/v1/auth/invitations/accept", json={"token": tok, "full_name": "View Only", "password": PW, "accept_terms": True}).status_code == 200
    v = login(client, "viewer@example.com")
    assert client.post("/api/v1/envelopes", json={"title": "x"}, headers=v).status_code == 403
    assert client.post("/api/v1/org/invitations", json={"email": "c@example.com", "role": "sender"}, headers=v).status_code == 403
    client.post("/api/v1/org/invitations", json={"email": "s2@example.com", "role": "sender"}, headers=h)
    r = client.post("/api/v1/org/invitations", json={"email": "s3@example.com", "role": "sender"}, headers=h)
    assert r.status_code == 402  # 3 seats: admin + viewer + pending s2
    log = client.get("/api/v1/org/audit-log", headers=h).json()
    assert any(x["action"] == "user.invited" for x in (log["items"] if isinstance(log, dict) else log))


def test_envelope_quota_on_free(client):
    h = signup(client, plan="free")
    for i in range(3):
        env = draft(client, h, ONE)
        assert client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h).status_code == 200
    env = draft(client, h, ONE)
    r = client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h)
    assert r.status_code == 402 and r.json()["detail"]["code"] == "quota_exceeded"


def test_api_key_scopes_idempotency_and_rate_headers(client, monkeypatch):
    h = signup(client)
    key = client.post("/api/v1/org/api-keys", json={"name": "erp", "scopes": ["envelopes:read"]}, headers=h).json()["key"]
    k = {"X-API-Key": key}
    assert client.get("/api/v1/envelopes", headers=k).status_code == 200
    assert client.post("/api/v1/envelopes", json={"title": "x"}, headers=k).status_code == 403
    key2 = client.post("/api/v1/org/api-keys", json={"name": "erp2", "scopes": ["envelopes:read", "envelopes:write"]}, headers=h).json()["key"]
    k2 = {"Authorization": f"Bearer {key2}", "Idempotency-Key": "abc-1"}
    a = client.post("/api/v1/envelopes", json={"title": "API"}, headers=k2).json()
    b = client.post("/api/v1/envelopes", json={"title": "API"}, headers=k2).json()
    assert a["id"] == b["id"]
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    r = client.get("/api/v1/envelopes", headers=k)
    assert "x-ratelimit-limit" in {x.lower() for x in r.headers}
    assert client.get("/api/v1/envelopes", headers={"X-API-Key": "vsk_bogus"}).status_code == 401


def test_webhook_signed_and_retried(client):
    from app.services import webhooks
    h = signup(client)
    secret = client.post("/api/v1/org/webhooks", json={"url": "https://hooks.example.com/x", "events": ["envelope.sent"]}, headers=h).json()["secret"]
    env = draft(client, h, ONE)
    client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h)
    calls = []

    class Fake:
        def __init__(self, code): self.code = code
        def post(self, url, content, headers):
            calls.append((content, headers)); return type("R", (), {"status_code": self.code})()
    with SessionLocal() as s:
        assert webhooks.deliver_due(s, Fake(500)) == 1
        d = s.query(models.WebhookDelivery).first()
        assert d.status == "retrying" and d.attempts == 1
        d.next_attempt_at = models.now(); s.commit()
        webhooks.deliver_due(s, Fake(200))
        assert s.query(models.WebhookDelivery).first().status == "delivered"
    body, hd = calls[-1]
    t, v1 = [p.split("=", 1)[1] for p in hd["X-VAICS-Signature"].split(",")]
    assert hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest() == v1


def test_billing_not_live_and_webhook_signature(client, monkeypatch):
    h = signup(client)
    r = client.post("/api/v1/billing/checkout", json={"plan": "standard", "cycle": "monthly", "seats": 1}, headers=h)
    assert r.status_code == 503  # provider not configured: no fake success
    with SessionLocal() as s:
        inv = s.query(models.Invoice).first()
        assert inv.total > inv.subtotal and inv.status == "open"  # GST computed
        number = inv.number
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "whtest")
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_1", "notes": {"invoice": number}}}}}).encode()
    assert client.post("/api/v1/billing/webhooks/razorpay", content=body, headers={"X-Razorpay-Signature": "bad"}).status_code == 400
    sig = hmac.new(b"whtest", body, hashlib.sha256).hexdigest()
    assert client.post("/api/v1/billing/webhooks/razorpay", content=body, headers={"X-Razorpay-Signature": sig}).json()["handled"] is True
    sub = client.get("/api/v1/billing/subscription", headers=h).json()
    assert sub["plan"]["code"] == "standard" and sub["status"] == "active"
    assert client.get("/api/v1/billing/invoices/1/pdf", headers=h).content[:4] == b"%PDF"


def test_templates_bulk_powerform(client):
    h = signup(client)
    env = draft(client, h, [{"name": "Ravi", "email": "ravi@example.com", "order": 1, "auth_method": "none", "role_name": "Client"}])
    t = client.post("/api/v1/templates", json={"envelope_id": env["id"], "name": "NDA", "sharing": "org"}, headers=h)
    assert t.status_code == 201, t.text
    tid = t.json()["id"]
    u = client.post("/api/v1/templates/use", json={"template_ids": [tid], "roles": [{"name": "Anu", "email": "anu@example.com"}], "send": True}, headers=h)
    assert u.status_code == 201, u.text
    assert outbox("signing_link", "anu@example.com")
    csv = "role1_name,role1_email\nA One,a1@example.com\nBad,not-an-email\n"
    j = client.post("/api/v1/bulk", data={"template_id": str(tid), "name": "Q4"}, files={"file": ("l.csv", csv, "text/csv")}, headers=h).json()
    assert j["total"] == 2 and j["valid"] == 1
    s = client.post(f"/api/v1/bulk/{j['id']}/send", headers=h).json()
    assert s["sent"] == 1
    assert "not a valid email" in client.get(f"/api/v1/bulk/{j['id']}/report.csv", headers=h).text
    # powerform: template with single role
    pf = client.post("/api/v1/powerforms", json={"template_id": tid, "name": "Self-serve NDA", "max_uses": 1}, headers=h)
    assert pf.status_code == 201, pf.text
    slug = pf.json()["slug"]
    vid = client.post(f"/api/v1/public/pf/{slug}/start", json={"name": "Walk Up", "email": "walk@example.com"}).json()["verification_id"]
    code = outbox("powerform_verify", "walk@example.com")[-1].secret
    r = client.post(f"/api/v1/public/pf/{slug}/verify", json={"verification_id": vid, "code": code})
    assert r.status_code == 200, r.text
    assert r.json()["token"]
    assert client.get(f"/api/v1/public/pf/{slug}").status_code == 410  # max uses reached


def test_retention_legal_hold_and_dsr(client):
    from app.services import retention
    h = signup(client)
    env = draft(client, h, ONE)
    client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h)
    tok, _ = link_and_code("ravi@example.com"); sign(client, tok, None)
    assert client.post(f"/api/v1/envelopes/{env['id']}/legal-hold", json={"hold": True}, headers=h).status_code == 200
    with SessionLocal() as s:
        e = s.get(models.Envelope, env["id"]); e.completed_at = models.now() - timedelta(days=4000); s.commit()
        assert retention.run_retention(s) == 0
        e = s.get(models.Envelope, env["id"]); e.legal_hold = False; s.commit()
        assert retention.run_retention(s) == 1
        assert s.query(models.DeletionRecord).count() == 1
    assert client.get(f"/api/v1/envelopes/{env['id']}/completed", headers=h).status_code in (404, 410)
    r = client.post("/api/v1/privacy/dsr", json={"email": "ravi@example.com", "kind": "access"}, headers=h).json()
    assert r["recipients"]
    assert client.get("/api/v1/privacy/export", headers=h).content[:2] == b"PK"


def test_audit_exports_reports_headers(client):
    h = signup(client)
    env = draft(client, h, ONE)
    client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h)
    tok, _ = link_and_code("ravi@example.com"); sign(client, tok, None)
    assert "event" in client.get(f"/api/v1/envelopes/{env['id']}/audit?format=csv", headers=h).text
    assert client.get(f"/api/v1/envelopes/{env['id']}/evidence", headers=h).content[:2] == b"PK"
    rep = client.get("/api/v1/reports/summary?days=30", headers=h).json()
    assert rep["total"]["completed"] == 1
    r = client.get("/api/health")
    assert r.headers["x-frame-options"] and "content-security-policy" in {k.lower() for k in r.headers}
    pub = client.get(f"/api/v1/public/verify/{env['public_id']}").json()
    assert pub["status"] == "completed"


def test_platform_admin(client):
    h = signup(client)
    with SessionLocal() as s:
        from app.core.security import hash_password
        s.add(models.User(org_id=None, email="ops@example.com", full_name="Ops", role="platform_admin", password_hash=hash_password(PW), email_verified=True)); s.commit()
    ph = login(client, "ops@example.com")
    assert client.get("/api/v1/platform/tenants", headers=h).status_code == 403
    ten = client.get("/api/v1/platform/tenants", headers=ph).json()
    oid = ten[0]["id"]
    assert client.get(f"/api/v1/platform/tenants/{oid}/envelopes", headers=ph).status_code == 403  # no support access granted
    assert client.post(f"/api/v1/platform/tenants/{oid}/status", json={"status": "suspended", "reason": "test"}, headers=ph).status_code == 200
    assert client.get("/api/v1/envelopes", headers=h).status_code == 403
    hl = client.get("/api/v1/platform/health", headers=ph).json()
    assert hl["email"] == "dev_outbox" and all(v["implemented"] is False for v in hl["signature_providers"])
