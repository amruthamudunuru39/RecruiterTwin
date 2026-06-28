"""Hybrid scoring: evidence-weighted JD fit × behavioral availability.

final = base_fit × behavioral_multiplier × penalty_multipliers
base_fit = 0.46·must_have_coverage + 0.16·tfidf_similarity
         + 0.14·ranking_depth + 0.10·experience_fit
         + 0.08·location_fit + 0.06·nice_to_have

Honeypots are removed before ranking (score forced to 0).
"""

from __future__ import annotations

import math
from typing import Any

from recruitertwin.ranking_engine import features as F


def _saturate(hits: int, k: float = 2.0) -> float:
    """Diminishing returns: 0 hits -> 0, k hits -> ~0.63, lots -> ~1."""
    return 1.0 - math.exp(-hits / k)


def score_candidate(c: dict[str, Any], tfidf_sim: float = 0.0) -> dict[str, Any]:
    p = c.get("profile", {}) or {}
    yoe = float(p.get("years_of_experience") or 0.0)

    ev = F.evidence_features(c)
    career = F.career_features(c)
    pots = F.honeypot_flags(c)
    behav_mult, behav_info = F.behavioral_multiplier(c)
    loc_score, loc_label = F.location_fit(c)
    exp_score = F.experience_fit(yoe)

    must = ev["must"]
    # Coverage across the four hard must-haves; each axis saturating.
    core_axes = ["embeddings_retrieval", "vector_search_infra", "ranking_systems", "evaluation"]
    covered = sum(1 for a in core_axes if must[a] > 0)
    must_cov = (covered / len(core_axes)) * 0.6 + 0.4 * (
        sum(_saturate(must[a]) for a in core_axes) / len(core_axes)
    )

    ranking_depth = _saturate(must["ranking_systems"] + must["embeddings_retrieval"], k=3.0)
    nice = _saturate(sum(ev["nice"].values()), k=3.0)
    llm_prod = _saturate(must["llm_depth"], k=3.0) * _saturate(must["production_engineering"], k=3.0)

    base = (
        0.46 * must_cov
        + 0.16 * max(0.0, min(tfidf_sim * 2.5, 1.0))  # cosine sims are small; rescale
        + 0.14 * ranking_depth
        + 0.10 * exp_score
        + 0.08 * loc_score
        + 0.06 * (0.5 * nice + 0.5 * llm_prod)
    )

    penalties: list[str] = []
    mult = 1.0

    if pots:
        return _result(c, 0.0, ["honeypot:" + "|".join(pots)], ev, career, behav_info,
                       loc_label, yoe, honeypot=True)

    # JD hard / near-hard disqualifiers.
    if career["research_only"]:
        mult *= 0.05
        penalties.append("research-only career (explicit JD disqualifier)")
    if career["non_engineering_title"]:
        mult *= 0.08
        penalties.append("non-engineering current title despite listed AI skills")
    if career["consulting_only"]:
        mult *= 0.25
        penalties.append("consulting-firms-only career (JD exclusion)")
    if career["job_hopper"]:
        mult *= 0.75
        penalties.append("frequent short stints (title-chaser pattern)")

    # Keyword-stuffer trap: concepts listed as skills but zero narrative evidence.
    if ev["listed_only_concepts"] >= 3 and must_cov < 0.25:
        mult *= 0.30
        penalties.append("skills listed without supporting career evidence (stuffer pattern)")

    # Wrong primary domain (CV/speech/robotics) without NLP/IR exposure.
    if ev["off_domain_hits"] >= 3 and ev["nlp_ir_hits"] <= 1:
        mult *= 0.45
        penalties.append("primary expertise in CV/speech without NLP/IR exposure")

    # JD logistics: no visa sponsorship; outside-India is case-by-case.
    if "outside India" in loc_label:
        mult *= 0.80

    final = base * mult * behav_mult
    return _result(c, final, penalties, ev, career, behav_info, loc_label, yoe)


def _result(c, final, penalties, ev, career, behav_info, loc_label, yoe, honeypot=False):
    return {
        "candidate_id": c.get("candidate_id", ""),
        "final_score": round(float(final), 6),
        "honeypot": honeypot,
        "penalties": penalties,
        "must_hits": ev["must"],
        "nice_hits": ev["nice"],
        "career": career,
        "behavior": behav_info,
        "location_label": loc_label,
        "yoe": yoe,
        "title": (c.get("profile", {}) or {}).get("current_title", ""),
        "company": (c.get("profile", {}) or {}).get("current_company", ""),
    }
