from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


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
# Aligned with Studio spec: docs/specs/e7-sketch-to-layout-extraction/59-sketch-extraction-contract.md

SketchConfidence = Literal["HIGH", "MEDIUM", "LOW", "MISSING"]
SketchLayoutValue = Literal["LINEAR", "L_SHAPE", "U_SHAPE", "ISLAND", "PENINSULA", "GALLEY", "CUSTOM", "UNKNOWN"]
SketchProjectTypeValue = Literal["KITCHEN", "CLOSET", "BOTH", "UNKNOWN"]
SketchUnitValue = Literal["MM", "CM", "IN", "UNKNOWN"]
SketchZoneTypeValue = Literal["SINK", "RANGE", "COOKTOP", "REFRIGERATOR", "DISHWASHER", "OVEN",
                               "PANTRY", "TALL_STORAGE", "OPEN_SHELVING", "WORKSPACE", "APPLIANCE", "OTHER"]
SketchObstacleTypeValue = Literal["WINDOW", "DOOR", "COLUMN", "OUTLET", "WATER",
                                   "GAS", "DRAIN", "RANGE_HOOD", "APPLIANCE", "OTHER"]
SketchCabinetCategoryValue = Literal["UPPER", "LOWER", "CORNER", "TALL", "SINK",
                                      "ISLAND", "DRAWER_BASE", "APPLIANCE", "FILLER", "PANEL"]
SketchMissingInfoSeverity = Literal["ERROR", "WARNING", "INFO"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class SketchStringField(_CamelModel):
    value: Optional[str] = None
    confidence: SketchConfidence
    source_text: Optional[str] = Field(None, alias="sourceText")


class SketchIntField(_CamelModel):
    value: Optional[int] = None
    confidence: SketchConfidence
    source_text: Optional[str] = Field(None, alias="sourceText")


class SketchMeasurement(_CamelModel):
    value: Optional[float] = None
    unit: Optional[SketchUnitValue] = None
    confidence: SketchConfidence
    source_text: Optional[str] = Field(None, alias="sourceText")


class SketchWallCandidate(_CamelModel):
    wall_code: SketchStringField = Field(alias="wallCode")
    length: SketchMeasurement
    height: SketchMeasurement
    angle_deg: Optional[SketchIntField] = Field(None, alias="angleDeg")


class SketchZoneCandidate(_CamelModel):
    zone_code: SketchStringField = Field(alias="zoneCode")
    zone_type: SketchStringField = Field(alias="zoneType")
    wall_code: Optional[SketchStringField] = Field(None, alias="wallCode")
    x: Optional[SketchMeasurement] = None
    width: Optional[SketchMeasurement] = None


class SketchObstacleCandidate(_CamelModel):
    obstacle_type: SketchStringField = Field(alias="obstacleType")
    label: SketchStringField
    wall_code: Optional[SketchStringField] = Field(None, alias="wallCode")
    x: Optional[SketchMeasurement] = None
    width: Optional[SketchMeasurement] = None


class SketchCabinetCandidate(_CamelModel):
    candidate_code: str = Field(alias="candidateCode")
    category: SketchStringField
    label: SketchStringField
    wall_code: Optional[SketchStringField] = Field(None, alias="wallCode")
    x: Optional[SketchMeasurement] = None
    width: Optional[SketchMeasurement] = None
    height: Optional[SketchMeasurement] = None
    depth: Optional[SketchMeasurement] = None
    doors: Optional[SketchIntField] = None
    drawers: Optional[SketchIntField] = None


class SketchMissingInfo(_CamelModel):
    code: str
    message: str
    severity: SketchMissingInfoSeverity


class SketchRawExtraction(_CamelModel):
    model: str
    pipeline: str = "sketch-analysis"
    text_observed: list[str] = Field(default_factory=list, alias="textObserved")
    generated_at: str = Field(alias="generatedAt")


class SketchAnalysisRequest(BaseModel):
    image_b64: str
    image_mime_type: str = "image/jpeg"
    session_code: Optional[str] = None
    project_type_hint: Optional[SketchProjectTypeValue] = None
    unit_hint: SketchUnitValue = "CM"
    language: str = "es-MX"
    user_prompt: Optional[str] = None


class SketchAnalysisResponse(_CamelModel):
    schema_version: str = Field("1.0", alias="schemaVersion")
    request_id: str = Field(alias="requestId")
    project_type: SketchStringField = Field(alias="projectType")
    layout: SketchStringField
    unit: SketchStringField
    walls: list[SketchWallCandidate] = []
    zones: list[SketchZoneCandidate] = []
    obstacles: list[SketchObstacleCandidate] = []
    cabinet_candidates: list[SketchCabinetCandidate] = Field(default_factory=list, alias="cabinetCandidates")
    missing_info: list[SketchMissingInfo] = Field(default_factory=list, alias="missingInfo")
    questions: list[str] = []
    warnings: list[str] = []
    raw_extraction: SketchRawExtraction = Field(alias="rawExtraction")


# ── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    detail: Optional[str] = None
