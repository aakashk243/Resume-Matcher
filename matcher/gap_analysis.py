"""Student portal: explainable skill-level gap analysis."""
from __future__ import annotations

import re

from .embedder import Embedder
from .preprocessing import EVIDENCE_SECTIONS, chunk_text, split_jd_requirements
from .skill_extractor import SkillExtractor

PARTIAL_THRESHOLD = 0.55  # SBERT cosine above which a resume line is "related evidence"


_OR_BETWEEN = re.compile(r"^\s*,?\s*(or|and/or)\s*$", re.I)


def _alternative_groups(text: str, extractor: SkillExtractor) -> dict[str, set[str]]:
    """Find 'PyTorch or TensorFlow' style alternatives in a JD."""
    alts: dict[str, set[str]] = {}
    for line in text.splitlines():
        spans = extractor.extract_spans(line)
        for (a, _, a_end), (b, b_start, _) in zip(spans, spans[1:]):
            if a != b and _OR_BETWEEN.match(line[a_end:b_start]):
                alts.setdefault(a, set()).add(b)
                alts.setdefault(b, set()).add(a)
    return alts


def jd_skill_priorities(jd_text: str, extractor: SkillExtractor) -> dict[str, dict]:
    """Return {skill: {priority, mentions, alternatives}} for a JD."""
    parts = split_jd_requirements(jd_text)
    req = extractor.extract(parts["required"])
    pref = extractor.extract(parts["preferred"])
    alts = _alternative_groups(jd_text, extractor)
    out = {}
    for skill in set(req) | set(pref):
        out[skill] = {
            "priority": "required" if skill in req else "preferred",
            "mentions": req.get(skill, 0) + pref.get(skill, 0),
            "alternatives": sorted(alts.get(skill, ())),
        }
    return out


def analyze_gaps(resume_text: str, resume_sections: dict, jd_text: str,
                 extractor: SkillExtractor, embedder: Embedder) -> dict:
    jd_skills = jd_skill_priorities(jd_text, extractor)
    resume_where = extractor.extract_by_section(resume_sections)
    resume_skills = set(resume_where)

    matched = sorted(s for s in jd_skills if s in resume_skills)
    missing = [s for s in jd_skills if s not in resume_skills]

    # "PyTorch or TensorFlow": knowing one alternative satisfies the other;
    # if neither is known, only the first one is a real gap.
    via_alt = {}
    for s in missing:
        have = [a for a in jd_skills[s]["alternatives"] if a in resume_skills]
        if have:
            via_alt[s] = have[0]
    missing = [s for s in missing if s not in via_alt]
    alt_of = {}
    for s in sorted(missing, key=lambda s: (-jd_skills[s]["mentions"], s)):
        if s in alt_of:
            continue
        for a in jd_skills[s]["alternatives"]:
            if a in missing and a not in alt_of:
                alt_of[a] = s
    counted = {s for s in jd_skills if s not in via_alt and s not in alt_of}

    # Semantic safety net: a skill may be described without being named
    # ("built dashboards with charts" for Data Visualization).
    partial = []
    if embedder.is_sbert and missing:
        r_chunks = chunk_text(resume_text)
        queries = [f"{s} ({extractor.category.get(s, '')})" for s in missing]
        sim = embedder.similarity_matrix(queries, r_chunks)
        for i, skill in enumerate(missing):
            j = int(sim[i].argmax()) if r_chunks else -1
            if j >= 0 and sim[i, j] >= PARTIAL_THRESHOLD:
                partial.append({"skill": skill, "evidence": r_chunks[j],
                                "similarity": round(float(sim[i, j]), 3)})
    partial_names = {p["skill"] for p in partial}
    missing = [s for s in missing if s not in partial_names]

    weight = {"required": 1.0, "preferred": 0.5}
    total_w = sum(weight[jd_skills[s]["priority"]] for s in counted) or 1.0
    got_w = sum(weight[jd_skills[s]["priority"]] for s in matched if s in counted)
    got_w += 0.5 * sum(weight[jd_skills[s]["priority"]] for s in partial_names if s in counted)
    coverage = round(100 * got_w / total_w, 1) if jd_skills else 0.0

    # Skills the student lists but never demonstrates in experience/projects
    unbacked = sorted(s for s in matched if not (resume_where[s] & EVIDENCE_SECTIONS)
                      and set(resume_sections) & EVIDENCE_SECTIONS)

    def pri(s):  # an un-chosen alternative is only "preferred"
        return "preferred" if s in alt_of else jd_skills[s]["priority"]

    missing_sorted = sorted(missing, key=lambda s: (pri(s) != "required", -jd_skills[s]["mentions"], s))
    return {
        "coverage": coverage,
        "jd_skills": jd_skills,
        "matched": [{"skill": s, "priority": pri(s), "category": extractor.category.get(s)} for s in matched]
                   + [{"skill": s, "priority": pri(s), "category": extractor.category.get(s), "via": v}
                      for s, v in sorted(via_alt.items())],
        "partial": partial,
        "missing": [{"skill": s, "priority": pri(s), "mentions": jd_skills[s]["mentions"],
                     "category": extractor.category.get(s),
                     "alternative_to": alt_of.get(s)} for s in missing_sorted],
        "unbacked": unbacked,
        "resume_skills": sorted(resume_skills),
        "extra_skills": sorted(resume_skills - set(jd_skills)),
        "suggestions": _suggestions(missing_sorted, {x: pri(x) for x in missing_sorted}, unbacked),
    }


def _suggestions(missing: list[str], priority: dict, unbacked: list[str]) -> list[str]:
    tips = []
    req = [s for s in missing if priority[s] == "required"]
    pref = [s for s in missing if priority[s] == "preferred"]
    if req:
        tips.append(f"Close the required gaps first: {', '.join(req[:4])}. "
                    f"A single deployed project that uses {' + '.join(req[:2])} is stronger evidence than a certificate.")
    if pref:
        tips.append(f"Nice-to-have skills you could pick up later: {', '.join(pref[:4])}.")
    if unbacked:
        tips.append(f"You list {', '.join(unbacked[:4])} but never show them in Experience/Projects — "
                    "add a bullet describing where you used each one, with a result.")
    if not missing:
        tips.append("You cover every skill this JD names. Tailor your summary to mirror its wording and quantify results.")
    return tips
