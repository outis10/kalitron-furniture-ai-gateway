from fastapi import APIRouter, HTTPException, status
from app.models.schemas import ChatRequest, ChatResponse
from app.services import llm_service

router = APIRouter()


@router.post("/message", response_model=ChatResponse)
async def send_message(payload: ChatRequest) -> ChatResponse:
    """Send a user message and receive an AI reply. Sets specs_ready=True when kitchen specs are complete."""
    try:
        reply, specs_ready = await llm_service.chat(
            session_id=payload.session_id,
            user_message=payload.message,
            image_b64=payload.image_b64,
            image_mime_type=payload.image_mime_type,
        )
        return ChatResponse(session_id=payload.session_id, reply=reply, specs_ready=specs_ready)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
