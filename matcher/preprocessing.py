"""Step 2: NLP preprocessing — clean text, split resumes into sections, split
job descriptions into required / preferred parts, and chunk text for SBERT."""
from __future__ import annotations

import re
import unicodedata

# Canonical section -> header keywords that introduce it on a resume.
SECTION_HEADERS = {
    "summary": ["summary", "profile", "objective", "about me", "career objective", "professional summary"],
    "experience": ["experience", "work experience", "professional experience", "employment",
                   "employment history", "internship", "internships", "work history"],
    "projects": ["projects", "academic projects", "personal projects", "key projects", "project work"],
    "skills": ["skills", "technical skills", "core skills", "key skills", "technologies",
               "tools", "skills & tools", "tech stack", "competencies"],
    "education": ["education", "academic background", "qualifications", "academics"],
    "certifications": ["certifications", "certificates", "courses", "licenses", "training"],
    "achievements": ["achievements", "awards", "accomplishments", "honors", "extracurricular",
                     "activities", "positions of responsibility", "publications"],
}

# Sections whose text counts as *evidence* that a skill was actually used.
EVIDENCE_SECTIONS = {"experience", "projects", "achievements"}

_HEADER_LOOKUP = {kw: sec for sec, kws in SECTION_HEADERS.items() for kw in kws}

_PREFERRED_CUES = re.compile(
    r"\b(nice to have|good to have|preferred|bonus|a plus|is a plus|desirable|optional|"
    r"added advantage|would be great|familiarity with)\b", re.I)
_PREFERRED_HEADER = re.compile(
    r"^\s*(nice to have|good to have|preferred( qualifications| skills)?|bonus( points)?|"
    r"desirable|pluses|plus)\s*:?\s*$", re.I)
_REQUIRED_HEADER = re.compile(
    r"^\s*(requirements|required( qualifications| skills)?|must have|minimum qualifications|"
    r"what you('ll)? need|qualifications|responsibilities|what you will do|basic qualifications)\s*:?\s*$",
    re.I)


def clean_text(text: str) -> str:
    """Normalise unicode, bullets and whitespace while keeping line breaks."""
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"[•●▪■‣⁃∙➢]", "-", text)
    text = text.replace("\t", " ")
    text = re.sub(r"[  ]{2,}", " ", text)
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _header_of(line: str) -> str | None:
    """Return a canonical section name if `line` looks like a section header."""
    candidate = re.sub(r"[^a-z& ]", "", line.lower()).strip()
    if not candidate or len(candidate) > 40 or len(line.split()) > 5:
        return None
    return _HEADER_LOOKUP.get(candidate)


def split_sections(text: str) -> dict[str, str]:
    """Split a resume into canonical sections. Text before the first header
    goes to 'header'; unrecognised structure ends up in 'other'."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in clean_text(text).splitlines():
        sec = _header_of(line)
        if sec:
            current = sec
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    out = {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}
    if len(out) <= 1:  # no headers detected at all
        out = {"other": clean_text(text)}
    return out


def split_jd_requirements(text: str) -> dict[str, str]:
    """Split a JD into 'required' and 'preferred' text using headers and cue words."""
    required, preferred = [], []
    mode = "required"
    for line in clean_text(text).splitlines():
        if _PREFERRED_HEADER.match(line):
            mode = "preferred"
            continue
        if _REQUIRED_HEADER.match(line):
            mode = "required"
            continue
        if mode == "preferred" or _PREFERRED_CUES.search(line):
            preferred.append(line)
        else:
            required.append(line)
    return {"required": "\n".join(required), "preferred": "\n".join(preferred)}


def chunk_text(text: str, max_words: int = 60, min_words: int = 4) -> list[str]:
    """Split text into sentence/bullet-sized chunks suitable for SBERT."""
    pieces: list[str] = []
    for line in clean_text(text).splitlines():
        line = line.strip(" -*")
        if not line:
            continue
        for sent in re.split(r"(?<=[.!?;])\s+", line):
            words = sent.split()
            for i in range(0, len(words), max_words):
                seg = " ".join(words[i:i + max_words])
                if len(seg.split()) >= min_words:
                    pieces.append(seg)
    # merge tiny leftovers so we never return an empty list for short docs
    if not pieces and text.strip():
        pieces = [clean_text(text)[:2000]]
    return pieces
