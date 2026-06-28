from __future__ import annotations


def normalize_candidate_record(record: dict) -> dict:
    """Starter hook for Person 3.

    Convert raw candidate records into a normalized internal shape.
    """
    return {
        "candidate_id": record.get("candidate_id", ""),
        "skills": record.get("skills", []),
        "experience": record.get("experience", ""),
        "projects": record.get("projects", []),
        "education": record.get("education", []),
        "certifications": record.get("certifications", []),
    }
