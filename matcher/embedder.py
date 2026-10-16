"""Step 3: the Siamese encoder.

SBERT (`all-MiniLM-L6-v2`) is a Siamese / bi-encoder network: the resume and
the JD pass *independently* through the same shared-weight transformer and
mean-pooling layer, and are compared with cosine similarity.

If sentence-transformers or the model weights are not available (e.g. no
internet on first run) we fall back to a TF-IDF encoder so the app still
works; the API reports which backend was used.
"""
from __future__ import annotations

import logging
import os

import numpy as np

log = logging.getLogger(__name__)

MODEL_NAME = os.environ.get("SBERT_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


class Embedder:
    def __init__(self, model_name: str = MODEL_NAME, force_fallback: bool = False):
        self.model = None
        self.backend = "tfidf"
        if not force_fallback and os.environ.get("MATCHER_BACKEND", "").lower() != "tfidf":
            try:
                from sentence_transformers import SentenceTransformer

                self.model = SentenceTransformer(model_name)
                self.backend = "sbert"
                log.info("Loaded SBERT model %s", model_name)
            except Exception as exc:  # noqa: BLE001
                log.warning("SBERT unavailable (%s) — using TF-IDF fallback", exc)

    @property
    def is_sbert(self) -> bool:
        return self.backend == "sbert"

    # Calibration used to map raw cosine similarity to a 0-100 score.
    # MiniLM cosine between unrelated professional texts sits around 0.1-0.2
    # and between strongly matching resume/JD pairs around 0.7-0.8.
    @property
    def calibration(self) -> tuple[float, float]:
        return (0.15, 0.75) if self.is_sbert else (0.05, 0.45)

    def similarity_matrix(self, texts_a: list[str], texts_b: list[str]) -> np.ndarray:
        """Cosine similarity between every text in A and every text in B."""
        if not texts_a or not texts_b:
            return np.zeros((len(texts_a), len(texts_b)))
        if self.is_sbert:
            emb_a = self.model.encode(texts_a, normalize_embeddings=True, convert_to_numpy=True)
            emb_b = self.model.encode(texts_b, normalize_embeddings=True, convert_to_numpy=True)
            return emb_a @ emb_b.T
        from sklearn.feature_extraction.text import TfidfVectorizer

        # Only two documents are compared, so IDF is meaningless (it would
        # down-weight exactly the shared terms); log-scaled TF works better.
        vec = TfidfVectorizer(stop_words="english", use_idf=False, sublinear_tf=True)
        mat = vec.fit_transform(list(texts_a) + list(texts_b))
        a, b = mat[: len(texts_a)], mat[len(texts_a):]
        return (a @ b.T).toarray()

    def similarity(self, a: str, b: str) -> float:
        return float(self.similarity_matrix([a], [b])[0, 0])


_shared: Embedder | None = None


def get_embedder() -> Embedder:
    """Load the model once per process."""
    global _shared
    if _shared is None:
        _shared = Embedder()
    return _shared
