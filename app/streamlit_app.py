"""RecruiterTwin-AI — Redrob hackathon demo dashboard.

Serves as the required sandbox: accepts a small candidate sample (JSONL or
JSON upload, or the bundled 50-candidate sample), runs the full ranking
pipeline end-to-end on CPU, and produces a downloadable ranked CSV.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from recruitertwin.ranking_engine.pipeline_v2 import rank_candidates, write_submission  # noqa: E402
from recruitertwin.ranking_engine.scorer_v2 import score_candidate  # noqa: E402
from recruitertwin.ranking_engine.reasoning import build_reasoning  # noqa: E402

st.set_page_config(page_title="RecruiterTwin-AI", page_icon="🎯", layout="wide")
st.title("RecruiterTwin-AI — Intelligent Candidate Ranking")
st.caption(
    "Senior AI Engineer @ Redrob JD · evidence-based scoring · honeypot filtering · "
    "behavioral availability · CPU-only, no LLM calls"
)

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
src = st.radio(
    "Candidate source",
    ["Bundled 50-candidate sample", "Upload JSONL / JSON (≤ 100 candidates)"],
    horizontal=True,
)

candidates: list[dict] = []
if src.startswith("Bundled"):
    sample_path = ROOT / "data" / "sample" / "redrob_sample_candidates.json"
    candidates = json.loads(sample_path.read_text())
else:
    up = st.file_uploader("Upload candidates (.jsonl or .json)", type=["jsonl", "json"])
    if up:
        raw = up.read().decode("utf-8")
        try:
            candidates = json.loads(raw)
            if isinstance(candidates, dict):
                candidates = [candidates]
        except json.JSONDecodeError:
            candidates = [json.loads(line) for line in raw.splitlines() if line.strip()]

if not candidates:
    st.info("Choose a candidate source to begin.")
    st.stop()

st.success(f"Loaded {len(candidates)} candidates.")
top_n = st.slider("Top-N to rank", 5, min(100, len(candidates)), min(20, len(candidates)))

if st.button("Run ranking pipeline", type="primary"):
    scored = []
    for c in candidates:
        r = score_candidate(c)
        scored.append(r)

    kept = [r for r in scored if not r["honeypot"]]
    pots = [r for r in scored if r["honeypot"]]
    kept.sort(key=lambda r: (-r["final_score"], r["candidate_id"]))
    top = kept[:top_n]

    rows = []
    for i, r in enumerate(top, start=1):
        rows.append({
            "rank": i,
            "candidate_id": r["candidate_id"],
            "score": r["final_score"],
            "title": r["title"],
            "company": r["company"],
            "yoe": r["yoe"],
            "location_fit": r["location_label"],
            "risk_flags": "; ".join(r["penalties"]) or "—",
            "reasoning": build_reasoning(r, i),
        })
    df = pd.DataFrame(rows)

    c1, c2, c3 = st.columns(3)
    c1.metric("Candidates scored", len(scored))
    c2.metric("Honeypots filtered", len(pots))
    c3.metric("Top score", f"{top[0]['final_score']:.3f}" if top else "—")

    st.subheader("Ranked shortlist")
    st.dataframe(df, use_container_width=True, hide_index=True)

    if pots:
        with st.expander(f"Filtered honeypots ({len(pots)})"):
            st.dataframe(pd.DataFrame([
                {"candidate_id": r["candidate_id"], "title": r["title"],
                 "flags": "; ".join(r["penalties"])} for r in pots
            ]), hide_index=True, use_container_width=True)

    buf = io.StringIO()
    df_out = df[["candidate_id", "rank", "score", "reasoning"]]
    df_out.to_csv(buf, index=False)
    st.download_button("Download submission CSV", buf.getvalue(),
                       file_name="ranked_shortlist.csv", mime="text/csv")
