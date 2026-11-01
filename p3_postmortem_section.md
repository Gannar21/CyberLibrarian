# Person 3: postmortem (section for postmortem.md)

## What went wrong

**1. BM25 did not match technique IDs.**
The first tokenizer split `T1486` into pieces, so searching for a MITRE technique by its ID failed. We found it while testing named-technique questions and fixed it by tokenizing on word characters (`\w+`).
*Lesson:* test the tokenizer on the exact strings users type (IDs, acronyms), not only on prose.

**2. Query rewriting silently did nothing.**
`rewrite.py` called the Anthropic client while the project used Groq. Every call failed, a bare `except Exception` swallowed the error, and the function returned the original query, so any ablation with rewriting enabled measured nothing. We only noticed when reviewing the code for Week 8.
*Lesson:* never swallow exceptions without logging them. It now logs a warning on failure. The LLM client also changed again (OpenAI), so the helper reads the provider from config.

**2b. A stub file that crashed on import.**
`hybrid.py` was still the skeleton from the team plan and raised `NotImplementedError` on import, while the real logic lived in `retriever.py`. It is now a thin wrapper.

**3. We kept a reranker that cost about 10 seconds and gained nothing.**
The project brief lists "hybrid + reranker" as the expected design, so we built it first and measured it late. The ablation showed identical recall at every k and 250 times the latency (40 ms to 9.8 s at p50). We turned it off by default and report it honestly in the ablation.
*Lesson:* measure each component as soon as it exists. A component is only justified by a number.

**4. The eval set is too easy and biased toward keyword search.**
Questions were written by copying phrases from passages, so BM25 matched hybrid or beat it and recall is near 100%. The table cannot show what vector search adds on paraphrased questions.
*Lesson:* write some questions without looking at the passage, and report which kind each question is.

**5. Configuration mistakes.**
- `requirements.txt` ended with `rank-bm25groq` (two packages glued together by a missing newline), which would have broken a clean install.
- Two `.env` lines were glued (`USE_MOCK=falseLLM_MAX_TOKENS=2000`), so `USE_MOCK` stayed true and the UI could have been showing mock answers.
- Stale tests still expected `NotImplementedError` after the functions were implemented.
*Lesson:* run the clean-clone test early and often; a linter or `pip install -r` in CI would have caught the first one.

**6. Model and key switch late in the project.**
We built against Groq (`gpt-oss-120b`) and later had to switch to the course's OpenAI key. The switch touched four files owned by other teammates and invalidated the generation results measured earlier, so the before/after numbers had to be re-collected on one model. In addition, a shared API key was pasted into a third-party chat while asking for help and had to be treated as leaked and revoked.
*Lesson:* agree the provider on day one, keep keys only in `.env` and host settings, and never paste them anywhere.

**7. Coordination and git.**
Two people built an answer cache at the same time (P2 and P3). A commit landed on a teammate's branch by mistake, and a cherry-pick onto the updated `main` conflicted with files other people had changed in the meantime. Nothing was lost, but it cost time.
*Lesson:* announce what you are building before starting, create your own branch before the first commit, and read `git status` before every push.

## What we would do differently

- Measure the reranker and the answer cache in Week 5 and 6, not in Week 8.
- Build the paraphrased half of the eval set before tuning anything.
- Log latency per stage from the first working version, so the 10-second reranker would have shown up immediately.
