import hashlib, hmac, re, secrets, string
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt, JWTError
from .config import settings

ALGO = "HS256"


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(p: str, h: str | None) -> bool:
    if not h:
        return False
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except ValueError:
        return False


def keyed_hash(purpose: str, value: str) -> str:
    """HMAC-SHA256 with the server secret; used for short secrets (access codes, OTPs) so a DB leak alone cannot brute-force them offline."""
    return hmac.new(settings.SECRET_KEY.encode(), f"{purpose}:{value}".encode(), hashlib.sha256).hexdigest()


def random_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)  # 32 bytes = 256 bits


def numeric_code(length: int) -> str:
    length = max(6, min(8, length))
    return "".join(secrets.choice(string.digits) for _ in range(length))


def create_access_token(user_id: int, sid: str, minutes: int | None = None) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes or settings.SESSION_ABSOLUTE_HOURS * 60)
    return jwt.encode({"sub": str(user_id), "sid": sid, "exp": exp}, settings.SECRET_KEY, algorithm=ALGO)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGO])
    except JWTError:
        return None


# A small offline list of the most common breached passwords; HIBP k-anonymity check optional (HIBP_CHECK=true).
COMMON_PASSWORDS = {"password", "password1", "password123", "123456", "12345678", "123456789", "1234567890", "qwerty", "qwerty123",
                    "111111", "abc123", "letmein", "welcome", "welcome1", "admin", "admin123", "iloveyou", "monkey", "dragon",
                    "football", "baseball", "sunshine", "princess", "passw0rd", "p@ssw0rd", "p@ssword", "changeme", "india123",
                    "demo@123", "test1234", "zaq12wsx", "1q2w3e4r", "qwertyuiop", "master", "trustno1", "superman", "hello123"}

DEFAULT_PASSWORD_POLICY = {"min_length": 10, "require_upper": True, "require_lower": True, "require_digit": True,
                           "require_symbol": False, "expiry_days": 0, "history": 3}


def password_problems(pw: str, policy: dict | None = None, email: str = "") -> list[str]:
    p = {**DEFAULT_PASSWORD_POLICY, **(policy or {})}
    out = []
    if len(pw) < int(p["min_length"]): out.append(f"at least {p['min_length']} characters")
    if p.get("require_upper") and not re.search(r"[A-Z]", pw): out.append("an uppercase letter")
    if p.get("require_lower") and not re.search(r"[a-z]", pw): out.append("a lowercase letter")
    if p.get("require_digit") and not re.search(r"\d", pw): out.append("a digit")
    if p.get("require_symbol") and not re.search(r"[^A-Za-z0-9]", pw): out.append("a symbol")
    if pw.lower() in COMMON_PASSWORDS or (email and email.split("@")[0].lower() in pw.lower() and len(email.split("@")[0]) > 3):
        out.append("not be a common or easily guessed password")
    elif settings.HIBP_CHECK and _hibp_breached(pw):
        out.append("not appear in known data breaches")
    return out


def _hibp_breached(pw: str) -> bool:
    try:
        import httpx
        h = hashlib.sha1(pw.encode()).hexdigest().upper()
        r = httpx.get(f"https://api.pwnedpasswords.com/range/{h[:5]}", timeout=4, headers={"Add-Padding": "true"})
        return any(line.split(":")[0] == h[5:] for line in r.text.splitlines())
    except Exception:
        return False  # fail open on network errors; offline list still applies


# --- TOTP (RFC 6238) ---
def new_totp_secret() -> str:
    import pyotp
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    import pyotp
    return bool(secret) and pyotp.TOTP(secret).verify(code.strip(), valid_window=1)


def totp_uri(secret: str, email: str, issuer: str) -> str:
    import pyotp
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)
