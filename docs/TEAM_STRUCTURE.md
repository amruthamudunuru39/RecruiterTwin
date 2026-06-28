# Team Structure

## Overview

This project is split across three technical contributors plus one project lead.

The aim is simple: parallel execution with fewer merge conflicts and fewer handoff problems.

## Person 2: AI/ML Engineer

Focus:

- JD understanding
- role DNA extraction

Responsibilities:

- parse and understand the raw job description
- extract role, seniority, domain, responsibilities, and skill expectations
- separate must-have and nice-to-have signals
- prepare structured output for downstream ranking

Suggested tools:

- Python
- OpenAI or Gemini API
- Sentence Transformers
- Pydantic
- LangChain

Expected output:

- structured JSON in the shape described by `data/contracts/job_intelligence_output.json`

## Person 3: Ranking Engine Engineer

Focus:

- candidate processing
- ranking pipeline

Responsibilities:

- clean candidate inputs from JSON and CSV
- extract skills, experience, projects, education, and certificates
- generate embeddings and shortlist candidate pools
- combine semantic and rule-based scoring
- return ranked candidates with evidence and risk flags

Suggested tools:

- Python
- Pandas
- FAISS
- ChromaDB
- scikit-learn

Expected output:

- ranked shortlist rows aligned to `data/contracts/ranked_output_columns.csv`

## Person 4: Frontend and UX Engineer

Focus:

- dashboard
- demo flow

Responsibilities:

- build Streamlit UI
- support JD and candidate uploads
- visualize ranked candidates, hidden gems, and risks
- add CSV and PDF export
- keep the demo easy to present

Suggested tools:

- Streamlit
- Plotly
- HTML/CSS
- Pandas
- ReportLab

Expected output:

- working dashboard shell inside `app/streamlit_app.py`

## Project Lead

Focus:

- alignment
- review
- final delivery

Responsibilities:

- keep the team aligned on scope
- approve shared data contracts
- review tradeoffs across all three modules
- protect demo quality and submission clarity
- prepare the final README, walkthrough, and presentation story

## Working Agreement

- Person 2 should avoid changing output keys casually once Person 3 starts integration.
- Person 3 should avoid changing ranked output columns casually once Person 4 starts the dashboard.
- Person 4 should treat contracts as source-of-truth instead of scraping ad hoc fields.
- The project lead should review interface changes before they hit `main`.
