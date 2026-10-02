"""Benchmark Document.get_relevant_sections: bi-encoder vs. laya reranker.

Scout's ``get_relevant_sections`` delegates ranking to domdistill. This script
exercises both ranking paths on a static HTML page (no browser needed) and
reports how many chunks each returns and the per-query latency, so the laya
reranker option can be compared against the default sentence-transformers
bi-encoder. It runs in CI on a CPU runner (see .github/workflows/laya-bench.yml).

Usage:
    python benchmarks/bench_relevant_sections.py --engines embedding,laya \
        --markdown-out bench_relevant.md
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from scout.core import Document

SAMPLE_HTML = """
<html><body>
  <h2>HTTP Server Security</h2>
  <p>Always terminate TLS at the edge and enable HSTS so browsers refuse plain
     HTTP. Rotate certificates automatically and disable legacy ciphers.</p>
  <p>Set security headers like Content-Security-Policy and X-Frame-Options to
     reduce the attack surface of the server.</p>

  <h2>Database Indexing</h2>
  <p>A B-tree index speeds up range queries but slows down writes because every
     insert must update the index pages.</p>
  <p>Composite indexes should list the most selective column first to maximise
     prefix matching.</p>

  <h2>Caching Strategies</h2>
  <p>Use a CDN for static assets and an in-memory cache such as Redis for hot
     keys. Pick a sensible TTL and invalidate on write.</p>
  <p>Cache stampedes can be avoided with request coalescing or a short lock.</p>
</body></html>
"""

QUERIES = [
    "how do I secure an http server with tls",
    "speed up database range queries",
    "reduce load with caching",
]


def _make_document(html: str) -> Document:
    return Document(
        url="https://example.test/benchmark",
        html=html,
        metadata={},
        markdown=None,
        screenshots=[],
        requests=[],
        response=[],
    )


def run_engine(engine: str, html: str, queries: list[str]) -> dict:
    use_laya = engine == "laya"
    if engine not in {"embedding", "laya"}:
        raise ValueError(f"unknown engine: {engine!r}")

    document = _make_document(html)

    # Warm up (model load / first call) outside the timed loop.
    warmup_started = time.perf_counter()
    document.get_relevant_sections(queries[0], top_k=5, use_laya=use_laya)
    warmup_ms = (time.perf_counter() - warmup_started) * 1000.0

    per_query: list[dict] = []
    latencies_ms: list[float] = []
    for query in queries:
        started = time.perf_counter()
        chunks = document.get_relevant_sections(query, top_k=5, use_laya=use_laya)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        latencies_ms.append(elapsed_ms)
        per_query.append(
            {
                "query": query,
                "num_chunks": len(chunks),
                "latency_ms": elapsed_ms,
                "top_chunk": chunks[0][:120] if chunks else None,
            }
        )

    return {
        "engine": engine,
        "queries": len(queries),
        "warmup_ms": warmup_ms,
        "latency_ms_avg": statistics.fmean(latencies_ms) if latencies_ms else 0.0,
        "latency_ms_max": max(latencies_ms) if latencies_ms else 0.0,
        "per_query": per_query,
    }


def _markdown_table(reports: list[dict]) -> str:
    header = (
        "| Engine | Queries | Avg latency (ms) | Max latency (ms) | Warmup (ms) |\n"
        "|---|---|---|---|---|"
    )
    rows = [
        "| {engine} | {queries} | {latency_ms_avg:.1f} | {latency_ms_max:.1f} | "
        "{warmup_ms:.0f} |".format(**report)
        for report in reports
    ]
    return "\n".join([header, *rows])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare get_relevant_sections ranking engines."
    )
    parser.add_argument("--engines", type=str, default="embedding,laya")
    parser.add_argument("--html-file", type=Path, default=None)
    parser.add_argument("--markdown-out", type=Path, default=None)
    args = parser.parse_args()

    html = (
        args.html_file.read_text(encoding="utf-8")
        if args.html_file is not None
        else SAMPLE_HTML
    )
    engines = [item.strip() for item in args.engines.split(",") if item.strip()]
    reports = [run_engine(engine, html, QUERIES) for engine in engines]

    table = _markdown_table(reports)
    print(table)
    print()
    print(json.dumps({"reports": reports}, indent=2))

    if args.markdown_out is not None:
        args.markdown_out.write_text(table + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
