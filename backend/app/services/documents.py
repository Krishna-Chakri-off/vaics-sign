"""Upload validation, malware scan, conversion to PDF, page geometry and text extraction."""
import io, os, shutil, socket, subprocess, tempfile
from pathlib import Path
from fastapi import HTTPException
from ..core.config import settings

PDF_MIME = "application/pdf"
CONVERTIBLE = {".doc", ".docx", ".odt", ".rtf", ".txt", ".xls", ".xlsx", ".ods", ".csv", ".ppt", ".pptx", ".odp", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff"}
MAGIC = {b"%PDF-": ".pdf", b"PK\x03\x04": "zip", b"\xd0\xcf\x11\xe0": "ole", b"\x89PNG": ".png", b"\xff\xd8\xff": ".jpg", b"GIF8": ".gif", b"BM": ".bmp", b"II*\x00": ".tif", b"MM\x00*": ".tif", b"{\\rtf": ".rtf"}


WINDOWS_SOFFICE = [r"C:\Program Files\LibreOffice\program\soffice.exe", r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"]
OTHER_SOFFICE = ["/usr/bin/soffice", "/usr/lib/libreoffice/program/soffice", "/opt/libreoffice/program/soffice",
                 "/Applications/LibreOffice.app/Contents/MacOS/soffice"]


def find_soffice() -> str | None:
    """SOFFICE_PATH (a full path or a command on PATH), then the usual LibreOffice install locations."""
    cfg = settings.SOFFICE_PATH or "soffice"
    if os.path.isfile(cfg):
        return cfg
    found = shutil.which(cfg) or shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    for c in (WINDOWS_SOFFICE if os.name == "nt" else OTHER_SOFFICE):
        if os.path.isfile(c):
            return c
    return None


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
    """Validate and, if needed, convert to PDF via LibreOffice. Returns (pdf_bytes, source_type)."""
    ext = os.path.splitext(filename.lower())[1]
    kind = sniff(data)
    if kind == ".pdf":
        return data, PDF_MIME
    if ext not in CONVERTIBLE:
        raise HTTPException(415, "Unsupported file type. Upload PDF, Word, Excel, PowerPoint, text or image files.")
    if kind is None and ext not in (".txt", ".csv"):
        raise HTTPException(415, "File content does not match its extension.")
    soffice = find_soffice()
    if not soffice:
        raise HTTPException(501, "Document conversion is not available on this server (LibreOffice not installed). Upload a PDF.")
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "input" + ext)
        with open(src, "wb") as fh: fh.write(data)
        try:
            subprocess.run([soffice, "--headless", "--norestore", "-env:UserInstallation=" + (Path(td) / "profile").as_uri(), "--convert-to", "pdf", "--outdir", td, src],
                           check=True, timeout=120, capture_output=True)
        except (subprocess.SubprocessError, OSError):
            raise HTTPException(422, "The document could not be converted to PDF.")
        out = os.path.join(td, "input.pdf")
        if not os.path.exists(out):
            raise HTTPException(422, "The document could not be converted to PDF.")
        with open(out, "rb") as fh:
            return fh.read(), ext.lstrip(".")


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
