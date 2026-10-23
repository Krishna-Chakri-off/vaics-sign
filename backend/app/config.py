from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    APP_NAME: str = "VAICS Sign"
    DATABASE_URL: str = "sqlite:///./cms.db"
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    CORS_ORIGINS: str = "http://localhost:5175,http://127.0.0.1:5175,http://192.168.20.51:5175"
    CORS_ORIGIN_REGEX: str = r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+):\d+"
    # AI assistant (optional). Provider: none | openai (any OpenAI-compatible endpoint)
    AI_PROVIDER: str = "none"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    # SMTP (optional)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "cms@vaics.local"
    WEBHOOKS_ENABLED: bool = True


settings = Settings()


class SignSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    SIGN_ORG_NAME: str = "VAICS Consulting"
    SIGN_PRODUCT_NAME: str = "VAICS Sign"
    SIGN_PRIMARY_COLOR: str = "#0D47A1"
    SIGN_ACCENT_COLOR: str = "#E6007E"
    SIGN_LOGO_URL: str = "/vaics-logo-full.png"
    SIGN_STORAGE_DIR: str = "./sign_storage"
    SIGN_MAX_UPLOAD_MB: int = 15
    SIGN_LINK_EXPIRY_DAYS: int = 7
    SIGN_PUBLIC_BASE_URL: str = "http://localhost:5175"
    SIGN_CODE_LENGTH: int = 6
    SIGN_CODE_MAX_ATTEMPTS: int = 5
    SIGN_CODE_EXPIRY_HOURS: int = 72
    SIGN_SESSION_MINUTES: int = 30
    SIGN_SMTP_SSL: bool = False  # True for port 465 (implicit TLS); False uses STARTTLS (e.g. SES on 587)


sign_settings = SignSettings()
