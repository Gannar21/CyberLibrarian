# Person 4: generation, cost model, optimisation, postmortem

## 1. Generation results

LLM: gpt-4o-mini (OpenAI). Evaluation: `eval/generation_eval.py` runs all P4 questions plus a spread sample of dev questions (36 questions: 31 answerable, 5 unanswerable) with the answer cache off. Faithfulness, citation accuracy and correctness are judged 0/1 by an LLM.

| metric | v1 prompt | v2 prompt (marker per sentence) |
|---|---|---|
| correct refusals (unanswerable) | 1.00 | 1.00 |
| false refusal rate | 0.129 | 0.129 |
| faithfulness | 0.815 | 0.815 |
| citation accuracy | 0.667 | 0.778 |
| correctness | 0.741 | 0.741 |

Requiring a [n] marker at the end of every sentence raised citation accuracy by 11 points without making the model answer unanswerable questions.

Known limitations:
- The judge is the same model as the generator, so faithfulness is probably optimistic.
- Correctness compares against a short reference answer, so correct but more detailed answers are sometimes marked wrong.
- With 31 answerable questions, one question moves a metric by about 3 points; differences of that size are noise.

## 2. Known failure cases

- Exact technique IDs (e.g. T1486) are not retrieved: similar MITRE pages outrank the right one, so the model correctly refuses. This is a retrieval problem, not a prompt problem (the prompt change did not move the false refusal rate).
- The right chunk sometimes ranks below several NIST incident-response pages (rank 4 of 5), so the answer is refused or incomplete.
- The model sometimes mixes facts from different chunks (e.g. listing "Least Privilege" as a primary SQL injection defense) and sometimes cites a chunk that does not support the claim.

## 3. Cost model (36 real requests, gpt-4o-mini, 5 chunks)

| item | value |
|---|---|
| tokens per request | about 3,700 (about 97% input) |
| cost per request | $0.00058 |
| latency p50 / p95 | 1.28 s / 1.91 s (generation is about 94% of it) |
| today: 50 users x 5 requests/day = 7,500/month | about $4.37/month |
| 100x: 750,000 requests/month | about $437/month |

With 3 chunks ($0.000379 per request): about $2.84/month today, about $284/month at 100x.
Assumptions: traffic of 50 users x 5 requests per day is a guess; hosting is $0; no cache hits; embeddings and reranker run locally. At 100x, API rate limits matter more than the bill.

## 4. Optimisation (Week 8)

Baseline: gpt-4o-mini, 5 chunks, prompt v2. Same 36-question set for every row.

| setting | cost / question | false refusal | faithfulness | citation | correctness |
|---|---|---|---|---|---|
| baseline (5 chunks) | $0.000583 | 0.129 | 0.815 | 0.778 | 0.741 |
| 3 chunks | $0.000379 (-35%) | 0.161 | 0.885 | 0.769 | 0.808 |
| 3 chunks + gpt-4.1-mini | $0.001029 | 0.125 | 0.429 | 0.357 | 0.500 |

- Sending 3 chunks instead of 5 cut cost by 35% with no measurable accuracy loss (citation -0.9 pt; the other metrics moved by one question or less, within noise). This is below the 50% target.
- gpt-4.1-mini was rejected: higher cost per question and much lower faithfulness, citation accuracy and correctness (37 questions, prices 0.40/1.60 per million tokens).
- gpt-4.1-nano is deprecated and not available on our key. Other small models (gpt-5.4-nano, gpt-5-nano) were not tested.
- p95 latency was not reduced: generation time barely depends on input size.
- Prompt caching was not tested. Our prompt starts with a short fixed rules block followed by sources that change with every question, so there is little repeated prefix to cache.
- Answer caching (a teammate's work) makes repeated questions free but does not apply to this eval, which runs with the cache off.

## 5. Postmortem (P4)

- Python 3.14 has no torch build, so `pip install -r requirements.txt` failed. Fix: Python 3.12.
- On Python 3.12, numpy 2 and a too-new transformers broke sentence-transformers. Fix: numpy<2, transformers<4.50, sentence-transformers<4.
- The UI sent `year_min`/`year_max` but the retriever only understood `year`, so every chunk was filtered out (0 chunks, "I don't know" for every question). Fix: `normalize_filters()` in `answer.py`.
- Our first API key turned out to be an OpenAI key, not Anthropic, and the default model name did not exist there. Fix: `LLM_MODEL=gpt-4o-mini`.
- A duplicated `LLM_MODEL=LLM_MODEL=...` line in `.env` and a `PUT_REAL_PRICE` placeholder wasted two eval runs; `gpt-4.1-nano` was deprecated and wasted four more.
- The cost-model script read different log field names than `answer()` writes and would have reported zero tokens. Fix: `norm()` accepts both.
- A first top-3 run changed nothing because `RERANK_TOP_N` was never saved to `.env`; the identical cost per question gave it away.
- Lesson: check that a setting is really applied before reading the result, and keep each change in its own eval run.