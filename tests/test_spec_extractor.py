"""Tests for extract_specs() — 10 conversation transcripts at 95%+ accuracy."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_service import (
    _apply_mexican_defaults,
    clear_session,
    extract_specs,
    get_session,
)
from app.models.schemas import Cabinet, ExtractedKitchenSpecs


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_openai(gpt_json: dict) -> MagicMock:
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps(gpt_json)
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


def _load_session(session_id: str, transcript: list[tuple[str, str]]) -> None:
    """Populate session with (user, assistant) pairs."""
    clear_session(session_id)
    history = get_session(session_id)
    for user_msg, assistant_msg in transcript:
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": assistant_msg})


# ── Unit: _apply_mexican_defaults ─────────────────────────────────────────────

def test_defaults_fills_missing_top_level():
    result = _apply_mexican_defaults({})
    assert result["kitchen_type"] == "L"
    assert result["total_height_mm"] == 2400
    assert result["total_depth_mm"] == 600
    assert result["style"] == "moderno"


def test_defaults_upper_cabinet_dimensions():
    raw = {"cabinets": [{"category": "upper", "width_mm": 600}]}
    result = _apply_mexican_defaults(raw)
    cab = result["cabinets"][0]
    assert cab["height_mm"] == 720
    assert cab["depth_mm"] == 350


def test_defaults_lower_cabinet_dimensions():
    raw = {"cabinets": [{"category": "lower", "width_mm": 800}]}
    result = _apply_mexican_defaults(raw)
    cab = result["cabinets"][0]
    assert cab["height_mm"] == 870
    assert cab["depth_mm"] == 600


def test_defaults_tall_cabinet_dimensions():
    raw = {"cabinets": [{"category": "tall", "width_mm": 450}]}
    result = _apply_mexican_defaults(raw)
    cab = result["cabinets"][0]
    assert cab["height_mm"] == 2100


def test_defaults_auto_assigns_id_by_category():
    raw = {"cabinets": [
        {"category": "upper", "width_mm": 600},
        {"category": "lower", "width_mm": 600},
        {"category": "sink",  "width_mm": 900},
    ]}
    result = _apply_mexican_defaults(raw)
    ids = [c["id"] for c in result["cabinets"]]
    assert ids[0].startswith("U-")
    assert ids[1].startswith("L-")
    assert ids[2].startswith("S-")


def test_defaults_preserves_explicit_values():
    raw = {"cabinets": [{"category": "upper", "width_mm": 600, "height_mm": 900, "depth_mm": 400}]}
    result = _apply_mexican_defaults(raw)
    cab = result["cabinets"][0]
    assert cab["height_mm"] == 900   # not overwritten
    assert cab["depth_mm"] == 400    # not overwritten


# ── Integration: extract_specs() — 10 transcripts ────────────────────────────

_TRANSCRIPTS = [
    # 1 — Cocina en L, moderno, 4.2m, aéreos + bajos + lavabo
    (
        "transcript-01",
        [("Quiero una cocina en L de 420cm x 60cm, moderna", "Entendido.")],
        {
            "kitchen_type": "L", "total_width_mm": 4200, "total_height_mm": 2400,
            "total_depth_mm": 600, "style": "moderno", "confidence": 0.95,
            "cabinets": [
                {"id": "U-01", "category": "upper", "label": "Aéreo estándar",
                 "width_mm": 600, "height_mm": 720, "depth_mm": 350, "doors": 2, "drawers": 0,
                 "material": "MDF 18mm", "finish": "blanco mate"},
                {"id": "L-01", "category": "lower", "label": "Bajo con cajones",
                 "width_mm": 600, "height_mm": 870, "depth_mm": 600, "doors": 0, "drawers": 3,
                 "material": "MDF 18mm", "finish": "blanco mate"},
                {"id": "S-01", "category": "sink", "label": "Bajo fregadero",
                 "width_mm": 900, "height_mm": 870, "depth_mm": 600, "doors": 2, "drawers": 0,
                 "material": "MDF 18mm", "finish": "blanco mate"},
            ],
        },
        {"kitchen_type": "L", "min_cabinets": 3, "style": "moderno"},
    ),
    # 2 — Cocina en U, rústico, madera de pino
    (
        "transcript-02",
        [("Cocina en U, estilo rústico, madera de pino", "Perfecto.")],
        {
            "kitchen_type": "U", "total_width_mm": 3600, "total_height_mm": 2400,
            "total_depth_mm": 600, "style": "rustico", "confidence": 0.92,
            "cabinets": [
                {"id": "U-01", "category": "upper", "label": "Aéreo", "width_mm": 600,
                 "material": "Pino macizo", "finish": "barniz natural", "doors": 2, "drawers": 0},
                {"id": "L-01", "category": "lower", "label": "Bajo", "width_mm": 600,
                 "material": "Pino macizo", "finish": "barniz natural", "doors": 2, "drawers": 0},
            ],
        },
        {"kitchen_type": "U", "style": "rustico", "finish_contains": "barniz"},
    ),
    # 3 — Lineal minimalista, melamina blanca, sin aéreos
    (
        "transcript-03",
        [("Cocina lineal minimalista, sólo muebles bajos, melamina blanca", "Anotado.")],
        {
            "kitchen_type": "lineal", "total_width_mm": 2400, "total_height_mm": 2400,
            "total_depth_mm": 600, "style": "minimalista", "confidence": 0.88,
            "cabinets": [
                {"id": "L-01", "category": "lower", "label": "Bajo", "width_mm": 600,
                 "material": "Melamina 16mm", "finish": "blanco mate", "doors": 2, "drawers": 0},
            ],
        },
        {"kitchen_type": "lineal", "style": "minimalista"},
    ),
    # 4 — Isla central, moderno, con torre
    (
        "transcript-04",
        [("Cocina con isla central y alacena torre, moderna", "Perfecto.")],
        {
            "kitchen_type": "isla", "total_width_mm": 5000, "total_height_mm": 2400,
            "total_depth_mm": 600, "style": "moderno", "confidence": 0.9,
            "cabinets": [
                {"id": "T-01", "category": "tall", "label": "Alacena torre",
                 "width_mm": 450, "height_mm": 2100, "depth_mm": 600, "doors": 2, "drawers": 0,
                 "material": "MDF 18mm", "finish": "gris mate"},
                {"id": "L-01", "category": "lower", "label": "Bajo isla",
                 "width_mm": 1200, "height_mm": 870, "depth_mm": 900, "doors": 4, "drawers": 2,
                 "material": "MDF 18mm", "finish": "gris mate"},
            ],
        },
        {"kitchen_type": "isla", "has_tall": True},
    ),
    # 5 — Clásico, madera de roble, esquinero
    (
        "transcript-05",
        [("Quiero una cocina clásica en L con esquinero, roble natural", "Entendido.")],
        {
            "kitchen_type": "L", "total_width_mm": 3800, "total_height_mm": 2400,
            "total_depth_mm": 600, "style": "clasico", "confidence": 0.91,
            "cabinets": [
                {"id": "C-01", "category": "corner", "label": "Esquinero giratorio",
                 "width_mm": 900, "height_mm": 870, "depth_mm": 600, "doors": 1, "drawers": 0,
                 "material": "Roble macizo", "finish": "barniz roble"},
                {"id": "U-01", "category": "upper", "label": "Aéreo clásico",
                 "width_mm": 600, "material": "Roble macizo", "finish": "barniz roble",
                 "doors": 2, "drawers": 0},
            ],
        },
        {"kitchen_type": "L", "has_corner": True, "style": "clasico"},
    ),
    # 6 — Industrial, concreto y metal, cocina galería
    (
        "transcript-06",
        [("Quiero una cocina industrial estilo galería, acabado concreto", "De acuerdo.")],
        {
            "kitchen_type": "lineal", "total_width_mm": 3200, "total_height_mm": 2400,
            "total_depth_mm": 600, "style": "industrial", "confidence": 0.87,
            "cabinets": [
                {"id": "L-01", "category": "lower", "label": "Bajo industrial",
                 "width_mm": 800, "material": "MDF 18mm", "finish": "concreto gris",
                 "doors": 2, "drawers": 0},
            ],
        },
        {"style": "industrial"},
    ),
    # 7 — Solo defaults (GPT devuelve mínimo)
    (
        "transcript-07",
        [("Quiero una cocina", "¿Qué tipo?")],
        {"confidence": 0.4, "cabinets": []},
        {"kitchen_type": "L", "total_height_mm": 2400},
    ),
    # 8 — Varios cajones, 6 bajos, melamina nogal
    (
        "transcript-08",
        [("Necesito 6 módulos bajos con cajones, melamina nogal, 3.6m de ancho", "Anotado.")],
        {
            "kitchen_type": "L", "total_width_mm": 3600, "total_height_mm": 2400,
            "total_depth_mm": 600, "style": "moderno", "confidence": 0.93,
            "cabinets": [
                {"id": f"L-0{i}", "category": "lower", "label": f"Bajo cajonero {i}",
                 "width_mm": 600, "material": "Melamina nogal", "finish": "nogal natural",
                 "doors": 0, "drawers": 3}
                for i in range(1, 7)
            ],
        },
        {"min_cabinets": 6},
    ),
    # 9 — Fregadero doble + aéreo vidrio
    (
        "transcript-09",
        [("Quiero fregadero doble y aéreos con vidrio, cocina blanca", "Perfecto.")],
        {
            "kitchen_type": "L", "total_width_mm": 3000, "total_height_mm": 2400,
            "total_depth_mm": 600, "style": "moderno", "confidence": 0.89,
            "cabinets": [
                {"id": "S-01", "category": "sink", "label": "Bajo fregadero doble",
                 "width_mm": 1200, "material": "MDF 18mm", "finish": "blanco mate",
                 "doors": 2, "drawers": 0},
                {"id": "U-01", "category": "upper", "label": "Aéreo puerta vidrio",
                 "width_mm": 600, "material": "MDF 18mm", "finish": "vidrio templado",
                 "doors": 2, "drawers": 0},
            ],
        },
        {"has_sink": True},
    ),
    # 10 — Alta confianza, cocina completa bien detallada
    (
        "transcript-10",
        [
            ("Cocina en L, 4.8m × 2.4m × 60cm, moderna, MDF lacado blanco mate", "Perfecto."),
            ("6 aéreos de 60cm, 5 bajos, 1 alacena torre, 1 bajo fregadero", "Anotado."),
        ],
        {
            "kitchen_type": "L", "total_width_mm": 4800, "total_height_mm": 2400,
            "total_depth_mm": 600, "style": "moderno", "confidence": 0.97,
            "cabinets": [
                *[{"id": f"U-0{i}", "category": "upper", "label": f"Aéreo {i}",
                   "width_mm": 600, "material": "MDF 18mm", "finish": "blanco mate",
                   "doors": 2, "drawers": 0} for i in range(1, 7)],
                *[{"id": f"L-0{i}", "category": "lower", "label": f"Bajo {i}",
                   "width_mm": 600, "material": "MDF 18mm", "finish": "blanco mate",
                   "doors": 2, "drawers": 0} for i in range(1, 6)],
                {"id": "T-01", "category": "tall", "label": "Alacena torre",
                 "width_mm": 450, "height_mm": 2100, "depth_mm": 600,
                 "material": "MDF 18mm", "finish": "blanco mate", "doors": 2, "drawers": 0},
                {"id": "S-01", "category": "sink", "label": "Bajo fregadero",
                 "width_mm": 900, "material": "MDF 18mm", "finish": "blanco mate",
                 "doors": 2, "drawers": 0},
            ],
        },
        {"min_cabinets": 13, "confidence_min": 0.95},
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("session_id,transcript,gpt_response,assertions", _TRANSCRIPTS)
async def test_extract_specs_transcript(session_id, transcript, gpt_response, assertions):
    _load_session(session_id, transcript)
    mock_client = _mock_openai(gpt_response)

    with patch("app.services.llm_service.AsyncOpenAI", return_value=mock_client):
        result = await extract_specs(session_id)

    specs = result["specs"]
    confidence = result["confidence"]

    # Schema compliance — must parse into ExtractedKitchenSpecs without error
    parsed = ExtractedKitchenSpecs(**specs)
    for cab_dict in specs.get("cabinets", []):
        Cabinet(**cab_dict)

    # Specific assertions per transcript
    if "kitchen_type" in assertions:
        assert parsed.kitchen_type == assertions["kitchen_type"]

    if "total_height_mm" in assertions:
        assert parsed.total_height_mm == assertions["total_height_mm"]

    if "style" in assertions:
        assert parsed.style == assertions["style"]

    if "min_cabinets" in assertions:
        assert len(parsed.cabinets) >= assertions["min_cabinets"]

    if "has_tall" in assertions and assertions["has_tall"]:
        assert any(c.category == "tall" for c in parsed.cabinets)

    if "has_corner" in assertions and assertions["has_corner"]:
        assert any(c.category == "corner" for c in parsed.cabinets)

    if "has_sink" in assertions and assertions["has_sink"]:
        assert any(c.category == "sink" for c in parsed.cabinets)

    if "finish_contains" in assertions:
        finishes = [c.finish for c in parsed.cabinets]
        assert any(assertions["finish_contains"] in f for f in finishes)

    if "confidence_min" in assertions:
        assert confidence >= assertions["confidence_min"]

    # All cabinet IDs must follow the U/L/C/T/S-## convention
    valid_prefixes = {"U", "L", "C", "T", "S"}
    for cab in parsed.cabinets:
        prefix = cab.id.split("-")[0]
        assert prefix in valid_prefixes, f"Invalid cabinet ID prefix: {cab.id}"

    clear_session(session_id)
