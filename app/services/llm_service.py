"""GPT-4o multi-turn chat service with SPECS_READY signal detection."""
from app.core.config import settings
from app.models.schemas import ChatMessage

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
    from openai import AsyncOpenAI

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


async def build_image_prompt(session_id: str) -> tuple[str, str]:
    """Return (positive_prompt, negative_prompt) from chat history."""
    from openai import AsyncOpenAI

    history = get_session(session_id)

    builder_messages = history + [
        {
            "role": "user",
            "content": (
                "Based on the kitchen specifications discussed, generate a Stable Diffusion prompt. "
                "Reply with exactly two lines:\n"
                "POSITIVE: <prompt>\n"
                "NEGATIVE: <negative prompt>"
            ),
        }
    ]

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=builder_messages,
        max_tokens=512,
    )

    raw = response.choices[0].message.content or ""
    positive, negative = "", ""
    for line in raw.splitlines():
        if line.startswith("POSITIVE:"):
            positive = line.removeprefix("POSITIVE:").strip()
        elif line.startswith("NEGATIVE:"):
            negative = line.removeprefix("NEGATIVE:").strip()

    if not positive:
        positive = "kitchen interior design, modern style, professional photography, 8k, photorealistic, architectural visualization"
    if not negative:
        negative = "cartoon, illustration, low quality, blurry, watermark, text, signature"

    return positive, negative
