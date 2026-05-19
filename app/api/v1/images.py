import logging

import httpx
from fastapi import APIRouter, HTTPException, status
from app.core.config import settings
from app.models.schemas import GenerateRequest, GenerateResponse, HealthResponse
from app.services import image_service, llm_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def comfyui_health() -> HealthResponse:
    """Check ComfyUI availability."""
    try:
        auth_params = {"token": settings.COMFYUI_TOKEN} if settings.COMFYUI_TOKEN else {}
        async with httpx.AsyncClient(timeout=5, verify=settings.COMFYUI_VERIFY_SSL) as client:
            if settings.COMFYUI_TOKEN:
                await client.get(f"{settings.COMFYUI_URL}/", params=auth_params, follow_redirects=True)
            resp = await client.get(f"{settings.COMFYUI_URL}/system_stats")
            resp.raise_for_status()
            data = resp.json()
            device = data.get("devices", [{}])[0].get("name", "unknown")
            return HealthResponse(status="ok", detail=f"ComfyUI running — device: {device}")
    except httpx.TimeoutException:
        return HealthResponse(status="unavailable", detail="ComfyUI timed out")
    except Exception as e:
        return HealthResponse(status="unavailable", detail=str(e))


@router.post("/generate", response_model=GenerateResponse)
async def generate_image(payload: GenerateRequest) -> GenerateResponse:
    """Generate a kitchen concept image using SDXL via ComfyUI."""
    logger.info(
        "generate request — session=%s style=%r layout=%r finish=%r project_type=%r has_image=%s brief_len=%s",
        payload.session_id,
        payload.style,
        payload.layout,
        payload.finish,
        payload.project_type,
        payload.client_image_b64 is not None,
        len(payload.design_brief) if payload.design_brief else 0,
    )
    try:
        positive_prompt, _ = await llm_service.build_image_prompt(
            session_id=payload.session_id,
            style=payload.style,
            layout=payload.layout,
            finish=payload.finish,
            project_type=payload.project_type,
            design_brief=payload.design_brief,
        )
        logger.info("resolved prompt — session=%s prompt=%r", payload.session_id, positive_prompt)
        result = await image_service.generate_kitchen_concept(
            session_id=payload.session_id,
            positive_prompt=positive_prompt,
            client_image_b64=payload.client_image_b64,
        )
        return GenerateResponse(session_id=payload.session_id, **result)
    except TimeoutError:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="ComfyUI timed out")
    except Exception as e:
        logger.exception("Image generation failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
