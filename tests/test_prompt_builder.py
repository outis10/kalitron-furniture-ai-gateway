"""Tests for build_prompt_from_chat — 10 conversation samples."""
import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_service import build_prompt_from_chat
from app.services.workflows import NEGATIVE_PROMPT, PROMPT_SUFFIX, STYLE_MAP, STYLE_PROMPTS

_HISTORY_SIMPLE = [
    {"role": "user", "content": "I want a modern kitchen with white cabinets"},
    {"role": "assistant", "content": "Great choice! Let me help you design that."},
]

_HISTORY_DETAILED = [
    {"role": "user", "content": "I want a rustic kitchen with exposed beams and a farmhouse sink"},
    {"role": "assistant", "content": "Wonderful! A farmhouse sink works beautifully in a rustic kitchen."},
    {"role": "user", "content": "I also want a large island and oak wood cabinets"},
    {"role": "assistant", "content": "Perfect — oak wood and an island will give it that warm, functional feel."},
]

_HISTORY_EMPTY: list[dict] = []


def _make_mock_openai(extracted: str = "blue subway tile backsplash"):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = extracted
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "style, layout, finish, expected_key, extracted",
    [
        # 1 — moderno + island + white matte
        ("moderno", "island", "white matte", "modern", "stainless steel appliances"),
        # 2 — rustico + l-shaped + oak wood
        ("rustico", "l-shaped", "oak wood", "rustic", "farmhouse sink, apron front"),
        # 3 — minimalista + galley + gray matte
        ("minimalista", "galley", "gray matte", "minimalist", ""),
        # 4 — clasico + u-shaped + white matte
        ("clasico", "u-shaped", "white matte", "classic", "crown molding details"),
        # 5 — industrial + island + black matte
        ("industrial", "island", "black matte", "industrial", "exposed brick accent wall"),
        # 6 — moderno, no layout, no finish
        ("moderno", None, None, "modern", ""),
        # 7 — rustico + galley, no finish
        ("rustico", "galley", None, "rustic", "copper pendant lights"),
        # 8 — minimalista, no layout + oak wood
        ("minimalista", None, "oak wood", "minimalist", ""),
        # 9 — clasico + l-shaped + black matte
        ("clasico", "l-shaped", "black matte", "classic", "glass-front upper cabinets"),
        # 10 — industrial + u-shaped + gray matte
        ("industrial", "u-shaped", "gray matte", "industrial", "reclaimed wood accents"),
    ],
)
async def test_build_prompt_from_chat(style, layout, finish, expected_key, extracted):
    history = _HISTORY_SIMPLE if extracted else _HISTORY_EMPTY
    mock_client = _make_mock_openai(extracted)

    with patch("app.services.llm_service.AsyncOpenAI", return_value=mock_client):
        result = await build_prompt_from_chat(history, style=style, layout=layout, finish=finish)

    assert isinstance(result, dict), "result must be a dict"
    assert set(result.keys()) == {"positive", "negative", "style_key"}

    positive = result["positive"]
    assert positive.startswith("kitchen interior design, "), (
        f"positive must start with 'kitchen interior design, ' — got: {positive[:60]}"
    )
    assert positive.endswith(PROMPT_SUFFIX), (
        f"positive must end with quality tags — got: ...{positive[-60:]}"
    )
    assert "cartoon" in result["negative"], "negative must contain 'cartoon'"
    assert result["style_key"] == expected_key, (
        f"style_key {result['style_key']!r} != expected {expected_key!r}"
    )

    # layout detail should appear when provided
    if layout == "island":
        assert "island" in positive.lower()
    if layout == "l-shaped":
        assert "l-shaped" in positive.lower() or "l shaped" in positive.lower()

    # finish detail should appear when provided
    if finish == "white matte":
        assert "white matte" in positive.lower()
    if finish == "oak wood":
        assert "oak wood" in positive.lower() or "oak" in positive.lower()

    # extracted detail should appear in positive when non-empty and history has messages
    if extracted and history:
        assert extracted.lower() in positive.lower(), (
            f"extracted detail {extracted!r} not found in positive prompt"
        )


@pytest.mark.asyncio
async def test_build_prompt_from_chat_uses_closet_project_type():
    result = await build_prompt_from_chat(
        [],
        style="minimalista",
        layout="lineal",
        finish="blanco brillante",
        project_type="CLOSET",
    )

    positive = result["positive"].lower()
    assert positive.startswith("wardrobe closet interior design, ")
    assert "kitchen interior design" not in positive
    assert "linear built-in wardrobe" in positive


def test_build_prompt_from_chat_extracts_gloss_black_finish_from_brief():
    brief = """
    • Tipo de proyecto: Cocina
    • Estilo: Minimalista negro
    • Distribución: En L
    • Material: Melamina negro alto brillo
    • Acabado/Color: Encimera blanca con ribetes negros
    • Notas adicionales: Mantener la estructura y distribución actual
    """

    async def run_test():
        with patch("app.services.llm_service._translate_design_brief", new=AsyncMock(return_value="minimalist kitchen with glossy black melamine flat cabinet doors")):
            return await build_prompt_from_chat([], style="minimalista", design_brief=brief)

    result = asyncio.run(run_test())

    positive = result["positive"].lower()
    assert "l-shaped kitchen layout" in positive
    assert "high gloss black melamine cabinet finish" in positive
    assert "reflective deep black flat surfaces" in positive
