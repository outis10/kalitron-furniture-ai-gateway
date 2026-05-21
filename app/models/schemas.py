from typing import Literal, Optional
from pydantic import BaseModel, Field


# ── Chat ────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    image_b64: Optional[str] = None  # base64-encoded image for vision
    image_mime_type: str = "image/jpeg"


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    specs_ready: bool = False  # True when LLM signals SPECS_READY


# ── Images ───────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    session_id: str
    client_image_b64: Optional[str] = None  # if provided → img2img pipeline
    style: str = "moderno"  # moderno | rustico | minimalista | clasico | industrial
    layout: Optional[str] = None  # island | l-shaped | u-shaped | galley
    finish: Optional[str] = None  # white matte | oak wood | gray matte | black matte
    project_type: str = "KITCHEN"  # KITCHEN | CLOSET | BOTH
    design_brief: Optional[str] = None


class GenerateResponse(BaseModel):
    session_id: str
    image_url: str
    prompt_used: str
    pipeline: str  # "img2img" | "txt2img"


# ── Design / Kitchen Specs ───────────────────────────────────────────────────

class KitchenSpecs(BaseModel):
    """Simple flat spec — used by csv_generator for cut-list production."""
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


class Cabinet(BaseModel):
    """Individual cabinet module extracted from the conversation."""
    id: str                          # U-01, L-02, C-01, T-01, S-01
    category: Literal["upper", "lower", "corner", "tall", "sink"]
    label: str                       # e.g. "Aéreo sobre estufa"
    width_mm: int
    height_mm: int
    depth_mm: int
    doors: int = 0
    drawers: int = 0
    material: str = "MDF 18mm"
    finish: str = "blanco mate"


class ExtractedKitchenSpecs(BaseModel):
    """Structured kitchen spec extracted from full conversation — used by spec extractor."""
    kitchen_type: Literal["L", "U", "lineal", "isla"] = "L"
    total_width_mm: int = 0
    total_height_mm: int = 2400
    total_depth_mm: int = 600
    style: str = "moderno"
    cabinets: list[Cabinet] = []


class ExtractSpecsRequest(BaseModel):
    session_id: str


class ExtractSpecsResponse(BaseModel):
    session_id: str
    specs: ExtractedKitchenSpecs
    confidence: float = Field(ge=0.0, le=1.0)


class GenerateCSVRequest(BaseModel):
    specs: KitchenSpecs
    project_name: str = "kitchen"


class GenerateCSVResponse(BaseModel):
    csv_content: str
    filename: str


# ── Sketch analysis ─────────────────────────────────────────────────────────

class SketchAnalysisRequest(BaseModel):
    image_b64: str
    image_mime_type: str = "image/jpeg"
    context: Optional[str] = None
    project_type: Optional[str] = None  # KITCHEN | CLOSET | BOTH | null = auto-detect
    unit: Literal["mm", "cm", "inches"] = "cm"
    session_id: Optional[str] = None


class SketchWall(BaseModel):
    label: str
    estimated_length_cm: Optional[float] = None
    confidence: float = Field(ge=0.0, le=1.0)


class SketchLayout(BaseModel):
    shape: Literal["L", "U", "lineal", "isla", "unknown"] = "unknown"
    walls: list[SketchWall] = []
    estimated_total_width_cm: Optional[float] = None
    estimated_total_depth_cm: Optional[float] = None
    confidence: float = Field(ge=0.0, le=1.0)


class SketchZone(BaseModel):
    type: Literal["sink", "cooktop", "refrigerator", "oven", "dishwasher", "window", "door", "column", "other"]
    wall: Optional[str] = None
    position_hint: Optional[str] = None  # "left" | "center" | "right" | "corner"
    confidence: float = Field(ge=0.0, le=1.0)


class SketchCabinet(BaseModel):
    id: str
    category: Literal["upper", "lower", "corner", "tall", "sink"]
    label: str
    estimated_width_cm: Optional[float] = None
    estimated_height_cm: Optional[float] = None
    estimated_depth_cm: Optional[float] = None
    wall: Optional[str] = None
    doors: Optional[int] = None
    drawers: Optional[int] = None
    confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = []


class SketchWarning(BaseModel):
    code: Literal[
        "missing_dimension",
        "low_confidence",
        "ambiguous_layout",
        "no_scale_reference",
        "partial_sketch",
        "unsupported_image",
        "other",
    ]
    message: str
    affected: Optional[str] = None


class SketchAnalysisResponse(BaseModel):
    session_id: Optional[str] = None
    detected_project_type: Literal["KITCHEN", "CLOSET", "BOTH", "UNKNOWN"]
    layout: SketchLayout
    zones: list[SketchZone] = []
    cabinets: list[SketchCabinet] = []
    overall_confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[SketchWarning] = []
    raw_notes: Optional[str] = None


# ── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    detail: Optional[str] = None
