from __future__ import annotations

from .models import JobIntelligenceOutput


def extract_role_dna(job_description: str) -> JobIntelligenceOutput:
    """Starter hook for Person 2.

    Replace this placeholder with the real JD parsing pipeline.
    """
    _ = job_description
    return JobIntelligenceOutput(
        role="TODO",
        seniority="TODO",
        domain="TODO",
        must_have_skills=[],
        nice_to_have_skills=[],
        responsibilities=[],
        success_traits=[],
    )
