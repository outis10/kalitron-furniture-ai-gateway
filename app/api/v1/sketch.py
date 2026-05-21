import logging

from fastapi import APIRouter, HTTPException, status

from app.models.schemas import SketchAnalysisRequest, SketchAnalysisResponse
from app.services import sketch_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=SketchAnalysisResponse)
async def analyze_sketch(payload: SketchAnalysisRequest) -> SketchAnalysisResponse:
    """Analyze a hand-drawn sketch and return a structured draft layout and cabinet list.

    All extracted fields carry confidence (HIGH/MEDIUM/LOW/MISSING) and sourceText.
    Missing dimensions are null — never silently invented.
    Studio must present the result for user review before persisting.
    """
    try:
        return await sketch_service.analyze_sketch(
            image_b64=payload.image_b64,
            image_mime_type=payload.image_mime_type,
            session_code=payload.session_code,
            project_type_hint=payload.project_type_hint,
            unit_hint=payload.unit_hint,
            language=payload.language,
            user_prompt=payload.user_prompt,
        )
    except Exception as e:
        logger.exception("Sketch analysis failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
