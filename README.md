<h1 align="center">RecruiterTwin-AI</h1>

<p align="center">
  Intelligent Candidate Discovery & Ranking — Redrob Hackathon submission.
</p>

<p align="center">
  Ranks 100,000 candidates against the <strong>Senior AI Engineer — Founding Team</strong> JD
  in ~65 seconds on a laptop CPU. No GPU, no network, no LLM API calls during ranking.
</p>

---

## TL;DR — reproduce the submission

```bash
pip install -r requirements.txt
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

That single command (spec §10.3) streams the full candidate pool, ranks it, and writes
the top-100 CSV in `candidate_id,rank,score,reasoning` format. Accepts `.jsonl` or
`.jsonl.gz`. Validate before uploading:

```bash
python validate_submission.py submission.csv   # validator from the hackathon bundle
```

**Measured performance:** 100,000 candidates in ~65 s, < 2 GB RAM, single CPU —
comfortably inside the 5-min / 16 GB budget.

## Why this architecture

The JD itself warns that keyword matching is a planted trap. So the system is built
around one principle: **trust what the career history evidences, not what the skills
list claims.** Three layers, applied in order of trust:

### 1. Evidence-based JD fit (primary signal)

`src/recruitertwin/job_intelligence/jd_profile.py` encodes the JD as concept lexicons
for its four hard must-haves — embeddings/retrieval, vector/hybrid search infra,
shipped ranking systems, and evaluation rigor (NDCG/MRR/A-B) — plus LLM depth and
production engineering. These are matched against **narrative text only** (career
descriptions, summary, headline, titles), with diminishing-returns saturation so one
buzzword ≠ deep experience.

The JD's explicit disqualifiers are modeled directly:

- **Keyword stuffers** — concepts present in the skills list but absent from every
  career description → heavy penalty. A "Marketing Manager" with a perfect AI skill
  list is not a fit, exactly as the JD says.
- **Research-only careers** (academic labs, research titles across all roles) → near-zero.
- **Consulting-firms-only careers** (TCS/Infosys/Wipro/Accenture/…) → heavy penalty;
  currently-at-consulting with prior product experience is fine, per the JD.
- **CV/speech/robotics specialists** without NLP/IR exposure → penalized.
- **Title-chasers / job-hoppers** (avg completed stint < 16 months) → penalized.
- Experience band centered on the JD's ideal 6–8 yrs (soft falloff outside 5–9).
- Location logic: Pune/Noida > Tier-1 India > India+relocate > outside India.

### 2. Honeypot / plausibility filter

`features.honeypot_flags()` removes internally impossible profiles before ranking:

- a skill used longer than the candidate's entire career
- multiple "expert" proficiencies with ~zero months of use
- career-history months wildly inconsistent with claimed years of experience
- a single role longer than the whole career; stated durations contradicting the
  start/end dates; future start dates

Flagged candidates are forced to score 0 and can never enter the top 100
(spec §7 disqualifies > 10% honeypots; our top-100 spot checks show zero flags).

### 3. Behavioral availability multiplier (Redrob signals)

A perfect-on-paper candidate who hasn't logged in for 6 months with a 5% response
rate is not hireable. The 23 `redrob_signals` are folded into a 0.45–1.10 multiplier
driven by activity recency, recruiter response rate, open-to-work, interview
completion, notice period, and verification status.

### Two-stage pipeline (latency–quality tradeoff)

```
Stage 1 (recall):     stream all 100K candidates → cheap evidence score
                      → keep top-1500 shortlist via a heap (O(N log K))
Stage 2 (precision):  hybrid re-rank of the shortlist —
                      dense:  MiniLM embeddings (semantic meaning, optional)
                      sparse: BM25 Okapi (exact terms, length-normalized)
                              + TF-IDF 1-2 grams (phrase matching)
                      → blended re-rank → top-100 + reasoning generation
