import logging

from fastapi import APIRouter, HTTPException, status

from app.models.schemas import SketchAnalysisRequest, SketchAnalysisResponse
from app.services import sketch_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=SketchAnalysisResponse)
async def analyze_sketch(payload: SketchAnalysisRequest) -> SketchAnalysisResponse:
    """Analyze a hand-drawn sketch and return a structured draft layout and cabinet list.

    The response always includes confidence values and warnings for uncertain items.
    Missing dimensions are represented as null — never silently invented.
    """
    try:
        return await sketch_service.analyze_sketch(
            image_b64=payload.image_b64,
            image_mime_type=payload.image_mime_type,
            context=payload.context,
            project_type=payload.project_type,
            unit=payload.unit,
            session_id=payload.session_id,
        )
    except Exception as e:
        logger.exception("Sketch analysis failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
