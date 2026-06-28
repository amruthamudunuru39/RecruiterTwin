# Contributing to RecruiterTwin-AI

This project is being built by a small hackathon team, so the workflow needs to stay simple, fast, and predictable.

The main rule is this:

- work inside your lane
- do not break shared contracts without discussion
- open small, reviewable pull requests

## Team Lanes

### Person 2: JD Intelligence

Primary folder:

- `src/recruitertwin/job_intelligence/`

You own:

- job description parsing
- role DNA extraction
- output shape for structured JD understanding

Before changing output keys in `data/contracts/job_intelligence_output.json`, align with Person 3 and the project lead.

### Person 3: Ranking Engine

Primary folders:

- `src/recruitertwin/ranking_engine/`
- `submission/`

You own:

- candidate normalization
- retrieval and ranking logic
- shortlist scoring
- ranked output schema

Before changing ranked output columns in `data/contracts/ranked_output_columns.csv`, align with Person 4 and the project lead.

### Person 4: Frontend and UX

Primary folder:

- `app/`

You own:

- dashboard flow
- upload flow
- results visualization
- export actions

Avoid depending on unstable fields that are not part of the shared contracts.

### Project Lead

The project lead should review:

- shared contract changes
- large architecture changes
- demo-impacting UI changes
- anything that affects final submission structure

## Branch Naming

Use short, obvious branch names.

Recommended patterns:

- `feature/jd-intelligence-*`
- `feature/ranking-engine-*`
- `feature/frontend-dashboard-*`
- `fix/*`
- `docs/*`

Examples:

- `feature/jd-intelligence-role-parser`
- `feature/ranking-engine-hybrid-scoring`
- `feature/frontend-dashboard-results-table`

## Pull Request Rules

1. Keep each PR focused on one topic.
2. Do not mix frontend, ranking logic, and JD parsing in one PR unless it is a true integration PR.
3. Include a short summary of what changed.
4. Mention any contract changes clearly.
5. Mention what you tested locally.
6. Add screenshots for UI changes.

## Before Opening a PR

Please do these checks first:

- run `python -m unittest discover -s tests`
- if you changed ranking logic, run `python scripts/generate_shortlist.py`
- if you changed the dashboard, run `streamlit run app/streamlit_app.py`
- make sure sample files and docs still make sense

## Shared Contract Rules

These files are the current handshake between contributors:

- `data/contracts/job_intelligence_output.json`
- `data/contracts/ranked_output_columns.csv`

Do not change them casually.

If you need to change them:

1. explain why in the PR
2. tag the affected teammate
3. update docs if the change is user-facing or architectural

## Commit Style

Use plain commit messages that explain the change clearly.

Good examples:

- `Add JD extraction placeholder pipeline`
- `Add ranking engine scoring hooks`
- `Build dashboard upload shell`
- `Update ranked output contract`

## Demo Readiness

Closer to submission, prioritize changes that improve:

- end-to-end flow
- stability
- clarity of ranked output
- ease of presentation

Avoid large refactors right before demo day unless they remove a serious blocker.
