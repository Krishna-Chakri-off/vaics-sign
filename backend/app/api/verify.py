"""Public verification (FR-134): check a completed PDF by upload (hash match + PAdES validation) or by envelope ID."""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from ..core.db import get_db
from ..core.security import sha256_hex
from ..models import Envelope, Organization
from ..services import seal

router = APIRouter(prefix="/public/verify", tags=["public verification"])


def _env_info(db, e: Envelope):
    org = db.get(Organization, e.org_id)
    return {"envelope_id": e.public_id, "organization": org.name, "status": e.status, "completed_at": e.completed_at, "sha256": e.completed_sha256,
            "seal": e.sealed, "signers": [{"name": r.name, "completed_at": r.completed_at} for r in e.recipients if r.status == "completed"]}


@router.post("")
async def verify_upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = await file.read()
    if len(data) > 100 * 1024 * 1024: raise HTTPException(413, "File too large")
    h = sha256_hex(data)
    e = db.query(Envelope).filter_by(completed_sha256=h).first()
    from starlette.concurrency import run_in_threadpool
    sig = await run_in_threadpool(seal.validate, data)
    return {"sha256": h, "matches_record": bool(e), "record": _env_info(db, e) if e else None, "signature": sig,
            "verdict": ("authentic" if e and all(x.get("intact") for x in sig.get("results", [])) else "unknown_or_modified"),
            "note": "A match means this exact file was issued by VAICS Sign. Any change to the file breaks the match." }


@router.get("/{public_id}")
def verify_id(public_id: str, db: Session = Depends(get_db)):
    e = db.query(Envelope).filter_by(public_id=public_id.strip().upper()).first()
    if not e or e.status != "completed": raise HTTPException(404, "No completed envelope with this ID")
    return {**_env_info(db, e), "note": "Upload the PDF to confirm it matches this record's SHA-256."}
