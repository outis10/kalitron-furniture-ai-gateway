"""Image storage: Cloudflare R2 (prod) with local disk fallback (dev)."""
import uuid
from pathlib import Path

import httpx

from app.core.config import settings


async def save_image(image_bytes: bytes, filename: str | None = None) -> str:
    """Persist image bytes and return a public URL."""
    filename = filename or f"{uuid.uuid4().hex}.png"

    if settings.r2_configured:
        return await _upload_to_r2(image_bytes, filename)
    return await _save_locally(image_bytes, filename)


async def _upload_to_r2(image_bytes: bytes, filename: str) -> str:
    import boto3
    from botocore.config import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
    )

    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: s3.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=filename,
            Body=image_bytes,
            ContentType="image/png",
        ),
    )

    return f"{settings.R2_PUBLIC_URL.rstrip('/')}/{filename}"


async def _save_locally(image_bytes: bytes, filename: str) -> str:
    output_dir = Path(settings.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename

    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, path.write_bytes, image_bytes)

    return f"/outputs/{filename}"
