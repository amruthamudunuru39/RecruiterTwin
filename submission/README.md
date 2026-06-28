# Submission artifacts

- `team_recruitertwin.csv` — top-100 ranking of the full 100K pool, produced by
  `python rank.py --candidates candidates.jsonl --out submission/team_recruitertwin.csv`
  and validated with the official `validate_submission.py` (passes).
  **Rename to your registered participant ID before uploading.**
- `ranked_shortlist.csv` — small demo output from the bundled 50-candidate sample
  (`python scripts/generate_shortlist.py`). Not the competition submission.
