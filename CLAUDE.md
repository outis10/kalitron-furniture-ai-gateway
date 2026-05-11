# Kalitron Furniture AI Gateway — Claude Code Context

## Project Overview
FastAPI Python service that acts as the AI brain for Kalitron Furniture Studio.
Handles multi-turn LLM conversations, orchestrates image generation via ComfyUI,
builds Stable Diffusion prompts from chat history, and stores results in Cloudflare R2.

**GitHub:** https://github.com/outis10/kalitron-furniture-ai-gateway
**Studio repo:** https://github.com/outis10/kalitron-furniture-studio
**Issues:** https://github.com/outis10/kalitron-furniture-ai-gateway/issues

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API framework | FastAPI 0.111 · Python 3.11 |
| LLM | OpenAI GPT-4o (chat + vision + prompt building) |
| Image generation | Stable Diffusion XL 1.0 via ComfyUI |
| Structure preservation | ControlNet Canny SDXL |
| Inference engine | ComfyUI — localhost:8188 |
| GPU | NVIDIA RTX 3080 12GB VRAM (dev) → RunPod RTX 4090 (prod) |
| Image storage | Cloudflare R2 (prod) · local disk fallback (dev) |
| Validation | Pydantic v2 |
| HTTP client | httpx (async) |
| ASGI server | uvicorn |

---

## Project Structure

```
kalitron-furniture-ai-gateway/
├── app/
│   ├── main.py                  ← FastAPI app, CORS, static files mount
│   ├── core/
│   │   └── config.py            ← Pydantic Settings from .env
│   ├── api/
│   │   └── v1/
│   │       ├── router.py        ← Registers all routers
│   │       ├── chat.py          ← POST /api/v1/chat/message
│   │       ├── images.py        ← POST /api/v1/images/generate
│   │       └── design.py        ← POST /api/v1/design/extract-specs
│   │                               POST /api/v1/design/generate-csv
│   ├── services/
│   │   ├── llm_service.py       ← GPT-4o multi-turn chat + SPECS_READY detection
│   │   ├── image_service.py     ← Main orchestrator: routes img2img vs txt2img
│   │   ├── workflows.py         ← ComfyUI workflow JSON (IMG2IMG + TXT2IMG)
│   │   ├── storage.py           ← R2 upload with local fallback
│   │   └── csv_generator.py     ← KitchenSpecs → CSV with panel calculations
│   └── models/
│       └── schemas.py           ← All Pydantic request/response models
├── fusion_gateway/
│   └── script_builder.py        ← Reads CSV → generates Fusion 360 .py script
├── outputs/                     ← Local image storage in dev (gitignored)
├── .env                         ← Never commit (in .gitignore)
├── .env.example                 ← Commit this with placeholder values
├── requirements.txt
├── Dockerfile                   ← NVIDIA CUDA base for RunPod
└── README.md
```

---

## Critical Rules

### Always async
Every endpoint and service method that does I/O must be `async def`.
Never block the event loop — use `httpx.AsyncClient`, not `requests`.

```python
# CORRECT
async def generate_concept(...) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(...)

# WRONG — blocks event loop
def generate_concept(...) -> dict:
    response = requests.post(...)
```

### Config via Pydantic Settings — never hardcode
```python
# CORRECT
from app.core.config import settings
url = settings.COMFYUI_URL

# WRONG
url = "http://localhost:8188"
```

### Session store pattern (MVP)
```python
# In-memory for MVP — dict keyed by session_id
_sessions: dict[str, list[dict]] = {}

def get_session(session_id: str) -> list[dict]:
    if session_id not in _sessions:
        _sessions[session_id] = []
    return _sessions[session_id]
```

### Error handling in endpoints
```python
@router.post("/generate")
async def generate(payload: GenerateRequest):
    try:
        result = await image_service.generate_kitchen_concept(...)
        return GenerateResponse(**result)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="ComfyUI timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Environment Variables

```bash
# ComfyUI
COMFYUI_URL=http://localhost:8188

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Cloudflare R2 (leave empty in dev — uses local fallback)
R2_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=kitchen-designs
R2_PUBLIC_URL=https://images.kalitron.com

# Local paths
OUTPUT_DIR=C:/AI/outputs

