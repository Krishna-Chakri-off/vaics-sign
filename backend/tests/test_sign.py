import io
from reportlab.pdfgen import canvas
from .conftest import login

API = "/api/v1/sign"


def pdf(pages=2):
    b = io.BytesIO(); c = canvas.Canvas(b)
    for i in range(pages): c.drawString(72, 720, f"Agreement page {i + 1}"); c.showPage()
    c.save(); return b.getvalue()


def up(client, h):
    r = client.post(f"{API}/documents", headers=h, data={"title": "MSA"}, files={"file": ("msa.pdf", pdf(), "application/pdf")})
    assert r.status_code == 200, r.text; return r.json()


def prep(client, h, did, n=2):
    rs = [{"name": f"Signer {i + 1}", "email": f"s{i + 1}@ext.com"} for i in range(n)]
    fs = [{"recipient_index": i, "page": p, "x": 0.1, "y": 0.45 + 0.2 * i, "w": 0.3, "h": 0.1} for i in range(n) for p in (1, 2)]
    r = client.put(f"{API}/documents/{did}", headers=h, json={"recipients": rs, "fields": fs}); assert r.status_code == 200, r.text
    return r.json()


def mails(client, h, to=None, kind=None):
    ms = client.get(f"{API}/outbox", headers=h).json()["emails"]
    return [m for m in ms if (to is None or m["to"] == to) and (kind is None or m["kind"] == kind)]


def latest(client, h, email):
    link = mails(client, h, email, "signing_link")[0]["link"]; code = mails(client, h, email, "access_code")[0]["code"]
    return link.rsplit("/", 1)[1], code


def unlock(client, tok, code):
    return client.post(f"{API}/public/{tok}/unlock", json={"code": code})


def sign_as(client, tok, code):
    s = unlock(client, tok, code); assert s.status_code == 200, s.text
    hs = {"X-Sign-Session": s.json()["session"]}
    doc = client.get(f"{API}/public/{tok}/doc", headers=hs).json()
    assert client.get(f"{API}/public/{tok}/file", headers=hs).content.startswith(b"%PDF")
    r = client.post(f"{API}/public/{tok}/sign", headers=hs, json={"consent": True, "reasons": {str(f["id"]): "Approved as authorised signatory" for f in doc["fields"]}})
    assert r.status_code == 200, r.text; return r.json()["status"]


def test_rejects_non_pdf_and_requires_auth(client):
    h = login(client, "manager")
    assert client.post(f"{API}/documents", headers=h, data={"title": "x"}, files={"file": ("a.pdf", b"hello", "application/pdf")}).status_code == 415
    assert client.get(f"{API}/documents").status_code == 401


def test_full_two_signer_flow_with_codes(client):
    h = login(client, "manager"); d = up(client, h); prep(client, h, d["id"])
    assert client.post(f"{API}/documents/{d['id']}/send", headers=h).json()["email_mode"] == "dev_outbox"
    # only signer 1 notified, link and code in separate emails
    assert mails(client, h, "s1@ext.com", "signing_link") and mails(client, h, "s1@ext.com", "access_code")
    assert not mails(client, h, "s2@ext.com")
    m_link = mails(client, h, "s1@ext.com", "signing_link")[0]; m_code = mails(client, h, "s1@ext.com", "access_code")[0]
    assert m_link["code"] is None and m_code["link"] is None and m_code["code"] not in m_link["body"]
    t1, c1 = latest(client, h, "s1@ext.com"); assert 6 <= len(c1) <= 8 and c1.isdigit()
    # document locked without code
    assert client.get(f"{API}/public/{t1}/doc").status_code == 401
    assert client.get(f"{API}/public/{t1}/file").status_code == 401
    assert sign_as(client, t1, c1) == "partially_signed"
    assert client.get(f"{API}/public/{t1}").status_code == 404  # link single-use
    t2, c2 = latest(client, h, "s2@ext.com")
    assert sign_as(client, t2, c2) == "completed"
    det = client.get(f"{API}/documents/{d['id']}", headers=h).json()
    assert all(f["field_hash"] and f["reason"] for f in det["fields"]) and len(det["fields"]) == 4
    f = client.get(f"{API}/documents/{d['id']}/completed", headers=h); assert f.status_code == 200
    from pypdf import PdfReader
    rd = PdfReader(io.BytesIO(f.content)); assert len(rd.pages) >= 3
    t = rd.pages[0].extract_text(); assert "Reason: Approved" in t and "IST" in t and "UTC" in t and "SHA-256" in t
    assert "Certificate of Completion" in rd.pages[2].extract_text()
    # completion emails to requester + both signers
    done = {m["to"] for m in mails(client, h, kind="completed")}
    assert done == {"manager@vaics.com", "s1@ext.com", "s2@ext.com"}
    dl = [m for m in mails(client, h, "s2@ext.com", "completed")][0]["link"].rsplit("/", 1)[1]
    assert client.get(f"{API}/public/download/{dl}").content.startswith(b"%PDF")
    ev = [e["event"] for e in det["audit"]]
    assert {"uploaded", "generated", "signer_notified", "code_verified", "viewed", "signed", "completed", "final_pdf_sealed"} <= set(ev)
    for a, b in zip(det["audit"], det["audit"][1:]): assert b["prev_hash"] == a["entry_hash"]
    assert client.get(f"{API}/dashboard", headers=h).json()["counts"]["completed"] == 1


