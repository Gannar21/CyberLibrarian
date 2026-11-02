# Cost model (data/requests_p4_v2.jsonl)
Requests: 36 | answered by the LLM: 36 | cache hits: 0 | free (small talk / don't know): 0

Latency, LLM-answered requests: retrieval p50 90 / p95 123 ms | generation p50 1205 / p95 1813 ms | total p50 1283 / p95 1907 ms
Latency, all requests: total p50 1283 / p95 1907 ms

Per LLM request: 3701 tokens, $0.00058
Per request, all traffic (includes free ones): $0.00058

| Scale | Requests/month | LLM $/month | Hosting $/month | Total $/month |
|---|---|---|---|---|
| Today (50 users x 5/day) | 7,500 | 4.37 | 0.00 | 4.37 |
| 100x | 750,000 | 436.94 | 0.00 | 436.94 |

Assumptions: reranker and embeddings run locally ($0 per request); the LLM is billed per token at the
prices in config.py; the traffic mix and cache hit rate stay the same at 100x (conservative: the
hit rate should rise). At 100x, API rate limits matter more than the bill: check your tier.

