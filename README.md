---
title: CyberLibrarian
emoji: 🛡️
colorFrom: blue
colorTo: teal
sdk: docker
app_port: 7860
pinned: false
---

# CyberLibrarian

An AI-powered cybersecurity knowledge assistant grounded in OWASP, NIST, and MITRE ATT&CK sources. Ask natural-language questions and get cited answers retrieved directly from authoritative security documents.

---

## Architecture overview

```
Raw corpus (OWASP · NIST · MITRE)
        │
        ▼
   Ingest & chunk (512 words / 64 overlap)
        │
   ┌────┴────┐
   ▼         ▼
BM25       ChromaDB
index    (all-MiniLM-L6-v2)
   └────┬────┘
        ▼
  Hybrid RRF fusion
        │  optional: cross-encoder rerank
        │  optional: LLM query rewrite
        ▼
  Prompt builder (numbered sources)
        ▼
     LLM call
        ▼
  Citation parser → AnswerResponse
        ▼
  Answer cache (in-memory, TTL 300 s)
        ▼
  FastAPI web UI  (port 7860)
```

---

## Knowledge sources

| Source | Documents | Characters | Chunks | License |
|--------|-----------|------------|--------|---------|
| OWASP Cheat Sheet Series | 137 | 2,623,194 | 814 | CC BY-SA 4.0 |
| MITRE ATT&CK Enterprise | 706 | 1,806,703 | 811 | Apache 2.0 |
| NIST (SP 800-61r3 · CSF 2.0 · SP 800-63-3 · SP 800-63B) | 236 | 520,532 | 243 | Public domain |
| **Total** | **1,079** | **4,950,429** | **1,864** | |

NIST publication dates ingested: SP 800-61r3 (2024-08-23), CSF 2.0 / CSWP 29 (2024-02-26), SP 800-63-3 and SP 800-63B (2017-06-22, archived).

---

## Retrieval evaluation (dev set, 53 answerable questions)

Run with `python -m eval.retrieval_eval`. Relevance = ≥ 60 % token overlap with the gold passage, or matching `source_doc` when no passage is given.

| Configuration | recall@1 | recall@5 | MRR | Latency p50 |
|---|---|---|---|---|
| BM25 only | 0.774 | 0.906 | 0.840 | 14 ms |
| Dense only (all-MiniLM-L6-v2) | 0.585 | 0.868 | 0.706 | 31 ms |
| Hybrid RRF | **0.811** | 0.962 | 0.869 | 30 ms |
| Hybrid + query rewrite | **0.868** | 0.943 | 0.907 | 1,672 ms |
| Hybrid + cross-encoder rerank | 0.836 | 0.959 | 0.894 | 12,495 ms |

The cross-encoder reranker improves recall@1 at the cost of ~12 s latency on CPU and was removed from the production path. Query rewriting is enabled via the `--rewrite` flag in the eval script.

---

## Generation evaluation (36 questions, gpt-4o-mini, cache OFF)

Run with `python -m eval.generation_eval`. Scores are LLM-judged (0/1 per question).

| Metric | Value |
|---|---|
| Correct refusals (5 unanswerable questions) | 1.000 |
| False refusal rate | 0.129 |
| Faithfulness | 0.815 |
| Citation accuracy | 0.778 |
| Correctness | 0.741 |
| Avg cost per question | $0.000583 |
| Avg latency | 1,898 ms |

Sending 3 chunks instead of 5 cuts cost by 35 % ($0.000379/question) with no statistically significant accuracy loss.

---

## Cost model

Based on 40 real gpt-4o-mini requests (full corpus, no rerank):

| | Value |
|---|---|
| Mean input tokens | 3,380 |
| Mean output tokens | 79 |
| Cost per query (gpt-4o-mini: $0.15/M in, $0.60/M out) | **$0.000554** |
| Cost per 1,000 queries | **$0.55** |
| Latency p50 / p95 | 1,166 ms / 1,758 ms |

Price constants are defined in `src/generation/answer.py` and can be overridden with `LLM_PRICE_INPUT_PER_M` and `LLM_PRICE_OUTPUT_PER_M` environment variables.

