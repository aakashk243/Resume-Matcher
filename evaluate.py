"""Small sanity-check: does the Siamese SBERT encoder beat a TF-IDF keyword
baseline on synonym-heavy resume/JD pairs? (The motivating problem from the
slides: "ML" vs "Machine Learning", "React" vs "frontend framework".)

This is an illustrative hand-made set of 12 pairs, not a benchmark.
Run:  python evaluate.py
"""
from matcher.embedder import Embedder

PAIRS = [  # (resume line, JD line, relevant?)
    ("Built ML models to predict customer churn", "Experience with machine learning for predictive analytics", 1),
    ("Developed SPA using React hooks and Redux", "Proficiency in a modern frontend framework", 1),
    ("Deployed services on EC2 and S3", "Hands-on experience with Amazon Web Services", 1),
    ("Containerised microservices with Docker and k8s", "Container orchestration experience", 1),
    ("Fine-tuned BERT for sentiment classification", "Experience with transformer-based NLP models", 1),
    ("Wrote complex joins and window functions", "Strong SQL querying skills", 1),
    ("Designed REST endpoints in Flask", "Backend API development in Python", 1),
    ("Led a team of five in a hackathon", "Demonstrated leadership ability", 1),
    ("Organised college cultural fest", "Experience with Kubernetes in production", 0),
    ("Painted murals for local cafes", "Strong SQL querying skills", 0),
    ("Taught mathematics to school students", "Hands-on experience with Amazon Web Services", 0),
    ("Managed social media for a bakery", "Experience with transformer-based NLP models", 0),
]


def evaluate(emb: Embedder):
    sims = [emb.similarity(r, j) for r, j, _ in PAIRS]
    pos = [s for s, (_, _, y) in zip(sims, PAIRS) if y]
    neg = [s for s, (_, _, y) in zip(sims, PAIRS) if not y]
    # best threshold accuracy
    best = max(sum((s >= t) == bool(y) for s, (_, _, y) in zip(sims, PAIRS)) / len(PAIRS) for t in sims)
    print(f"{emb.backend:>6}: mean sim relevant={sum(pos)/len(pos):.3f}  irrelevant={sum(neg)/len(neg):.3f}  "
          f"gap={sum(pos)/len(pos)-sum(neg)/len(neg):.3f}  best-threshold accuracy={best:.0%}")


if __name__ == "__main__":
    evaluate(Embedder(force_fallback=True))
    sbert = Embedder()
    if sbert.is_sbert:
        evaluate(sbert)
    else:
        print("  sbert: not available — pip install sentence-transformers to compare")
