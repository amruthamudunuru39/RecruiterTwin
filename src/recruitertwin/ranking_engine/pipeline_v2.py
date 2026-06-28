"""End-to-end ranking pipeline.

Two-stage architecture chosen for the 5-min / 16 GB / CPU-only budget:

Stage 1 (recall): single streaming pass over candidates.jsonl computes the
  cheap evidence/career/behavioral score for all 100K candidates and keeps
  the top-K (default 1500) shortlist plus their raw text.
Stage 2 (precision): TF-IDF cosine similarity between the JD query and the
  shortlist's narrative text refines ordering, then reasoning strings are
  generated for the final top 100.

No network calls, no GPU, no hosted LLMs.
"""

from __future__ import annotations

import csv
import gzip
import heapq
import json
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from recruitertwin.job_intelligence.jd_profile import JD_QUERY_TEXT
from recruitertwin.ranking_engine import scorer_v2
from recruitertwin.ranking_engine.reasoning import build_reasoning


def iter_candidates(path: str | Path) -> Iterator[dict[str, Any]]:
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def rank_candidates(
    candidates_path: str | Path,
    top_n: int = 100,
    shortlist_size: int = 1500,
    verbose: bool = True,
) -> list[dict[str, Any]]:
    """Rank candidates from a JSONL/JSON-array file path (CLI entry point).

    Thin wrapper around :func:`rank_from_iter` that streams the file from disk.
    """
    rows, _stats = rank_from_iter(
        iter_candidates(candidates_path),
        top_n=top_n,
        shortlist_size=shortlist_size,
        verbose=verbose,
    )
    return rows


