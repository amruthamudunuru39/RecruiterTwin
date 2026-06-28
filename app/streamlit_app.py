"""RecruiterTwin-AI — Redrob hackathon demo dashboard.

Serves as the required sandbox: accepts a candidate file (JSONL, JSON array,
or gzipped JSONL upload, or the bundled 50-candidate sample), runs the full
two-stage ranking pipeline end-to-end on CPU, and produces a downloadable
ranked CSV.

Large uploads (up to 512 MB) are streamed record-by-record and reduced through
a bounded top-K heap, so peak memory stays flat regardless of file size — the
whole file is never loaded into RAM at once.
"""

from __future__ import annotations

import gzip
import io
import json
import sys
from pathlib import Path
from typing import Iterator

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from recruitertwin.ranking_engine.pipeline_v2 import rank_from_iter  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB hard ceiling (config allows 512)
SHORTLIST_SIZE = 1500                 # bounded heap kept in memory (Stage 1)
MEMORY_WARN_MB = 3000                 # warn if RSS climbs above ~3 GB

st.set_page_config(page_title="RecruiterTwin-AI", page_icon="🎯", layout="wide")
st.title("RecruiterTwin-AI — Intelligent Candidate Ranking")
st.caption(
    "Senior AI Engineer @ Redrob JD · evidence-based scoring · honeypot filtering · "
    "behavioral availability · CPU-only, no LLM calls"
)


# ---------------------------------------------------------------------------
# Streaming reader — never loads the whole file into RAM
# ---------------------------------------------------------------------------
def _iter_jsonl(text_stream) -> Iterator[dict]:
    """Yield one parsed object per non-blank line of a text stream."""
    for line in text_stream:
        line = line.strip()
        if line:
            yield json.loads(line)


def stream_records(uploaded_file) -> Iterator[dict]:
    """Stream-parse a JSONL / JSON-array / gzipped-JSONL upload lazily.

    A JSON array is parsed incrementally with ``ijson`` (no full-file load);
    line-delimited JSON is iterated line-by-line. Both paths yield dicts one at
    a time so the caller's bounded heap is the only thing that grows.
    """
    name = (uploaded_file.name or "").lower()
    uploaded_file.seek(0)

    if name.endswith(".gz"):
        text = io.TextIOWrapper(gzip.GzipFile(fileobj=uploaded_file), encoding="utf-8")
        yield from _iter_jsonl(text)
        return

    # Peek the first non-whitespace character: '[' → JSON array, else JSONL.
    head = uploaded_file.read(64)
    uploaded_file.seek(0)
    if isinstance(head, bytes):
        head = head.decode("utf-8", "ignore")
    first = head.lstrip()[:1]

    if first == "[":
        try:
            import ijson
        except ImportError:
            # Fallback only safe for smaller arrays — surfaced to the user below.
            st.warning(
                "`ijson` not installed — falling back to a full in-memory parse "
                "for this JSON array. Install `ijson` (see requirements.txt) or "
                "use JSONL for large files."
            )
            data = json.load(uploaded_file)
            yield from (data if isinstance(data, list) else [data])
            return
        for record in ijson.items(uploaded_file, "item"):
            yield record
    else:
        text = io.TextIOWrapper(uploaded_file, encoding="utf-8")
        yield from _iter_jsonl(text)


def check_memory(label: str = "") -> float | None:
    """Best-effort RSS check; warns past MEMORY_WARN_MB. No-op without psutil."""
    try:
        import os

        import psutil
    except ImportError:
        return None
    mem_mb = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
    if mem_mb > MEMORY_WARN_MB:
        st.warning(
            f"High memory usage at {label or 'checkpoint'}: {mem_mb:.0f} MB — "
            "prefer JSONL for very large uploads."
        )
    return mem_mb


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
src = st.radio(
    "Candidate source",
    ["Bundled 50-candidate sample", "Upload JSONL / JSON / JSONL.gz (up to 500 MB)"],
    horizontal=True,
)

# `make_stream` returns a fresh single-use iterator each run; `source_bytes` is
# the upload's byte size (for byte-based progress) or None for the sample.
make_stream = None
source_bytes: int | None = None

if src.startswith("Bundled"):
    sample_path = ROOT / "data" / "sample" / "redrob_sample_candidates.json"

    def make_stream() -> Iterator[dict]:
        data = json.loads(sample_path.read_text())
        yield from (data if isinstance(data, list) else [data])
