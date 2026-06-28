"""Optional dense-embedding layer for Stage 2 re-ranking.

Uses a small local sentence-transformer (all-MiniLM-L6-v2, ~80 MB) loaded
from disk — zero network calls at ranking time, CPU-only. If the model
directory or the sentence-transformers package is missing, the pipeline
falls back to the BM25 + TF-IDF lexical blend and logs a warning.

One-time setup (requires internet, allowed as pre-computation per spec §10.3):

    python scripts/download_model.py
"""

from __future__ import annotations

from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[3] / "models" / "all-MiniLM-L6-v2"
MAX_CHARS = 2000  # ~512 tokens; summary + recent roles carry the signal


def embeddings_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return MODEL_DIR.exists()


def semantic_similarities(texts: list[str], query: str) -> list[float] | None:
    """Cosine similarity of each text to the query, or None if unavailable."""
    if not embeddings_available():
        return None
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(str(MODEL_DIR), device="cpu")
    docs = [t[:MAX_CHARS] for t in texts]
    doc_vecs = model.encode(docs, batch_size=64, convert_to_numpy=True,
                            normalize_embeddings=True, show_progress_bar=False)
    q_vec = model.encode([query[:MAX_CHARS]], convert_to_numpy=True,
                         normalize_embeddings=True)[0]
    sims = doc_vecs @ q_vec  # normalized → dot product is cosine
    # Min-max normalize to [0, 1] for blending with lexical scores.
    lo, hi = float(sims.min()), float(sims.max())
    if hi <= lo:
        return [0.0] * len(texts)
    return [float((s - lo) / (hi - lo)) for s in sims]
