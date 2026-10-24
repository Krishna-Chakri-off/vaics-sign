"""Phase 1 (internal VAICS): no SaaS surfaces, signer intent required, self-service privacy requests."""
from .conftest import signup, login, draft, link_and_code, outbox, PW


def test_saas_surfaces_removed(client):
    h = signup(client)
    r = client.post("/api/v1/auth/signup", json={"full_name": "Xavier Yu", "email": "x@example.com", "password": PW, "organization": "Org", "country": "IN", "accept_terms": True})
    assert r.status_code in (404, 405)
    for path in ("/api/v1/billing/subscription", "/api/v1/platform/tenants", "/api/v1/org/api-keys", "/api/v1/org/webhooks", "/api/v1/powerforms", "/api/v1/org/usage"):
        assert client.get(path, headers=h).status_code == 404, path
    me = client.get("/api/v1/auth/me", headers=h).json()
    assert "plan" not in str(me.get("org", {})) and "features" not in (me.get("org") or {})
    assert client.get("/api/v1/envelopes/dashboard", headers=h).status_code == 200


def test_in_person_signing_always_available(client):
    h = signup(client)
    me = client.get("/api/v1/auth/me", headers=h).json()
    e = client.post("/api/v1/envelopes", json={"title": "In person"}, headers=h).json()
    r = client.put(f"/api/v1/envelopes/{e['id']}", json={"recipients": [{"name": "Walk In", "email": "walkin@example.com", "type": "in_person", "order": 1, "host_user_id": me["id"]}]}, headers=h)
    assert r.status_code == 200, r.text
    assert "plan" not in r.text.lower()


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
