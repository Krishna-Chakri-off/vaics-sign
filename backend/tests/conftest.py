import io, os, tempfile
_tmp = tempfile.mkdtemp(prefix="vaics-test-")
os.environ.update({"DATABASE_URL": os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmp}/test.db", "STORAGE_DIR": f"{_tmp}/storage", "ENV": "test", "SECRET_KEY": "test-secret-not-for-production",
                   "RATE_LIMIT_ENABLED": "false", "AUTO_CREATE_TABLES": "true", "SMTP_HOST": "", "HIBP_CHECK": "false", "PUBLIC_APP_URL": "http://app.test"})
import pytest
from fastapi.testclient import TestClient
from app.core.db import Base, engine, SessionLocal
from app import models
from app.main import app
from app.seed import ensure_plans

PW = "Correct-Horse-9-Battery"


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine); Base.metadata.create_all(bind=engine); ensure_plans()
    from app.core.middleware import limiter
    limiter.hits.clear() if hasattr(limiter, "hits") else None
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal(); yield s; s.close()


def outbox(kind=None, to=None):
    with SessionLocal() as s:
        q = s.query(models.EmailLog)
        if kind: q = q.filter_by(kind=kind)
        if to: q = q.filter_by(to=to)
        return q.order_by(models.EmailLog.id).all()


def make_pdf(pages=1, rotate=0) -> bytes:
    from reportlab.pdfgen import canvas
    from pypdf import PdfReader, PdfWriter
    b = io.BytesIO(); c = canvas.Canvas(b)
    for i in range(pages):
        c.drawString(72, 720, f"VAICS test agreement page {i + 1}"); c.showPage()
    c.save()
    if not rotate: return b.getvalue()
    r = PdfReader(io.BytesIO(b.getvalue())); w = PdfWriter()
    for p in r.pages: p.rotate(rotate); w.add_page(p)
    o = io.BytesIO(); w.write(o); return o.getvalue()


def signup(client, email="krishna@example.com", org="VAICS Consulting", country="IN", verify=True, plan=None):
    r = client.post("/api/v1/auth/signup", json={"full_name": "Krishna", "email": email, "password": PW, "organization": org, "country": country, "accept_terms": True})
    assert r.status_code == 201, r.text
    if verify:
        link = outbox("verify_email", email)[-1].link
        assert client.post(f"/api/v1/auth/verify-email/{link.rsplit('/', 1)[1]}").status_code == 200
    if plan:
        with SessionLocal() as s:
            o = s.get(models.Organization, r.json()["org_id"]); o.plan_id = s.query(models.Plan).filter_by(code=plan).first().id; o.status = "active"; s.commit()
    return login(client, email)


def login(client, email, pw=PW):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def draft(client, h, recipients, fields_per=1, pdf=None, title="Consulting Agreement"):
    e = client.post("/api/v1/envelopes", json={"title": title}, headers=h).json()
    d = client.post(f"/api/v1/envelopes/{e['id']}/documents", files={"file": ("agreement.pdf", pdf or make_pdf(), "application/pdf")}, headers=h)
    assert d.status_code in (200, 201), d.text
    doc_id = d.json()["id"] if "id" in d.json() else d.json()["documents"][-1]["id"]
    fields = []
    for i, _ in enumerate(recipients):
        for k in range(fields_per):
            fields.append({"recipient": str(i), "document_id": doc_id, "type": "signature", "page": 1, "x": 0.1 + 0.3 * k, "y": 0.6 + 0.12 * i, "w": 0.25, "h": 0.1})
    r = client.put(f"/api/v1/envelopes/{e['id']}", json={"recipients": recipients, "fields": fields}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def link_and_code(email):
    link = [m for m in outbox(to=email) if m.kind in ("signing_link", "reminder")][-1].link
    codes = outbox("access_code", email)
    return link.rsplit("/", 1)[1], (codes[-1].secret if codes else None)


def sign(client, tok, code, name="Signer", reason="Approved"):
    if code:
        r = client.post(f"/api/v1/public/s/{tok}/unlock", json={"code": code})
    else:
        r = client.post(f"/api/v1/public/s/{tok}/open")
    assert r.status_code == 200, r.text
    sh = {"X-Signer-Session": r.json()["session"]}
    env = client.get(f"/api/v1/public/s/{tok}/envelope", headers=sh)
    assert env.status_code == 200, env.text
    reasons = {f["id"]: reason for f in env.json()["fields"] if f["type"] == "signature"}
    r = client.post(f"/api/v1/public/s/{tok}/finish", json={"consent": True, "signature": {"kind": "typed", "style": "great_vibes"}, "reasons": reasons}, headers=sh)
    assert r.status_code == 200, r.text
    return r.json()
