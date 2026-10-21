"""
RAG evaluation harness for Ask My Logs (/logs/ask).

Pipeline:
  1. Delete/recreate the fixture logs via /logs/ingest.
  2. For every question in qa_dataset.json:
       - call /logs/ask (RAG + Gemini)
       - call /logs/search as a non-RAG baseline (same question text as `q`)
     Time each call. Score correctness (`must_mention` substring match),
     citation accuracy (did a cited log's message contain any
     `expected_citation_substrings`), and unsupported-claim rate (did the
     model mention a `must_mention` fact without a citation that supports it).
  3. Write both JSON and a Markdown report under eval_rag/results/.

Prerequisites to RUN this harness (not needed to read it):
  - SignalOps backend reachable at $SIGNALOPS_URL (default http://localhost:8000)
  - OpenSearch, Postgres, Redis up (docker-compose up)
  - Vertex AI / Gemini credentials configured so /logs/ask works
    (otherwise it falls back and the eval still runs but the "RAG" column is
    just the fallback summary)

Usage:
  cd backend
  python -m eval_rag.run_eval                 # full run
  python -m eval_rag.run_eval --limit 3       # smoke-test on 3 questions
  python -m eval_rag.run_eval --skip-ingest   # reuse already-ingested fixtures
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any

import httpx

from .fixtures import ALL_LOGS

EVAL_DIR = Path(__file__).parent
QA_PATH = EVAL_DIR / "qa_dataset.json"
RESULTS_DIR = EVAL_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

BASE_URL = os.getenv("SIGNALOPS_URL", "http://localhost:8000")


def ingest_fixtures(client: httpx.Client) -> int:
    """POST every fixture log to /logs/ingest. Returns the count ingested."""
    n = 0
    for log in ALL_LOGS:
        r = client.post(f"{BASE_URL}/logs/ingest", json=log, timeout=10.0)
        r.raise_for_status()
        n += 1
    # Give OpenSearch a moment to make them visible.
    time.sleep(2)
    return n


def _substrs_in(text: str, needles: list[str], mode: str = "all") -> bool:
    t = text.lower()
    found = [n.lower() in t for n in needles]
    return all(found) if mode == "all" else any(found)


def _citation_hits(citations: list[dict[str, Any]], expected: list[str]) -> int:
    """How many citations contain any expected substring in their message."""
    if not expected:
        return 0
    hits = 0
    for c in citations:
        msg = (c.get("message") or c.get("text") or "").lower()
        if any(e.lower() in msg for e in expected):
            hits += 1
    return hits


def run_rag(client: httpx.Client, question: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    r = client.post(f"{BASE_URL}/logs/ask", json={"question": question, "limit": 50}, timeout=60.0)
    dt = time.perf_counter() - t0
    r.raise_for_status()
    data = r.json()
    return {
        "answer": data.get("answer", ""),
        "citations": data.get("citations", []),
        "log_count": data.get("log_count", 0),
        "latency_s": dt,
    }


def run_baseline(client: httpx.Client, question: str) -> dict[str, Any]:
    """Baseline: direct keyword search on /logs/search, then synthesize an
    answer by concatenating the top-10 messages. No LLM involved."""
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/logs/search", params={"q": question}, timeout=30.0)
    dt = time.perf_counter() - t0
    r.raise_for_status()
    hits = r.json()[:10]
    answer = " | ".join(h.get("message", "") for h in hits)
    citations = [{"message": h.get("message", ""), "service": h.get("service"),
                  "level": h.get("level"), "id": h.get("id")} for h in hits]
    return {"answer": answer, "citations": citations, "log_count": len(hits), "latency_s": dt}


def score(result: dict[str, Any], q: dict[str, Any]) -> dict[str, Any]:
    needles = q.get("must_mention", [])
    mode = q.get("must_mention_mode", "all")
    correct = _substrs_in(result["answer"], needles, mode=mode)
    cit_hits = _citation_hits(result["citations"], q.get("expected_citation_substrings", []))
    cit_ok = cit_hits > 0 if q.get("expected_citation_substrings") else True
    # Unsupported-claim proxy: answer mentions a must_mention fact but no
    # citation message contains it.
    unsupported = False
    for n in needles:
        if n.lower() in result["answer"].lower():
            backed = any(n.lower() in (c.get("message", "") or "").lower()
                         for c in result["citations"])
            if not backed:
                unsupported = True
                break
    return {
        "correct": correct,
        "citation_hit_count": cit_hits,
        "citation_ok": cit_ok,
        "has_unsupported_claim": unsupported,
    }


def evaluate(limit: int | None = None, skip_ingest: bool = False) -> dict[str, Any]:
    qa = json.loads(QA_PATH.read_text())["questions"]
    if limit:
        qa = qa[:limit]
    out: dict[str, Any] = {"base_url": BASE_URL, "n": len(qa), "runs": []}
    with httpx.Client() as client:
        if not skip_ingest:
            out["ingested"] = ingest_fixtures(client)
        for q in qa:
            rag = run_rag(client, q["question"])
            base = run_baseline(client, q["question"])
            out["runs"].append({
                "id": q["id"], "incident": q.get("incident"), "difficulty": q.get("difficulty"),
                "question": q["question"],
                "rag": {**rag, "score": score(rag, q)},
                "baseline": {**base, "score": score(base, q)},
            })
    out["summary"] = summarize(out["runs"])
    return out


def _rate(hits: int, total: int) -> float:
    return (hits / total) if total else 0.0


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    s: dict[str, Any] = {}
    for name in ("rag", "baseline"):
        correct = sum(1 for r in runs if r[name]["score"]["correct"])
        cit_ok = sum(1 for r in runs if r[name]["score"]["citation_ok"])
        unsupported = sum(1 for r in runs if r[name]["score"]["has_unsupported_claim"])
        latencies = [r[name]["latency_s"] for r in runs]
        s[name] = {
            "n": len(runs),
            "correct": correct,
            "accuracy": _rate(correct, len(runs)),
            "citation_accuracy": _rate(cit_ok, len(runs)),
            "unsupported_claim_rate": _rate(unsupported, len(runs)),
            "latency_p50_s": statistics.median(latencies) if latencies else 0.0,
            "latency_mean_s": statistics.fmean(latencies) if latencies else 0.0,
        }
    return s


def write_markdown(result: dict[str, Any], out_path: Path) -> None:
    s = result["summary"]
    lines = [
        "# SignalOps RAG Evaluation",
        "",
        f"- Dataset: `eval_rag/qa_dataset.json` ({result['n']} questions)",
        f"- Fixture corpus: `eval_rag/fixtures.py` ({len(ALL_LOGS)} logs, 5 incidents + benign filler)",
        f"- Backend: `{result['base_url']}`",
        "",
        "## Summary",
        "",
        "| metric | RAG (Ask My Logs) | baseline (direct search) |",
        "|---|---|---|",
        f"| answer accuracy | {s['rag']['correct']}/{s['rag']['n']} ({s['rag']['accuracy']*100:.1f}%) | {s['baseline']['correct']}/{s['baseline']['n']} ({s['baseline']['accuracy']*100:.1f}%) |",
        f"| citation accuracy | {s['rag']['citation_accuracy']*100:.1f}% | {s['baseline']['citation_accuracy']*100:.1f}% |",
        f"| unsupported-claim rate | {s['rag']['unsupported_claim_rate']*100:.1f}% | {s['baseline']['unsupported_claim_rate']*100:.1f}% |",
        f"| latency p50 (s) | {s['rag']['latency_p50_s']:.2f} | {s['baseline']['latency_p50_s']:.2f} |",
        f"| latency mean (s) | {s['rag']['latency_mean_s']:.2f} | {s['baseline']['latency_mean_s']:.2f} |",
        "",
        "## Incorrect answers (RAG)",
        "",
    ]
    for r in result["runs"]:
        if not r["rag"]["score"]["correct"]:
            lines.append(f"- **{r['id']}** ({r['difficulty']}, incident {r['incident']}): {r['question']}")
            lines.append(f"  - got: {r['rag']['answer'][:240]}")
    lines.append("")
    lines.append("## Unsupported-claim examples (RAG)")
    lines.append("")
    for r in result["runs"]:
        if r["rag"]["score"]["has_unsupported_claim"]:
            lines.append(f"- **{r['id']}**: {r['question']}")
            lines.append(f"  - answer: {r['rag']['answer'][:240]}")
    out_path.write_text("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="run only the first N questions (smoke test)")
    ap.add_argument("--skip-ingest", action="store_true",
                    help="assume fixtures are already in the backend")
    ap.add_argument("--out", type=str, default=None, help="override results basename")
    args = ap.parse_args()

    result = evaluate(limit=args.limit, skip_ingest=args.skip_ingest)
    stem = args.out or time.strftime("rag_eval_%Y%m%d_%H%M%S")
    json_path = RESULTS_DIR / f"{stem}.json"
    md_path = RESULTS_DIR / f"{stem}.md"
    json_path.write_text(json.dumps(result, indent=2))
    write_markdown(result, md_path)
    s = result["summary"]
    print(f"\nwrote {json_path}\nwrote {md_path}\n")
    print(f"RAG accuracy:      {s['rag']['accuracy']*100:5.1f}%  "
          f"(baseline {s['baseline']['accuracy']*100:5.1f}%)")
    print(f"RAG citations ok:  {s['rag']['citation_accuracy']*100:5.1f}%  "
          f"(baseline {s['baseline']['citation_accuracy']*100:5.1f}%)")
    print(f"RAG unsupported:   {s['rag']['unsupported_claim_rate']*100:5.1f}%  "
          f"(baseline {s['baseline']['unsupported_claim_rate']*100:5.1f}%)")
    print(f"RAG latency p50:   {s['rag']['latency_p50_s']:.2f}s  "
          f"(baseline {s['baseline']['latency_p50_s']:.2f}s)")


if __name__ == "__main__":
    main()
