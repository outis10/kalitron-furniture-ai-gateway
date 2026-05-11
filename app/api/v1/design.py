from fastapi import APIRouter, HTTPException, status
from app.models.schemas import (
    ExtractSpecsRequest,
    ExtractSpecsResponse,
    GenerateCSVRequest,
    GenerateCSVResponse,
    KitchenSpecs,
)
from app.services import csv_generator

router = APIRouter()


@router.post("/extract-specs", response_model=ExtractSpecsResponse)
async def extract_specs(payload: ExtractSpecsRequest) -> ExtractSpecsResponse:
    """Extract structured kitchen specs from the conversation history using GPT-4o."""
    try:
        from openai import AsyncOpenAI
        from app.core.config import settings
        from app.services.llm_service import get_session
        import json

        history = get_session(payload.session_id)
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=history + [
                {
                    "role": "user",
                    "content": (
                        "Extract the kitchen specifications from the conversation as JSON matching this schema: "
                        '{"width_cm": float|null, "depth_cm": float|null, "height_cm": float|null, '
                        '"style": string|null, "material": string|null, "color": string|null, '
                        '"num_drawers": int|null, "num_doors": int|null, "has_island": bool, "notes": string|null}. '
                        'Also include "confidence" (0.0 to 1.0). Reply with only the JSON object.'
                    ),
                }
            ],
            max_tokens=512,
            response_format={"type": "json_object"},
        )

        raw = json.loads(response.choices[0].message.content or "{}")
        confidence = float(raw.pop("confidence", 0.5))
        specs = KitchenSpecs(**raw)
        return ExtractSpecsResponse(session_id=payload.session_id, specs=specs, confidence=confidence)

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/generate-csv", response_model=GenerateCSVResponse)
async def generate_csv(payload: GenerateCSVRequest) -> GenerateCSVResponse:
    """Generate a cut-list CSV from kitchen specs with panel calculations."""
    try:
        csv_content, filename = csv_generator.generate_csv(payload.specs, payload.project_name)
        return GenerateCSVResponse(csv_content=csv_content, filename=filename)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
