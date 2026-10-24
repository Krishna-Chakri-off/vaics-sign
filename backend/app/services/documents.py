"""Upload validation, malware scan, conversion to PDF, page geometry and text extraction."""
import io, os, shutil, socket, subprocess, tempfile
from pathlib import Path
from fastapi import HTTPException
from ..core.config import settings

PDF_MIME = "application/pdf"
MAGIC = {b"%PDF-": ".pdf", b"PK\x03\x04": "zip", b"\xd0\xcf\x11\xe0": "ole", b"\x89PNG": ".png", b"\xff\xd8\xff": ".jpg", b"GIF8": ".gif", b"BM": ".bmp", b"II*\x00": ".tif", b"MM\x00*": ".tif", b"{\\rtf": ".rtf"}


def sniff(data: bytes) -> str | None:
    for m, kind in MAGIC.items():
        if data.startswith(m):
            return kind
    return None


def scan_malware(data: bytes) -> str:
    """Returns 'clean' / 'not_scanned'. Raises 422 if infected. Uses clamd INSTREAM when CLAMD_HOST is set."""
    if not settings.CLAMD_HOST:
        return "not_scanned"
    try:
        with socket.create_connection((settings.CLAMD_HOST, settings.CLAMD_PORT), timeout=30) as s:
            s.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), 8192):
                chunk = data[i:i + 8192]; s.sendall(len(chunk).to_bytes(4, "big") + chunk)
            s.sendall(b"\0\0\0\0")
            resp = s.recv(4096).decode(errors="ignore")
    except OSError as ex:
        raise HTTPException(503, f"Malware scanner unavailable: {ex}")
    if "FOUND" in resp:
        raise HTTPException(422, "The file was rejected by the malware scanner.")
    return "clean"


def to_pdf(filename: str, data: bytes) -> tuple[bytes, str]:
    """Accept PDF files only (checked by content, not just extension)."""
    if sniff(data) != ".pdf" or not filename.lower().endswith(".pdf"):
        raise HTTPException(415, "Only PDF files can be uploaded.")
    return data, PDF_MIME


def inspect_pdf(data: bytes) -> tuple[list[dict], str]:
    """Returns displayed page geometry [{w,h,rotation}] and extracted text. Rejects encrypted / corrupt PDFs."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
    try:
        r = PdfReader(io.BytesIO(data))
    except (PdfReadError, Exception):
        raise HTTPException(422, "The PDF is damaged and could not be read.")
    if r.is_encrypted:
        raise HTTPException(422, "Password-protected PDFs are not supported. Remove the password and upload again.")
    pages, text = [], []
    for p in r.pages:
        box = p.cropbox
        w, h = float(box.width), float(box.height)
        rot = int(p.get("/Rotate", 0) or 0) % 360
        if rot in (90, 270):
            w, h = h, w
        pages.append({"w": round(w, 2), "h": round(h, 2), "rotation": rot})
        try:
            text.append(p.extract_text() or "")
        except Exception:
            pass
    if not pages:
        raise HTTPException(422, "The PDF has no pages.")
    return pages, "\n".join(text)[:200000]
