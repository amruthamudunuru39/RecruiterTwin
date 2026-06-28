from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import json
import math
import re
from typing import Any


TOKEN_RE = re.compile(r"[a-z0-9+#.]+")

SYNONYM_GROUPS = [
    {"ai", "ml", "machine", "learning", "llm", "nlp"},
    {"search", "retrieval", "ranking", "relevance"},
    {"backend", "api", "platform", "distributed", "services"},
    {"python", "pytorch", "tensorflow", "scikit-learn"},
    {"hiring", "recruitment", "talent", "sourcing"},
]

SENIORITY_ORDER = {
    "intern": 0,
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "lead": 4,
    "staff": 5,
    "principal": 6,
}


@dataclass
class JobProfile:
    role_title: str
    summary: str
    seniority: str
    min_years_experience: int
    required_skills: list[str]
    preferred_skills: list[str]
    domains: list[str]


@dataclass
class CandidateProfile:
    candidate_id: str
    name: str
    current_title: str
    summary: str
    years_experience: int
    skills: list[str]
    domains: list[str]
    activity_signals: dict[str, float]


@dataclass
class RankedCandidate:
    rank: int
    candidate_id: str
    name: str
    overall_score: float
    skill_score: float
    semantic_score: float
    seniority_score: float
    domain_score: float
    activity_score: float
    recommendation: str
    explanation: str


def load_job_profile(path: Path) -> JobProfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return JobProfile(**payload)


def load_candidates(path: Path) -> list[CandidateProfile]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [CandidateProfile(**candidate) for candidate in payload]


def tokenize(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text.lower()))


def expanded_tokens(text: str) -> set[str]:
    tokens = tokenize(text)
    expanded = set(tokens)
    for group in SYNONYM_GROUPS:
        if tokens & group:
            expanded.update(group)
    return expanded


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left:
        return 0.0
    return len(left & right) / len(left)


def normalize_signal(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return clamp(value / scale)


def infer_seniority(title: str, years_experience: int) -> str:
    title_tokens = tokenize(title)
    for seniority in ("principal", "staff", "lead", "senior", "junior", "intern"):
        if seniority in title_tokens:
            return seniority
    if years_experience >= 8:
        return "lead"
    if years_experience >= 5:
        return "senior"
    if years_experience >= 3:
        return "mid"
    if years_experience >= 1:
        return "junior"
    return "intern"


def score_candidate(job: JobProfile, candidate: CandidateProfile) -> dict[str, Any]:
    required = expanded_tokens(" ".join(job.required_skills))
    preferred = expanded_tokens(" ".join(job.preferred_skills))
    candidate_skills = expanded_tokens(" ".join(candidate.skills))
    job_text = expanded_tokens(
        " ".join(
            [
                job.role_title,
                job.summary,
                " ".join(job.required_skills),
                " ".join(job.preferred_skills),
                " ".join(job.domains),
            ]
        )
    )
    candidate_text = expanded_tokens(
        " ".join(
            [
                candidate.current_title,
                candidate.summary,
                " ".join(candidate.skills),
                " ".join(candidate.domains),
            ]
        )
    )

    required_match = overlap_ratio(required, candidate_skills)
    preferred_match = overlap_ratio(preferred, candidate_skills)
    skill_score = clamp((0.75 * required_match) + (0.25 * preferred_match))

    semantic_score = overlap_ratio(job_text, candidate_text)

    candidate_domains = expanded_tokens(" ".join(candidate.domains))
    job_domains = expanded_tokens(" ".join(job.domains))
    domain_score = overlap_ratio(job_domains, candidate_domains)

    target_level = SENIORITY_ORDER.get(job.seniority.lower(), 3)
    candidate_level = SENIORITY_ORDER.get(
        infer_seniority(candidate.current_title, candidate.years_experience), 2
    )
    level_gap = abs(target_level - candidate_level)
    seniority_score = clamp(1 - (level_gap / 4))

    experience_score = clamp(candidate.years_experience / max(job.min_years_experience, 1))
    engagement_score = normalize_signal(candidate.activity_signals.get("engagement_score", 0), 10)
    profile_completeness = candidate.activity_signals.get("profile_completeness", 0)
    recency_signal = normalize_signal(candidate.activity_signals.get("recent_activity_days", 0), 30)
    activity_score = clamp((0.4 * engagement_score) + (0.35 * profile_completeness) + (0.25 * recency_signal))

    overall_score = clamp(
        (0.33 * skill_score)
        + (0.25 * semantic_score)
        + (0.15 * domain_score)
        + (0.12 * seniority_score)
        + (0.08 * experience_score)
        + (0.07 * activity_score)
    )

    explanation_bits = []
    if required_match >= 0.7:
        explanation_bits.append("strong required-skill coverage")
    if semantic_score >= 0.45:
        explanation_bits.append("good semantic match with the role")
    if domain_score >= 0.5:
        explanation_bits.append("relevant domain background")
    if seniority_score >= 0.75:
        explanation_bits.append("seniority aligns with the target role")
    if activity_score >= 0.7:
        explanation_bits.append("healthy profile and activity signals")
    if not explanation_bits:
        explanation_bits.append("partial alignment with room for manual review")

    if overall_score >= 0.8:
        recommendation = "Strong shortlist"
    elif overall_score >= 0.65:
        recommendation = "Worth recruiter review"
    else:
        recommendation = "Backup option"

    return {
        "overall_score": round(overall_score, 4),
        "skill_score": round(skill_score, 4),
        "semantic_score": round(semantic_score, 4),
        "seniority_score": round(seniority_score, 4),
        "domain_score": round(domain_score, 4),
        "activity_score": round(activity_score, 4),
        "recommendation": recommendation,
        "explanation": "; ".join(explanation_bits),
    }


def rank_candidates(job: JobProfile, candidates: list[CandidateProfile]) -> list[RankedCandidate]:
    ranked_rows = []
    for candidate in candidates:
        scores = score_candidate(job, candidate)
        ranked_rows.append(
            RankedCandidate(
                rank=0,
                candidate_id=candidate.candidate_id,
                name=candidate.name,
                overall_score=scores["overall_score"],
                skill_score=scores["skill_score"],
                semantic_score=scores["semantic_score"],
                seniority_score=scores["seniority_score"],
                domain_score=scores["domain_score"],
                activity_score=scores["activity_score"],
                recommendation=scores["recommendation"],
                explanation=scores["explanation"],
            )
        )

    ranked_rows.sort(
        key=lambda item: (
            item.overall_score,
            item.skill_score,
            item.semantic_score,
            item.activity_score,
        ),
        reverse=True,
    )

    for index, row in enumerate(ranked_rows, start=1):
        row.rank = index
    return ranked_rows


def write_ranked_output(rows: list[RankedCandidate], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "rank",
                "candidate_id",
                "candidate_name",
                "overall_score",
                "skill_score",
                "semantic_score",
                "seniority_score",
                "domain_score",
                "activity_score",
                "recommendation",
                "explanation",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.rank,
                    row.candidate_id,
                    row.name,
                    f"{row.overall_score:.4f}",
                    f"{row.skill_score:.4f}",
                    f"{row.semantic_score:.4f}",
                    f"{row.seniority_score:.4f}",
                    f"{row.domain_score:.4f}",
                    f"{row.activity_score:.4f}",
                    row.recommendation,
                    row.explanation,
                ]
            )
