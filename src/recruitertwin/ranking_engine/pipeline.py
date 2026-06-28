"""Legacy hook — delegates to the v2 two-stage pipeline."""
from __future__ import annotations

from recruitertwin.ranking_engine.scorer_v2 import score_candidate


def shortlist_candidates(job_dna: dict, candidates: list[dict]) -> list[dict]:
    _ = job_dna
    scored = [score_candidate(c) for c in candidates]
    scored = [s for s in scored if not s["honeypot"]]
    scored.sort(key=lambda s: (-s["final_score"], s["candidate_id"]))
    return scored
