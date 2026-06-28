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
from typing import Any, Iterator

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
    t0 = time.time()

    # ---- Stage 1: streaming evidence scoring over the full pool ----------
    heap: list[tuple[float, str, dict, str]] = []  # (score, cid, result, text)
    n = 0
    for cand in iter_candidates(candidates_path):
        n += 1
        res = scorer_v2.score_candidate(cand)
        if res["honeypot"] or res["final_score"] <= 0:
            continue
        from recruitertwin.ranking_engine.features import candidate_texts
        text, _ = candidate_texts(cand)
        item = (res["final_score"], res["candidate_id"], res, text)
        if len(heap) < shortlist_size:
            heapq.heappush(heap, item)
        elif item[0] > heap[0][0]:
            heapq.heapreplace(heap, item)
        if verbose and n % 20000 == 0:
            print(f"  scanned {n} candidates ({time.time() - t0:.1f}s)")

    shortlist = sorted(heap, key=lambda x: (-x[0], x[1]))
    if verbose:
        print(f"Stage 1 done: {n} scanned, shortlist {len(shortlist)} "
              f"({time.time() - t0:.1f}s)")

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
    emb = semantic_similarities(texts, jd_text)
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
    return out


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
