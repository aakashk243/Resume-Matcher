"""Employer portal: is each overlapping skill backed by experience/project text?

This is a screening signal to guide interview questions — not a lie detector.
"""
from __future__ import annotations

from .preprocessing import EVIDENCE_SECTIONS
from .skill_extractor import SkillExtractor

QUESTION_TEMPLATES = {
    "Programming Languages": "Walk me through a non-trivial program you wrote in {s}. What would you do differently now?",
    "Web Development": "Describe a feature you built with {s}. How did you handle state, errors and performance?",
    "Databases": "Design a {s} schema for an order-management system and explain your indexing choices.",
    "DevOps & Cloud": "How have you used {s} in a real deployment? What broke, and how did you debug it?",
    "AI / Machine Learning": "Explain a project where you applied {s}. How did you evaluate the model and avoid overfitting?",
    "Data Science": "Show how you would use {s} to clean and explore a messy dataset.",
    "Data Engineering": "Describe a pipeline you built with {s}. How did you handle failures and late data?",
    "Soft Skills": "Tell me about a specific situation that demonstrates your {s}.",
}
DEFAULT_Q = "Where have you used {s} hands-on, and what was the outcome?"


def check_consistency(resume_sections: dict, jd_skills: dict, extractor: SkillExtractor) -> dict:
    where = extractor.extract_by_section(resume_sections)
    has_evidence_sections = bool(set(resume_sections) & EVIDENCE_SECTIONS)
    well, list_only, missing = [], [], []
    for skill, meta in sorted(jd_skills.items()):
        if skill not in where:
            missing.append({"skill": skill, "priority": meta["priority"]})
            continue
        secs = sorted(where[skill])
        item = {"skill": skill, "priority": meta["priority"], "sections": secs}
        if where[skill] & EVIDENCE_SECTIONS or not has_evidence_sections:
            well.append(item)
        else:
            item["question"] = QUESTION_TEMPLATES.get(extractor.category.get(skill), DEFAULT_Q).format(s=skill)
            list_only.append(item)
    overlap = len(well) + len(list_only)
    return {
        "support_ratio": round(100 * len(well) / overlap, 1) if overlap else 0.0,
        "well_supported": well,
        "list_only": list_only,
        "missing": missing,
        "sections_detected": sorted(resume_sections),
        "note": ("No Experience/Projects section was detected, so support could not be checked."
                 if not has_evidence_sections else
                 "Screening signal only — use list-only skills to focus interview questions."),
    }
