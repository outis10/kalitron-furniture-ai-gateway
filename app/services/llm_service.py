"""GPT-4o multi-turn chat service with SPECS_READY signal detection and prompt building."""
import json

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.workflows import (
    FINISH_DETAILS,
    CLOSET_LAYOUT_DETAILS,
    LAYOUT_DETAILS,
    NEGATIVE_PROMPT,
    PROMPT_SUFFIX,
    PROJECT_STYLE_PROMPTS,
    STYLE_MAP,
)

_SPECS_READY_SIGNAL = "SPECS_READY"

_sessions: dict[str, list[dict]] = {}

_SYSTEM_PROMPT = """\
Eres un diseñador de interiores experto de Kalitron Furniture Studio, especializado en \
cocinas, armarios y mobiliario a medida. Tu objetivo es guiar al cliente para definir \
sus especificaciones de diseño de forma conversacional, amable y eficiente.

REGLAS OBLIGATORIAS:
1. Responde SIEMPRE en español.
2. Haz MÁXIMO 2 preguntas por turno. Nunca bombardees al cliente con más.
3. Sigue el flujo de 7 pasos en orden, adaptando el tono al cliente.
4. Cuando el cliente confirme el resumen estructurado, escribe el token SPECS_READY \
en una línea sola al final de tu respuesta.

FLUJO DE CONVERSACIÓN:
Paso 1 – Bienvenida: Saluda y pregunta el tipo de proyecto (cocina / armario / ambos).
Paso 2 – Estilo: Explora preferencias de estilo (moderno, rústico, minimalista, clásico, industrial).
Paso 3 – Espacio: Solicita dimensiones (ancho × fondo × alto en cm) y distribución \
(en L, en U, galería, isla o lineal).
Paso 4 – Módulos: Pregunta qué módulos necesita (cajones, puertas, estantes abiertos, alacenas, \
cajoneras).
Paso 5 – Materiales y acabados: Consulta materiales (MDF lacado, madera maciza, melamina, \
tablero enchapado) y color o acabado deseado.
Paso 6 – Resumen: Presenta un resumen estructurado con TODOS los datos recabados usando \
este formato exacto:
  • Tipo de proyecto: ...
  • Estilo: ...
  • Dimensiones: ... cm × ... cm × ... cm
  • Distribución: ...
  • Módulos: ...
  • Material: ...
  • Acabado/Color: ...
  • Notas adicionales: ...
Paso 7 – Confirmación: Pregunta si el resumen es correcto. Cuando el cliente confirme, \
escribe SPECS_READY en una línea sola.

TONO: Profesional, cálido y conciso. Evita tecnicismos innecesarios.\
"""


# ── Session management ────────────────────────────────────────────────────────

def get_session(session_id: str) -> list[dict]:
    """Return the message history for *session_id*, creating it if it doesn't exist."""
    if session_id not in _sessions:
        _sessions[session_id] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    return _sessions[session_id]


def clear_session(session_id: str) -> None:
    """Delete all history for *session_id*. No-op if the session doesn't exist."""
    _sessions.pop(session_id, None)


def session_turn_count(session_id: str) -> int:
    """Return the number of user turns in the session (excludes system message)."""
    history = _sessions.get(session_id, [])
    return sum(1 for m in history if m["role"] == "user")


# ── Chat ──────────────────────────────────────────────────────────────────────

async def chat(
    session_id: str,
    user_message: str,
    image_b64: str | None = None,
    image_mime_type: str = "image/jpeg",
) -> tuple[str, bool]:
    """Send *user_message* and return (reply, specs_ready).

    If *image_b64* is provided it is sent as a vision content array alongside
    the text so GPT-4o can analyse the reference photo.
    """
    history = get_session(session_id)

    if image_b64:
        visual_instruction = (
            "El cliente adjuntó una imagen de referencia. Analízala visualmente y úsala para inferir "
            "distribución, módulos, colores, materiales y estilo. No digas que no puedes ver imágenes. "
            "Si algún detalle no es claro, pregunta solo por ese detalle.\n\n"
            f"Mensaje del cliente: {user_message}"
        )
        content: list | str = [
            {"type": "text", "text": visual_instruction},
            {"type": "image_url", "image_url": {"url": f"data:{normalize_image_mime_type(image_mime_type)};base64,{image_b64}"}},
        ]
    else:
        content = user_message

    history.append({"role": "user", "content": content})

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=history,
        max_tokens=1024,
        temperature=0.7,
    )

    reply = response.choices[0].message.content or ""
    history.append({"role": "assistant", "content": reply})

    specs_ready = _SPECS_READY_SIGNAL in reply
    clean_reply = reply.replace(_SPECS_READY_SIGNAL, "").strip()
    return clean_reply, specs_ready


