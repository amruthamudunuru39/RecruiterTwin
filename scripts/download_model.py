#!/usr/bin/env python3
"""One-time precompute step: download the local embedding model.

Run this ONCE with internet access, before ranking:

    python scripts/download_model.py

It saves sentence-transformers/all-MiniLM-L6-v2 (~80 MB) to ./models/minilm.
The ranking step then loads it from disk with ZERO network calls, keeping the
submission compliant with the no-network constraint (spec allows
pre-computation outside the 5-minute window).
"""
from __future__ import annotations

from pathlib import Path

from sentence_transformers import SentenceTransformer

TARGET = Path(__file__).resolve().parents[1] / "models" / "all-MiniLM-L6-v2"

if __name__ == "__main__":
    print("Downloading sentence-transformers/all-MiniLM-L6-v2 ...")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(TARGET))
    print(f"Saved to {TARGET}")
