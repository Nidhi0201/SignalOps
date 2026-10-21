# SignalOps RAG evaluation

Measures how accurate the `/logs/ask` RAG endpoint is relative to a direct
keyword-search baseline on a known-answer log corpus.

## Files

- `fixtures.py` — 189 synthetic logs across 5 hand-crafted incidents (payment
  gateway timeout cascade, auth brute-force, DB slow query + index fix, bad
  deploy + rollback, inventory failure) plus 80 benign filler logs so the
  retriever must actually search.
- `qa_dataset.json` — 30 questions with:
  - `must_mention`: substrings the answer MUST contain (case-insensitive) to
    count as correct. `must_mention_mode: "any"` accepts any of them.
  - `expected_citation_substrings`: snippets a cited log must contain for the
    citation to count.
- `run_eval.py` — ingests fixtures, calls `/logs/ask` (RAG) and `/logs/search`
  (baseline) per question, scores both, and writes a Markdown report.
- `results/` — JSON and Markdown reports from each run.

## What is measured

| metric | definition |
|---|---|
| answer accuracy | fraction of answers that include every `must_mention` fact |
| citation accuracy | fraction of answers whose citations include an expected log |
| unsupported-claim rate | fraction of answers that mention a fact without a citation that contains it (a hallucination proxy) |
| latency p50 / mean | response time of the endpoint, seconds |

The baseline column shows how `/logs/search` + top-10-message concatenation
performs on the same scoring rubric, so improvements over search-alone are
visible per question.

## Running

```bash
# 1. Bring the stack up
docker compose up -d           # postgres, redis, opensearch
cd backend && ./run.sh         # uvicorn on :8000

# 2. Vertex AI / Gemini auth so /logs/ask doesn't fall back
#    (one of these must work; see app/ai_service.py)
gcloud auth application-default login
#   OR
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json
export GCP_PROJECT_ID=your-project-id

# 3. Run the eval
cd backend
python -m eval_rag.run_eval                 # full 30-question run
python -m eval_rag.run_eval --limit 3       # smoke test
python -m eval_rag.run_eval --skip-ingest   # reuse already-ingested fixtures
```

Reports land in `eval_rag/results/rag_eval_YYYYMMDD_HHMMSS.{json,md}`.

## Notes on scoring

- Scoring is substring-match on the model's answer string, not an LLM judge.
  This under-counts correct answers that paraphrase (e.g. "half of a minute"
  instead of "30 seconds"). That is intentional for v1 — a cheap-and-explainable
  rubric is easier to defend than an LLM judge, and failures can be re-read by
  eye in the Markdown report.
- Citation accuracy requires at least ONE cited log to contain an expected
  snippet, not all of them. The log corpus is deliberately small so top-k
  retrieval returning more than one correct log is realistic.
- `has_unsupported_claim` is a proxy: it fires when the answer states a fact
  (per `must_mention`) that no cited log's message contains. It is a lower
  bound on hallucinations (an answer can hallucinate things that aren't in
  `must_mention`); failing cases should still be read manually.

## Interpreting the baseline

The direct-search baseline concatenates the top-10 message strings into one
answer. That means its "accuracy" is inflated whenever the required substring
appears in any returned log — it is the right lower bound to compare against.
If RAG does not beat this on any question, retrieval is the bottleneck, not
generation.
