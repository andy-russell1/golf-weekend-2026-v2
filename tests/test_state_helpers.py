from __future__ import annotations

import unittest

import pandas as pd

from components.live_scoring import _player_id_validation_error as live_player_id_validation_error
from components.score_tracker import _changed_scorecard_holes, _invalid_complete_holes
from support.google_sheets import GoogleSheetsError
from support.state_helpers import _score_rows_to_round_frame, duplicate_score_identities, verify_scores_for_hole


class StateHelperTests(unittest.TestCase):
    def test_score_rows_bind_to_runtime_player_ids_not_default_names(self) -> None:
        rows = [
            {
                "round_id": "R1",
                "hole": 1,
                "player_id": "captain",
                "gross_score": 5,
                "status": "Complete",
                "updated_at": "2026-05-16T10:01:00+00:00",
            },
            {
                "round_id": "R1",
                "hole": 1,
                "player_id": "alex",
                "gross_score": 4,
                "status": "Complete",
                "updated_at": "2026-05-16T10:01:00+00:00",
            },
            {
                "round_id": "R1",
                "hole": 1,
                "player_id": "andy",
                "gross_score": 3,
                "status": "Complete",
                "updated_at": "2026-05-16T10:01:00+00:00",
            },
        ]

        frame = _score_rows_to_round_frame(
            rows,
            holes=[1],
            format_name="4-Ball",
            player_ids=["captain", "wingman", "alex", "andy"],
        )
        row = frame.iloc[0]

        self.assertEqual(row["player_1"], 5)
        self.assertTrue(pd.isna(row["player_2"]))
        self.assertEqual(row["player_3"], 4)
        self.assertEqual(row["player_4"], 3)
        self.assertEqual(row["status"], "In Progress")

    def test_score_rows_use_latest_duplicate_for_same_hole_player(self) -> None:
        rows = [
            {
                "round_id": "R1",
                "hole": 1,
                "player_id": "adam",
                "gross_score": 4,
                "status": "Complete",
                "updated_at": "2026-05-16T10:01:00+00:00",
            },
            {
                "round_id": "R1",
                "hole": 1,
                "player_id": "adam",
                "gross_score": 7,
                "status": "Complete",
                "updated_at": "2026-05-16T10:02:00+00:00",
            },
            {
                "round_id": "R1",
                "hole": 1,
                "player_id": "vincent",
                "gross_score": 5,
                "status": "Complete",
                "updated_at": "2026-05-16T10:02:00+00:00",
            },
            {
                "round_id": "R1",
                "hole": 1,
                "player_id": "alex",
                "gross_score": 4,
                "status": "Complete",
                "updated_at": "2026-05-16T10:02:00+00:00",
            },
            {
                "round_id": "R1",
                "hole": 1,
                "player_id": "andy",
                "gross_score": 3,
                "status": "Complete",
                "updated_at": "2026-05-16T10:02:00+00:00",
            },
        ]

        frame = _score_rows_to_round_frame(rows, holes=[1], format_name="4-Ball", player_ids=["adam", "vincent", "alex", "andy"])

        self.assertEqual(frame.iloc[0]["player_1"], 7)
        self.assertEqual(frame.iloc[0]["status"], "Complete")

    def test_score_rows_without_runtime_player_ids_stay_blank(self) -> None:
        rows = [
            {
                "round_id": "R1",
                "hole": 1,
                "player_id": "adam",
                "gross_score": 4,
                "status": "Complete",
                "updated_at": "2026-05-16T10:01:00+00:00",
            },
        ]

        frame = _score_rows_to_round_frame(rows, holes=[1], format_name="4-Ball", player_ids=[])

        self.assertEqual(frame.iloc[0]["status"], "Pending")
        self.assertTrue(pd.isna(frame.iloc[0]["player_1"]))

    def test_changed_scorecard_holes_only_reports_edited_rows(self) -> None:
        before = pd.DataFrame(
            [
                {"hole": 1, "status": "Complete", "player_1": 4, "player_2": 5},
                {"hole": 2, "status": "Pending", "player_1": pd.NA, "player_2": pd.NA},
            ]
        )
        after = pd.DataFrame(
            [
                {"hole": 1, "status": "Complete", "player_1": 4, "player_2": 6},
                {"hole": 2, "status": "Pending", "player_1": pd.NA, "player_2": pd.NA},
            ]
        )

        self.assertEqual(_changed_scorecard_holes(before, after, ["player_1", "player_2"]), [1])

    def test_invalid_complete_holes_reject_blank_scores(self) -> None:
        scores = pd.DataFrame(
            [
                {"hole": 1, "status": "Complete", "player_1": 4, "player_2": pd.NA},
                {"hole": 2, "status": "In Progress", "player_1": 4, "player_2": pd.NA},
            ]
        )

        self.assertEqual(_invalid_complete_holes(scores, ["player_1", "player_2"]), [1])

    def test_player_id_validation_rejects_blank_and_duplicate_ids(self) -> None:
        self.assertIn("stable player ID", live_player_id_validation_error(["adam", "", "alex", "andy"]))
        self.assertIn("unique", live_player_id_validation_error(["adam", "ADAM", "alex", "andy"]))
        self.assertEqual(live_player_id_validation_error(["adam", "vincent", "alex", "andy"]), "")

    def test_verify_scores_for_hole_detects_mismatched_saved_rows(self) -> None:
        from unittest.mock import patch

        expected_rows = [{"player_id": "adam", "gross_score": 4, "status": "Complete"}]
        loaded_rows = [{"round_id": "R1", "hole": 1, "player_id": "adam", "gross_score": 5, "status": "Complete"}]

        with (
            patch("support.state_helpers.persistence_snapshot", lambda interactive=False: {"mode": "sheets", "scores_version": "test"}),
            patch("support.state_helpers.google_sheets.load_scores", lambda round_id, version: loaded_rows),
        ):
            with self.assertRaisesRegex(GoogleSheetsError, "only 0 of 1 expected scores"):
                verify_scores_for_hole("R1", 1, expected_rows)

    def test_verify_scores_for_hole_confirms_successful_readback(self) -> None:
        from unittest.mock import patch

        expected_rows = [
            {"player_id": "adam", "gross_score": 4, "status": "Complete"},
            {"player_id": "vincent", "gross_score": 5, "status": "Complete"},
        ]
        loaded_rows = [
            {
                "round_id": "R1",
                "hole": 1,
                "player_id": "adam",
                "gross_score": "4",
                "status": "Complete",
                "updated_at": "2026-05-16T10:01:00+00:00",
            },
            {
                "round_id": "R1",
                "hole": 1,
                "player_id": "vincent",
                "gross_score": 5,
                "status": "Complete",
                "updated_at": "2026-05-16T10:02:00+00:00",
            },
        ]

        with (
            patch("support.state_helpers.persistence_snapshot", lambda interactive=False: {"mode": "sheets", "scores_version": "test"}),
            patch("support.state_helpers.google_sheets.load_scores", lambda round_id, version: loaded_rows),
        ):
            result = verify_scores_for_hole("R1", 1, expected_rows)

        self.assertEqual(result.confirmed_count, 2)
        self.assertEqual(result.expected_count, 2)
        self.assertEqual(result.verified_at.isoformat(), "2026-05-16T10:02:00+00:00")

    def test_verify_scores_for_hole_reports_partial_write_failure(self) -> None:
        from unittest.mock import patch

        expected_rows = [
            {"player_id": "adam", "gross_score": 4, "status": "Complete"},
            {"player_id": "vincent", "gross_score": 5, "status": "Complete"},
            {"player_id": "alex", "gross_score": 4, "status": "Complete"},
            {"player_id": "andy", "gross_score": 3, "status": "Complete"},
        ]
        loaded_rows = [
            {"round_id": "R1", "hole": 1, "player_id": "adam", "gross_score": 4, "status": "Complete"},
            {"round_id": "R1", "hole": 1, "player_id": "vincent", "gross_score": 5, "status": "Complete"},
        ]

        with (
            patch("support.state_helpers.persistence_snapshot", lambda interactive=False: {"mode": "sheets", "scores_version": "test"}),
            patch("support.state_helpers.google_sheets.load_scores", lambda round_id, version: loaded_rows),
        ):
            with self.assertRaisesRegex(
                GoogleSheetsError,
                "Save verification failed: only 2 of 4 expected scores were confirmed in Google Sheets.",
            ):
                verify_scores_for_hole("R1", 1, expected_rows)

    def test_duplicate_score_identities_reports_canonical_duplicate_rows(self) -> None:
        rows = [
            {"round_id": "R1", "hole": 1, "player_id": "Adam", "updated_at": "2026-05-16T10:01:00+00:00"},
            {"round_id": "R1", "hole": 1, "player_id": "adam", "updated_at": "2026-05-16T10:02:00+00:00"},
            {"round_id": "R1", "hole": 2, "player_id": "adam", "updated_at": "2026-05-16T10:02:00+00:00"},
        ]

        duplicates = duplicate_score_identities(rows)

        self.assertEqual(duplicates, [{"round_id": "R1", "hole": 1, "player_id": "adam", "count": 2}])


if __name__ == "__main__":
    unittest.main()
