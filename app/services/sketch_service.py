"""GPT-4o Vision pipeline for sketch-to-layout extraction.

Contract aligned with Studio spec:
docs/specs/e7-sketch-to-layout-extraction/59-sketch-extraction-contract.md
"""
import json
import logging
import uuid
from datetime import datetime, timezone

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.schemas import (
    SketchAnalysisResponse,
    SketchCabinetCandidate,
    SketchIntField,
    SketchMeasurement,
    SketchMissingInfo,
    SketchObstacleCandidate,
    SketchRawExtraction,
    SketchStringField,
    SketchWallCandidate,
    SketchZoneCandidate,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert furniture layout analyst specializing in kitchens and closets.
You analyze hand-drawn sketches, photos, or informal drawings and extract structured layout information.

STRICT RULES:
1. NEVER invent exact dimensions not visible or annotated in the sketch.
2. Missing or uncertain dimensions must have value: null and confidence: "MISSING".
3. Use confidence levels honestly:
   - HIGH: field clearly visible or explicitly labeled
   - MEDIUM: likely correct but needs review
   - LOW: weak inference from context
   - MISSING: field not found — value must be null
4. Always populate missingInfo and questions when important data is absent.
5. sourceText must be the exact text or visual cue from the sketch that led to the extraction, or null.
6. Wall codes: use letters A, B, C, D... in order of appearance.
7. Cabinet codes: A-001, A-002... per wall; category prefix U=upper, L=lower, C=corner, T=tall, S=sink.
8. All extracted measurements must include unit ("MM", "CM", "IN", "UNKNOWN").
9. textObserved: list every number or label you can read from the sketch.

LAYOUT VALUES: LINEAR | L_SHAPE | U_SHAPE | ISLAND | PENINSULA | GALLEY | CUSTOM | UNKNOWN
PROJECT TYPE VALUES: KITCHEN | CLOSET | BOTH | UNKNOWN
ZONE TYPES: SINK | RANGE | COOKTOP | REFRIGERATOR | DISHWASHER | OVEN | PANTRY | TALL_STORAGE | OPEN_SHELVING | WORKSPACE | APPLIANCE | OTHER
OBSTACLE TYPES: WINDOW | DOOR | COLUMN | OUTLET | WATER | GAS | DRAIN | RANGE_HOOD | APPLIANCE | OTHER
CABINET CATEGORIES: UPPER | LOWER | CORNER | TALL | SINK | ISLAND | DRAWER_BASE | APPLIANCE | FILLER | PANEL
MISSING INFO SEVERITY: ERROR | WARNING | INFO

Return ONLY this JSON (no explanation, no markdown):
{
  "projectType": { "value": "KITCHEN", "confidence": "HIGH", "sourceText": "..." },
  "layout": { "value": "LINEAR", "confidence": "MEDIUM", "sourceText": "..." },
  "unit": { "value": "MM", "confidence": "MEDIUM", "sourceText": "..." },
  "walls": [
    {
      "wallCode": { "value": "A", "confidence": "HIGH" },
      "length": { "value": 3120, "unit": "MM", "confidence": "MEDIUM", "sourceText": "312" },
      "height": { "value": null, "unit": "MM", "confidence": "MISSING", "sourceText": null },
      "angleDeg": { "value": 0, "confidence": "HIGH" }
    }
  ],
  "zones": [
    {
      "zoneCode": { "value": "SINK-1", "confidence": "HIGH" },
      "zoneType": { "value": "SINK", "confidence": "HIGH", "sourceText": "tarja dibujada" },
      "wallCode": { "value": "A", "confidence": "MEDIUM" },
      "x": { "value": null, "unit": "MM", "confidence": "MISSING", "sourceText": null },
      "width": { "value": 800, "unit": "MM", "confidence": "LOW", "sourceText": null }
    }
  ],
  "obstacles": [
    {
      "obstacleType": { "value": "WINDOW", "confidence": "LOW", "sourceText": "rectángulo sobre tarja" },
      "label": { "value": "Posible ventana", "confidence": "LOW" },
      "wallCode": { "value": "A", "confidence": "LOW" },
      "x": { "value": null, "unit": "MM", "confidence": "MISSING", "sourceText": null },
      "width": { "value": null, "unit": "MM", "confidence": "MISSING", "sourceText": null }
    }
  ],
  "cabinetCandidates": [
    {
      "candidateCode": "A-001",
      "category": { "value": "LOWER", "confidence": "HIGH" },
      "label": { "value": "Base puerta izquierda", "confidence": "MEDIUM" },
      "wallCode": { "value": "A", "confidence": "MEDIUM" },
      "x": { "value": 0, "unit": "MM", "confidence": "LOW", "sourceText": null },
      "width": { "value": 600, "unit": "MM", "confidence": "MEDIUM", "sourceText": "600" },
      "height": { "value": null, "unit": "MM", "confidence": "MISSING", "sourceText": null },
      "depth": { "value": 600, "unit": "MM", "confidence": "MEDIUM", "sourceText": "600" },
      "doors": { "value": 2, "confidence": "LOW", "sourceText": "dos frentes dibujados" },
      "drawers": { "value": 0, "confidence": "LOW" }
    }
  ],
  "missingInfo": [
    { "code": "ROOM_HEIGHT_MISSING", "message": "No se detectó altura total del cuarto.", "severity": "WARNING" }
  ],
  "questions": ["¿Las medidas están en milímetros o centímetros?"],
  "warnings": ["Las posiciones X son aproximadas porque el dibujo no tiene escala completa."],
  "textObserved": ["600", "312", "500", "tarja"]
}
"""


async def analyze_sketch(
    image_b64: str,
    image_mime_type: str = "image/jpeg",
    session_code: str | None = None,
    project_type_hint: str | None = None,
    unit_hint: str = "CM",
    language: str = "es-MX",
    user_prompt: str | None = None,
) -> SketchAnalysisResponse:
    """Send a sketch image to GPT-4o Vision and return structured layout extraction."""
    request_id = f"sketch-{uuid.uuid4().hex[:12]}"

    text_parts = ["Analyze this sketch and extract the layout and cabinet information."]
    if project_type_hint:
        text_parts.append(f"Project type hint: {project_type_hint}.")
    if unit_hint and unit_hint != "CM":
        text_parts.append(f"Annotations may use {unit_hint} — convert all output measurements to that unit and set unit field accordingly.")
    if language:
        text_parts.append(f"Use {language} for all label and message strings.")
    if user_prompt:
        text_parts.append(f"User context: {user_prompt}")

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": " ".join(text_parts)},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image_mime_type};base64,{image_b64}", "detail": "high"},
                },
            ],
        },
    ]

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        max_tokens=3000,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    raw = json.loads(response.choices[0].message.content or "{}")
    logger.info("sketch analysis — request_id=%s session_code=%s project_type=%s layout=%s",
                request_id, session_code,
                raw.get("projectType", {}).get("value"),
                raw.get("layout", {}).get("value"))

    return _parse_response(raw, request_id, settings.OPENAI_MODEL)


def _sf(raw: dict | None) -> SketchStringField:
    if not raw:
        return SketchStringField(value=None, confidence="MISSING")
    return SketchStringField(
        value=raw.get("value"),
        confidence=raw.get("confidence", "MISSING"),
        sourceText=raw.get("sourceText"),
    )


def _mf(raw: dict | None) -> SketchMeasurement:
    if not raw:
        return SketchMeasurement(value=None, confidence="MISSING")
    return SketchMeasurement(
        value=raw.get("value"),
        unit=raw.get("unit"),
        confidence=raw.get("confidence", "MISSING"),
        sourceText=raw.get("sourceText"),
    )


def _intf(raw: dict | None) -> SketchIntField | None:
    if not raw:
        return None
    return SketchIntField(
        value=raw.get("value"),
        confidence=raw.get("confidence", "MISSING"),
        sourceText=raw.get("sourceText"),
    )


def _parse_response(raw: dict, request_id: str, model: str) -> SketchAnalysisResponse:
    walls = [
        SketchWallCandidate(
            wallCode=_sf(w.get("wallCode")),
            length=_mf(w.get("length")),
            height=_mf(w.get("height")),
            angleDeg=_intf(w.get("angleDeg")),
        )
        for w in raw.get("walls", [])
    ]

    zones = [
        SketchZoneCandidate(
            zoneCode=_sf(z.get("zoneCode")),
            zoneType=_sf(z.get("zoneType")),
            wallCode=_sf(z.get("wallCode")) if z.get("wallCode") else None,
            x=_mf(z.get("x")) if z.get("x") else None,
            width=_mf(z.get("width")) if z.get("width") else None,
        )
        for z in raw.get("zones", [])
    ]

    obstacles = [
        SketchObstacleCandidate(
            obstacleType=_sf(o.get("obstacleType")),
            label=_sf(o.get("label")),
            wallCode=_sf(o.get("wallCode")) if o.get("wallCode") else None,
            x=_mf(o.get("x")) if o.get("x") else None,
            width=_mf(o.get("width")) if o.get("width") else None,
        )
        for o in raw.get("obstacles", [])
    ]

    cabinets = [
        SketchCabinetCandidate(
            candidateCode=c.get("candidateCode", "X-000"),
            category=_sf(c.get("category")),
            label=_sf(c.get("label")),
            wallCode=_sf(c.get("wallCode")) if c.get("wallCode") else None,
            x=_mf(c.get("x")) if c.get("x") else None,
            width=_mf(c.get("width")) if c.get("width") else None,
            height=_mf(c.get("height")) if c.get("height") else None,
            depth=_mf(c.get("depth")) if c.get("depth") else None,
            doors=_intf(c.get("doors")),
            drawers=_intf(c.get("drawers")),
        )
        for c in raw.get("cabinetCandidates", [])
    ]

    missing_info = [
        SketchMissingInfo(
            code=m.get("code", "OTHER"),
            message=m.get("message", ""),
            severity=m.get("severity", "WARNING"),
        )
        for m in raw.get("missingInfo", [])
    ]

    raw_extraction = SketchRawExtraction(
        model=model,
        pipeline="sketch-analysis",
        textObserved=raw.get("textObserved", []),
        generatedAt=datetime.now(timezone.utc).isoformat(),
    )

    return SketchAnalysisResponse(
        schemaVersion="1.0",
        requestId=request_id,
        projectType=_sf(raw.get("projectType")),
        layout=_sf(raw.get("layout")),
        unit=_sf(raw.get("unit")),
        walls=walls,
        zones=zones,
        obstacles=obstacles,
        cabinetCandidates=cabinets,
        missingInfo=missing_info,
        questions=raw.get("questions", []),
        warnings=raw.get("warnings", []),
        rawExtraction=raw_extraction,
    )