def test_wrong_code_and_lockout_then_reissue(client):
    h = login(client, "manager"); d = up(client, h); prep(client, h, d["id"], 1)
    client.post(f"{API}/documents/{d['id']}/send", headers=h)
    t, c = latest(client, h, "s1@ext.com"); bad = "000000" if c != "000000" else "111111"
    for i in range(4): assert unlock(client, t, bad).status_code == 403
    assert unlock(client, t, bad).status_code == 423
    assert unlock(client, t, c).status_code == 423  # locked even with right code
    rid = client.get(f"{API}/documents/{d['id']}", headers=h).json()["recipients"][0]["id"]
    assert client.post(f"{API}/documents/{d['id']}/recipients/{rid}/resend", headers=h).status_code == 200
    assert client.get(f"{API}/public/{t}").status_code == 404  # old link revoked
    t2, c2 = latest(client, h, "s1@ext.com")
    assert sign_as(client, t2, c2) == "completed"


def test_order_enforced(client):
    h = login(client, "manager"); d = up(client, h); prep(client, h, d["id"])
    client.post(f"{API}/documents/{d['id']}/send", headers=h)
    det = client.get(f"{API}/documents/{d['id']}", headers=h).json()
    # signer 2 cannot be reissued before signer 1 completes
    assert client.post(f"{API}/documents/{d['id']}/recipients/{det['recipients'][1]['id']}/resend", headers=h).status_code == 409
    assert not mails(client, h, "s2@ext.com")


def test_isolation_decline_cancel(client):
    h = login(client, "manager"); d = up(client, h)
    h2 = login(client, "approver")
    assert client.get(f"{API}/documents/{d['id']}", headers=h2).status_code == 403
    assert client.get(f"{API}/documents/{d['id']}/file", headers=h2).status_code == 403
    prep(client, h, d["id"], 1); client.post(f"{API}/documents/{d['id']}/send", headers=h)
    t, c = latest(client, h, "s1@ext.com"); s = unlock(client, t, c).json()["session"]
    assert client.post(f"{API}/public/{t}/decline", headers={"X-Sign-Session": s}, data={"reason": "terms"}).json()["status"] == "declined"
    d2 = up(client, h); prep(client, h, d2["id"], 1); client.post(f"{API}/documents/{d2['id']}/send", headers=h)
    t2, _ = latest(client, h, "s1@ext.com")
    client.post(f"{API}/documents/{d2['id']}/cancel", headers=h)
    assert client.get(f"{API}/public/{t2}").status_code == 404


def test_generate_requires_fields(client):
    h = login(client, "manager"); d = up(client, h)
    client.put(f"{API}/documents/{d['id']}", headers=h, json={"recipients": [{"name": "A", "email": "a@x.com"}], "fields": []})
    assert client.post(f"{API}/documents/{d['id']}/send", headers=h).status_code == 422
