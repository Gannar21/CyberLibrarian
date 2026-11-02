# Person 3: cost model (section for the report)

Source: `eval/cost_model.py` on `data/requests_before.jsonl` and `data/requests_after.jsonl` (40 requests each, `gpt-4o-mini`).

## Per request

| | Value |
|---|---|
| Input / output tokens | about 3,400 / 270 (about 3,450 total) |
| LLM price | $0.15 per million input tokens, $0.60 per million output tokens (verify against OpenAI's pricing page) |
| **Cost per answered request** | **$0.00055** |
| Embeddings, BM25, reranker | $0 per request (run locally on the server) |
| Small talk, "I don't know", cache hits | $0 (no LLM call) |

About 3,000 of the 3,400 input tokens are the retrieved chunks and the system prompt, so fewer or shorter chunks is the main lever if cost ever matters.

## Monthly projection

Assumption (not measured): 50 users, 5 requests per user per day, 30 days = 7,500 requests per month. <<FILL: replace with the real numbers from the user tests collected by P1>>

| Scale | Requests / month | LLM cost / month | Hosting / month | Total / month |
|---|---|---|---|---|
| Today | 7,500 | $4.1 | <<FILL: host price>> | |
| 100x | 750,000 | $410 | <<FILL>> | |

Assumptions: the same mix of questions at 100x (conservative, because the answer cache hit rate should rise with volume); the price per token stays constant.

## What breaks first at 100x

- **API rate limits**, not the bill: 750,000 requests a month is about 25,000 a day, so check the tokens-per-minute limit of the provider tier.
- **A single server process:** the in-memory answer cache and the rate limiter assume one worker. More traffic needs a shared cache (for example Redis) and more than one instance.
- **Memory:** the embedding model, BM25 index and Chroma need about 2 GB RAM per instance (more with the reranker, which is why it is off).