```

BM25+TF-IDF on the shortlist (rather than embedding all 100K) is a deliberate
latency-quality tradeoff: the evidence layer is already high-recall for this JD, and
the lexical re-ranker only needs to refine ordering within the shortlist. BM25
contributes term saturation and document-length normalization (short vs long
profiles are compared fairly); TF-IDF bigrams add phrase-level matching like
"hybrid search" and "learning to rank". The two are min-max normalized and
blended 60/40 when running lexical-only.

**Dense embedding layer (optional, recommended).** Run once with internet:

```bash
python scripts/download_model.py   # saves all-MiniLM-L6-v2 (~80 MB) to ./models/
```

Afterwards ranking loads the model from disk — zero network at ranking time,
CPU-only, applied to the 1,500-candidate shortlist (not all 100K) to stay
inside the 5-minute budget. Blend becomes 0.50·embedding + 0.30·BM25 +
0.20·TF-IDF. This catches "plain-language Tier 5" candidates who describe
ranking/retrieval work without buzzwords — dense for meaning, sparse for
exact terms, rules for constraints the text can't express. If the model
folder is missing, the pipeline automatically falls back to BM25+TF-IDF.

#

### Optional dense embedding layer (recommended)

One-time setup with internet access (pre-computation is allowed by spec §10.3 —
only the ranking step must be offline):

```bash
pip install sentence-transformers
python scripts/download_model.py    # saves all-MiniLM-L6-v2 (~80 MB) to ./models/
```

At ranking time the model loads from disk with zero network calls and runs on
CPU over the 1,500-candidate shortlist only (~60–90 s extra). It catches
plain-language strong candidates — engineers who built ranking/retrieval systems
without using buzzwords — which lexical matching misses. Blend with the model
present: 0.50·embedding + 0.30·BM25 + 0.20·TF-IDF. If the model folder is
missing, the pipeline automatically falls back to the BM25+TF-IDF blend with a
logged warning (nothing breaks). The interview-ready rationale: dense for
meaning, sparse for exact technical terms, rules for constraints text can't
express.

## Reasoning generation

`reasoning.py` composes 1–2 sentence justifications **only from extracted profile
facts** (title, years, evidenced concept areas, response rate, notice period,
location, flagged concerns) with deterministic template variation and tone matched
to rank — directly targeting the six Stage-4 review checks (specific facts, JD
connection, honest concerns, no hallucination, variation, rank consistency).

## Repository layout

```text
RecruiterTwin-AI/
|-- rank.py                          # single-command submission reproducer
|-- app/streamlit_app.py             # sandbox demo dashboard (Streamlit)
|-- src/recruitertwin/
|   |-- job_intelligence/
|   |   `-- jd_profile.py            # JD-as-code: lexicons, disqualifiers, logistics
|   `-- ranking_engine/
|       |-- features.py              # evidence, career shape, honeypots, behavior
|       |-- scorer_v2.py             # blended scoring + penalty multipliers
|       |-- pipeline_v2.py           # two-stage streaming pipeline + CSV writer
|       |-- reasoning.py             # rank-consistent reasoning generator
|       |-- scorer.py / pipeline.py  # legacy hooks delegating to v2
|-- data/sample/redrob_sample_candidates.json   # 50-candidate sample for the demo
|-- submission/team_recruitertwin.csv           # generated top-100 submission
|-- tests/                           # unit tests for traps, honeypots, reasoning
|-- docs/                            # architecture & workflow notes
`-- requirements.txt
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Dependencies are intentionally minimal: `scikit-learn` (TF-IDF), `rank-bm25` (BM25 Okapi), `pandas`,
`streamlit` + `plotly` (demo only). The ranking step itself needs only
scikit-learn and the standard library.

## Run the sandbox demo

```bash
streamlit run app/streamlit_app.py
```

The dashboard accepts a small candidate sample (bundled 50-candidate file or a
JSONL/JSON upload of ≤ 100 candidates), runs the full pipeline end-to-end on CPU,
shows the ranked shortlist with risk flags and filtered honeypots, and exports the
ranked CSV — satisfying the spec §10.5 sandbox requirements. Deploy as-is to
Streamlit Cloud or HuggingFace Spaces (free tier).

## Run the tests

```bash
python -m unittest discover -s tests -v
```

Tests cover: strong-candidate scoring, keyword-stuffer penalty, honeypot exclusion,
behavioral down-weighting, consulting-only penalty, reasoning specificity/variation,
and a full pass over the bundled sample.

## Compute-constraint compliance (spec §3)

| Constraint | Limit | This system |
|---|---|---|
| Runtime | ≤ 5 min | ~70 s for 100K candidates |
| Memory | ≤ 16 GB | < 2 GB (streaming, top-K heap) |
| Compute | CPU only | CPU only |
| Network | Off | Zero external calls |
| Disk | ≤ 5 GB | No intermediate state |

## AI tools declaration

Claude (Anthropic) was used as a development assistant for code drafting and
documentation. All architecture decisions, JD interpretation, trap analysis, and
validation were human-reviewed; the ranking step contains no LLM calls.

## Submission checklist

- [x] `submission/team_recruitertwin.csv` — validated against `validate_submission.py`
- [x] Single reproduction command documented above
- [x] `requirements.txt` with pinned minimums
- [x] `submission_metadata.yaml` at repo root (fill in team details)
- [ ] Push to GitHub + deploy `app/streamlit_app.py` to Streamlit Cloud / HF Spaces
- [ ] Rename CSV to your registered participant ID before uploading
