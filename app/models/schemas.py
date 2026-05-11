from typing import Optional
from pydantic import BaseModel, Field


# ── Chat ────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    image_b64: Optional[str] = None  # base64-encoded image for vision


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    specs_ready: bool = False  # True when LLM signals SPECS_READY


# ── Images ───────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    session_id: str
    client_image_b64: Optional[str] = None  # if provided → img2img pipeline
    style: str = "modern"


class GenerateResponse(BaseModel):
    session_id: str
    image_url: str
    prompt_used: str
    pipeline: str  # "img2img" | "txt2img"


# ── Design / Kitchen Specs ───────────────────────────────────────────────────

class KitchenSpecs(BaseModel):
    width_cm: Optional[float] = None
    depth_cm: Optional[float] = None
    height_cm: Optional[float] = None
    style: Optional[str] = None
    material: Optional[str] = None
    color: Optional[str] = None
    num_drawers: Optional[int] = None
    num_doors: Optional[int] = None
    has_island: bool = False
    notes: Optional[str] = None


class ExtractSpecsRequest(BaseModel):
    session_id: str


class ExtractSpecsResponse(BaseModel):
    session_id: str
    specs: KitchenSpecs
    confidence: float = Field(ge=0.0, le=1.0)


class GenerateCSVRequest(BaseModel):
    specs: KitchenSpecs
    project_name: str = "kitchen"


class GenerateCSVResponse(BaseModel):
    csv_content: str
    filename: str


# ── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    detail: Optional[str] = None
