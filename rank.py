#!/usr/bin/env python3
"""Produce the Redrob hackathon submission CSV.

Usage (the single reproduction command per submission spec §10.3):

    python rank.py --candidates ./candidates.jsonl --out ./submission.csv

Accepts .jsonl or .jsonl.gz. CPU-only, no network, designed to finish a
100K-candidate pool in well under the 5-minute budget on a laptop.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from recruitertwin.ranking_engine.pipeline_v2 import rank_candidates, write_submission


def main() -> int:
    ap = argparse.ArgumentParser(description="Redrob candidate ranker (RecruiterTwin-AI)")
    ap.add_argument("--candidates", required=True, help="Path to candidates.jsonl(.gz)")
    ap.add_argument("--out", required=True, help="Output submission CSV path")
    ap.add_argument("--top", type=int, default=100, help="Rows to emit (default 100)")
    ap.add_argument("--shortlist", type=int, default=1500,
                    help="Stage-1 shortlist size before TF-IDF re-rank")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    rows = rank_candidates(args.candidates, top_n=args.top,
                           shortlist_size=args.shortlist, verbose=not args.quiet)
    write_submission(rows, args.out)
    print(f"Wrote {len(rows)} ranked rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
