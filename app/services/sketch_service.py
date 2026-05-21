"""GPT-4o Vision pipeline for sketch-to-layout extraction."""
import json
import logging

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.schemas import (
    SketchAnalysisResponse,
    SketchCabinet,
    SketchLayout,
    SketchWarning,
    SketchWall,
    SketchZone,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert furniture layout analyst specializing in kitchens and closets.
You analyze hand-drawn sketches, photos, or informal drawings and extract structured layout information.

RULES:
1. Never invent exact dimensions that are not visible or annotated in the sketch.
2. Represent missing or uncertain measurements as null, not as guesses.
3. Always include a warning when a dimension is missing or a detection is uncertain.
4. Use confidence values honestly: 0.9+ only when clearly visible, 0.5-0.7 for inferred, below 0.5 for guesses.
5. Cabinet IDs: U-## = upper, L-## = lower, C-## = corner, T-## = tall/tower, S-## = sink.
6. All dimensions in cm unless the sketch clearly annotates another unit.

Return ONLY this JSON object (no explanation, no markdown):
{
  "detected_project_type": "KITCHEN" | "CLOSET" | "BOTH" | "UNKNOWN",
  "layout": {
    "shape": "L" | "U" | "lineal" | "isla" | "unknown",
    "walls": [
      { "label": "wall_1", "estimated_length_cm": <float or null>, "confidence": <0-1> }
    ],
    "estimated_total_width_cm": <float or null>,
    "estimated_total_depth_cm": <float or null>,
    "confidence": <0-1>
  },
  "zones": [
    {
      "type": "sink" | "cooktop" | "refrigerator" | "oven" | "dishwasher" | "window" | "door" | "column" | "other",
      "wall": <string or null>,
      "position_hint": "left" | "center" | "right" | "corner" | null,
      "confidence": <0-1>
    }
  ],
  "cabinets": [
    {
      "id": "U-01",
      "category": "upper" | "lower" | "corner" | "tall" | "sink",
      "label": <string in Spanish>,
      "estimated_width_cm": <float or null>,
      "estimated_height_cm": <float or null>,
      "estimated_depth_cm": <float or null>,
      "wall": <string or null>,
      "doors": <int or null>,
      "drawers": <int or null>,
      "confidence": <0-1>,
      "warnings": [<string>]
    }
  ],
  "overall_confidence": <0-1>,
  "warnings": [
    {
      "code": "missing_dimension" | "low_confidence" | "ambiguous_layout" | "no_scale_reference" | "partial_sketch" | "unsupported_image" | "other",
      "message": <string>,
      "affected": <string or null>
    }
  ],
  "raw_notes": <string or null>
}
"""


async def analyze_sketch(
    image_b64: str,
    image_mime_type: str = "image/jpeg",
    context: str | None = None,
    project_type: str | None = None,
    unit: str = "cm",
    session_id: str | None = None,
) -> SketchAnalysisResponse:
    """Send a sketch image to GPT-4o Vision and return structured layout extraction."""
    user_text_parts = ["Analyze this sketch and extract the layout and cabinet information."]
    if project_type:
        user_text_parts.append(f"Project type hint: {project_type}.")
    if unit != "cm":
        user_text_parts.append(f"Annotations in the sketch use {unit} — convert all output to cm.")
    if context:
        user_text_parts.append(f"Additional context from user: {context}")

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": " ".join(user_text_parts)},
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
        max_tokens=2000,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    raw = json.loads(response.choices[0].message.content or "{}")
    logger.info("sketch analysis — session=%s project_type=%s confidence=%s",
                session_id, raw.get("detected_project_type"), raw.get("overall_confidence"))

    return _parse_response(raw, session_id)


def _parse_response(raw: dict, session_id: str | None) -> SketchAnalysisResponse:
    layout_raw = raw.get("layout", {})
    layout = SketchLayout(
        shape=layout_raw.get("shape", "unknown"),
        walls=[SketchWall(**w) for w in layout_raw.get("walls", [])],
        estimated_total_width_cm=layout_raw.get("estimated_total_width_cm"),
        estimated_total_depth_cm=layout_raw.get("estimated_total_depth_cm"),
        confidence=float(layout_raw.get("confidence", 0.0)),
    )

    zones = [SketchZone(**z) for z in raw.get("zones", [])]

    cabinets = [SketchCabinet(**c) for c in raw.get("cabinets", [])]

    warnings = [SketchWarning(**w) for w in raw.get("warnings", [])]

    return SketchAnalysisResponse(
        session_id=session_id,
        detected_project_type=raw.get("detected_project_type", "UNKNOWN"),
        layout=layout,
        zones=zones,
        cabinets=cabinets,
        overall_confidence=float(raw.get("overall_confidence", 0.0)),
        warnings=warnings,
        raw_notes=raw.get("raw_notes"),
    )
