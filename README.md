# Kalitron Furniture AI Gateway

![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)
![SDXL](https://img.shields.io/badge/SDXL-1.0-orange)
![ControlNet](https://img.shields.io/badge/ControlNet-Canny-purple)
![ComfyUI](https://img.shields.io/badge/ComfyUI-latest-blue)
![RunPod](https://img.shields.io/badge/RunPod-ready-green)
![CUDA](https://img.shields.io/badge/CUDA-12.1-76B900?logo=nvidia)

AI brain for **Kalitron Furniture Studio** — handles multi-turn LLM design conversations, orchestrates Stable Diffusion image generation via ComfyUI, and stores renders in Cloudflare R2.

This service is intentionally separate from the JHipster monolith so GPU workloads can scale independently on RunPod without touching the Spring Boot backend.

---

## Architecture

```
React Studio (localhost:9000)
        │  chat / generate
        ▼
JHipster Backend (localhost:8080)
        │  POST /api/v1/...
        ▼
Kalitron AI Gateway  ◄─── this repo ───►  Cloudflare R2
        │                                  (renders + CSVs)
        │  ComfyUI REST API
        ▼
ComfyUI (localhost:8188)
        │  SDXL 1.0 + ControlNet Canny
        ▼
NVIDIA GPU (RTX 3080 dev / RTX 4090 RunPod)
```

### Services

| Component | Role |
|-----------|------|
| **FastAPI Gateway** | REST API, session management, LLM orchestration |
| **GPT-4o** | Multi-turn design conversation + spec extraction + SD prompt building |
| **ComfyUI** | SDXL inference engine (separate process/container) |
| **Cloudflare R2** | Object storage for renders, CSVs, Fusion 360 scripts |

---

## Image Generation Pipelines

### Pipeline A — img2img (client has a reference photo)

```
client photo (base64)
  → resize / upload to ComfyUI
  → CannyEdgePreprocessor  (extracts structure lines)
  → ControlNetApplyAdvanced (strength=0.75)
  → KSampler  30 steps · denoise=0.75
  → VAEDecode
  → JPEG → Cloudflare R2
  → public URL
```

Best for: preserving the existing kitchen layout while restyling finishes and materials.

### Pipeline B — txt2img (description only)

```
chat history
  → GPT-4o prompt builder (style + layout + finish + extras)
  → positive + negative prompt
  → KSampler  35 steps · denoise=1.0 · 1024×768
  → VAEDecode
  → JPEG → Cloudflare R2
  → public URL
```

Best for: generating a concept from scratch based on the design conversation.

---

## Models

| Model | VRAM | Path |
|-------|------|------|
| SDXL 1.0 base | ~6.5 GB | `models/checkpoints/sd_xl_base_1.0.safetensors` |
| ControlNet Canny SDXL | ~1.5 GB | `models/controlnet/controlnet-canny-sdxl-1.0.safetensors` |
| SDXL VAE fp16-fix | ~330 MB | `models/vae/sdxl_vae.safetensors` |
| GPT-4o | API | OpenAI cloud |

Total GPU VRAM (RTX 3080 12 GB): ~9.3 GB — fits with headroom.

---

## Local Setup — Windows RTX 3080

### 1. ComfyUI

```bash
# Clone and install (run once)
git clone https://github.com/comfyanonymous/ComfyUI C:/AI/ComfyUI
cd C:/AI/ComfyUI
python -m venv venv
venv\Scripts\activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt

# Download models into C:/AI/ComfyUI/models/
# SDXL 1.0:     https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0
# ControlNet:   https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0
# VAE:          https://huggingface.co/madebyollin/sdxl-vae-fp16-fix

# Start ComfyUI (keep running in a separate terminal)
python main.py --listen 0.0.0.0
```

### 2. AI Gateway

```bash
git clone https://github.com/outis10/kalitron-furniture-ai-gateway
cd kalitron-furniture-ai-gateway

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / macOS

pip install -r requirements.txt

cp .env.example .env
# Edit .env — add your OPENAI_API_KEY at minimum

uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000/docs** to explore the API.

---

## API Reference

### `POST /api/v1/chat/message`

Multi-turn design conversation with GPT-4o. Returns `specs_ready=true` when the 7-step flow is complete.

```json
// Request
{
  "session_id": "abc123",
  "message": "Quiero una cocina moderna en L de 3.6m",
  "image_b64": null
}

// Response
{
  "session_id": "abc123",
  "reply": "¡Excelente elección! ¿Qué acabado prefieres para los módulos?",
  "specs_ready": false
}
```

### `POST /api/v1/images/generate`

Generate a kitchen concept render via ComfyUI.

```json
// Request
{
  "session_id": "abc123",
  "style": "moderno",
  "layout": "island",
  "finish": "white matte",
  "client_image_b64": null
}

// Response
{
  "session_id": "abc123",
  "image_url": "https://images.kalitron.com/concepts/abc123/concept_a1b2c3d4.jpg",
  "prompt_used": "kitchen interior design, modern minimalist style...",
  "pipeline": "txt2img"
}
```

### `GET /api/v1/images/health`

Check ComfyUI availability.

```json
{ "status": "ok", "detail": "ComfyUI running — device: RTX 3080" }
// or
{ "status": "unavailable", "detail": "All connection attempts failed" }
```

### `POST /api/v1/design/extract-specs`

Extract structured `ExtractedKitchenSpecs` from conversation history.

```json
// Request
{ "session_id": "abc123" }

// Response
{
  "session_id": "abc123",
  "confidence": 0.95,
  "specs": {
    "kitchen_type": "L",
    "total_width_mm": 3600,
    "total_height_mm": 2400,
    "total_depth_mm": 600,
    "style": "moderno",
    "cabinets": [
      {
        "id": "U-01",
        "category": "upper",
        "label": "Aéreo estándar",
        "width_mm": 600, "height_mm": 720, "depth_mm": 350,
        "doors": 2, "drawers": 0,
        "material": "MDF 18mm", "finish": "blanco mate"
      }
    ]
  }
}
```

Cabinet ID convention: `U`=upper · `L`=lower · `C`=corner · `T`=tall · `S`=sink

### `POST /api/v1/design/generate-csv`

Generate a cut-list CSV from specs for Fusion 360.

```json
// Request
{
  "project_name": "cocina_martinez",
  "specs": { "width_cm": 360, "depth_cm": 60, "height_cm": 240, ... }
}

// Response
{
  "filename": "cocina_martinez_cut_list.csv",
  "csv_content": "part,qty,width_cm,height_cm,thickness_mm,material\n..."
}
```

### `GET /health`

```json
{ "status": "ok" }
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ✅ | GPT-4o API key |
| `OPENAI_MODEL` | — | Default: `gpt-4o` |
| `COMFYUI_URL` | — | Default: `http://localhost:8188` |
| `R2_ENDPOINT_URL` | Production | `https://<account>.r2.cloudflarestorage.com` |
| `R2_ACCESS_KEY_ID` | Production | Cloudflare R2 key ID |
| `R2_SECRET_ACCESS_KEY` | Production | Cloudflare R2 secret |
| `R2_BUCKET_NAME` | Production | Default: `kitchen-designs` |
| `R2_PUBLIC_URL` | Production | e.g. `https://images.kalitron.com` |
| `OUTPUT_DIR` | — | Local fallback path. Default: `./outputs` |
| `JHIPSTER_BACKEND_URL` | — | Default: `http://localhost:8080` |
| `CORS_ORIGINS` | — | JSON array. Default: `["http://localhost:8080","http://localhost:9000"]` |

> **Dev tip:** Leave all R2 variables empty. The gateway automatically falls back to saving renders in `OUTPUT_DIR` served via `/outputs`.

---

## RunPod Deployment

### 1. Build and push the image

```bash
docker build -t your-dockerhub/kalitron-ai-gateway:latest .
docker push your-dockerhub/kalitron-ai-gateway:latest
```

### 2. Create a RunPod GPU pod

- Template: **RunPod PyTorch 2.1 / CUDA 12.1**
- GPU: **RTX 4090** (24 GB VRAM — recommended for production)
- Expose port: **8000**
- Container image: `your-dockerhub/kalitron-ai-gateway:latest`

### 3. Set environment variables

In the RunPod pod settings → Environment Variables, add all variables from the table above. For production, R2 credentials are required.

### 4. Mount ComfyUI as a sidecar

ComfyUI runs in a separate pod on the same RunPod network. Set `COMFYUI_URL` to its internal address.

### 5. Verify

```bash
curl https://<pod-id>.runpod.net/health
# {"status": "ok"}

curl https://<pod-id>.runpod.net/api/v1/images/health
# {"status": "ok", "detail": "ComfyUI running — device: RTX 4090"}
```

---

## Performance Benchmarks

| Operation | RTX 3080 12GB | RTX 4090 24GB |
|-----------|--------------|--------------|
| txt2img (35 steps, 1024×768) | ~28s | ~10s |
| img2img + ControlNet (30 steps) | ~35s | ~13s |
| GPT-4o chat turn | ~2s | ~2s (API-bound) |
| Spec extraction | ~1.5s | ~1.5s (API-bound) |
| R2 upload (~500KB JPEG) | ~0.3s | ~0.3s (network-bound) |

RTX 3080 is sufficient for development. RTX 4090 is recommended for production to keep end-to-end latency under 15s.

---

## Development Commands

```bash
# Start gateway
uvicorn app.main:app --reload --port 8000

# Run tests
pytest tests/ -v

# Docker (local, no GPU)
docker build -t kalitron-ai-gateway .
docker run -p 8000:8000 --env-file .env kalitron-ai-gateway

# Docker (GPU)
docker run --gpus all -p 8000:8000 --env-file .env kalitron-ai-gateway

# Docker Compose (GPU)
docker compose up

# Health checks
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/images/health

# Swagger UI
open http://localhost:8000/docs
```

---

## Related Repositories

- [kalitron-furniture-studio](https://github.com/outis10/kalitron-furniture-studio) — JHipster React + Spring Boot monolith
- [kalitron-furniture-ai-gateway](https://github.com/outis10/kalitron-furniture-ai-gateway) — this repo