# JHipster studio backend
JHIPSTER_BACKEND_URL=http://localhost:8080
```

---

## ComfyUI API Reference

```
POST http://localhost:8188/prompt
     Body: { "prompt": <workflow_dict>, "client_id": "<uuid>" }
     Returns: { "prompt_id": "<id>" }

GET  http://localhost:8188/history/<prompt_id>
     Returns: { "<prompt_id>": { "outputs": { "<node_id>": { "images": [...] } } } }

GET  http://localhost:8188/view?filename=<name>&subfolder=<sub>&type=output
     Returns: image bytes

POST http://localhost:8188/upload/image
     Form: image file + type=input + overwrite=true
     Returns: { "name": "<filename>" }

GET  http://localhost:8188/system_stats
     Returns: { "devices": [{ "name": "RTX 3080", "vram_total": ... }] }
```

---

## VRAM Budget (RTX 3080 12GB)

| Model | VRAM | Path |
|-------|------|------|
| SDXL 1.0 base | ~6.5GB | models/checkpoints/sd_xl_base_1.0.safetensors |
| ControlNet Canny SDXL | ~1.5GB | models/controlnet/controlnet-canny-sdxl-1.0.safetensors |
| SDXL VAE fp16-fix | ~330MB | models/vae/sdxl_vae.safetensors |
| System overhead | ~1.0GB | — |
| **Total** | **~9.3GB** | ✓ fits in 12GB |

---

## Image Generation Pipelines

### Pipeline A — img2img (client has a photo)
```
client photo (base64)
    → resize to 1024x1024
    → upload to ComfyUI /upload/image
    → CannyEdgePreprocessor (extracts structure lines)
    → ControlNetApplyAdvanced (strength=0.75)
    → KSampler (30 steps, denoise=0.75)
    → VAEDecode
    → image bytes
    → upload to R2
    → return public URL
```

### Pipeline B — txt2img (description only)
```
chat history
    → GPT-4o prompt builder
    → positive + negative prompt
    → KSampler (35 steps, denoise=1.0, 1024x768)
    → VAEDecode
    → image bytes
    → upload to R2
    → return public URL
```

### Routing logic
```python
if client_image_b64:
    # img2img — preserve structure
    workflow = deepcopy(IMG2IMG_WORKFLOW)
else:
    # txt2img — generate from scratch
    workflow = deepcopy(TXT2IMG_WORKFLOW)
```

---

## Prompt Engineering Rules

Positive prompts must:
- Always be in English (SDXL trained on English)
- Start with: `kitchen interior design, `
- Include specific materials (quartz, marble, oak, MDF, etc.)
- Include lighting (natural light, under-cabinet lighting, etc.)
- End with: `professional photography, 8k, photorealistic, architectural visualization`

Negative prompts must include:
- `cartoon, illustration, low quality, blurry, watermark, text, signature`

Style → prompt template mapping lives in `services/workflows.py → STYLE_PROMPTS`.

---

## Git Workflow

```bash
# One branch per issue
git checkout -b feat/eN-short-description

# Atomic commits
git commit -m "feat(eN): description - closes #N"

# Push and PR
git push origin feat/eN-short-description
gh pr create --title "feat(eN): description" --body "Closes #N"
```

### Commit types
```
feat    new feature
fix     bug fix
perf    performance improvement
docs    documentation only
test    adding tests
chore   tooling, deps, config
```

---

## Common Commands

```bash
# Start gateway
uvicorn app.main:app --reload --port 8000

# Start ComfyUI (Windows — run in separate terminal)
cd C:/AI/ComfyUI && venv/Scripts/activate && python main.py --listen 0.0.0.0

# Install dependencies
pip install -r requirements.txt

# Check Swagger
open http://localhost:8000/docs

# Health check
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/images/health

# Docker build (for RunPod)
docker build -t kalitron-ai-gateway .
docker run --gpus all -p 8000:8000 --env-file .env kalitron-ai-gateway
```

---

## Issue Resolution Checklist

When resolving a GitHub issue, always:
- [ ] Create branch `feat/eN-issue-short-name`
- [ ] All new functions must be `async def`
- [ ] Config values from `settings`, never hardcoded
- [ ] Add docstring to every public function
- [ ] Run `uvicorn app.main:app` — no import errors before PR
- [ ] Test the endpoint manually via Swagger at `/docs`
- [ ] Commit with `closes #N` in message
- [ ] Open PR referencing the issue
