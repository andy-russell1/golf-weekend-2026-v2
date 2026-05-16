from __future__ import annotations

import unittest

import pandas as pd

from components.live_scoring import saved_hole_action_mode
from support.round_progress import build_round_progress


def _score_frame(completed_holes: list[int], total_holes: int = 18) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "hole": hole,
                "status": "Complete" if hole in completed_holes else "Pending",
                "player_1": 4 if hole in completed_holes else pd.NA,
                "player_2": 5 if hole in completed_holes else pd.NA,
                "player_3": 4 if hole in completed_holes else pd.NA,
                "player_4": 5 if hole in completed_holes else pd.NA,
            }
            for hole in range(1, total_holes + 1)
        ]
    )


def _score_rows(completed_holes: list[int]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for hole in completed_holes:
        for player_id in ("adam", "vincent", "alex", "andy"):
            rows.append(
                {
                    "round_id": "rolls_monmouth",
                    "hole": hole,
                    "player_id": player_id,
                    "gross_score": 4,
                    "status": "Complete",
                    "updated_at": f"2026-05-16T10:{hole:02d}:00+00:00",
                }
            )
    return rows


class RoundProgressResumeTests(unittest.TestCase):
    def test_blank_round_resumes_at_hole_1(self) -> None:
        progress = build_round_progress(_score_frame([]), holes=list(range(1, 19)), score_rows=[])

        self.assertEqual(progress["completed_count"], 0)
        self.assertEqual(progress["resume_hole"], 1)
        self.assertFalse(progress["round_complete"])

    def test_after_saving_hole_1_resumes_at_hole_2_after_reload(self) -> None:
        scores = _score_frame([1])
        rows = _score_rows([1])

        before_reload = build_round_progress(scores, holes=list(range(1, 19)), score_rows=rows)
        after_reload = build_round_progress(scores.copy(), holes=list(range(1, 19)), score_rows=list(rows))

        self.assertEqual(before_reload["completed_count"], 1)
        self.assertEqual(before_reload["resume_hole"], 2)
        self.assertEqual(after_reload["resume_hole"], 2)
        self.assertEqual(after_reload["latest_saved_hole"], 1)

    def test_saved_hole_defaults_to_protected_view_not_normal_save_next(self) -> None:
        self.assertEqual(saved_hole_action_mode(saved_hole_complete=True, edit_saved_hole=False), "protected_saved")
        self.assertEqual(saved_hole_action_mode(saved_hole_complete=True, edit_saved_hole=True), "edit_saved")
        self.assertEqual(saved_hole_action_mode(saved_hole_complete=False, edit_saved_hole=False), "normal")

    def test_after_front_nine_complete_resumes_at_hole_10(self) -> None:
        progress = build_round_progress(
            _score_frame(list(range(1, 10))),
            holes=list(range(1, 19)),
            score_rows=_score_rows(list(range(1, 10))),
        )

        self.assertEqual(progress["completed_count"], 9)
        self.assertEqual(progress["last_completed_hole"], 9)
        self.assertEqual(progress["resume_hole"], 10)
        self.assertFalse(progress["round_complete"])

    def test_complete_round_has_no_next_unsaved_hole(self) -> None:
        progress = build_round_progress(
            _score_frame(list(range(1, 19))),
            holes=list(range(1, 19)),
            score_rows=_score_rows(list(range(1, 19))),
        )

        self.assertEqual(progress["completed_count"], 18)
        self.assertEqual(progress["resume_hole"], 18)
        self.assertIsNone(progress["first_incomplete_hole"])
        self.assertTrue(progress["round_complete"])

    def test_live_hub_and_match_centre_can_share_same_progress_payload(self) -> None:
        progress = build_round_progress(_score_frame([1]), holes=list(range(1, 19)), score_rows=_score_rows([1]))
        live_scoring = dict(progress)
        weekend_hub = dict(progress)
        match_centre = dict(progress)

        self.assertEqual(live_scoring["completed_count"], weekend_hub["completed_count"])
        self.assertEqual(weekend_hub["resume_hole"], match_centre["resume_hole"])
        self.assertEqual(match_centre["latest_saved_hole"], 1)


if __name__ == "__main__":
    unittest.main()
