from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JobIntelligenceOutput:
    role: str
    seniority: str
    domain: str
    must_have_skills: list[str]
    nice_to_have_skills: list[str]
    responsibilities: list[str]
    success_traits: list[str]
