"""PAdES sealing of completed PDFs with pyHanko.
- Production: SEAL_CERT_P12_PATH (+ password) – an organization/document-signing certificate (keys should live in an HSM; a PKCS#12
  file is the integration point here) and SEAL_TSA_URL for an RFC 3161 timestamp (PAdES B-T).
- Development: SEAL_DEV_SELF_SIGNED=true generates a self-signed certificate. The signature is cryptographically real and any
  later change is detectable, but readers will show the signer as UNTRUSTED. Reported as 'pades_dev_selfsigned', never as trusted.
- Otherwise: not sealed ('no')."""
import datetime as dt, io, os
from ..core.config import settings

_DEV_P12 = None


def _dev_p12() -> tuple[bytes, bytes]:
    global _DEV_P12
    if _DEV_P12:
        return _DEV_P12
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    path = os.path.join(settings.STORAGE_DIR, "_dev_seal.p12")
    pw = b"dev-only"
    if os.path.exists(path):
        _DEV_P12 = (open(path, "rb").read(), pw); return _DEV_P12
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "VAICS Sign DEVELOPMENT seal (untrusted)"), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "VAICS Sign dev")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=3650))
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False, data_encipherment=False, key_agreement=False,
                                         key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False)
            .sign(key, hashes.SHA256()))
    data = pkcs12.serialize_key_and_certificates(b"vaics-dev-seal", key, cert, None, serialization.BestAvailableEncryption(pw))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh: fh.write(data)
    _DEV_P12 = (data, pw); return _DEV_P12


def seal_mode() -> str:
    if settings.SEAL_CERT_P12_PATH:
        return "pades_timestamped" if settings.SEAL_TSA_URL else "pades"
    if settings.SEAL_DEV_SELF_SIGNED and settings.ENV != "production":
        return "pades_dev_selfsigned"
    return "no"


def seal(pdf: bytes, reason: str, location: str = "") -> tuple[bytes, str]:
    mode = seal_mode()
    if mode == "no":
        return pdf, "no"
    from pyhanko.sign import signers, timestamps
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign.fields import SigSeedSubFilter
    if mode == "pades_dev_selfsigned":
        p12, pw = _dev_p12()
    else:
        p12, pw = open(settings.SEAL_CERT_P12_PATH, "rb").read(), (settings.SEAL_CERT_P12_PASSWORD or "").encode() or None
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".p12", delete=False) as tf:
        tf.write(p12); tmp = tf.name
    try:
        signer = signers.SimpleSigner.load_pkcs12(tmp, passphrase=pw)
    finally:
        os.unlink(tmp)
    if signer is None:
        raise RuntimeError("Seal certificate could not be loaded")
    tsa = timestamps.HTTPTimeStamper(settings.SEAL_TSA_URL) if settings.SEAL_TSA_URL else None
    meta = signers.PdfSignatureMetadata(field_name="VAICSSeal", reason=reason[:200], location=location or None,
                                        subfilter=SigSeedSubFilter.PADES, md_algorithm="sha256")
    w = IncrementalPdfFileWriter(io.BytesIO(pdf))
    out = signers.PdfSigner(meta, signer=signer, timestamper=tsa).sign_pdf(w)
    return out.getvalue(), mode


def validate(pdf: bytes) -> dict:
    """Integrity check of embedded signatures (does not establish trust in self-signed certs)."""
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext
    try:
        r = PdfFileReader(io.BytesIO(pdf))
    except Exception as ex:
        return {"signatures": 0, "error": str(ex)[:200]}
    out = []
    for sig in r.embedded_signatures:
        try:
            st = validate_pdf_signature(sig, ValidationContext(allow_fetching=False))
            out.append({"field": sig.field_name, "intact": bool(st.intact), "valid": bool(st.valid), "trusted": bool(st.trusted),
                        "coverage": str(st.coverage).split(".")[-1], "signer": st.signing_cert.subject.human_friendly if st.signing_cert else None,
                        "timestamp": bool(getattr(st, "timestamp_validity", None))})
        except Exception as ex:  # noqa: BLE001
            out.append({"field": sig.field_name, "intact": False, "error": str(ex)[:200]})
    return {"signatures": len(out), "results": out}
