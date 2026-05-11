"""GPT-4o multi-turn chat service with SPECS_READY signal detection and prompt building."""
from openai import AsyncOpenAI

from app.core.config import settings
from app.services.workflows import (
    FINISH_DETAILS,
    LAYOUT_DETAILS,
    NEGATIVE_PROMPT,
    PROMPT_SUFFIX,
    STYLE_MAP,
    STYLE_PROMPTS,
)

_SPECS_READY_SIGNAL = "SPECS_READY"

_sessions: dict[str, list[dict]] = {}

_SYSTEM_PROMPT = (
    "You are an expert interior designer specializing in kitchen design. "
    "Help the client define their kitchen specifications through conversation. "
    "When you have gathered enough information (dimensions, style, materials, colors, "
    "drawer/door count), include the token SPECS_READY on its own line to signal "
    "that the specs are complete."
)


def get_session(session_id: str) -> list[dict]:
    if session_id not in _sessions:
        _sessions[session_id] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    return _sessions[session_id]


async def chat(session_id: str, user_message: str, image_b64: str | None = None) -> tuple[str, bool]:
    """Send a message and return (reply, specs_ready)."""
    history = get_session(session_id)

    content: list | str
    if image_b64:
        content = [
            {"type": "text", "text": user_message},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        ]
    else:
        content = user_message

    history.append({"role": "user", "content": content})

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=history,
        max_tokens=1024,
    )

    reply = response.choices[0].message.content or ""
    history.append({"role": "assistant", "content": reply})

    specs_ready = _SPECS_READY_SIGNAL in reply
    clean_reply = reply.replace(_SPECS_READY_SIGNAL, "").strip()
    return clean_reply, specs_ready


async def build_prompt_from_chat(
    history: list[dict],
    style: str = "moderno",
    layout: str | None = None,
    finish: str | None = None,
) -> dict:
    """Build a complete SD prompt from conversation history + explicit style/layout/finish.

    Returns {"positive": str, "negative": str, "style_key": str}.
    The positive prompt is always in English, starts with 'kitchen interior design,'
    and ends with quality tags.
    """
    style_key = STYLE_MAP.get(style.lower(), "modern")
    base = STYLE_PROMPTS[style_key]

    extra: list[str] = []

    if layout:
        detail = LAYOUT_DETAILS.get(layout.lower())
        if detail:
            extra.append(detail)

    if finish:
        detail = FINISH_DETAILS.get(finish.lower())
        if detail:
            extra.append(detail)

    conversation = [m for m in history if m.get("role") in ("user", "assistant")]
    if conversation:
        extracted = await _extract_design_details(history)
        if extracted:
            extra.append(extracted)

    if extra:
        positive = f"{base}, {', '.join(extra)}, {PROMPT_SUFFIX}"
    else:
        positive = f"{base}, {PROMPT_SUFFIX}"

    return {"positive": positive, "negative": NEGATIVE_PROMPT, "style_key": style_key}


async def build_image_prompt(
    session_id: str,
    style: str = "moderno",
    layout: str | None = None,
    finish: str | None = None,
) -> tuple[str, str]:
    """Convenience wrapper: build prompt from the session's chat history."""
    history = get_session(session_id)
    result = await build_prompt_from_chat(history, style, layout, finish)
    return result["positive"], result["negative"]


async def _extract_design_details(history: list[dict]) -> str:
    """Ask GPT-4o to extract conversation-specific design details not covered by templates."""
    messages = list(history) + [
        {
            "role": "user",
            "content": (
                "From the kitchen design conversation above, extract ONLY specific details "
                "not already implied by the general style (e.g., a particular color, unusual material, "
                "special feature, or custom element). "
                "Return a short English phrase suitable for a Stable Diffusion prompt. "
                "If there are no additional relevant details, return an empty string. "
                "No explanation — only the phrase or empty string."
            ),
        }
    ]

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        max_tokens=80,
    )
    return (response.choices[0].message.content or "").strip()
