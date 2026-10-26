import io
from pypdf import PdfReader
from .conftest import signup, draft, link_and_code, sign, outbox, make_pdf, login
from app.core.db import SessionLocal
from app import models

R = [{"name": "Ravi VAICS", "email": "ravi@example.com", "order": 1, "auth_method": "access_code"},
     {"name": "Client Counter", "email": "client@example.org", "order": 2, "auth_method": "access_code"}]


def test_krishna_two_signer_flow(client):
    h = signup(client)
    env = draft(client, h, R, fields_per=2)
    r = client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["email_mode"] == "dev_outbox"
    # signer 2 has not been notified yet (strict order)
    assert not outbox("signing_link", "client@example.org")
    tok1, code1 = link_and_code("ravi@example.com")
    assert code1 and code1.isdigit() and 6 <= len(code1) <= 8
    # the code is in a separate email from the link
    assert code1 not in outbox("signing_link", "ravi@example.com")[-1].body
    sign(client, tok1, code1, reason="Approved on behalf of VAICS")
    tok2, code2 = link_and_code("client@example.org")
    out = sign(client, tok2, code2, reason="Countersigned")
    assert out["completed"] is True
    done = outbox("completed")
    assert {m.to for m in done} == {"krishna@example.com", "ravi@example.com", "client@example.org"}
    pdf = client.get(f"/api/v1/envelopes/{env['id']}/completed", headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    reader = PdfReader(io.BytesIO(pdf.content))
    text = "".join(p.extract_text() or "" for p in reader.pages)
    assert "Approved on behalf of VAICS" in text and "Countersigned" in text and "IST" in text and "UTC" in text
    assert "Certificate of Completion" in text
    # audit chain verifies
    a = client.get(f"/api/v1/envelopes/{env['id']}/audit", headers=h).json()
    assert a["chain_valid"] is True


def test_order_enforced_and_wrong_code_lockout(client):
    h = signup(client)
    env = draft(client, h, R)
    client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h)
    tok1, code1 = link_and_code("ravi@example.com")
    bad = "0" * len(code1) if code1 != "0" * len(code1) else "1" * len(code1)
    for i in range(4):
        r = client.post(f"/api/v1/public/s/{tok1}/unlock", json={"code": bad})
        assert r.status_code == 403
    r = client.post(f"/api/v1/public/s/{tok1}/unlock", json={"code": bad})
    assert r.status_code == 423
    assert client.post(f"/api/v1/public/s/{tok1}/unlock", json={"code": code1}).status_code == 423
    assert outbox("recipient_locked", "krishna@example.com")
    # reissue gives a new link + code, old link dead
    rid = [x for x in client.get(f"/api/v1/envelopes/{env['id']}", headers=h).json()["recipients"] if x["order"] == 1][0]["id"]
    assert client.post(f"/api/v1/envelopes/{env['id']}/recipients/{rid}/reissue", json={}, headers=h).status_code == 200
    assert client.get(f"/api/v1/public/s/{tok1}").status_code == 404
    tok1b, code1b = link_and_code("ravi@example.com")
    sign(client, tok1b, code1b)


def test_not_your_turn(client):
    h = signup(client)
    env = draft(client, h, [{**R[0], "auth_method": "none"}, {**R[1], "auth_method": "none"}])
    client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h)
    # forge: signer 2 has no link yet; signer1 link works
    tok1, _ = link_and_code("ravi@example.com")
    assert client.get(f"/api/v1/public/s/{tok1}").status_code == 200


def test_parallel_routing_works(client):
    h = signup(client)
    rs = [{**R[0], "order": 1, "auth_method": "none"}, {**R[1], "order": 1, "auth_method": "none"}]
    env = draft(client, h, rs)
    assert client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h).status_code == 200
    assert outbox("signing_link", "ravi@example.com") and outbox("signing_link", "client@example.org")
    t2, _ = link_and_code("client@example.org")
    sign(client, t2, None)
    t1, _ = link_and_code("ravi@example.com")
    assert sign(client, t1, None)["completed"]


def test_reason_required(client):
    h = signup(client)
    env = draft(client, h, [{**R[0], "auth_method": "none"}])
    client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h)
    tok, _ = link_and_code("ravi@example.com")
    s = client.post(f"/api/v1/public/s/{tok}/open").json()["session"]
    r = client.post(f"/api/v1/public/s/{tok}/finish", json={"consent": True, "intent": True, "signature": {"kind": "typed"}, "reasons": {}}, headers={"X-Signer-Session": s})
    assert r.status_code == 422 and "reason" in r.text.lower()


def test_session_required(client):
    h = signup(client)
    env = draft(client, h, [R[0]])
    client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h)
    tok, _ = link_and_code("ravi@example.com")
    assert client.get(f"/api/v1/public/s/{tok}/envelope").status_code in (401, 403)


def test_email_otp(client):
    h = signup(client)
    env = draft(client, h, [{**R[0], "auth_method": "email_otp"}])
    client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h)
    tok, _ = link_and_code("ravi@example.com")
    assert client.post(f"/api/v1/public/s/{tok}/otp").status_code == 200
    code = outbox("otp", "ravi@example.com")[-1].secret
    r = client.post(f"/api/v1/public/s/{tok}/unlock", json={"code": code})
    assert r.status_code == 200


