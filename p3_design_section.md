# Person 3: retrieval design (section for design.md)

## Pipeline (src/retrieval/retriever.py)

1. **Optional query rewrite.** An LLM turns the question into 1 to 3 standalone search queries (acronyms expanded, multi-part questions split). Off by default.
2. **Two searches.** BM25 (`rank-bm25`, lower-cased `\w+` tokens, so IDs like `T1486` match) and vector search (`all-MiniLM-L6-v2` embeddings in Chroma). Each returns the top 50 chunks (200 when a metadata filter is set, so filters do not starve the results).
3. **Reciprocal Rank Fusion.** `score(d) = sum over lists of 1 / (60 + rank)`. RRF needs no score normalisation, which matters because BM25 scores and cosine similarities live on different scales.
4. **Metadata filters** on `source` and `year`, applied after fusion.
5. **Pinning.** Up to 3 chunks of a document named in the query are forced into the results: MITRE technique IDs (`T1486`, `T1059.001`) and OWASP cheat sheet titles ("Authentication Cheat Sheet").
6. **Optional cross-encoder reranker** (`cross-encoder/ms-marco-MiniLM-L-6-v2`, top 30 reranked to 5). **Off by default** (see the ablation below).
7. **Optional skip-when-confident rule:** skip the reranker if the top fused chunk is within the top N of both the BM25 and the vector list. Off by default.

`retrieve(query, k, filters, mode, rerank, rewrite, ..., info)` keeps the contract from `schemas.py`; the optional `info` dict returns what happened (reranked, skipped) for logging.

## Choices

| Decision | Choice | Why / status |
|---|---|---|
| Fusion | RRF, k0 = 60 | Standard default; **not tuned** |
| Candidate pool | 50 per search | **Not tuned** |
| Reranker | Off | Measured: no recall gain, about 10 s per request (below) |
| Pinning | On | **Not ablated.** <<FILL: run with `PIN_NAMED=false` and add the row, or state it was not measured>> |

## Evaluation setup

73 answerable questions from `questions_p1..p3.jsonl` (unanswerable ones removed). A retrieved chunk counts as relevant if it contains at least 60% of the gold passage's tokens. Metrics: recall@k, MRR, and latency of the search step only (not the LLM). One question is worth 1.4 points of recall, so differences of one or two questions are noise.

## Retrieval results and ablation

| config | n | recall@1 | recall@3 | recall@5 | recall@10 | MRR | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|
| keyword only | 73 | 0.904 | 0.973 | 0.986 | 0.986 | 0.935 | 12.3 | 21.3 |
| vector only | 73 | 0.685 | 0.836 | 0.932 | 0.973 | 0.775 | 32.3 | 51.6 |
| hybrid (RRF) | 73 | 0.877 | 0.973 | 0.986 | 1.000 | 0.923 | 39.5 | 56.5 |
| hybrid + reranker | 73 | 0.877 | 0.973 | 0.986 | 1.000 | 0.928 | 9,813 | 15,232 |
| hybrid + rewrite | <<FILL>> | | | | | | | |

What the table shows:

- **The reranker added nothing measurable**: recall is identical at every k and MRR differs by 0.005 (about one question), while search latency rose from 40 ms to 9.8 s at p50 and from 57 ms to 15 s at p95 on a MacBook Air CPU.
- **Keyword search is as good as hybrid at k=5** and better at k=1 (0.904 vs 0.877). Hybrid's only visible gain is recall@10 (1.000 vs 0.986, one question).
- **Vector search alone is the weakest** (recall@1 0.685).
- **Caution:** the questions were written from the source passages, so they share vocabulary with the documents. That favours keyword search, and recall is close to its ceiling, so this set cannot separate the methods well. <<FILL: if paraphrased questions were added, add their results here>>

## Known failure cases

Hybrid retrieval missed none of the 73 questions at k=10, so there are no observed failures to categorise. These are risks we know about but did not measure:

- **Tables, code blocks, cross-references:** chunking splits them; no eval question tests them.
- **Year filter and undated documents:** documents without a date never match a year filter (`filters.py`), so they disappear when the user picks a year.
- **Pinning can crowd out better chunks:** up to 3 of the 5 results can be pinned.
- **Reranker input is truncated** to 2,000 characters per chunk.
- **Vague or multi-part questions:** query rewriting is the intended fix. <<FILL: result of the rewrite row above>>
- **Cold start:** before the warm-up at API startup, the first request after a restart took 24 to 29 s (model loading).
