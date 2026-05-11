from fastapi import APIRouter, HTTPException, status
from app.models.schemas import (
    ExtractedKitchenSpecs,
    ExtractSpecsRequest,
    ExtractSpecsResponse,
    GenerateCSVRequest,
    GenerateCSVResponse,
)
from app.services import csv_generator
from app.services.llm_service import extract_specs

router = APIRouter()


@router.post("/extract-specs", response_model=ExtractSpecsResponse)
async def extract_kitchen_specs(payload: ExtractSpecsRequest) -> ExtractSpecsResponse:
    """Extract structured kitchen specs from the session's conversation history using GPT-4o."""
    try:
        result = await extract_specs(payload.session_id)
        specs = ExtractedKitchenSpecs(**result["specs"])
        return ExtractSpecsResponse(
            session_id=payload.session_id,
            specs=specs,
            confidence=result["confidence"],
        )
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
