"""Official company stamp/seal image: admin-uploaded, stored server-side by SHA-256. Only the current image is kept; replace/remove deletes old files.
When the VAICS representative signs, the verified image is copied into that envelope's evidence so the final PDF uses exactly what was applied."""
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
    prev = meta(org)
    storage().put(org.region, _key(org, sha), data)
    if prev and prev["sha256"] != sha:
        storage().delete(org.region, _key(org, prev["sha256"]))
    m = {"sha256": sha, "mime": mime, "size": len(data), "uploaded_by": actor_email, "uploaded_at": now().isoformat() + "Z"}
    org.settings = {**(org.settings or {}), "company_stamp": m}
    return m


def remove(org) -> dict | None:
    m = meta(org)
    s = dict(org.settings or {}); s.pop("company_stamp", None); org.settings = s
    if m: storage().delete(org.region, _key(org, m["sha256"]))
    _purge_leftovers(org)
    return m


def _purge_leftovers(org):
    """Delete any other stamp library files for this org (e.g. versions kept by older builds)."""
    import os, glob
    root = getattr(storage(), "root", None)
    if root:
        for p in glob.glob(os.path.join(root, org.region, str(org.id), "stamp", "*.img")):
            os.chmod(p, 0o644); os.remove(p)


def current_image(org) -> tuple[str, bytes] | None:
    """The configured stamp, verified against its SHA-256; None if not configured, missing or mismatched."""
    m = meta(org)
    if not m: return None
    try:
        data = load(org, m["sha256"])
    except Exception:
        return None
    return m["sha256"], data


def _env_key(org, env_id: int, sha: str) -> str:
    return f"{org.region}/{org.id}/envstamp/{env_id}/{sha}.img"


def snapshot(org, env_id: int, sha: str, data: bytes) -> None:
    storage().put(org.region, _env_key(org, env_id, sha), data)


def load_applied(org, env_id: int, sha: str) -> bytes:
    data = storage().get(org.region, _env_key(org, env_id, sha))
    if sha256_hex(data) != sha: raise RuntimeError("Applied company stamp failed its integrity check")
    return data


def load(org, sha: str) -> bytes:
    data = storage().get(org.region, _key(org, sha))
    if sha256_hex(data) != sha: raise RuntimeError("Company stamp image failed its integrity check")
    return data


def is_internal(db, org, r) -> bool:
    return r.type == "signer" and db.query(User).filter_by(org_id=org.id, email=(r.email or "").lower(), is_active=True).first() is not None