def normalize_image_mime_type(image_mime_type: str | None) -> str:
    if image_mime_type in ("image/jpeg", "image/png", "image/webp"):
        return image_mime_type
    return "image/jpeg"


# ── Prompt building ───────────────────────────────────────────────────────────

async def build_prompt_from_chat(
    history: list[dict],
    style: str = "moderno",
    layout: str | None = None,
    finish: str | None = None,
    project_type: str = "KITCHEN",
    design_brief: str | None = None,
) -> dict:
    """Build a complete SD prompt from conversation history + explicit style/layout/finish.

    Returns {"positive": str, "negative": str, "style_key": str}.
    The positive prompt is always in English and ends with quality tags.
    """
    style_key = _resolve_style_key(style)
    project_key = normalize_project_type(project_type)
    base = PROJECT_STYLE_PROMPTS[project_key][style_key]

    extra: list[str] = []

    # Explicit color extracted from composite style name ("Minimalista Negro" → "black")
    color_fragment = _extract_color_from_style(style)
    if color_fragment:
        extra.append(color_fragment)

    # When layout/finish arrive as null, attempt to extract them from the brief
    effective_layout = layout
    effective_finish = finish
    if design_brief and (not effective_layout or not effective_finish):
        extracted_layout, extracted_finish = _extract_layout_finish_from_brief(design_brief)
        effective_layout = effective_layout or extracted_layout
        effective_finish = effective_finish or extracted_finish

    if effective_layout:
        detail = layout_details_for_project(project_key).get(effective_layout.lower())
        if detail:
            extra.append(detail)

    if effective_finish:
        detail = FINISH_DETAILS.get(effective_finish.lower())
        if detail:
            extra.append(detail)

    conversation = [m for m in history if m.get("role") in ("user", "assistant")]
    if conversation:
        extracted = await _extract_design_details(history, project_key)
        if extracted:
            extra.append(extracted)

    if design_brief:
        extra.append(await _translate_design_brief(design_brief, project_key))

    positive = f"{base}, {', '.join(extra)}, {PROMPT_SUFFIX}" if extra else f"{base}, {PROMPT_SUFFIX}"
    return {"positive": positive, "negative": NEGATIVE_PROMPT, "style_key": style_key}


async def build_image_prompt(
    session_id: str,
    style: str = "moderno",
    layout: str | None = None,
    finish: str | None = None,
    project_type: str = "KITCHEN",
    design_brief: str | None = None,
) -> tuple[str, str]:
    """Convenience wrapper: build SD prompt from the session's chat history."""
    history = get_session(session_id)
    result = await build_prompt_from_chat(history, style, layout, finish, project_type, design_brief)
    return result["positive"], result["negative"]


_COLOR_MAP: dict[str, str] = {
    "negro": "matte black cabinets, all-black kitchen furniture, dark black cabinet color",
    "black": "matte black cabinets, all-black kitchen furniture, dark black cabinet color",
    "blanco": "white cabinets, all-white kitchen furniture, bright white cabinet color",
    "white": "white cabinets, all-white kitchen furniture, bright white cabinet color",
    "gris": "gray cabinets, grey kitchen furniture, gray cabinet color",
    "gray": "gray cabinets, grey kitchen furniture, gray cabinet color",
    "grey": "gray cabinets, grey kitchen furniture, gray cabinet color",
    "roble": "oak wood cabinets, warm oak cabinet color, natural wood grain",
    "oak": "oak wood cabinets, warm oak cabinet color, natural wood grain",
}


