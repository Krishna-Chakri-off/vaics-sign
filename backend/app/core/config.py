"""Central configuration. All values come from environment / .env – no secrets in code."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- core ---
    ENV: str = "development"  # development | test | production
    APP_NAME: str = "VAICS Sign"
    DATABASE_URL: str = "sqlite:///./vaics_sign.db"
    SECRET_KEY: str = "dev-only-change-me"
    PUBLIC_APP_URL: str = "http://localhost:5175"  # frontend base URL used in emails
    PUBLIC_API_URL: str = "http://localhost:8000"
    CORS_ORIGINS: str = "http://localhost:5175,http://127.0.0.1:5175"
    CORS_ORIGIN_REGEX: str = r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+):\d+"
    AUTO_CREATE_TABLES: bool = True  # dev convenience; production uses `alembic upgrade head`
    RUN_SCHEDULER: bool = False  # background reminders/expiry/retention loop inside the API process
    SCHEDULER_INTERVAL_SECONDS: int = 300

    # --- sessions / auth ---
    SESSION_IDLE_MINUTES: int = 30
    SESSION_ABSOLUTE_HOURS: int = 12
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_LOCK_MINUTES: int = 15
    EMAIL_TOKEN_HOURS: int = 24
    RESET_TOKEN_MINUTES: int = 30
    INVITE_DAYS: int = 7
    HIBP_CHECK: bool = False  # k-anonymity check against haveibeenpwned (network)

    # --- branding defaults (per-tenant branding overrides these) ---
    BRAND_PRODUCT_NAME: str = "VAICS Sign"
    BRAND_ORG_NAME: str = "VAICS Consulting"
    BRAND_PRIMARY: str = "#0D47A1"
    BRAND_ACCENT: str = "#E6007E"
    BRAND_LOGO_URL: str = "/vaics-logo-full.png"

    # --- documents ---
    MAX_DOC_MB: int = 25
    MAX_ENVELOPE_MB: int = 100
    MAX_DOCS_PER_ENVELOPE: int = 50
    CLAMD_HOST: str = ""  # malware scanning via clamd; empty = not configured
    CLAMD_PORT: int = 3310

    # --- storage ---
    STORAGE_BACKEND: str = "local"  # local | s3
    STORAGE_DIR: str = "./storage"
    S3_BUCKET_IN: str = ""
    S3_BUCKET_EU: str = ""
    S3_BUCKET_US: str = ""
    S3_REGION_IN: str = "ap-south-1"
    S3_REGION_EU: str = "eu-central-1"
    S3_REGION_US: str = "us-east-1"
    S3_ENDPOINT_URL: str = ""  # e.g. MinIO for local testing
    S3_OBJECT_LOCK_DAYS: int = 0  # >0 applies COMPLIANCE retention to completed docs (bucket must have Object Lock)

    # --- signing ---
    LINK_EXPIRY_DAYS: int = 120
    ACCESS_CODE_LENGTH: int = 6
    CODE_MAX_ATTEMPTS: int = 5
    ACCESS_CODE_EXPIRY_HOURS: int = 72
    OTP_MINUTES: int = 10
    SIGNER_SESSION_MINUTES: int = 30

    # --- email ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@example.com"
    SMTP_SSL: bool = False
    EMAIL_ATTACH_MAX_MB: int = 9

    # --- SMS ---
    SMS_PROVIDER: str = "dev"  # dev (outbox only) | twilio | msg91
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM: str = ""
    MSG91_AUTH_KEY: str = ""
    MSG91_TEMPLATE_ID: str = ""

    # --- trust providers ---
    SEAL_CERT_P12_PATH: str = ""  # PKCS#12 document-signing certificate for PAdES seal
    SEAL_CERT_P12_PASSWORD: str = ""
    SEAL_TSA_URL: str = ""  # RFC 3161 timestamp authority
    SEAL_DEV_SELF_SIGNED: bool = True  # dev only: generate a self-signed seal cert (NOT trusted by readers)
    ESIGN_ESP_URL: str = ""  # Aadhaar eSign (CCA-empanelled ESP)
    ESIGN_ASP_ID: str = ""
    DSC_PROVIDER_URL: str = ""
    QTSP_PROVIDER_URL: str = ""

    # --- rate limiting ---
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PUBLIC_PER_MIN: int = 120
    RATE_LIMIT_AUTH_PER_MIN: int = 20

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