else:
    up = st.file_uploader(
        "Upload candidates (.jsonl, .json, .jsonl.gz)",
        type=["jsonl", "json", "gz"],
    )
    if up is not None:
        file_size_mb = up.size / (1024 * 1024)
        st.caption(f"File size: {file_size_mb:.1f} MB · `{up.name}`")

        if up.size > MAX_UPLOAD_BYTES:
            st.error(f"File too large ({file_size_mb:.0f} MB). Maximum is 500 MB.")
            st.stop()

        if up.name.lower().endswith(".json") and file_size_mb > 50:
            st.warning(
                "Large JSON **arrays** stream slower than JSONL. Consider converting "
                "to JSONL — e.g.:\n\n"
                '```\npython -c "import sys,json; '
                "[print(json.dumps(r)) for r in json.load(open(sys.argv[1]))]\" "
                "file.json > file.jsonl\n```"
            )

        source_bytes = up.size

        def make_stream() -> Iterator[dict]:
            return stream_records(up)

if make_stream is None:
    st.info("Choose a candidate source to begin.")
    st.stop()

top_n = st.slider("Top-N to rank", 5, 100, 20)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if st.button("Run ranking pipeline", type="primary"):
    progress_bar = st.progress(0.0, text="Starting…")
    status_text = st.empty()

    def progress_cb(scanned: int, honeypots: int, shortlist_len: int) -> None:
        # Byte-based fraction when we know the file size (works for gzip too,
        # since we measure compressed bytes consumed); otherwise show activity.
        frac = 0.0
        if source_bytes:
            try:
                frac = min(up.tell() / source_bytes, 0.99)
            except Exception:
                frac = min(scanned / 100_000, 0.99)
        else:
            frac = min(scanned / 100_000, 0.99)
        progress_bar.progress(
            frac, text=f"Stage 1 — scanning… {scanned:,} candidates"
        )
        status_text.markdown(
            f"**Scanned:** {scanned:,} · **Honeypots filtered:** {honeypots:,} · "
            f"**Shortlist held:** {shortlist_len:,}/{SHORTLIST_SIZE:,}"
        )

    def stage2_cb(n_docs: int) -> None:
        status_text.markdown(
            f"**Stage 2** — embedded {n_docs:,} shortlisted candidates "
            "(BM25 + TF-IDF + dense re-rank)…"
        )

    with st.spinner("Ranking… Stage 1 streaming scan, then Stage 2 re-rank"):
        results, stats = rank_from_iter(
            make_stream(),
            top_n=top_n,
            shortlist_size=SHORTLIST_SIZE,
            progress_cb=progress_cb,
            stage2_cb=stage2_cb,
            verbose=False,
        )
    check_memory("after ranking")

    progress_bar.progress(
        1.0, text=f"Complete — {stats['scanned']:,} candidates scanned"
    )
    status_text.empty()

    if not results:
        st.warning(
            f"No rankable candidates (scanned {stats['scanned']:,}, "
            f"{stats['honeypots']:,} honeypots filtered)."
        )
        st.stop()

    rows = []
    for r in results:
        d = r["_debug"]
        rows.append({
            "rank": r["rank"],
            "candidate_id": r["candidate_id"],
            "score": r["score"],
            "title": d.get("title", ""),
            "company": d.get("company", ""),
            "yoe": d.get("yoe", ""),
            "location_fit": d.get("location_label", ""),
            "risk_flags": "; ".join(d.get("penalties", [])) or "—",
            "reasoning": r["reasoning"],
        })
    df = pd.DataFrame(rows)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Candidates scanned", f"{stats['scanned']:,}")
    c2.metric("Honeypots filtered", f"{stats['honeypots']:,}")
    c3.metric("Shortlisted", f"{stats['shortlist']:,}")
    c4.metric("Top score", f"{results[0]['score']:.3f}")

    st.caption(
        f"Stage 1: {stats.get('stage1_seconds', '—')}s · "
        f"Stage 2: {stats.get('stage2_seconds', '—')}s · "
        f"total {stats.get('seconds', '—')}s"
    )

    st.subheader("Ranked shortlist")
    st.dataframe(df, use_container_width=True, hide_index=True)

    sample = stats.get("honeypot_sample") or []
    if sample:
        cap_note = (
            f" (showing first {len(sample)} of {stats['honeypots']:,})"
            if stats["honeypots"] > len(sample) else ""
        )
        with st.expander(f"Filtered honeypots{cap_note}"):
            st.dataframe(pd.DataFrame(sample), hide_index=True, use_container_width=True)

    buf = io.StringIO()
    df[["candidate_id", "rank", "score", "reasoning"]].to_csv(buf, index=False)
    st.download_button(
        "Download submission CSV", buf.getvalue(),
        file_name="ranked_shortlist.csv", mime="text/csv",
    )
