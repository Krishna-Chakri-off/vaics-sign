"""Storage abstraction with per-region placement (data residency). Keys look like '<region>/<org_id>/<kind>/<uuid>.pdf'."""
import os, uuid
from ..core.config import settings


class Storage:
    def put(self, region: str, key: str, data: bytes, worm: bool = False) -> None: ...
    def get(self, region: str, key: str) -> bytes: ...
    def delete(self, region: str, key: str) -> None: ...
    name = "base"


class LocalStorage(Storage):
    name = "local"

    def __init__(self, root: str):
        self.root = os.path.abspath(root)

    def _path(self, region, key):
        p = os.path.abspath(os.path.join(self.root, key))
        if not p.startswith(self.root + os.sep):
            raise ValueError("invalid key")
        return p

    def put(self, region, key, data, worm=False):
        p = self._path(region, key); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh: fh.write(data)
        if worm:
            os.chmod(p, 0o444)  # best-effort read-only; real WORM needs S3 Object Lock

    def get(self, region, key):
        with open(self._path(region, key), "rb") as fh: return fh.read()

    def delete(self, region, key):
        p = self._path(region, key)
        if os.path.exists(p):
            os.chmod(p, 0o644); os.remove(p)


class S3Storage(Storage):
    """One bucket per region (S3_BUCKET_IN / _EU / _US). Uses SSE (AES-256 / KMS) and optional Object Lock for WORM."""
    name = "s3"

    def __init__(self):
        import boto3
        self.boto3 = boto3
        self.clients = {}

    def _c(self, region):
        reg = {"in": settings.S3_REGION_IN, "eu": settings.S3_REGION_EU, "us": settings.S3_REGION_US}[region]
        bucket = {"in": settings.S3_BUCKET_IN, "eu": settings.S3_BUCKET_EU, "us": settings.S3_BUCKET_US}[region]
        if not bucket:
            raise RuntimeError(f"S3 bucket for region '{region}' is not configured")
        if region not in self.clients:
            self.clients[region] = self.boto3.client("s3", region_name=reg, endpoint_url=settings.S3_ENDPOINT_URL or None)
        return self.clients[region], bucket

    def put(self, region, key, data, worm=False):
        c, b = self._c(region)
        kw = {"ServerSideEncryption": "AES256"}
        if worm and settings.S3_OBJECT_LOCK_DAYS > 0:
            from datetime import datetime, timedelta, timezone
            kw.update(ObjectLockMode="COMPLIANCE", ObjectLockRetainUntilDate=datetime.now(timezone.utc) + timedelta(days=settings.S3_OBJECT_LOCK_DAYS))
        c.put_object(Bucket=b, Key=key, Body=data, ContentType="application/pdf", **kw)

    def get(self, region, key):
        c, b = self._c(region); return c.get_object(Bucket=b, Key=key)["Body"].read()

    def delete(self, region, key):
        c, b = self._c(region); c.delete_object(Bucket=b, Key=key)


_storage: Storage | None = None


def storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = S3Storage() if settings.STORAGE_BACKEND == "s3" else LocalStorage(settings.STORAGE_DIR)
    return _storage


def new_key(region: str, org_id: int, kind: str, ext: str = "pdf") -> str:
    return f"{region}/{org_id}/{kind}/{uuid.uuid4().hex}.{ext}"
