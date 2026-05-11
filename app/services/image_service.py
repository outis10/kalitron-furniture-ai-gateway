"""Main image generation orchestrator: routes img2img vs txt2img via ComfyUI."""
import asyncio
import base64
import uuid
from copy import deepcopy

import httpx

from app.core.config import settings
from app.services import workflows
from app.services.storage import save_image


async def generate_kitchen_concept(
    session_id: str,
    positive_prompt: str,
    style: str = "modern",
    client_image_b64: str | None = None,
) -> dict:
    """Orchestrate image generation and return a dict with image_url, prompt_used, pipeline."""
    if client_image_b64:
        image_url, prompt_used = await _run_img2img(client_image_b64, positive_prompt)
        pipeline = "img2img"
    else:
        image_url, prompt_used = await _run_txt2img(positive_prompt, style)
        pipeline = "txt2img"

    return {"image_url": image_url, "prompt_used": prompt_used, "pipeline": pipeline}


async def _run_img2img(image_b64: str, positive_prompt: str) -> tuple[str, str]:
    image_bytes = base64.b64decode(image_b64)
    filename = await _upload_image_to_comfyui(image_bytes)
    workflow = workflows.get_img2img_workflow(positive_prompt, filename)
    image_data = await _run_workflow(workflow, output_node="17")
    url = await save_image(image_data)
    return url, workflow["6"]["inputs"]["text"]


async def _run_txt2img(positive_prompt: str, style: str) -> tuple[str, str]:
    workflow = workflows.get_txt2img_workflow(positive_prompt, style)
    image_data = await _run_workflow(workflow, output_node="11")
    url = await save_image(image_data)
    return url, workflow["6"]["inputs"]["text"]


async def _upload_image_to_comfyui(image_bytes: bytes) -> str:
    filename = f"{uuid.uuid4().hex}.png"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.COMFYUI_URL}/upload/image",
            files={"image": (filename, image_bytes, "image/png")},
            data={"type": "input", "overwrite": "true"},
        )
        response.raise_for_status()
        return response.json()["name"]


async def _run_workflow(workflow: dict, output_node: str) -> bytes:
    client_id = uuid.uuid4().hex

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.COMFYUI_URL}/prompt",
            json={"prompt": workflow, "client_id": client_id},
        )
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

    image_data = await _poll_for_result(prompt_id, output_node)
    return image_data


async def _poll_for_result(prompt_id: str, output_node: str, timeout: int = 300) -> bytes:
    deadline = asyncio.get_event_loop().time() + timeout

    async with httpx.AsyncClient(timeout=10) as client:
        while asyncio.get_event_loop().time() < deadline:
            resp = await client.get(f"{settings.COMFYUI_URL}/history/{prompt_id}")
            resp.raise_for_status()
            history = resp.json()

            if prompt_id in history and history[prompt_id].get("outputs", {}).get(output_node):
                image_meta = history[prompt_id]["outputs"][output_node]["images"][0]
                img_resp = await client.get(
                    f"{settings.COMFYUI_URL}/view",
                    params={"filename": image_meta["filename"], "subfolder": image_meta.get("subfolder", ""), "type": "output"},
                )
                img_resp.raise_for_status()
                return img_resp.content

            await asyncio.sleep(2)

    raise TimeoutError(f"ComfyUI did not complete prompt {prompt_id} within {timeout}s")
