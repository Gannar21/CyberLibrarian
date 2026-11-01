# syntax=docker/dockerfile:1
#
# CyberLibrarian – single container
#
# Build:   docker build -t cyberlibrarian .
# Run:     docker run -p 8501:8501 \
#              -e LLM_API_KEY=... -e USE_MOCK=false cyberlibrarian
#
# Default UI: app.web (FastAPI + vanilla JS) on port 8501.
# Fallback UI: set UI=streamlit to use Streamlit instead.
# Port 8000 (retrieval API) is bound to 127.0.0.1 — NOT meant to be published.
#
# Index strategy (see scripts/start.sh): by default the index is built at
# container start from the corpus that was baked in at image-build time.
# Set SKIP_INDEX_BUILD=true to skip if a prebuilt index volume is mounted.
#
# CPU-only torch: installed first in its own layer so sentence-transformers
# does not trigger a CUDA wheel download. The verification step below the
# requirements install confirms torch.version.cuda is None.

FROM python:3.12-slim

# --- system deps ------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
    && rm -rf /var/lib/apt/lists/*

# --- non-root user ----------------------------------------------------------
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# --- CPU-only torch (must come before requirements so pip keeps this wheel) --
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=120 --retries 10 \
        torch --index-url https://download.pytorch.org/whl/cpu

# --- remaining python deps --------------------------------------------------
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=120 --retries 10 \
        -r requirements.txt && \
    python -c "import torch; v=torch.version.cuda; print('torch', torch.__version__, 'cuda:', v); assert v is None, 'GPU torch installed – expected CPU-only'"

# --- source code ------------------------------------------------------------
COPY --chown=appuser:appuser . .

# --- runtime user -----------------------------------------------------------
USER appuser

EXPOSE 8501

# Non-secret configuration defaults. Secrets (LLM_API_KEY, etc.) must be
# supplied at run time via -e or --env-file; do not set them here.
ENV LLM_MODEL=""         \
    EMBEDDING_MODEL=""   \
    LLM_BASE_URL=""      \
    API_URL="http://localhost:8000" \
    USE_MOCK="false"     \
    TEST_ROUND=""        \
    ADMIN_MODE="false"   \
    BUDGET_USD="5.0"     \
    SKIP_INDEX_BUILD="false" \
    UI="web"             \
    PORT="8501"

ENTRYPOINT ["bash", "scripts/start.sh"]
