"""Main image generation orchestrator: routes img2img vs txt2img via ComfyUI."""
import asyncio
import base64
import logging
import time
import uuid

import httpx

from app.core.config import settings
from app.services import workflows
from app.services.storage import save_image

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 2  # seconds between history checks


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
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.COMFYUI_URL}/upload/image",
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
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.COMFYUI_URL}/prompt",
            json={"prompt": workflow, "client_id": client_id},
        )
        resp.raise_for_status()
        prompt_id: str = resp.json()["prompt_id"]
    logger.debug("Queued ComfyUI prompt — id=%s", prompt_id)
    return prompt_id


async def _wait_for_result(prompt_id: str, output_node: str, timeout: int = 180) -> bytes:
    """Poll GET /history/{prompt_id} every 2s until images are ready, then fetch bytes from GET /view."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout

    async with httpx.AsyncClient(timeout=10) as client:
        while loop.time() < deadline:
            resp = await client.get(f"{settings.COMFYUI_URL}/history/{prompt_id}")
            resp.raise_for_status()
            history = resp.json()

            outputs = history.get(prompt_id, {}).get("outputs", {})
            if outputs.get(output_node):
                image_meta = outputs[output_node]["images"][0]
                img_resp = await client.get(
                    f"{settings.COMFYUI_URL}/view",
                    params={
                        "filename": image_meta["filename"],
                        "subfolder": image_meta.get("subfolder", ""),
                        "type": "output",
                    },
                )
                img_resp.raise_for_status()
                logger.debug("Retrieved image from ComfyUI — prompt_id=%s filename=%s", prompt_id, image_meta["filename"])
                return img_resp.content

            await asyncio.sleep(_POLL_INTERVAL)

    raise TimeoutError(f"ComfyUI did not complete prompt {prompt_id} within {timeout}s")
