import io
from pypdf import PdfReader
from .conftest import signup, link_and_code, sign, make_pdf, login, PW
from app.core.db import SessionLocal
from app import models


def png(color=(200, 0, 0, 255)):
    from PIL import Image
    b = io.BytesIO(); Image.new("RGBA", (60, 40), color).save(b, "PNG"); return b.getvalue()


def add_user(email, role):
    from app.core.security import hash_password
    with SessionLocal() as s:
        o = s.query(models.Organization).first()
        s.add(models.User(org_id=o.id, email=email, full_name=email.split("@")[0], role=role, password_hash=hash_password(PW), email_verified=True, password_changed_at=models.now()))
        s.commit()


def stamp_draft(client, h, rep_email="krishna@example.com"):
    e = client.post("/api/v1/envelopes", json={"title": "Stamped"}, headers=h).json()
    doc = client.post(f"/api/v1/envelopes/{e['id']}/documents", files={"file": ("a.pdf", make_pdf(), "application/pdf")}, headers=h).json()
    doc_id = doc["id"] if "id" in doc else doc["documents"][-1]["id"]
    rs = [{"name": "Krishna", "email": rep_email, "order": 1, "type": "signer", "auth_method": "access_code", "role_name": "VAICS representative"},
          {"name": "Client", "email": "client@example.org", "order": 2, "type": "signer", "auth_method": "access_code", "role_name": "Countersigner"}]
    f = [{"recipient": "0", "document_id": doc_id, "type": "signature", "page": 1, "x": 0.1, "y": 0.6, "w": 0.25, "h": 0.1},
         {"recipient": "0", "document_id": doc_id, "type": "stamp", "page": 1, "x": 0.5, "y": 0.6, "w": 0.18, "h": 0.1},
         {"recipient": "1", "document_id": doc_id, "type": "signature", "page": 1, "x": 0.1, "y": 0.75, "w": 0.25, "h": 0.1}]
    r = client.put(f"/api/v1/envelopes/{e['id']}", json={"recipients": rs, "fields": f}, headers=h)
    assert r.status_code == 200, r.text
    return e["id"]


def test_stamp_upload_admin_only_and_validated(client):
    h = signup(client)
    add_user("sender@example.com", "sender")
    hs = login(client, "sender@example.com")
    assert client.post("/api/v1/org/branding/stamp", files={"file": ("s.png", png(), "image/png")}, headers=hs).status_code == 403
    assert client.post("/api/v1/org/branding/stamp", files={"file": ("s.png", b"GIF89a....", "image/png")}, headers=h).status_code == 415
    assert client.post("/api/v1/org/branding/stamp", files={"file": ("s.png", b"\x89PNG\r\n\x1a\n" + b"x" * (1024 * 1024 + 10), "image/png")}, headers=h).status_code == 413
    r = client.post("/api/v1/org/branding/stamp", files={"file": ("s.png", png(), "image/png")}, headers=h)
    assert r.status_code == 200 and r.json()["configured"]
    assert client.get("/api/v1/org/branding/stamp/image", headers=hs).status_code == 403
    assert client.get("/api/v1/org/branding/stamp/image", headers=h).content == png()
    assert client.post("/api/v1/org/branding/stamp", files={"file": ("s.png", png((0, 0, 200, 255)), "image/png")}, headers=h).status_code == 200
    assert client.delete("/api/v1/org/branding/stamp", headers=hs).status_code == 403
    assert client.delete("/api/v1/org/branding/stamp", headers=h).status_code == 200
    with SessionLocal() as s:
        acts = [a.action for a in s.query(models.AdminAuditLog).order_by(models.AdminAuditLog.id)]
    assert ["org.company_stamp_uploaded", "org.company_stamp_replaced", "org.company_stamp_removed"] == [a for a in acts if "stamp" in a]


def test_send_blocked_without_stamp_or_for_external_rep(client):
    h = signup(client)
    eid = stamp_draft(client, h)
    r = client.post(f"/api/v1/envelopes/{eid}/send", headers=h)
    assert r.status_code == 422 and "company stamp" in r.text.lower()
    client.post("/api/v1/org/branding/stamp", files={"file": ("s.png", png(), "image/png")}, headers=h)
    eid2 = stamp_draft(client, h, rep_email="outsider@example.org")
    r = client.post(f"/api/v1/envelopes/{eid2}/send", headers=h)
    assert r.status_code == 422 and "internal" in r.text.lower()


def test_stamp_applied_into_pdf_and_audited(client):
    from app.core.security import sha256_hex
    h = signup(client)
    img = png()
    client.post("/api/v1/org/branding/stamp", files={"file": ("s.png", img, "image/png")}, headers=h)
    eid = stamp_draft(client, h)
    assert client.post(f"/api/v1/envelopes/{eid}/send", headers=h).status_code == 200
    tok, code = link_and_code("krishna@example.com")
    # signer-supplied stamp value must be ignored
    r = client.post(f"/api/v1/public/s/{tok}/unlock", json={"code": code}); sh = {"X-Signer-Session": r.json()["session"]}
    fl = client.get(f"/api/v1/public/s/{tok}/envelope", headers=sh).json()["fields"]
    stamp_id = next(f["id"] for f in fl if f["type"] == "stamp")
    reasons = {f["id"]: "Approved" for f in fl if f["type"] == "signature"}
    r = client.post(f"/api/v1/public/s/{tok}/finish", json={"consent": True, "intent": True, "signature": {"kind": "typed"}, "reasons": reasons, "values": {stamp_id: "data:image/png;base64,AAAA"}}, headers=sh)
    assert r.status_code == 200, r.text
    tok2, code2 = link_and_code("client@example.org")
    sign(client, tok2, code2)
    with SessionLocal() as s:
        env = s.get(models.Envelope, eid)
        f = next(x for x in env.fields if x.type == "stamp")
        assert f.value == f"sha256:{sha256_hex(img)}" and f.field_hash
        ev = [e for e in env.audit_events if e.event == "company_stamp_applied"] if hasattr(env, "audit_events") else s.query(models.AuditEvent).filter_by(envelope_id=eid, event="company_stamp_applied").all()
        assert len(ev) == 1 and sha256_hex(img) in ev[0].detail and "krishna@example.com" in ev[0].detail
        assert env.status == "completed"
    pdf = client.get(f"/api/v1/envelopes/{eid}/completed", headers=h)
    assert pdf.status_code == 200
    page = PdfReader(io.BytesIO(pdf.content)).pages[0]
    xo = page["/Resources"].get("/XObject") or {}
    def has_img(x):
        for k in x:
            o = x[k].get_object()
            if o.get("/Subtype") == "/Image": return True
            if o.get("/Subtype") == "/Form" and "/Resources" in o and has_img(o["/Resources"].get("/XObject") or {}): return True
        return False
    assert has_img(xo)