def rank_from_iter(
    candidates: Iterable[dict[str, Any]],
    top_n: int = 100,
    shortlist_size: int = 1500,
    progress_cb: Callable[[int, int, int], None] | None = None,
    stage2_cb: Callable[[int], None] | None = None,
    verbose: bool = True,
    honeypot_sample_cap: int = 50,
    progress_every: int = 500,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Two-stage ranking over an arbitrary candidate iterator.

    Stage 1 streams every candidate once and keeps only the top ``shortlist_size``
    in a bounded heap, so peak memory stays ~O(shortlist_size) regardless of how
    many candidates flow through (a 500 MB JSONL upload never lands in RAM whole).

    ``progress_cb(scanned, honeypots, shortlist_len)`` is invoked every
    ``progress_every`` records during Stage 1 (and once at the end) so callers
    such as the Streamlit UI can render a live progress bar. ``stage2_cb(n_docs)``
    is forwarded to the embedding step. Returns ``(rows, stats)``.
    """
    t0 = time.time()
    from recruitertwin.ranking_engine.features import candidate_texts

    # ---- Stage 1: streaming evidence scoring over the full pool ----------
    heap: list[tuple[float, str, dict, str]] = []  # (score, cid, result, text)
    n = 0
    honeypots = 0
    honeypot_sample: list[dict[str, Any]] = []
    for cand in candidates:
        n += 1
        res = scorer_v2.score_candidate(cand)
        if res["honeypot"]:
            honeypots += 1
            if len(honeypot_sample) < honeypot_sample_cap:
                honeypot_sample.append({
                    "candidate_id": res["candidate_id"],
                    "title": res["title"],
                    "flags": "; ".join(res["penalties"]),
                })
        elif res["final_score"] > 0:
            text, _ = candidate_texts(cand)
            item = (res["final_score"], res["candidate_id"], res, text)
            if len(heap) < shortlist_size:
                heapq.heappush(heap, item)
            elif item[0] > heap[0][0]:
                heapq.heapreplace(heap, item)
        if progress_cb and n % progress_every == 0:
            progress_cb(n, honeypots, len(heap))
        if verbose and n % 20000 == 0:
            print(f"  scanned {n} candidates ({time.time() - t0:.1f}s)")

    if progress_cb:
        progress_cb(n, honeypots, len(heap))

    shortlist = sorted(heap, key=lambda x: (-x[0], x[1]))
    stats: dict[str, Any] = {
        "scanned": n,
        "honeypots": honeypots,
        "shortlist": len(shortlist),
        "honeypot_sample": honeypot_sample,
        "stage1_seconds": round(time.time() - t0, 2),
    }
    if verbose:
        print(f"Stage 1 done: {n} scanned, shortlist {len(shortlist)} "
              f"({time.time() - t0:.1f}s)")

    if not shortlist:
        stats["seconds"] = round(time.time() - t0, 2)
        return [], stats

    # ---- Stage 2: BM25 + TF-IDF hybrid re-ranking over the shortlist ------
    # BM25 (Okapi) brings term saturation and document-length normalization
    # that plain TF-IDF lacks — short and long profiles are compared fairly.
    # TF-IDF cosine with 1-2 grams adds phrase-level matching ("hybrid
    # search", "learning to rank"). The two lexical views are min-max
    # normalized and blended.
    import re as _re

    from rank_bm25 import BM25Okapi
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    token_re = _re.compile(r"[a-z0-9][a-z0-9+#./-]*")
    texts = [item[3] for item in shortlist]
    jd_text = JD_QUERY_TEXT.lower()

    bm25 = BM25Okapi([token_re.findall(t) for t in texts])
    bm25_raw = bm25.get_scores(token_re.findall(jd_text))
    lo, hi = float(min(bm25_raw)), float(max(bm25_raw))
    bm25_norm = [(s - lo) / (hi - lo) if hi > lo else 0.0 for s in bm25_raw]

    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=60000,
                          sublinear_tf=True)
    X = vec.fit_transform(texts + [jd_text])
    tfidf_sims = cosine_similarity(X[-1], X[:-1]).ravel()

    # Optional dense layer: semantic similarity via local MiniLM. Catches
    # plain-language strong candidates that lexical matching misses.
    from recruitertwin.ranking_engine.embedder import semantic_similarities
    emb = semantic_similarities(texts, jd_text, progress_cb=stage2_cb)
    if emb is None and verbose:
        print("  [info] embedding model not found — using BM25+TF-IDF only "
              "(run scripts/download_model.py to enable the dense layer)")

    refined = []
    for i, ((base_score, cid, res, _), bm, sim) in enumerate(
            zip(shortlist, bm25_norm, tfidf_sims)):
        tf = max(0.0, min(float(sim) * 2.5, 1.0))
        if emb is not None:
            lexical = 0.50 * emb[i] + 0.30 * bm + 0.20 * tf
            weight = 0.20
        else:
            lexical = 0.6 * bm + 0.4 * tf
            weight = 0.16
        boosted = base_score + weight * lexical * _avail(res)
        res = dict(res)
        res["bm25_score"] = round(float(bm), 4)
        res["tfidf_sim"] = round(float(sim), 4)
        if emb is not None:
            res["embedding_sim"] = round(emb[i], 4)
        res["final_score"] = round(boosted, 6)
        refined.append(res)

    refined.sort(key=lambda r: (-r["final_score"], r["candidate_id"]))
    top = refined[:top_n]
    if verbose:
        print(f"Stage 2 done: re-ranked {len(refined)} ({time.time() - t0:.1f}s)")

    # ---- reasoning + final shape ------------------------------------------
    out = []
    for i, r in enumerate(top, start=1):
        out.append({
            "candidate_id": r["candidate_id"],
            "rank": i,
            "score": r["final_score"],
            "reasoning": build_reasoning(r, i),
            "_debug": r,
        })
    if verbose:
        print(f"Pipeline complete in {time.time() - t0:.1f}s")
    stats["stage2_seconds"] = round(time.time() - t0 - stats["stage1_seconds"], 2)
    stats["seconds"] = round(time.time() - t0, 2)
    return out, stats


def _avail(res: dict[str, Any]) -> float:
    """Approximate availability multiplier already applied to base score."""
    b = res["behavior"]
    m = 1.0
    d = b.get("days_inactive", 0)
    if d > 180:
        m *= 0.55
    elif d > 90:
        m *= 0.72
    return m


def write_submission(rows: list[dict[str, Any]], out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Enforce non-increasing scores with unique ranks (spec section 3).
    prev = None
    for row in rows:
        if prev is not None and row["score"] > prev:
            row["score"] = prev
        prev = row["score"]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["candidate_id", "rank", "score", "reasoning"])
        for row in rows:
            w.writerow([row["candidate_id"], row["rank"],
                        f"{row['score']:.6f}", row["reasoning"]])