def _extract_color_from_style(style: str) -> str | None:
    """Return an explicit English color phrase when the style name contains a color modifier.

    'Minimalista Negro' → 'matte black cabinets, all-black kitchen furniture, dark black cabinet color'
    'Moderno Blanco'    → 'white cabinets, ...'
    'Moderno'           → None
    """
    style_lower = style.lower()
    for token, phrase in _COLOR_MAP.items():
        if token in style_lower:
            return phrase
    return None


def _resolve_style_key(style: str) -> str:
    """Map a raw style string (possibly composite like 'Minimalista Negro') to a STYLE_MAP key.

    Tries exact match first, then substring match so 'Minimalista Negro' → 'minimalist'.
    """
    style_lower = style.lower().strip()
    if style_lower in STYLE_MAP:
        return STYLE_MAP[style_lower]
    for key, mapped in STYLE_MAP.items():
        if key in style_lower:
            return mapped
    return "modern"


def _extract_layout_finish_from_brief(brief: str) -> tuple[str | None, str | None]:
    """Extract layout and finish values from a structured design brief using keyword scan.

    Looks for 'Distribución:' and 'Acabado/Color:' lines and returns normalized tokens
    that can be looked up in LAYOUT_DETAILS and FINISH_DETAILS.
    """
    layout: str | None = None
    finish: str | None = None

    for line in brief.splitlines():
        line_lower = line.lower()
        if "distribución:" in line_lower or "distribucion:" in line_lower:
            value = line.split(":", 1)[-1].strip().lower()
            layout = value
        elif "acabado" in line_lower and ":" in line_lower:
            value = line.split(":", 1)[-1].strip().lower()
            finish = value

    return layout, finish


def normalize_project_type(project_type: str | None) -> str:
    if not project_type:
        return "KITCHEN"
    normalized = project_type.strip().upper()
    if normalized in ("CLOSET", "ARMARIO", "WARDROBE"):
        return "CLOSET"
    if normalized in ("BOTH", "AMBOS"):
        return "BOTH"
    return "KITCHEN"


def layout_details_for_project(project_key: str) -> dict[str, str]:
    if project_key == "CLOSET":
        return CLOSET_LAYOUT_DETAILS
    return LAYOUT_DETAILS


