# Architecture Blueprint

## Purpose

This architecture is designed to let three contributors work in parallel without waiting on each other for every change.

The repo is split into three workstreams:

1. job understanding
2. ranking and shortlist generation
3. recruiter-facing dashboard and exports

## High-Level Flow

```text
Raw Job Description
    ->
Person 2 module: Job Intelligence
    ->
Structured Role DNA JSON
    ->
Person 3 module: Ranking Engine
    ->
Ranked Candidate Output
    ->
Person 4 module: Frontend and UX
    ->
Dashboard, insights, CSV/PDF export
```

## Workstream Boundaries

### Person 2: Job Intelligence

Folder:

- `src/recruitertwin/job_intelligence/`

Input:

- raw job description text

Output:

- structured JSON with role, seniority, domain, must-have skills, nice-to-have skills, responsibilities, and success traits

Main responsibility:

- make the job understandable to downstream systems

### Person 3: Ranking Engine

Folder:

- `src/recruitertwin/ranking_engine/`
- `submission/`

Input:

- structured role-DNA JSON
- candidate profiles from JSON or CSV

Output:

- ranked shortlist rows with score, rank, key factors, and risk flags

Main responsibility:

- turn candidate data into a useful shortlist

### Person 4: Frontend and UX

Folder:

- `app/`

Input:

- job upload
- candidate upload
- ranked output from the ranking engine

Output:

- recruiter-friendly dashboard
- visual insights
- CSV/PDF export flow

Main responsibility:

- make the system easy to demo and easy to understand

## Shared Contracts

The most important integration points are the data contracts.

### Contract A: Job Intelligence Output

Stored at:

- `data/contracts/job_intelligence_output.json`

Owned by:

- Person 2

Consumed by:

- Person 3

### Contract B: Ranked Output Columns

Stored at:

- `data/contracts/ranked_output_columns.csv`

Owned by:

- Person 3

Consumed by:

- Person 4

## Starter Implementation Notes

- `src/recruitertwin/ranker.py` is kept as a baseline reference, not as the final architecture.
- The new team folders are the preferred path for future work.
- The baseline script in `scripts/generate_shortlist.py` helps the repo stay runnable while the team builds the real pipeline.

## Integration Sequence

1. Lock the job-intelligence output shape
2. Connect ranking-engine ingestion to that shape
3. Stabilize ranked output columns
4. Bind the dashboard to the ranked output
5. Add export and polishing passes

## Project Lead Checklist

Before merging work across contributors, verify:

- Person 2 did not change output keys without notice
- Person 3 did not change ranked output columns without notice
- Person 4 is not depending on unstable field names
- the demo still runs from end to end
