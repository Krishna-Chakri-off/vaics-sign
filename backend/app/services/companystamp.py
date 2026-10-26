"""Official company stamp/seal image: admin-uploaded, stored server-side by SHA-256 (versions kept so in-flight envelopes stamp the exact image recorded at signing)."""
from fastapi import HTTPException
from ..core.security import sha256_hex
from ..models import User, now
from .storage import storage

MAX_BYTES = 1024 * 1024


def sniff(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"): return "image/png"
    if data.startswith(b"\xff\xd8\xff"): return "image/jpeg"
    return None


def _key(org, sha: str) -> str:
    return f"{org.region}/{org.id}/stamp/{sha}.img"


def meta(org) -> dict | None:
    m = (org.settings or {}).get("company_stamp")
    return m if m and m.get("sha256") else None


def save(org, data: bytes, actor_email: str) -> dict:
    if not data: raise HTTPException(422, "Choose a stamp image")
    if len(data) > MAX_BYTES: raise HTTPException(413, "Stamp image must be 1 MB or smaller")
    mime = sniff(data)
    if not mime: raise HTTPException(415, "Stamp image must be a PNG or JPEG file")
    try:
        from PIL import Image
        import io
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
    except Exception:
        raise HTTPException(415, "Stamp image could not be read")
    sha = sha256_hex(data)
    storage().put(org.region, _key(org, sha), data)
    m = {"sha256": sha, "mime": mime, "size": len(data), "uploaded_by": actor_email, "uploaded_at": now().isoformat() + "Z"}
    org.settings = {**(org.settings or {}), "company_stamp": m}
    return m


def remove(org) -> dict | None:
    m = meta(org)
    s = dict(org.settings or {}); s.pop("company_stamp", None); org.settings = s
    return m  # the stored image is kept: envelopes signed with it must still render and verify


def load(org, sha: str) -> bytes:
    data = storage().get(org.region, _key(org, sha))
    if sha256_hex(data) != sha: raise RuntimeError("Company stamp image failed its integrity check")
    return data


def is_internal(db, org, r) -> bool:
    return r.type == "signer" and db.query(User).filter_by(org_id=org.id, email=(r.email or "").lower(), is_active=True).first() is not None
