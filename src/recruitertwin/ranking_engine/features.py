"""Feature extraction for a single candidate record.

Three layers, in deliberate order of trust:

1. EVIDENCE — what the career-history descriptions actually say they built.
   This is the primary signal. Skills *listed* but never *evidenced* are
   exactly the keyword-stuffer trap the dataset plants.
2. PLAUSIBILITY — honeypot detection. Internally inconsistent profiles
   (skill used longer than total career, "expert" with zero months, career
   timeline that doesn't add up) are forced out of contention.
3. AVAILABILITY — Redrob behavioral signals as a multiplier. A perfect
   profile that never logs in and never replies is not hireable.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from recruitertwin.job_intelligence import jd_profile as jd

REFERENCE_DATE = date(2026, 6, 11)


# ---------------------------------------------------------------------------
# text assembly
# ---------------------------------------------------------------------------

def candidate_texts(c: dict[str, Any]) -> tuple[str, str]:
    """Return (evidence_text, listed_skills_text), both lowercased.

    evidence_text = narrative fields a candidate can't trivially stuff
    (career descriptions, summary, headline, titles).
    """
    p = c.get("profile", {}) or {}
    parts = [p.get("headline", ""), p.get("summary", ""), p.get("current_title", "")]
    for job in c.get("career_history", []) or []:
        parts.append(job.get("title", ""))
        parts.append(job.get("description", ""))
    evidence = " \n ".join(x for x in parts if x).lower()
    skills = " , ".join((s.get("name", "") or "") for s in (c.get("skills") or [])).lower()
    return evidence, skills


def _hits(text: str, terms: list[str]) -> int:
    return sum(1 for t in terms if t in text)


# ---------------------------------------------------------------------------
# 1. evidence features
# ---------------------------------------------------------------------------

def evidence_features(c: dict[str, Any]) -> dict[str, Any]:
    evidence, skills_text = candidate_texts(c)
    must: dict[str, int] = {}
    for name, terms in jd.MUST_HAVE_CONCEPTS.items():
        must[name] = _hits(evidence, terms)
    nice = {name: _hits(evidence, terms) for name, terms in jd.NICE_TO_HAVE_CONCEPTS.items()}

    # skills-list-only matches (the stuffer signature): concept appears in the
    # skills list but never in any narrative text.
    listed_only = 0
    for terms in jd.MUST_HAVE_CONCEPTS.values():
        in_list = any(t.strip() in skills_text for t in terms)
        in_evidence = any(t in evidence for t in terms)
        if in_list and not in_evidence:
            listed_only += 1

    off_domain = _hits(evidence, jd.OFF_DOMAIN_TERMS)
    nlp_ir = _hits(evidence, jd.NLP_IR_TERMS)

    return {
        "must": must,
        "nice": nice,
        "listed_only_concepts": listed_only,
        "off_domain_hits": off_domain,
        "nlp_ir_hits": nlp_ir,
        "evidence_text": evidence,
    }


# ---------------------------------------------------------------------------
# career-shape features (disqualifiers from the JD)
# ---------------------------------------------------------------------------

def career_features(c: dict[str, Any]) -> dict[str, Any]:
    p = c.get("profile", {}) or {}
    history = c.get("career_history", []) or []
    title = (p.get("current_title") or "").lower()

    companies = [(j.get("company") or "").lower() for j in history]
    titles = [(j.get("title") or "").lower() for j in history]

    def is_consulting(name: str) -> bool:
        return any(f in name for f in jd.CONSULTING_FIRMS)

    consulting_flags = [is_consulting(x) for x in companies]
    consulting_only = bool(companies) and all(consulting_flags)
    has_product_exp = any(not f for f in consulting_flags)

    def is_research(comp: str, t: str) -> bool:
        return any(x in comp for x in jd.RESEARCH_ORG_TERMS) or any(
            x in t for x in jd.RESEARCH_TITLE_TERMS
        )

    research_only = bool(history) and all(
        is_research(comp, t) for comp, t in zip(companies, titles)
    )

    non_eng_title = any(t in title for t in jd.NON_ENGINEERING_TITLE_TERMS)
    eng_title = any(t in title for t in jd.ENGINEERING_TITLE_TERMS)

    # Title-chaser / job-hopper: average completed-stint tenure.
    durations = [j.get("duration_months") or 0 for j in history if not j.get("is_current")]
    avg_tenure = (sum(durations) / len(durations)) if durations else 36.0
    hopper = len(history) >= 3 and avg_tenure < 16

    return {
        "consulting_only": consulting_only,
        "currently_consulting_with_product_past": (
            bool(consulting_flags) and consulting_flags[0] and has_product_exp
        ),
        "research_only": research_only,
        "non_engineering_title": non_eng_title and not eng_title,
        "job_hopper": hopper,
        "avg_tenure_months": avg_tenure,
    }


# ---------------------------------------------------------------------------
# 2. honeypot / plausibility checks
# ---------------------------------------------------------------------------

def honeypot_flags(c: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    p = c.get("profile", {}) or {}
    yoe = float(p.get("years_of_experience") or 0)
    total_months = yoe * 12.0
    skills = c.get("skills") or []
    history = c.get("career_history") or []

    # Skill used longer than the entire career (with slack).
    over = [s for s in skills if (s.get("duration_months") or 0) > total_months + 9]
    if over:
        flags.append("skill_duration_exceeds_career")

    # "Expert" proficiency with ~zero actual usage.
    zero_experts = [
        s for s in skills
        if (s.get("proficiency") == "expert") and (s.get("duration_months") or 0) <= 1
    ]
    if len(zero_experts) >= 3:
        flags.append("expert_skills_with_zero_usage")

    # Career timeline wildly inconsistent with claimed experience.
    hist_months = sum(j.get("duration_months") or 0 for j in history)
    if history and total_months > 0:
        if hist_months > total_months * 1.9 + 24:
            flags.append("history_exceeds_claimed_experience")
        # Claims many years but documented history is a tiny fraction.
        if yoe >= 6 and hist_months < total_months * 0.25:
            flags.append("claimed_experience_unsupported")

    # Tenure at a single role longer than the claimed total career.
    if any((j.get("duration_months") or 0) > total_months + 12 for j in history):
        flags.append("single_role_exceeds_career")

    # Date arithmetic check: stated duration vs actual start/end dates.
    for j in history:
        try:
            start = datetime.strptime(j["start_date"], "%Y-%m-%d").date()
            end = (
                REFERENCE_DATE
                if j.get("is_current") or not j.get("end_date")
                else datetime.strptime(j["end_date"], "%Y-%m-%d").date()
            )
            real_months = (end.year - start.year) * 12 + (end.month - start.month)
            stated = j.get("duration_months") or 0
            if abs(real_months - stated) > 18:
                flags.append("duration_date_mismatch")
                break
            if start > REFERENCE_DATE:
                flags.append("future_start_date")
                break
        except Exception:
            continue

    return flags


# ---------------------------------------------------------------------------
# 3. behavioral availability multiplier (0.45 .. 1.10)
# ---------------------------------------------------------------------------

def behavioral_multiplier(c: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    s = c.get("redrob_signals", {}) or {}
    m = 1.0
    info: dict[str, Any] = {}

    # Recency of activity — dominant availability signal.
    days_inactive = 9999
    try:
        last = datetime.strptime(s.get("last_active_date", ""), "%Y-%m-%d").date()
        days_inactive = (REFERENCE_DATE - last).days
    except Exception:
        pass
    info["days_inactive"] = days_inactive
    if days_inactive <= 14:
        m *= 1.05
    elif days_inactive <= 45:
        m *= 1.0
    elif days_inactive <= 90:
        m *= 0.88
    elif days_inactive <= 180:
        m *= 0.72
    else:
        m *= 0.55

    rr = float(s.get("recruiter_response_rate") or 0.0)
    info["response_rate"] = rr
    if rr >= 0.6:
        m *= 1.05
    elif rr >= 0.3:
        m *= 1.0
    elif rr >= 0.15:
        m *= 0.85
    else:
        m *= 0.70

    if s.get("open_to_work_flag"):
        m *= 1.04
    icr = s.get("interview_completion_rate")
    if icr is not None and icr >= 0 and icr < 0.5:
        m *= 0.85

    notice = int(s.get("notice_period_days") or 0)
    info["notice_days"] = notice
    if notice <= 30:
        m *= 1.03
    elif notice <= 60:
        m *= 0.97
    else:
        m *= 0.90

    if s.get("verified_email") and s.get("verified_phone"):
        m *= 1.01

    return max(0.45, min(m, 1.10)), info


# ---------------------------------------------------------------------------
# location & experience fit
# ---------------------------------------------------------------------------

def location_fit(c: dict[str, Any]) -> tuple[float, str]:
    p = c.get("profile", {}) or {}
    loc = (p.get("location") or "").lower()
    country = (p.get("country") or "").lower()
    relocate = bool((c.get("redrob_signals") or {}).get("willing_to_relocate"))

    if any(city in loc for city in jd.PREFERRED_CITIES):
        return 1.0, "in a preferred hub (Pune/Noida)"
    if country == "india" and any(city in loc for city in jd.TIER1_INDIA_CITIES):
        return 0.85, "Tier-1 India city"
    if country == "india":
        return (0.65 if relocate else 0.45), (
            "in India, willing to relocate" if relocate else "in India, relocation unclear"
        )
    return (0.30 if relocate else 0.10), "outside India (case-by-case per JD)"


def experience_fit(yoe: float) -> float:
    if jd.EXP_IDEAL_LO <= yoe <= jd.EXP_IDEAL_HI:
        return 1.0
    if jd.EXP_MIN <= yoe <= jd.EXP_MAX:
        return 0.9
    if 4.0 <= yoe < jd.EXP_MIN:
        return 0.7
    if jd.EXP_MAX < yoe <= 12.0:
        return 0.65
    if 3.0 <= yoe < 4.0:
        return 0.45
    return 0.25