def test_decline_void_and_completed_reaccess(client):
    h = signup(client)
    env = draft(client, h, [{**R[0], "auth_method": "none"}])
    client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h)
    tok, _ = link_and_code("ravi@example.com")
    s = client.post(f"/api/v1/public/s/{tok}/open").json()["session"]
    assert client.post(f"/api/v1/public/s/{tok}/decline", json={"reason": "Wrong amount"}, headers={"X-Signer-Session": s}).json()["status"] == "declined"
    assert outbox("declined", "krishna@example.com")
    env2 = draft(client, h, [{**R[0], "auth_method": "none"}])
    client.post(f"/api/v1/envelopes/{env2['id']}/send", headers=h)
    assert client.post(f"/api/v1/envelopes/{env2['id']}/void", json={"reason": "Superseded"}, headers=h).status_code == 200
    env3 = draft(client, h, [{**R[0], "auth_method": "none"}])
    client.post(f"/api/v1/envelopes/{env3['id']}/send", headers=h)
    t3, _ = link_and_code("ravi@example.com")
    sign(client, t3, None)
    dl = [m for m in outbox("completed", "ravi@example.com")][-1].link.rsplit("/", 1)[1]
    assert client.post(f"/api/v1/public/completed/{dl}/download", json={"code": "000000"}).status_code == 403
    client.post(f"/api/v1/public/completed/{dl}/otp")
    code = outbox("otp", "ravi@example.com")[-1].secret
    r = client.post(f"/api/v1/public/completed/{dl}/download", json={"code": code})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


def test_rotated_page_stamp_and_seal(client):
    h = signup(client)
    env = draft(client, h, [{**R[0], "auth_method": "none"}], pdf=make_pdf(rotate=90))
    client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h)
    tok, _ = link_and_code("ravi@example.com")
    sign(client, tok, None, reason="Rotated OK")
    pdf = client.get(f"/api/v1/envelopes/{env['id']}/completed", headers=h).content
    assert "Rotated OK" in PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    v = client.post("/api/v1/public/verify", files={"file": ("x.pdf", pdf, "application/pdf")}).json()
    assert v["matches_record"] is True
    assert v["signature"]["signatures"] >= 1 and v["signature"]["results"][0]["intact"] is True
    tampered = pdf + b"\n%tamper"
    assert client.post("/api/v1/public/verify", files={"file": ("x.pdf", tampered, "application/pdf")}).json()["matches_record"] is False


def test_in_person(client):
    h = signup(client)
    me = client.get("/api/v1/auth/me", headers=h).json()
    uid = me.get("id") or me["user"]["id"]
    env = draft(client, h, [{"name": "Walk In", "email": "walkin@example.org", "type": "in_person", "order": 1, "host_user_id": uid}])
    assert client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h).status_code == 200
    rid = client.get(f"/api/v1/envelopes/{env['id']}", headers=h).json()["recipients"][0]["id"]
    r = client.post(f"/api/v1/envelopes/{env['id']}/recipients/{rid}/in-person", json={"id_type": "PAN", "id_number": "ABCDE1234F", "confirmed": True}, headers=h)
    assert r.status_code == 200, r.text
    tok, sess = r.json()["token"], r.json()["session"]
    sh = {"X-Signer-Session": sess}
    fields = client.get(f"/api/v1/public/s/{tok}/envelope", headers=sh).json()["fields"]
    out = client.post(f"/api/v1/public/s/{tok}/finish", json={"consent": True, "intent": True, "signature": {"kind": "typed"}, "reasons": {f["id"]: "In person" for f in fields}}, headers=sh)
    assert out.status_code == 200 and out.json()["completed"]


def test_expiry_job_and_reminders(client):
    from datetime import timedelta
    from app.services import jobs
    h = signup(client)
    env = draft(client, h, [{**R[0], "auth_method": "none"}])
    client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h)
    with SessionLocal() as s:
        r = s.query(models.Recipient).first(); r.notified_at = models.now() - timedelta(days=3); s.commit()
        assert jobs.reminders(s) == 1
    assert outbox("reminder", "ravi@example.com")
    with SessionLocal() as s:
        e = s.get(models.Envelope, env["id"]); e.expires_at = models.now() - timedelta(minutes=1); s.commit()
        jobs.expire(s)
        assert s.get(models.Envelope, env["id"]).status == "expired"


def test_countersigner_sees_prior_signature_only_after_signing(client):
    h = signup(client)
    env = draft(client, h, [{**R[0], "auth_method": "none"}, {**R[1], "auth_method": "none"}])
    client.post(f"/api/v1/envelopes/{env['id']}/send", headers=h)
    tok1, _ = link_and_code("ravi@example.com")
    s1 = client.post(f"/api/v1/public/s/{tok1}/open").json()["session"]
    e1 = client.get(f"/api/v1/public/s/{tok1}/envelope", headers={"X-Signer-Session": s1}).json()
    assert e1["completed_fields"] == []  # nobody has signed yet
    reasons = {f["id"]: "For VAICS" for f in e1["fields"]}
    r = client.post(f"/api/v1/public/s/{tok1}/finish", json={"consent": True, "intent": True, "signature_meaning": "Approved", "signature": {"kind": "typed", "style": "allura"}, "reasons": reasons}, headers={"X-Signer-Session": s1})
    assert r.status_code == 200, r.text
    tok2, _ = link_and_code("client@example.org")
    s2 = client.post(f"/api/v1/public/s/{tok2}/open").json()["session"]
    e2 = client.get(f"/api/v1/public/s/{tok2}/envelope", headers={"X-Signer-Session": s2}).json()
    prior = e2["completed_fields"]
    assert len(prior) == 1 and prior[0]["by"] == "Ravi VAICS" and prior[0]["reason"] == "For VAICS" and prior[0]["signed_at"]
    assert all("email" not in f and "access_code" not in f for f in prior)
    assert all(f["id"] not in {p["id"] for p in prior} for f in e2["fields"])