---

## Quick start (local, mock mode — no API key needed)

**Requirements:** Python 3.12, ~2 GB disk for the sentence-transformers model.

```bash
# 1. Clone and create a virtual environment
git clone https://github.com/Gannar21/CyberLibrarian.git
cd CyberLibrarian
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2. Install dependencies (CPU-only torch must come first)
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 3. Download corpus (idempotent — skips files that already exist)
python data/download_corpus.py

# 4. Build BM25 + vector indexes (~2 min on first run)
python -m src.indexing.build_index

# 5. Start the web UI in mock mode (no LLM calls)
USE_MOCK=true uvicorn app.web:app --port 7860 --reload
```

Open `http://localhost:7860`.

---

## Full setup (real LLM)

```bash
# Copy the example env file and fill in your key
cp .env.example .env
# Edit .env:
#   LLM_API_KEY=sk-...          (OpenAI key, or compatible endpoint)
#   LLM_MODEL=gpt-4o-mini
#   USE_MOCK=false
```

Then start the backend API and the web UI in two terminals:

```bash
# Terminal 1 – retrieval API (internal, port 8000)
uvicorn src.api.main:app --host 127.0.0.1 --port 8000

# Terminal 2 – web UI (public, port 7860)
USE_MOCK=false uvicorn app.web:app --port 7860 --reload
```

---

## Docker (recommended for deployment)

```bash
# Build (indexes are built inside the image — takes ~5 min)
docker build -t cyberlibrarian .

# Run (supply your LLM key at runtime — never bake secrets into the image)
docker run -p 7860:7860 \
  -e LLM_API_KEY=sk-... \
  -e LLM_MODEL=gpt-4o-mini \
  -e USE_MOCK=false \
  cyberlibrarian
```

The container runs two processes: the retrieval API on `127.0.0.1:8000` (internal only) and the web UI on port 7860 (public). CPU-only PyTorch is installed; no GPU required.

---

## Running evaluations

```bash
# Retrieval ablation on dev set only (keyword / vector / hybrid)
python -m eval.retrieval_eval --questions "data/eval/questions_dev.jsonl"

# Add cross-encoder reranker
python -m eval.retrieval_eval --questions "data/eval/questions_dev.jsonl" --full

# Add LLM query rewriting (requires LLM_API_KEY)
python -m eval.retrieval_eval --questions "data/eval/questions_dev.jsonl" --rewrite

# Generation eval (costs real money — start small)
python -m eval.generation_eval --n-dev 10
```

Results are written to `eval/results/`.

---

## Project structure

```
src/
  ingest/        corpus loaders (OWASP markdown, MITRE STIX JSON, NIST PDF)
  indexing/      chunker, BM25 builder, ChromaDB builder
  retrieval/     BM25, vector, hybrid RRF, reranker, query rewriter
  generation/    prompt builder, LLM call, citation parser, answer cache
  common/        config (Config), shared schemas
  api/           FastAPI /ask and /health endpoints (port 8000)
app/
  web.py         public FastAPI + vanilla JS web UI (port 7860)
  web/           index.html, style.css, app.js
eval/
  retrieval_eval.py    ablation across retrieval configurations
  generation_eval.py   faithfulness / correctness / refusal eval
  results/             stored ablation.json, generation_eval.md, failures.jsonl
data/
  raw/           downloaded corpus files (gitignored except .gitkeep)
  processed/     documents.jsonl (1,079 docs after ingest)
  eval/          questions_dev.jsonl (56), questions_test.jsonl (24)
indexes/         bm25.pkl (gitignored)
chroma/          ChromaDB vector store (gitignored)
```

---

## Contributors

| Person | Responsibility |
|--------|---------------|
| Asma Gannar | Web UI, Docker deployment, evaluation pipeline, project integration |
| nouhaamin6 | Retrieval pipeline — BM25, vector search, RRF hybrid, reranker |
| Nouhaaouiti | Data ingestion and corpus processing |
| Asma Aouiti | Answer generation, LLM integration, BM25 tokeniser fix |
| eyabedoui | FastAPI retrieval API |
