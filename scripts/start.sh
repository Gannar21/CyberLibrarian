#!/usr/bin/env bash
# Container entry-point.
#
# Process layout (two processes, same container):
#   port 8000  – Person 4's FastAPI retrieval API, bound to 127.0.0.1 (internal only)
#   port 8501  – Public-facing UI, default: app.web (FastAPI + vanilla JS)
#
# Set UI=streamlit to use the Streamlit fallback instead of the web UI.
#
# Index strategy:
#   SKIP_INDEX_BUILD=false (default): build BM25 + vector index at startup.
#     Slow first start (~2 min) but the container is self-contained.
#   SKIP_INDEX_BUILD=true: skip build; mount prebuilt indexes at
#     /app/indexes (BM25) and /app/chroma (ChromaDB).
set -euo pipefail

cd /app

# --- optional index build ---------------------------------------------------
if [ "${SKIP_INDEX_BUILD:-false}" != "true" ]; then
    echo "[start] Building indexes from full corpus..."
    python -m src.indexing.build_index
    echo "[start] Index build complete."
fi

# --- launch Person 4 API (background, loopback only) -----------------------
echo "[start] Starting retrieval API on 127.0.0.1:8000..."
uvicorn src.api.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

# --- launch public UI (background) -----------------------------------------
PORT="${PORT:-8501}"
UI="${UI:-web}"

if [ "$UI" = "streamlit" ]; then
    echo "[start] Starting Streamlit UI on port ${PORT}..."
    streamlit run app/streamlit_app.py \
        --server.port "${PORT}" \
        --server.address 0.0.0.0 \
        --server.headless true \
        --browser.gatherUsageStats false &
    UI_PID=$!
else
    echo "[start] Starting web UI (app.web) on port ${PORT}..."
    uvicorn app.web:app --host 0.0.0.0 --port "${PORT}" &
    UI_PID=$!
fi

# --- wait and forward signals -----------------------------------------------
trap "kill $API_PID $UI_PID 2>/dev/null; wait" SIGTERM SIGINT
wait $API_PID $UI_PID
