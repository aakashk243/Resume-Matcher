"""Step 4: similarity score.

score = 50% whole-document cosine + 50% "requirement alignment": every JD
chunk (sentence/bullet) is matched to its most similar resume chunk and the
best-match similarities are averaged. The alignment term rewards resumes that
address *each* requirement, not just the overall topic, and it lets us show
which JD lines are least covered.
"""
from __future__ import annotations

import numpy as np

from .embedder import Embedder
from .preprocessing import chunk_text, clean_text


def _scale(x: float, lo: float, hi: float) -> float:
    return float(np.clip((x - lo) / (hi - lo), 0.0, 1.0) * 100.0)


def semantic_match(resume_text: str, jd_text: str, embedder: Embedder) -> dict:
    lo, hi = embedder.calibration
    doc_cos = embedder.similarity(clean_text(resume_text), clean_text(jd_text))

    r_chunks, j_chunks = chunk_text(resume_text), chunk_text(jd_text)
    sim = embedder.similarity_matrix(j_chunks, r_chunks)
    best = sim.max(axis=1) if sim.size else np.zeros(len(j_chunks))
    align = float(best.mean()) if len(best) else 0.0

    score = 0.5 * _scale(doc_cos, lo, hi) + 0.5 * _scale(align, lo, hi)

    # JD requirement lines with the weakest support in the resume
    weakest = []
    if len(best):
        for idx in np.argsort(best)[:3]:
            weakest.append({
                "jd_line": j_chunks[idx],
                "closest_resume_line": (r_chunks[int(sim[idx].argmax())]
                                        if r_chunks and best[idx] > 0.05 else ""),
                "similarity": round(float(best[idx]), 3),
            })
    return {
        "score": round(score, 1),
        "document_cosine": round(doc_cos, 3),
        "alignment_cosine": round(align, 3),
        "weakest_requirements": weakest,
        "backend": embedder.backend,
    }
