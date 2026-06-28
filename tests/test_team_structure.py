from __future__ import annotations

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class TeamStructureTestCase(unittest.TestCase):
    def test_team_scaffold_paths_exist(self) -> None:
        expected_paths = [
            REPO_ROOT / "app" / "streamlit_app.py",
            REPO_ROOT / "docs" / "TEAM_STRUCTURE.md",
            REPO_ROOT / "data" / "contracts" / "job_intelligence_output.json",
            REPO_ROOT / "data" / "contracts" / "ranked_output_columns.csv",
            REPO_ROOT / "src" / "recruitertwin" / "job_intelligence" / "extractor.py",
            REPO_ROOT / "src" / "recruitertwin" / "ranking_engine" / "pipeline.py",
        ]
        for path in expected_paths:
            self.assertTrue(path.exists(), f"Missing expected scaffold path: {path}")


if __name__ == "__main__":
    unittest.main()
