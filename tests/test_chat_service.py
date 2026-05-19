"""Tests for GPT-4o multi-turn chat service — issue #11."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_service import (
    _SPECS_READY_SIGNAL,
    _SYSTEM_PROMPT,
    _sessions,
    chat,
    clear_session,
    get_session,
    session_turn_count,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_mock_openai(reply: str) -> MagicMock:
    mock_response = MagicMock()
    mock_response.choices[0].message.content = reply
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


def _fresh_session() -> str:
    """Return a unique session_id and ensure it's clean."""
    import uuid
    sid = uuid.uuid4().hex
    clear_session(sid)
    return sid


# ── System prompt checks ──────────────────────────────────────────────────────

def test_system_prompt_is_in_spanish():
    assert "español" in _SYSTEM_PROMPT.lower() or "Responde SIEMPRE en español" in _SYSTEM_PROMPT


def test_system_prompt_contains_specs_ready_signal():
    assert _SPECS_READY_SIGNAL in _SYSTEM_PROMPT


def test_system_prompt_limits_questions_per_turn():
    assert "2" in _SYSTEM_PROMPT and ("pregunta" in _SYSTEM_PROMPT.lower() or "MÁXIMO" in _SYSTEM_PROMPT)


def test_system_prompt_has_all_7_steps():
    for step in ("Paso 1", "Paso 2", "Paso 3", "Paso 4", "Paso 5", "Paso 6", "Paso 7"):
        assert step in _SYSTEM_PROMPT, f"{step} missing from system prompt"


# ── Session management ────────────────────────────────────────────────────────

def test_get_session_initialises_with_system_message():
    sid = _fresh_session()
    history = get_session(sid)
    assert history[0]["role"] == "system"
    assert _SPECS_READY_SIGNAL in history[0]["content"]
    clear_session(sid)


def test_get_session_returns_same_object_on_repeat_calls():
    sid = _fresh_session()
    h1 = get_session(sid)
    h2 = get_session(sid)
    assert h1 is h2
    clear_session(sid)


def test_clear_session_removes_history():
    sid = _fresh_session()
    get_session(sid)          # initialise
    assert sid in _sessions
    clear_session(sid)
    assert sid not in _sessions


def test_clear_session_is_noop_for_unknown_session():
    clear_session("does-not-exist")  # must not raise


def test_session_turn_count_zero_for_new_session():
    sid = _fresh_session()
    assert session_turn_count(sid) == 0
    clear_session(sid)


# ── chat() behaviour ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_appends_user_and_assistant_messages():
    sid = _fresh_session()
    mock_client = _make_mock_openai("Hola, ¿en qué tipo de proyecto trabajamos hoy?")

    with patch("app.services.llm_service.AsyncOpenAI", return_value=mock_client):
        reply, specs_ready = await chat(sid, "Hola", image_b64=None)

    history = get_session(sid)
    roles = [m["role"] for m in history]
    assert roles == ["system", "user", "assistant"]
    assert reply == "Hola, ¿en qué tipo de proyecto trabajamos hoy?"
    assert specs_ready is False
    clear_session(sid)


@pytest.mark.asyncio
async def test_chat_detects_and_strips_specs_ready():
    sid = _fresh_session()
    reply_with_signal = f"Todo confirmado. Aquí está tu resumen.\n{_SPECS_READY_SIGNAL}"
    mock_client = _make_mock_openai(reply_with_signal)

    with patch("app.services.llm_service.AsyncOpenAI", return_value=mock_client):
        reply, specs_ready = await chat(sid, "Sí, confirmo todo")

    assert specs_ready is True
    assert _SPECS_READY_SIGNAL not in reply
    assert "Todo confirmado" in reply
    clear_session(sid)