async def _extract_design_details(history: list[dict], project_key: str) -> str:
    """Ask GPT-4o to extract conversation-specific design details not covered by style templates."""
    subject = "wardrobe closet" if project_key == "CLOSET" else "kitchen"
    messages = list(history) + [
        {
            "role": "user",
            "content": (
                f"From the {subject} design conversation above, extract ONLY specific details "
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


async def _translate_design_brief(design_brief: str, project_key: str) -> str:
    subject = "wardrobe closet" if project_key == "CLOSET" else "kitchen"
    messages = [
        {
            "role": "user",
            "content": (
                f"Translate this {subject} design summary into a concise English Stable Diffusion prompt fragment. "
                "Rules:\n"
                "- If the layout is 'lineal' or 'galley' or 'linear', you MUST include 'single-wall galley kitchen layout' and NEVER include island, L-shape or U-shape.\n"
                "- If the layout is 'en L' or 'L-shaped', include 'L-shaped kitchen layout'.\n"
                "- If the layout is 'en U' or 'U-shaped', include 'U-shaped kitchen layout'.\n"
                "- If the layout is 'isla' or 'island', include 'kitchen with central island'.\n"
                "- Preserve finish, color, material and modules.\n"
                "- Do not add a kitchen if the summary is for a closet.\n"
                "- Return only the prompt fragment, no explanation.\n\n"
                f"{design_brief}"
            ),
        }
    ]

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        max_tokens=180,
        temperature=0.2,
    )
    return (response.choices[0].message.content or "").strip()


# ── Spec extraction ───────────────────────────────────────────────────────────

_EXTRACTION_SYSTEM_PROMPT = """\
You are a kitchen spec extractor. Analyze the conversation and return a single JSON object.

Cabinet ID convention:
  U-## = upper/aéreo  |  L-## = lower/bajo  |  C-## = corner/esquinero
  T-## = tall/torre/alacena  |  S-## = sink/fregadero

Mexican market defaults (apply when not explicitly mentioned):
  - Upper cabinet:  height_mm=720,  depth_mm=350
  - Lower cabinet:  height_mm=870,  depth_mm=600
  - Corner cabinet: height_mm=870,  depth_mm=600
  - Tall cabinet:   height_mm=2100, depth_mm=600
  - Sink cabinet:   height_mm=870,  depth_mm=600
  - Default material: "MDF 18mm"
  - Default finish:   "blanco mate"
  - Default kitchen_type: "L"
  - Default total_height_mm: 2400
  - Default total_depth_mm:  600

Return ONLY this JSON (no explanation):
{
  "kitchen_type": "L|U|lineal|isla",
  "total_width_mm": <int>,
  "total_height_mm": <int>,
  "total_depth_mm": <int>,
  "style": <string>,
  "confidence": <float 0.0-1.0>,
  "cabinets": [
    {
      "id": "U-01",
      "category": "upper|lower|corner|tall|sink",
      "label": <string in Spanish>,
      "width_mm": <int>,
      "height_mm": <int>,
      "depth_mm": <int>,
      "doors": <int>,
      "drawers": <int>,
      "material": <string>,
      "finish": <string>
    }
  ]
}
"""

# Defaults per category (mm) — Mexican market standard
_CATEGORY_DEFAULTS: dict[str, dict] = {
    "upper":  {"height_mm": 720,  "depth_mm": 350},
    "lower":  {"height_mm": 870,  "depth_mm": 600},
    "corner": {"height_mm": 870,  "depth_mm": 600},
    "tall":   {"height_mm": 2100, "depth_mm": 600},
    "sink":   {"height_mm": 870,  "depth_mm": 600},
}


def _apply_mexican_defaults(raw: dict) -> dict:
    """Fill missing values with Mexican market defaults in-place and return the dict."""
    raw.setdefault("kitchen_type", "L")
    raw.setdefault("total_height_mm", 2400)
    raw.setdefault("total_depth_mm", 600)
    raw.setdefault("total_width_mm", 0)
    raw.setdefault("style", "moderno")
    raw.setdefault("cabinets", [])

    counters: dict[str, int] = {}
    for cab in raw["cabinets"]:
        category = cab.get("category", "lower")
        defaults = _CATEGORY_DEFAULTS.get(category, _CATEGORY_DEFAULTS["lower"])

        cab.setdefault("height_mm", defaults["height_mm"])
        cab.setdefault("depth_mm", defaults["depth_mm"])
        cab.setdefault("material", "MDF 18mm")
        cab.setdefault("finish", "blanco mate")
        cab.setdefault("doors", 0)
        cab.setdefault("drawers", 0)
        cab.setdefault("label", category.capitalize())

        # Auto-assign ID if missing or malformed
        prefix = {"upper": "U", "lower": "L", "corner": "C", "tall": "T", "sink": "S"}.get(category, "L")
        if not cab.get("id", "").startswith(prefix):
            counters[prefix] = counters.get(prefix, 0) + 1
            cab["id"] = f"{prefix}-{counters[prefix]:02d}"

    return raw


async def extract_specs(session_id: str) -> dict:
    """Extract structured kitchen specs from the session's conversation history.

    Returns a dict with keys 'specs' (ExtractedKitchenSpecs-compatible) and 'confidence'.
    Uses temperature=0.1 for deterministic extraction.
    """
    history = get_session(session_id)
    conversation = [m for m in history if m.get("role") in ("user", "assistant")]
    if not conversation:
        return {
            "specs": _apply_mexican_defaults({}),
            "confidence": 0.0,
        }

    messages = [
        {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
        *[m for m in history if m.get("role") in ("user", "assistant")],
        {"role": "user", "content": "Extract the kitchen specifications from the conversation above."},
    ]

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        temperature=0.1,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )

    raw = json.loads(response.choices[0].message.content or "{}")
    confidence = float(raw.pop("confidence", 0.7))
    specs = _apply_mexican_defaults(raw)

    return {"specs": specs, "confidence": confidence}
