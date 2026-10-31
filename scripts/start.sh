#!/usr/bin/env bash
# Container entry-point.
# Starts the FastAPI backend (uvicorn) and the Streamlit UI in the same process
# group, forwarding signals so both shut down cleanly on SIGTERM.
#
# Index strategy:
#   - Default (SKIP_INDEX_BUILD=false): build BM25 + vector index at startup
#     from the sample corpus baked into the image.  Slow first start (~2 min),
#     but the container is fully self-contained and needs no external volume.
#   - SKIP_INDEX_BUILD=true: skip the build step.  Mount a prebuilt index
#     directory at /app/indexes (BM25) and /app/chroma (ChromaDB) using
#     a Docker volume or bind-mount.  Faster startup, but requires a separate
#     build step before deployment.
#   Recommendation: use SKIP_INDEX_BUILD=false for demos and CI; use a
#   prebuilt volume mount for production to avoid the 2-minute cold start.
set -euo pipefail

cd /app

# --- optional index build ---------------------------------------------------
if [ "${SKIP_INDEX_BUILD:-false}" != "true" ]; then
    echo "[start] Building indexes from sample corpus..."
    python -m src.indexing.build_index --sample
    echo "[start] Index build complete."
fi

# --- launch API (background) ------------------------------------------------
echo "[start] Starting FastAPI on port 8000..."
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

# --- launch UI (foreground) -------------------------------------------------
echo "[start] Starting Streamlit on port 8501..."
streamlit run app/streamlit_app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false &
UI_PID=$!

# --- wait and forward signals -----------------------------------------------
trap "kill $API_PID $UI_PID 2>/dev/null; wait" SIGTERM SIGINT
wait $API_PID $UI_PID
