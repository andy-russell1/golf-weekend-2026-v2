from __future__ import annotations

import unittest

import pandas as pd

from support.app_context import ensure_round_focus


class AppContextRegressionTests(unittest.TestCase):
    def test_ensure_round_focus_backfills_missing_key_from_context_fields(self) -> None:
        context = {
            "selected_fixture": {
                "id": "fixture-1",
                "title": "Friday Fourballs",
            },
            "round_runtime": {
                "tee_label": "White",
            },
            "round_state": {
                "active_hole": 4,
                "scores": pd.DataFrame(
                    [
                        {"hole": 1, "status": "Complete"},
                        {"hole": 2, "status": "Complete"},
                        {"hole": 3, "status": "In Progress"},
                        {"hole": 4, "status": "Pending"},
                    ]
                ),
            },
            "selected_result": {
                "status_text": "Red leads by 1",
            },
            "tee_rating": {
                "course_rating": 71.2,
            },
        }

        normalized = ensure_round_focus(context)

        self.assertIn("round_focus", normalized)
        self.assertEqual(normalized["round_focus"]["progress_text"], "2 of 4 holes saved")
        self.assertEqual(normalized["round_focus"]["status_text"], "Red leads by 1")
        self.assertEqual(normalized["round_focus"]["next_hole"], 3)
        self.assertEqual(normalized["round_focus"]["primary_page"], "pages/2_Live_Scoring.py")


if __name__ == "__main__":
    unittest.main()
