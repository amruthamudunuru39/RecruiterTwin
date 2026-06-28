"""Legacy hook — delegates to the v2 evidence-based scorer."""
from __future__ import annotations

from recruitertwin.ranking_engine.scorer_v2 import score_candidate as _score


def score_candidate(job_dna: dict, candidate: dict) -> dict:
    _ = job_dna  # JD knowledge lives in job_intelligence.jd_profile
    res = _score(candidate)
    return {
        "candidate_id": res["candidate_id"],
        "final_score": res["final_score"],
        "rank": None,
        "key_factors": [k for k, v in res["must_hits"].items() if v > 0],
        "risk_flags": res["penalties"] + (["honeypot"] if res["honeypot"] else []),
    }
