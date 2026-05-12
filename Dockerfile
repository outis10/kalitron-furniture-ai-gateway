# Kalitron Furniture AI Gateway
# Base: NVIDIA CUDA 12.1 runtime — GPU inference via ComfyUI (separate container)
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ── System dependencies ───────────────────────────────────────────────────────
# Single RUN to minimise layers; clean apt cache to keep image small
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-dev \
        python3-pip \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies (cached layer) ───────────────────────────────────────
# Copy requirements first so this layer is only rebuilt when deps change
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir --upgrade pip \
    && pip3 install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────────────
# Copied last — most frequent change, cheapest cache miss
COPY app/ ./app/
COPY fusion_gateway/ ./fusion_gateway/

# ── Non-root user (security) ──────────────────────────────────────────────────
RUN adduser --disabled-password --gecos "" --uid 1000 appuser \
    && mkdir -p /app/outputs \
    && chown -R appuser:appuser /app
USER appuser

# ── Runtime configuration ─────────────────────────────────────────────────────
EXPOSE 8000

# Models and outputs are NOT bundled — mount as volumes at runtime:
#   -v /host/models:/models  (for ComfyUI model sharing)
#   -v /host/outputs:/app/outputs
ENV OUTPUT_DIR=/app/outputs

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
