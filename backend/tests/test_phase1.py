"""Phase 1 (internal VAICS) mode: SaaS surfaces off, signer intent required, self-service privacy requests."""
from app.core.config import settings
from .conftest import signup, login, draft, link_and_code, outbox, PW


def test_saas_surfaces_disabled(client, monkeypatch):
    h = signup(client)
    monkeypatch.setattr(settings, "SAAS_MODE", False)
    r = client.post("/api/v1/auth/signup", json={"full_name": "Xavier Yu", "email": "x@example.com", "password": PW, "organization": "Org", "country": "IN", "accept_terms": True})
    assert r.status_code == 404
    assert client.get("/api/v1/billing/subscription", headers=h).status_code == 404
    assert client.get("/api/v1/envelopes/dashboard", headers=h).status_code == 200


def test_intent_required_and_audited(client):
    h = signup(client)
    e = draft(client, h, [{"name": "Rep", "email": "rep@example.com", "order": 1}])
    assert client.post(f"/api/v1/envelopes/{e['id']}/send", headers=h).status_code == 200
    tok, code = link_and_code("rep@example.com")
    sh = {"X-Signer-Session": client.post(f"/api/v1/public/s/{tok}/unlock", json={"code": code}).json()["session"]}
    fields = client.get(f"/api/v1/public/s/{tok}/envelope", headers=sh).json()["fields"]
    reasons = {f["id"]: "Approved" for f in fields}
    body = {"consent": True, "signature": {"kind": "typed"}, "reasons": reasons}
    assert client.post(f"/api/v1/public/s/{tok}/finish", json=body, headers=sh).status_code == 422
    r = client.post(f"/api/v1/public/s/{tok}/finish", json={**body, "intent": True, "signature_meaning": "Reviewed"}, headers=sh)
    assert r.status_code == 200, r.text
    ev = client.get(f"/api/v1/envelopes/{e['id']}/audit", headers=h)
    assert ev.status_code == 200
    assert any(x["event"] == "signature_intent_affirmed" and "Reviewed" in x["detail"] for x in ev.json()["events"])


def test_self_service_export_requires_admin_approval(client):
    h = signup(client)
    r = client.post("/api/v1/privacy/my-requests", json={"kind": "export"}, headers=h)
    assert r.status_code == 201
    rid = r.json()["id"]
    assert client.get(f"/api/v1/privacy/my-requests/{rid}/download", headers=h).status_code == 409
    assert client.post(f"/api/v1/privacy/dsr/{rid}/decide", json={"approve": True}, headers=h).status_code == 200
    d = client.get(f"/api/v1/privacy/my-requests/{rid}/download", headers=h)
    assert d.status_code == 200 and d.json()["profile"]["email"] == "krishna@example.com"
