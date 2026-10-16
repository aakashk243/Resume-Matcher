"""The shared matching engine used by both portals.

pdf_parser -> preprocessing -> skill_extractor -> SBERT similarity
    -> gap_analysis + roadmap   (student portal)
    -> consistency_check        (employer portal)
"""
from __future__ import annotations

from functools import lru_cache

from .consistency_check import check_consistency
from .embedder import get_embedder
from .gap_analysis import analyze_gaps, jd_skill_priorities
from .preprocessing import split_sections
from .roadmap import RoadmapBuilder
from .similarity import semantic_match
from .skill_extractor import SkillExtractor


@lru_cache(maxsize=1)
def _extractor() -> SkillExtractor:
    return SkillExtractor()


@lru_cache(maxsize=1)
def _roadmap_builder() -> RoadmapBuilder:
    return RoadmapBuilder(category=_extractor().category)


def _validate(resume_text: str, jd_text: str):
    if len((resume_text or "").split()) < 20:
        raise ValueError("The resume text is too short — upload a full resume.")
    if len((jd_text or "").split()) < 15:
        raise ValueError("The job description is too short — paste the full JD.")


def analyze_student(resume_text: str, jd_text: str, hours_per_week: float = 10,
                    free_only: bool = False) -> dict:
    _validate(resume_text, jd_text)
    ext, emb = _extractor(), get_embedder()
    sections = split_sections(resume_text)
    match = semantic_match(resume_text, jd_text, emb)
    gaps = analyze_gaps(resume_text, sections, jd_text, ext, emb)
    known = set(gaps["resume_skills"]) | {p["skill"] for p in gaps["partial"]}
    roadmap = _roadmap_builder().build(gaps["missing"], known, hours_per_week, free_only)
    return {"match": match, "gaps": gaps, "roadmap": roadmap, "sections": sorted(sections)}


def analyze_employer(resume_text: str, jd_text: str) -> dict:
    _validate(resume_text, jd_text)
    ext, emb = _extractor(), get_embedder()
    sections = split_sections(resume_text)
    match = semantic_match(resume_text, jd_text, emb)
    jd_skills = jd_skill_priorities(jd_text, ext)
    consistency = check_consistency(sections, jd_skills, ext)
    overlap = len(consistency["well_supported"]) + len(consistency["list_only"])
    coverage = round(100 * overlap / len(jd_skills), 1) if jd_skills else 0.0
    return {"match": match, "coverage": coverage, "consistency": consistency}
