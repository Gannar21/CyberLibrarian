# Person 3: Week 8 optimisation (section for optimisation.md)

**Target:** cut p95 latency (or cost) by 50% with at most 2 points of accuracy lost, measured on the same test set before and after.
**Chosen metric: p95 latency.** Cost per request is already about $0.0005 and the reranker runs locally, so it never contributed to the bill.

## Method

`eval/replay.py` sends the same 40 eval questions (spread across the question files) through `answer()` and logs per-stage latency, tokens and cost to `data/requests_before.jsonl` / `data/requests_after.jsonl`. `eval/cost_model.py` summarises each log. Same model (`gpt-4o-mini`), same questions, same code; only `USE_RERANK` differs.

## Result: turning the reranker off

| | Before (reranker on) | After (reranker off) | Change |
|---|---|---|---|
| Retrieval p50 / p95 | 7,606 / 8,809 ms | 74 / 94 ms | -99% |
| Generation p50 / p95 | 1,199 / 2,039 ms | 1,090 / 1,590 ms | (LLM, unchanged by this) |
| **Total p50 / p95** | 8,915 / 10,531 ms | **1,167 / 1,672 ms** | **-87% / -84%** |
| Tokens per request | 3,402 | 3,459 | +2% |
| Cost per request | $0.00055 | $0.00055 | 0% |
| recall@5 (73 questions) | 0.986 | 0.986 | 0 |
| recall@1 / MRR | 0.877 / 0.928 | 0.877 / 0.923 | -0.005 MRR |

The 50% target is met on latency (84% at p95). Cost is unchanged because the reranker is local.

## Accuracy check (generation)

The retrieval metrics above are identical, but the "at most 2 points lost" rule is about answer quality. Generation eval with the same 40 questions:

| | Reranker on | Reranker off |
|---|---|---|
| Answer correctness | <<FILL from P4>> | <<FILL>> |
| Faithfulness | <<FILL>> | <<FILL>> |
| Citation accuracy | <<FILL>> | <<FILL>> |

## Earlier change: moving from gpt-oss-120b (Groq) to gpt-4o-mini (OpenAI)

This is a separate change (the course API key is an OpenAI key) and is not part of the reranker result above. It was measured on earlier interactive logs (49 requests, different questions), so treat it as indicative:

| | gpt-oss-120b | gpt-4o-mini |
|---|---|---|
| Generation p50 | 12,126 ms | about 1,200 ms |
| Cost per request | $0.00072 | $0.00055 |

The old model spent most of its time on hidden reasoning tokens.

## Other changes

| Change | Status | Effect |
|---|---|---|
| Warm-up of index and models at API startup | Done | Removed the 24 to 29 s first request after a restart |
| Answer cache (normalised question + filters + config fingerprint, 24 h TTL) | Implemented | A hit costs 0 tokens and a few ms. <<FILL: hit rate from real traffic, or the two-identical-requests demo>> |
| Skip the reranker when BM25 and vector agree | Implemented, off by default | <<FILL: skip rate and recall from `eval/skip_calibration.py`, or "not needed once the reranker was off">> |
| Smaller rerank pool (30 to 10) | <<FILL: from calibration, or not tried>> | |

## What did not help

- **The reranker itself:** it was the biggest cost and brought no recall gain on this corpus. It may help on harder, paraphrased queries, which our question set does not contain.
- **Cost reduction:** there was nothing to cut; the LLM call is the only billed item and is already small.
