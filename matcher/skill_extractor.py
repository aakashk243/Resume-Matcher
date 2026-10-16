"""Step 2b: skill extraction with spaCy's PhraseMatcher over a JSON taxonomy.

Every skill has a canonical name and aliases ("ML" -> "Machine Learning"), so
synonyms that break keyword-based ATS matching are normalised here.
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict

import spacy
from spacy.matcher import PhraseMatcher

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


class SkillExtractor:
    def __init__(self, taxonomy_path: str | None = None):
        taxonomy_path = taxonomy_path or os.path.join(DATA_DIR, "skills_taxonomy.json")
        with open(taxonomy_path, encoding="utf-8") as fh:
            self.skills = json.load(fh)["skills"]
        self.category = {s["name"]: s["category"] for s in self.skills}

        # A blank English pipeline is enough: we only need the tokenizer.
        self.nlp = spacy.blank("en")
        self.lower_matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        self.exact_matcher = PhraseMatcher(self.nlp.vocab, attr="ORTH")
        for s in self.skills:
            name = s["name"]
            case_sensitive = s.get("case_sensitive")
            lower_terms = list(s.get("aliases", []))
            if case_sensitive:
                self.exact_matcher.add(name, [self.nlp.make_doc(t) for t in case_sensitive])
            else:
                lower_terms.append(name)
            if lower_terms:
                self.lower_matcher.add(name, [self.nlp.make_doc(t) for t in lower_terms])

    # ------------------------------------------------------------------
    def extract(self, text: str) -> Counter:
        """Return Counter{canonical skill: number of mentions}."""
        return Counter(name for name, _, _ in self.extract_spans(text))

    def extract_spans(self, text: str) -> list[tuple[str, int, int]]:
        """Return [(skill, start_char, end_char)] in document order."""
        doc = self.nlp.make_doc(text or "")
        found: list[tuple[str, int, int]] = []
        taken: set[int] = set()
        matches = [(m, s, e) for m, s, e in self.lower_matcher(doc)]
        matches += [(m, s, e) for m, s, e in self.exact_matcher(doc)]
        # prefer longer matches so "Spring Boot" beats a shorter overlapping one
        for match_id, start, end in sorted(matches, key=lambda x: -(x[2] - x[1])):
            if any(i in taken for i in range(start, end)):
                continue
            name = self.nlp.vocab.strings[match_id]
            nxt = doc[end].text if end < len(doc) else ""
            if name == "C" and nxt in {"#", "++"}:  # C# / C++ are not C
                continue
            taken.update(range(start, end))
            span = doc[start:end]
            found.append((name, span.start_char, span.end_char))
        return sorted(found, key=lambda x: x[1])

    def extract_set(self, text: str) -> set[str]:
        return set(self.extract(text))

    def extract_by_section(self, sections: dict[str, str]) -> dict[str, set[str]]:
        """Return {skill: {sections where it appears}}."""
        where: dict[str, set[str]] = defaultdict(set)
        for sec, body in sections.items():
            for skill in self.extract(body):
                where[skill].add(sec)
        return dict(where)
