"""Fixture tests for sketch-to-layout extraction — issue #27.

Tests use _parse_response directly (no network calls) plus mocked AsyncOpenAI
for the full analyze_sketch path. All fixtures are based on the contract defined
in docs/specs/e7-sketch-to-layout-extraction/59-sketch-extraction-contract.md.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.sketch_service import _parse_response, _sf, _mf, _intf, analyze_sketch
from app.models.schemas import (
    SketchAnalysisResponse,
    SketchStringField,
    SketchMeasurement,
    SketchIntField,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

FIXTURE_LINEAR_KITCHEN = {
    "projectType": {"value": "KITCHEN", "confidence": "HIGH", "sourceText": "cocina"},
    "layout": {"value": "LINEAR", "confidence": "MEDIUM", "sourceText": "vista frontal lineal"},
    "unit": {"value": "MM", "confidence": "MEDIUM", "sourceText": "600, 312, 500"},
    "walls": [
        {
            "wallCode": {"value": "A", "confidence": "HIGH"},
            "length": {"value": 3120, "unit": "MM", "confidence": "MEDIUM", "sourceText": "312"},
            "height": {"value": None, "unit": "MM", "confidence": "MISSING", "sourceText": None},
            "angleDeg": {"value": 0, "confidence": "HIGH"},
        }
    ],
    "zones": [
        {
            "zoneCode": {"value": "SINK-1", "confidence": "HIGH"},
            "zoneType": {"value": "SINK", "confidence": "HIGH", "sourceText": "tarja dibujada"},
            "wallCode": {"value": "A", "confidence": "MEDIUM"},
            "x": {"value": None, "unit": "MM", "confidence": "MISSING", "sourceText": None},
            "width": {"value": 800, "unit": "MM", "confidence": "LOW", "sourceText": None},
        }
    ],
    "obstacles": [
        {
            "obstacleType": {"value": "WINDOW", "confidence": "LOW", "sourceText": "rectángulo sobre tarja"},
            "label": {"value": "Posible ventana", "confidence": "LOW"},
            "wallCode": {"value": "A", "confidence": "LOW"},
            "x": {"value": None, "unit": "MM", "confidence": "MISSING", "sourceText": None},
            "width": {"value": None, "unit": "MM", "confidence": "MISSING", "sourceText": None},
        }
    ],
    "cabinetCandidates": [
        {
            "candidateCode": "A-001",
            "category": {"value": "LOWER", "confidence": "HIGH"},
            "label": {"value": "Base puerta izquierda", "confidence": "MEDIUM"},
            "wallCode": {"value": "A", "confidence": "MEDIUM"},
            "x": {"value": 0, "unit": "MM", "confidence": "LOW", "sourceText": None},
            "width": {"value": 600, "unit": "MM", "confidence": "MEDIUM", "sourceText": "600"},
            "height": {"value": None, "unit": "MM", "confidence": "MISSING", "sourceText": None},
            "depth": {"value": 600, "unit": "MM", "confidence": "MEDIUM", "sourceText": "600"},
            "doors": {"value": 2, "confidence": "LOW", "sourceText": "dos frentes dibujados"},
            "drawers": {"value": 0, "confidence": "LOW"},
        },
        {
            "candidateCode": "A-002",
            "category": {"value": "UPPER", "confidence": "HIGH"},
            "label": {"value": "Aéreo sobre zona de cocción", "confidence": "MEDIUM"},
            "wallCode": {"value": "A", "confidence": "MEDIUM"},
            "width": {"value": 600, "unit": "MM", "confidence": "MEDIUM", "sourceText": "600"},
            "height": {"value": 720, "unit": "MM", "confidence": "MEDIUM", "sourceText": "72"},
            "depth": {"value": None, "unit": "MM", "confidence": "MISSING", "sourceText": None},
            "doors": {"value": 2, "confidence": "MEDIUM", "sourceText": "2 puertas"},
            "drawers": {"value": 0, "confidence": "HIGH"},
        },
    ],
    "missingInfo": [
        {"code": "ROOM_HEIGHT_MISSING", "message": "No se detectó altura total del cuarto.", "severity": "WARNING"},
        {"code": "CONFIRM_UNITS", "message": "Confirmar si las medidas están en mm o cm.", "severity": "WARNING"},
    ],
    "questions": [
        "¿Las medidas del dibujo están en milímetros o centímetros?",
        "¿Cuál es la altura total del cuarto?",
    ],
    "warnings": ["Las posiciones X de los módulos son aproximadas porque el dibujo no tiene escala completa."],
    "textObserved": ["600", "312", "500", "tarja"],
}

FIXTURE_L_SHAPE_CLOSET = {
    "projectType": {"value": "CLOSET", "confidence": "HIGH", "sourceText": "armario"},
    "layout": {"value": "L_SHAPE", "confidence": "HIGH", "sourceText": "esquina en L"},
    "unit": {"value": "CM", "confidence": "LOW", "sourceText": None},
    "walls": [
        {
            "wallCode": {"value": "A", "confidence": "HIGH"},
            "length": {"value": 240, "unit": "CM", "confidence": "MEDIUM", "sourceText": "240"},
            "height": {"value": 240, "unit": "CM", "confidence": "MEDIUM", "sourceText": "240"},
        },
        {
            "wallCode": {"value": "B", "confidence": "HIGH"},
            "length": {"value": 180, "unit": "CM", "confidence": "MEDIUM", "sourceText": "180"},
            "height": {"value": None, "unit": "CM", "confidence": "MISSING", "sourceText": None},
        },
    ],
    "zones": [],
    "obstacles": [],
    "cabinetCandidates": [
        {
            "candidateCode": "A-001",
            "category": {"value": "TALL", "confidence": "HIGH"},
            "label": {"value": "Torre de ropa colgada", "confidence": "HIGH"},
            "wallCode": {"value": "A", "confidence": "HIGH"},
            "width": {"value": 60, "unit": "CM", "confidence": "MEDIUM", "sourceText": "60"},
            "height": {"value": 240, "unit": "CM", "confidence": "MEDIUM", "sourceText": "240"},
            "depth": {"value": 60, "unit": "CM", "confidence": "MEDIUM", "sourceText": "60"},
        },
    ],
    "missingInfo": [
        {"code": "ROOM_HEIGHT_MISSING", "message": "Altura solo visible en pared A.", "severity": "WARNING"},
    ],
    "questions": ["¿La altura del muro B es también 240 cm?"],
    "warnings": [],
    "textObserved": ["240", "180", "60"],
}

FIXTURE_EMPTY_SKETCH = {
    "projectType": {"value": "UNKNOWN", "confidence": "MISSING", "sourceText": None},
    "layout": {"value": "UNKNOWN", "confidence": "MISSING", "sourceText": None},
    "unit": {"value": "UNKNOWN", "confidence": "MISSING", "sourceText": None},
    "walls": [],
    "zones": [],
    "obstacles": [],
    "cabinetCandidates": [],
    "missingInfo": [
        {"code": "ROOM_HEIGHT_MISSING", "message": "No se pudo extraer información del boceto.", "severity": "ERROR"},
    ],
    "questions": ["¿Puede proporcionar un boceto más detallado?"],
    "warnings": ["La imagen no contiene suficiente detalle para extraer información de layout."],
    "textObserved": [],
}


# ── Helper tests ──────────────────────────────────────────────────────────────

def test_sf_returns_string_field():
    field = _sf({"value": "KITCHEN", "confidence": "HIGH", "sourceText": "cocina"})
    assert isinstance(field, SketchStringField)
    assert field.value == "KITCHEN"
    assert field.confidence == "HIGH"
    assert field.source_text == "cocina"


def test_sf_handles_none_input():
    field = _sf(None)
    assert field.value is None
    assert field.confidence == "MISSING"


def test_mf_returns_measurement():
    meas = _mf({"value": 3120, "unit": "MM", "confidence": "MEDIUM", "sourceText": "312"})
    assert isinstance(meas, SketchMeasurement)
    assert meas.value == 3120
    assert meas.unit == "MM"
    assert meas.confidence == "MEDIUM"


def test_mf_null_value_on_missing():
    meas = _mf({"value": None, "unit": "MM", "confidence": "MISSING", "sourceText": None})
    assert meas.value is None
    assert meas.confidence == "MISSING"


def test_intf_returns_none_for_none_input():
    assert _intf(None) is None


def test_intf_returns_field():
    field = _intf({"value": 2, "confidence": "LOW", "sourceText": "dos puertas"})
    assert isinstance(field, SketchIntField)
    assert field.value == 2
    assert field.confidence == "LOW"


# ── _parse_response fixture tests ─────────────────────────────────────────────

def test_parse_linear_kitchen_structure():
    result = _parse_response(FIXTURE_LINEAR_KITCHEN, "req-001", "gpt-4o")

    assert isinstance(result, SketchAnalysisResponse)
    assert result.schema_version == "1.0"
    assert result.request_id == "req-001"


def test_parse_linear_kitchen_project_type():
    result = _parse_response(FIXTURE_LINEAR_KITCHEN, "req-001", "gpt-4o")

    assert result.project_type.value == "KITCHEN"
    assert result.project_type.confidence == "HIGH"
    assert result.project_type.source_text == "cocina"


def test_parse_linear_kitchen_layout():
    result = _parse_response(FIXTURE_LINEAR_KITCHEN, "req-001", "gpt-4o")

    assert result.layout.value == "LINEAR"
    assert result.layout.confidence == "MEDIUM"


def test_parse_linear_kitchen_walls():
    result = _parse_response(FIXTURE_LINEAR_KITCHEN, "req-001", "gpt-4o")

    assert len(result.walls) == 1
    wall = result.walls[0]
    assert wall.wall_code.value == "A"
    assert wall.length.value == 3120
    assert wall.length.unit == "MM"
    assert wall.height.value is None
    assert wall.height.confidence == "MISSING"
    assert wall.angle_deg.value == 0


def test_parse_linear_kitchen_zones():
    result = _parse_response(FIXTURE_LINEAR_KITCHEN, "req-001", "gpt-4o")

    assert len(result.zones) == 1
    zone = result.zones[0]
    assert zone.zone_type.value == "SINK"
    assert zone.zone_type.confidence == "HIGH"
    assert zone.x.confidence == "MISSING"
    assert zone.x.value is None
    assert zone.width.value == 800


def test_parse_linear_kitchen_obstacles():
    result = _parse_response(FIXTURE_LINEAR_KITCHEN, "req-001", "gpt-4o")

    assert len(result.obstacles) == 1
    obs = result.obstacles[0]
    assert obs.obstacle_type.value == "WINDOW"
    assert obs.obstacle_type.confidence == "LOW"
    assert obs.x.value is None
    assert obs.width.value is None


def test_parse_linear_kitchen_cabinets():
    result = _parse_response(FIXTURE_LINEAR_KITCHEN, "req-001", "gpt-4o")

    assert len(result.cabinet_candidates) == 2
    lower = result.cabinet_candidates[0]
    assert lower.candidate_code == "A-001"
    assert lower.category.value == "LOWER"
    assert lower.width.value == 600
    assert lower.height.value is None
    assert lower.height.confidence == "MISSING"
    assert lower.doors.value == 2
    assert lower.drawers.value == 0

    upper = result.cabinet_candidates[1]
    assert upper.candidate_code == "A-002"
    assert upper.category.value == "UPPER"
    assert upper.depth.value is None
    assert upper.depth.confidence == "MISSING"


def test_parse_linear_kitchen_missing_info():
    result = _parse_response(FIXTURE_LINEAR_KITCHEN, "req-001", "gpt-4o")

    assert len(result.missing_info) == 2
    codes = {m.code for m in result.missing_info}
    assert "ROOM_HEIGHT_MISSING" in codes
    assert "CONFIRM_UNITS" in codes
    severities = {m.severity for m in result.missing_info}
    assert severities == {"WARNING"}


def test_parse_linear_kitchen_questions_and_warnings():
    result = _parse_response(FIXTURE_LINEAR_KITCHEN, "req-001", "gpt-4o")

    assert len(result.questions) == 2
    assert len(result.warnings) == 1
    assert "posiciones X" in result.warnings[0].lower() or "aproximadas" in result.warnings[0].lower()


def test_parse_linear_kitchen_raw_extraction():
    result = _parse_response(FIXTURE_LINEAR_KITCHEN, "req-001", "gpt-4o")

    assert result.raw_extraction.model == "gpt-4o"
    assert result.raw_extraction.pipeline == "sketch-analysis"
    assert set(result.raw_extraction.text_observed) == {"600", "312", "500", "tarja"}
    assert result.raw_extraction.generated_at  # non-empty ISO timestamp


def test_parse_l_shape_closet_two_walls():
    result = _parse_response(FIXTURE_L_SHAPE_CLOSET, "req-002", "gpt-4o")

    assert result.project_type.value == "CLOSET"
    assert result.layout.value == "L_SHAPE"
    assert len(result.walls) == 2
    assert result.walls[0].wall_code.value == "A"
    assert result.walls[1].wall_code.value == "B"
    assert result.walls[1].height.confidence == "MISSING"


def test_parse_l_shape_closet_no_zones_or_obstacles():
    result = _parse_response(FIXTURE_L_SHAPE_CLOSET, "req-002", "gpt-4o")

    assert result.zones == []
    assert result.obstacles == []


def test_parse_empty_sketch_all_unknown():
    result = _parse_response(FIXTURE_EMPTY_SKETCH, "req-003", "gpt-4o")

    assert result.project_type.value == "UNKNOWN"
    assert result.project_type.confidence == "MISSING"
    assert result.layout.value == "UNKNOWN"
    assert result.walls == []
    assert result.zones == []
    assert result.cabinet_candidates == []
    assert len(result.missing_info) == 1
    assert result.missing_info[0].severity == "ERROR"


# ── Serialization contract tests ──────────────────────────────────────────────

def test_response_serializes_camel_case():
    result = _parse_response(FIXTURE_LINEAR_KITCHEN, "req-001", "gpt-4o")
    output = result.model_dump(by_alias=True)

    assert "schemaVersion" in output
    assert "requestId" in output
    assert "projectType" in output
    assert "cabinetCandidates" in output
    assert "missingInfo" in output
    assert "rawExtraction" in output
    # snake_case keys must NOT appear at top level
    assert "schema_version" not in output
    assert "cabinet_candidates" not in output


def test_response_camel_case_nested():
    result = _parse_response(FIXTURE_LINEAR_KITCHEN, "req-001", "gpt-4o")
    output = result.model_dump(by_alias=True)

    wall = output["walls"][0]
    assert "wallCode" in wall
    assert "angleDeg" in wall

    zone = output["zones"][0]
    assert "zoneCode" in zone
    assert "zoneType" in zone
    assert "wallCode" in zone

    obs = output["obstacles"][0]
    assert "obstacleType" in obs
    assert "wallCode" in obs

    cab = output["cabinetCandidates"][0]
    assert "candidateCode" in cab
    assert "wallCode" in cab

    raw = output["rawExtraction"]
    assert "textObserved" in raw
    assert "generatedAt" in raw


def test_source_text_serialized_as_source_text():
    result = _parse_response(FIXTURE_LINEAR_KITCHEN, "req-001", "gpt-4o")
    output = result.model_dump(by_alias=True)

    # sourceText alias used in output
    assert "sourceText" in output["projectType"]
    assert output["projectType"]["sourceText"] == "cocina"


# ── Full analyze_sketch with mocked OpenAI ───────────────────────────────────

def _make_mock_openai(fixture: dict) -> MagicMock:
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps(fixture)
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.mark.anyio
async def test_analyze_sketch_linear_kitchen():
    mock_client = _make_mock_openai(FIXTURE_LINEAR_KITCHEN)

    with patch("app.services.sketch_service.AsyncOpenAI", return_value=mock_client):
        result = await analyze_sketch(
            image_b64="ZmFrZQ==",
            image_mime_type="image/jpeg",
            project_type_hint="KITCHEN",
            unit_hint="MM",
            session_code="KD-2026-TEST",
        )

    assert isinstance(result, SketchAnalysisResponse)
    assert result.project_type.value == "KITCHEN"
    assert result.layout.value == "LINEAR"
    assert len(result.walls) == 1
    assert len(result.cabinet_candidates) == 2
    assert result.request_id  # auto-generated


@pytest.mark.anyio
async def test_analyze_sketch_passes_hint_in_prompt():
    mock_client = _make_mock_openai(FIXTURE_LINEAR_KITCHEN)

    with patch("app.services.sketch_service.AsyncOpenAI", return_value=mock_client) as mock_cls:
        await analyze_sketch(
            image_b64="ZmFrZQ==",
            project_type_hint="CLOSET",
            unit_hint="CM",
            user_prompt="Armario en esquina.",
        )

    call_args = mock_cls.return_value.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_text = messages[1]["content"][0]["text"]
    assert "CLOSET" in user_text
    assert "Armario en esquina." in user_text


@pytest.mark.anyio
async def test_analyze_sketch_uses_high_detail():
    mock_client = _make_mock_openai(FIXTURE_EMPTY_SKETCH)

    with patch("app.services.sketch_service.AsyncOpenAI", return_value=mock_client) as mock_cls:
        await analyze_sketch(image_b64="ZmFrZQ==")

    call_args = mock_cls.return_value.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    image_part = messages[1]["content"][1]
    assert image_part["image_url"]["detail"] == "high"


@pytest.mark.anyio
async def test_analyze_sketch_uses_low_temperature():
    mock_client = _make_mock_openai(FIXTURE_EMPTY_SKETCH)

    with patch("app.services.sketch_service.AsyncOpenAI", return_value=mock_client) as mock_cls:
        await analyze_sketch(image_b64="ZmFrZQ==")

    call_args = mock_cls.return_value.chat.completions.create.call_args
    assert call_args.kwargs["temperature"] == 0.1


@pytest.mark.anyio
async def test_analyze_sketch_empty_sketch_returns_unknown():
    mock_client = _make_mock_openai(FIXTURE_EMPTY_SKETCH)

    with patch("app.services.sketch_service.AsyncOpenAI", return_value=mock_client):
        result = await analyze_sketch(image_b64="ZmFrZQ==")

    assert result.project_type.value == "UNKNOWN"
    assert result.layout.value == "UNKNOWN"
    assert result.walls == []
    assert result.cabinet_candidates == []
    assert any(m.severity == "ERROR" for m in result.missing_info)
