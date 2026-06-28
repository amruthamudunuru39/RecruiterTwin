# Team Workflow

## Goal

This workflow is meant to keep the team moving quickly without creating merge confusion.

## Recommended Flow

1. Pull latest `main`
2. Create a feature branch in your lane
3. Make a focused change
4. Run the basic local checks
5. Open a pull request with the template
6. Get review from the project lead if contracts or architecture changed
7. Merge once the change is stable

## Safe Parallel Work

Best parallel split for this repo:

- Person 2 works mainly in `src/recruitertwin/job_intelligence/`
- Person 3 works mainly in `src/recruitertwin/ranking_engine/`
- Person 4 works mainly in `app/`

Shared caution zones:

- `data/contracts/`
- `submission/`
- `README.md`
- `docs/ARCHITECTURE.md`

## Merge Priority

When multiple branches are in progress, prefer this order:

1. contract-defining changes
2. ranking integration changes
3. UI binding changes
4. polish and presentation changes

## When To Ask The Project Lead

Ask for review before merging if:

- a shared contract changed
- the output format changed
- the demo flow changed
- one workstream now depends on another workstream differently
