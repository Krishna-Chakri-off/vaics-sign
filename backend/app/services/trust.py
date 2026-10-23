"""Integration boundaries for certificate-based signatures (FRS §7.13). These adapters DO NOT fake success:
without a configured, licensed provider they raise ProviderNotConfigured and the API returns 501."""
from ..core.config import settings


class ProviderNotConfigured(Exception):
    pass


class SignatureProvider:
    code = "base"
    label = "base"

    def configured(self) -> bool:
        return False

    def start(self, envelope, recipient, document_hash: str) -> dict:
        """Begin a provider signing transaction; returns {'redirect_url': ...}."""
        raise ProviderNotConfigured(f"{self.label} provider is not configured")

    def complete(self, envelope, recipient, callback_payload: dict) -> dict:
        """Verify the provider response and return the signature container (CMS/PKCS#7) to embed."""
        raise ProviderNotConfigured(f"{self.label} provider is not configured")


class AadhaarESign(SignatureProvider):
    """CCA eSign API 2.1/3.2 via an empanelled ESP: build signed eSign XML request with document hash, redirect user to ESP for
    Aadhaar OTP/biometric, receive response with PKCS#7 signature + certificate, embed in PDF (deferred signing)."""
    code, label = "aadhaar_esign", "Aadhaar eSign (ESP)"

    def configured(self):
        return bool(settings.ESIGN_ESP_URL and settings.ESIGN_ASP_ID)


class DSCSigner(SignatureProvider):
    """DSC (USB token via local signing utility, or cloud signing). Requires CA chain validation against CCA root + CRL/OCSP."""
    code, label = "dsc", "DSC / PKI"

    def configured(self):
        return bool(settings.DSC_PROVIDER_URL)


class QTSPSigner(SignatureProvider):
    """eIDAS AdES/QES through a Qualified Trust Service Provider (CSC API remote signing)."""
    code, label = "qes", "eIDAS QTSP (AdES/QES)"

    def configured(self):
        return bool(settings.QTSP_PROVIDER_URL)


PROVIDERS = {p.code: p for p in (AadhaarESign(), DSCSigner(), QTSPSigner())}


def status() -> list[dict]:
    return [{"code": p.code, "label": p.label, "configured": p.configured(), "implemented": False} for p in PROVIDERS.values()]
