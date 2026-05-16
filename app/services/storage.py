"""
Image and file storage — Strategy pattern.

Backend selection at startup via get_storage_backend():
  R2StorageBackend    — when R2_ENDPOINT_URL + credentials are configured
  LocalStorageBackend — always-available fallback (OUTPUT_DIR + /outputs static route)

To add a new provider (e.g. AWS S3, MinIO):
  1. Subclass StorageBackend and implement save() + public_url() + name.
  2. Add it to get_storage_backend() selection logic.
  No other file needs to change.

ADR ref: kalitron-furniture-studio/docs/adr/ADR-004-cloudflare-r2-vs-s3.md
"""
from __future__ import annotations

import asyncio
import io
import logging
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_CONTROL_IMMUTABLE = "public, max-age=31536000, immutable"


# ── Abstract backend (Strategy interface) ────────────────────────────────────

class StorageBackend(ABC):
    """Strategy interface — concrete backends must implement save() and public_url()."""

    @abstractmethod
    async def save(
        self,
        data: bytes,
        key: str,
        content_type: str = "application/octet-stream",
        cache_control: str = "",
    ) -> str:
        """Persist *data* under *key* and return its public URL."""

    @abstractmethod
    def public_url(self, key: str) -> str:
        """Return the public URL for an already-stored *key*."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend identifier (used in logs)."""


# ── Cloudflare R2 backend ─────────────────────────────────────────────────────

class R2StorageBackend(StorageBackend):
    """Cloudflare R2 via S3-compatible boto3 client."""

    def __init__(self) -> None:
        from app.core.config import settings
        import boto3
        from botocore.config import Config

        self._bucket = settings.R2_BUCKET_NAME
        self._public_base = settings.R2_PUBLIC_URL.rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
        )

    @property
    def name(self) -> str:
        return "Cloudflare R2"

    async def save(
        self,
        data: bytes,
        key: str,
        content_type: str = "application/octet-stream",
        cache_control: str = _CACHE_CONTROL_IMMUTABLE,
    ) -> str:
        extra: dict = {"ContentType": content_type}
        if cache_control:
            extra["CacheControl"] = cache_control

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.put_object(Bucket=self._bucket, Key=key, Body=data, **extra),
        )
        url = self.public_url(key)
        logger.debug("R2 upload ok — key=%s bytes=%d url=%s", key, len(data), url)
        return url

    def public_url(self, key: str) -> str:
        return f"{self._public_base}/{key}"


# ── Local filesystem backend ──────────────────────────────────────────────────

class LocalStorageBackend(StorageBackend):
    """Saves to OUTPUT_DIR; files served by FastAPI's /outputs StaticFiles route."""

    def __init__(self) -> None:
        from app.core.config import settings
        self._output_dir = Path(settings.OUTPUT_DIR)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "Local filesystem"

    async def save(
        self,
        data: bytes,
        key: str,
        content_type: str = "application/octet-stream",
        cache_control: str = "",
    ) -> str:
        # Flatten key path (concepts/session/file.jpg → concepts_session_file.jpg)
        # so the flat /outputs directory doesn't need sub-folders.
        flat_name = key.replace("/", "_")
        path = self._output_dir / flat_name
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, path.write_bytes, data)
        url = self.public_url(flat_name)
        logger.debug("Local save ok — path=%s bytes=%d url=%s", path, len(data), url)
        return url

    def public_url(self, key: str) -> str:
        from app.core.config import settings
        return f"{settings.GATEWAY_PUBLIC_URL.rstrip('/')}/outputs/{key}"


# ── Factory (lazy singleton) ──────────────────────────────────────────────────

_backend: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    """Return the active StorageBackend, lazily initialised once per process."""
    global _backend
    if _backend is None:
        from app.core.config import settings
        if settings.r2_configured:
            _backend = R2StorageBackend()
        else:
            _backend = LocalStorageBackend()
        logger.info("Storage backend selected: %s", _backend.name)
    return _backend


def _reset_backend() -> None:
    """Reset the singleton — use only in tests."""
    global _backend
    _backend = None


# ── Key builder ───────────────────────────────────────────────────────────────

def build_image_key(session_id: str, image_type: str = "concept", seed: str | None = None) -> str:
    """Return the canonical object key: concepts/{session_id}/{image_type}_{seed}.jpg"""
    seed = seed or uuid.uuid4().hex[:8]
    return f"concepts/{session_id}/{image_type}_{seed}.jpg"


# ── JPEG conversion ───────────────────────────────────────────────────────────

def _to_jpeg(raw: bytes, quality: int = 90) -> bytes:
    """Convert any PIL-readable image (e.g. PNG from ComfyUI) to JPEG bytes."""
    from PIL import Image
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


# ── Public API ────────────────────────────────────────────────────────────────

async def save_image(
    data: bytes,
    session_id: str = "default",
    image_type: str = "concept",
    seed: str | None = None,
) -> str:
    """Convert image to JPEG, upload under the canonical key, and return the public URL."""
    jpeg_data = _to_jpeg(data)
    key = build_image_key(session_id, image_type, seed)
    return await get_storage_backend().save(jpeg_data, key, content_type="image/jpeg")


async def save_file(data: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
    """Persist arbitrary file bytes (CSV, PDF, etc.) and return the public URL."""
    return await get_storage_backend().save(data, filename, content_type=content_type)


async def upload_to_r2(image_bytes: bytes, key: str) -> str:
    """Explicitly upload to R2 (or active backend) with canonical image settings."""
    return await get_storage_backend().save(
        image_bytes, key, content_type="image/jpeg", cache_control=_CACHE_CONTROL_IMMUTABLE
    )
