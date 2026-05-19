"""Main image generation orchestrator: routes img2img vs txt2img via ComfyUI."""
import asyncio
import base64
import logging
import time
import uuid
from contextlib import asynccontextmanager

import httpx

from app.core.config import settings
from app.services import workflows
from app.services.storage import save_image

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 2  # seconds between history checks


def _comfyui_headers() -> dict[str, str]:
    """Return auth headers for Comfy.org Cloud; empty dict for local ComfyUI."""
    if settings.comfyui_cloud_mode:
        return {"X-API-Key": settings.COMFYUI_API_KEY}
    return {}


def _comfyui_params() -> dict[str, str]:
    """Return base query params; adds token for Vast.ai auth."""
    if settings.COMFYUI_TOKEN:
        return {"token": settings.COMFYUI_TOKEN}
    return {}


@asynccontextmanager
async def _comfyui_client(timeout: int = 30):
    """Authenticated httpx client for ComfyUI.

    When COMFYUI_TOKEN is set (Vast.ai), makes a GET to /?token=... first to
    establish the session cookie so subsequent POST requests are not redirected.
    """
    async with httpx.AsyncClient(
        timeout=timeout,
        headers=_comfyui_headers(),
        verify=settings.COMFYUI_VERIFY_SSL,
    ) as client:
        if settings.COMFYUI_TOKEN:
            await client.get(
                f"{settings.COMFYUI_URL}/",
                params=_comfyui_params(),
                follow_redirects=True,
            )
        yield client


def _prompt_url() -> str:
    """POST endpoint to submit a workflow."""
    if settings.comfyui_cloud_mode:
        return f"{settings.COMFYUI_URL}/api/prompt"
    return f"{settings.COMFYUI_URL}/prompt"


def _history_url(prompt_id: str) -> str:
    """GET endpoint to poll job status."""
    if settings.comfyui_cloud_mode:
        return f"{settings.COMFYUI_URL}/api/job/{prompt_id}/status"
    return f"{settings.COMFYUI_URL}/history/{prompt_id}"


def _view_url() -> str:
    """GET endpoint to download output image bytes."""
    if settings.comfyui_cloud_mode:
        return f"{settings.COMFYUI_URL}/api/view"
    return f"{settings.COMFYUI_URL}/view"


def _upload_url() -> str:
    """POST endpoint to upload a reference image."""
    if settings.comfyui_cloud_mode:
        return f"{settings.COMFYUI_URL}/api/upload/image"
    return f"{settings.COMFYUI_URL}/upload/image"


def _is_job_done(prompt_id: str, payload: dict) -> tuple[bool, dict]:
    """Parse the poll response for both local and cloud formats.

    Local: { "<prompt_id>": { "outputs": { "<node>": { "images": [...] } } } }
    Cloud: { "status": "completed", "outputs": { "<node>": { "images": [...] } } }
    Returns (done, outputs_dict).
    """
    if settings.comfyui_cloud_mode:
        if payload.get("status") == "completed":
            return True, payload.get("outputs", {})
        return False, {}
    outputs = payload.get(prompt_id, {}).get("outputs", {})
    return bool(outputs), outputs


async def generate_kitchen_concept(
    session_id: str,
    positive_prompt: str,
    client_image_b64: str | None = None,
) -> dict:
    """Orchestrate image generation and return a dict with image_url, prompt_used, pipeline."""
    start = time.monotonic()

    if client_image_b64:
        image_url, prompt_used = await _run_img2img(client_image_b64, positive_prompt, session_id)
        pipeline = "img2img"
    else:
        image_url, prompt_used = await _run_txt2img(positive_prompt, session_id)
        pipeline = "txt2img"

    elapsed = time.monotonic() - start
    logger.info("session=%s pipeline=%s elapsed=%.2fs url=%s", session_id, pipeline, elapsed, image_url)

    return {"image_url": image_url, "prompt_used": prompt_used, "pipeline": pipeline}


async def _run_img2img(image_b64: str, positive_prompt: str, session_id: str) -> tuple[str, str]:
    image_bytes = base64.b64decode(image_b64)
    filename = f"{uuid.uuid4().hex}.png"
    uploaded_name = await _upload_image_to_comfyui(image_bytes, filename)
    workflow = workflows.get_img2img_workflow(positive_prompt, uploaded_name)
    prompt_id = await _queue_comfyui_prompt(workflow)
    image_data = await _wait_for_result(prompt_id, output_node="17")
    url = await save_image(image_data, session_id=session_id, image_type="img2img")
    return url, workflow["6"]["inputs"]["text"]


async def _run_txt2img(positive_prompt: str, session_id: str) -> tuple[str, str]:
    workflow = workflows.get_txt2img_workflow(positive_prompt)
    prompt_id = await _queue_comfyui_prompt(workflow)
    image_data = await _wait_for_result(prompt_id, output_node="11")
    url = await save_image(image_data, session_id=session_id, image_type="txt2img")
    return url, workflow["6"]["inputs"]["text"]


async def _upload_image_to_comfyui(image_bytes: bytes, filename: str | None = None) -> str:
    """Upload a reference image to ComfyUI and return the stored filename."""
    filename = filename or f"{uuid.uuid4().hex}.png"
    async with _comfyui_client(timeout=30) as client:
        response = await client.post(
            _upload_url(),
            files={"image": (filename, image_bytes, "image/png")},
            data={"type": "input", "overwrite": "true"},
        )
        response.raise_for_status()
        name = response.json()["name"]
    logger.debug("Uploaded reference image to ComfyUI as %s", name)
    return name


async def _queue_comfyui_prompt(workflow: dict) -> str:
    """Submit a workflow to ComfyUI and return the prompt_id."""
    client_id = uuid.uuid4().hex
    async with _comfyui_client(timeout=30) as client:
        resp = await client.post(
            _prompt_url(),
            json={"prompt": workflow, "client_id": client_id},
        )
        if not resp.is_success:
            logger.error("ComfyUI rejected prompt — status=%s body=%s", resp.status_code, resp.text)
        resp.raise_for_status()
        body = resp.json()
        logger.info("ComfyUI prompt response: %s", body)
        if "prompt_id" not in body:
            raise RuntimeError(f"ComfyUI rejected workflow: {body}")
        prompt_id: str = body["prompt_id"]
    logger.debug("Queued ComfyUI prompt — id=%s (mode=%s)", prompt_id, "cloud" if settings.comfyui_cloud_mode else "local")
    return prompt_id


async def _wait_for_result(prompt_id: str, output_node: str, timeout: int = 180) -> bytes:
    """Poll the job status endpoint every 2s until images are ready, then fetch bytes."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout

    async with _comfyui_client(timeout=10) as client:
        while loop.time() < deadline:
            resp = await client.get(_history_url(prompt_id))
            resp.raise_for_status()

            done, outputs = _is_job_done(prompt_id, resp.json())
            if done and outputs.get(output_node):
                image_meta = outputs[output_node]["images"][0]
                img_resp = await client.get(
                    _view_url(),
                    params={
                        "filename": image_meta["filename"],
                        "subfolder": image_meta.get("subfolder", ""),
                        "type": "output",
                    },
                )
                img_resp.raise_for_status()
                logger.debug("Retrieved image — prompt_id=%s filename=%s", prompt_id, image_meta["filename"])
                return img_resp.content

            await asyncio.sleep(_POLL_INTERVAL)

    raise TimeoutError(f"ComfyUI did not complete prompt {prompt_id} within {timeout}s")
