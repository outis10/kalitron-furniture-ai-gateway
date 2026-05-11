"""Tests for the storage Strategy pattern."""
import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from pathlib import Path

from app.services.storage import (
    LocalStorageBackend,
    R2StorageBackend,
    StorageBackend,
    _reset_backend,
    build_image_key,
    get_storage_backend,
    save_image,
    upload_to_r2,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_tiny_png() -> bytes:
    """1×1 white PNG — valid Pillow input."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color=(255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


# ── Unit: build_image_key ──────────────────────────────────────────────────────

def test_build_image_key_format():
    key = build_image_key("sess123", "concept", "abcd1234")
    assert key == "concepts/sess123/concept_abcd1234.jpg"


def test_build_image_key_auto_seed():
    key = build_image_key("sess456", "txt2img")
    assert key.startswith("concepts/sess456/txt2img_")
    assert key.endswith(".jpg")


# ── Unit: backend selection ────────────────────────────────────────────────────

def test_get_storage_backend_returns_local_when_r2_not_configured(monkeypatch):
    _reset_backend()
    monkeypatch.setattr("app.core.config.settings.R2_ENDPOINT_URL", "")
    backend = get_storage_backend()
    assert isinstance(backend, LocalStorageBackend)
    _reset_backend()


def test_get_storage_backend_returns_r2_when_configured(monkeypatch):
    _reset_backend()
    monkeypatch.setattr("app.core.config.settings.R2_ENDPOINT_URL", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setattr("app.core.config.settings.R2_ACCESS_KEY_ID", "key")
    monkeypatch.setattr("app.core.config.settings.R2_SECRET_ACCESS_KEY", "secret")

    with patch("boto3.client", return_value=MagicMock()):
        backend = get_storage_backend()

    assert isinstance(backend, R2StorageBackend)
    _reset_backend()


def test_get_storage_backend_is_singleton():
    _reset_backend()
    b1 = get_storage_backend()
    b2 = get_storage_backend()
    assert b1 is b2
    _reset_backend()


# ── Unit: LocalStorageBackend ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_local_backend_save_returns_outputs_url(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.OUTPUT_DIR", str(tmp_path))
    backend = LocalStorageBackend()
    url = await backend.save(b"hello", "test.txt", content_type="text/plain")
    assert url == "/outputs/test.txt"
    assert (tmp_path / "test.txt").read_bytes() == b"hello"


@pytest.mark.asyncio
async def test_local_backend_flattens_nested_key(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.OUTPUT_DIR", str(tmp_path))
    backend = LocalStorageBackend()
    url = await backend.save(b"data", "concepts/sess/concept_abc.jpg")
    assert url == "/outputs/concepts_sess_concept_abc.jpg"


# ── Unit: R2StorageBackend ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_r2_backend_save_calls_put_object(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.R2_ENDPOINT_URL", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setattr("app.core.config.settings.R2_ACCESS_KEY_ID", "key")
    monkeypatch.setattr("app.core.config.settings.R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr("app.core.config.settings.R2_BUCKET_NAME", "test-bucket")
    monkeypatch.setattr("app.core.config.settings.R2_PUBLIC_URL", "https://cdn.example.com")

    mock_s3 = MagicMock()
    with patch("boto3.client", return_value=mock_s3):
        backend = R2StorageBackend()
        url = await backend.save(b"imgdata", "concepts/s/concept_abc.jpg", content_type="image/jpeg")

    mock_s3.put_object.assert_called_once()
    kwargs = mock_s3.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "test-bucket"
    assert kwargs["Key"] == "concepts/s/concept_abc.jpg"
    assert kwargs["ContentType"] == "image/jpeg"
    assert "CacheControl" in kwargs
    assert url == "https://cdn.example.com/concepts/s/concept_abc.jpg"


# ── Integration: save_image ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_image_converts_png_to_jpeg_and_uses_canonical_key(tmp_path, monkeypatch):
    _reset_backend()
    monkeypatch.setattr("app.core.config.settings.OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr("app.core.config.settings.R2_ENDPOINT_URL", "")

    png_bytes = _make_tiny_png()
    url = await save_image(png_bytes, session_id="sess1", image_type="concept", seed="seed01")

    assert url == "/outputs/concepts_sess1_concept_seed01.jpg"
    saved = (tmp_path / "concepts_sess1_concept_seed01.jpg").read_bytes()
    assert saved[:2] == b"\xff\xd8"  # JPEG magic bytes
    _reset_backend()


@pytest.mark.asyncio
async def test_upload_to_r2_delegates_to_active_backend(tmp_path, monkeypatch):
    _reset_backend()
    monkeypatch.setattr("app.core.config.settings.OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr("app.core.config.settings.R2_ENDPOINT_URL", "")

    url = await upload_to_r2(b"raw", "concepts/s/img_abc.jpg")
    assert url == "/outputs/concepts_s_img_abc.jpg"
    _reset_backend()