@pytest.mark.asyncio
async def test_chat_formats_vision_content_array_when_image_provided():
    sid = _fresh_session()
    mock_client = _make_mock_openai("Veo una cocina moderna en la foto.")

    with patch("app.services.llm_service.AsyncOpenAI", return_value=mock_client):
        await chat(sid, "Aquí está mi cocina actual", image_b64="abc123", image_mime_type="image/webp")

    history = get_session(sid)
    user_msg = next(m for m in history if m["role"] == "user")
    assert isinstance(user_msg["content"], list)
    types = {part["type"] for part in user_msg["content"]}
    assert types == {"text", "image_url"}
    assert "No digas que no puedes ver imágenes" in user_msg["content"][0]["text"]
    assert "No pidas al cliente confirmar la distribución" in user_msg["content"][0]["text"]
    assert "conservar la estructura" in user_msg["content"][0]["text"]
    assert "abc123" in user_msg["content"][1]["image_url"]["url"]
    assert "data:image/webp;base64" in user_msg["content"][1]["image_url"]["url"]
    clear_session(sid)


@pytest.mark.asyncio
async def test_chat_plain_text_when_no_image():
    sid = _fresh_session()
    mock_client = _make_mock_openai("Entendido.")

    with patch("app.services.llm_service.AsyncOpenAI", return_value=mock_client):
        await chat(sid, "Quiero una cocina moderna")

    history = get_session(sid)
    user_msg = next(m for m in history if m["role"] == "user")
    assert isinstance(user_msg["content"], str)
    clear_session(sid)


@pytest.mark.asyncio
async def test_chat_accumulates_history_across_turns():
    sid = _fresh_session()
    replies = [
        "Hola. ¿Qué tipo de proyecto tienes en mente?",
        "Perfecto. ¿Qué estilo prefieres?",
        "¿Cuánto mide el espacio?",
    ]

    for i, scripted_reply in enumerate(replies):
        mock_client = _make_mock_openai(scripted_reply)
        with patch("app.services.llm_service.AsyncOpenAI", return_value=mock_client):
            await chat(sid, f"Mensaje {i}")

    assert session_turn_count(sid) == 3
    # system + 3×(user+assistant) = 7 messages
    assert len(get_session(sid)) == 7
    clear_session(sid)


# ── Full conversation simulation — must reach SPECS_READY in < 8 turns ────────

@pytest.mark.asyncio
async def test_conversation_reaches_specs_ready_within_8_turns():
    """Simulate a scripted 7-step conversation and verify SPECS_READY fires on turn 7."""
    sid = _fresh_session()

    # Scripted GPT-4o responses for each user turn
    scripted = [
        "¡Bienvenido a Kalitron! ¿Qué tipo de proyecto tienes? ¿Cocina, armario o ambos?",
        "Entendido, una cocina. ¿Qué estilo te atrae? ¿Moderno, rústico, minimalista, clásico o industrial?",
        "Minimalista, excelente elección. ¿Cuáles son las dimensiones del espacio? ¿Y qué distribución prefieres?",
        "Perfecto: 320×60×220 cm en L. ¿Qué módulos necesitas? ¿Cajones, puertas batientes, alacenas?",
        "Anotado: 6 cajones y 4 puertas. ¿Qué material y acabado tienes en mente?",
        (
            "Aquí está el resumen:\n"
            "• Tipo: Cocina\n• Estilo: Minimalista\n• Dimensiones: 320×60×220 cm\n"
            "• Distribución: En L\n• Módulos: 6 cajones, 4 puertas\n"
            "• Material: MDF lacado\n• Acabado: Blanco mate\n"
            "¿Lo confirmas?"
        ),
        f"¡Perfecto! Comenzamos el diseño.\n{_SPECS_READY_SIGNAL}",
    ]

    user_messages = [
        "Hola",
        "Una cocina",
        "Minimalista, distribución en L, 320×60×220 cm",
        "6 cajones y 4 puertas batientes",
        "MDF lacado blanco mate",
        "Sí, eso es todo",
        "Confirmo, está perfecto",
    ]

    specs_ready = False
    for turn, (user_msg, scripted_reply) in enumerate(zip(user_messages, scripted), start=1):
        mock_client = _make_mock_openai(scripted_reply)
        with patch("app.services.llm_service.AsyncOpenAI", return_value=mock_client):
            _, specs_ready = await chat(sid, user_msg)
        if specs_ready:
            break

    assert specs_ready, "Conversation did not reach SPECS_READY"
    assert session_turn_count(sid) <= 7, (
        f"Took {session_turn_count(sid)} turns — must complete in ≤ 7 (< 8)"
    )
    clear_session(sid)
