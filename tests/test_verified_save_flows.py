from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from components.live_scoring import _persist_live_scores
from components.score_tracker import _save_verified_scorecard_changes
from support.state_helpers import ScoreVerificationResult


def _round_runtime() -> dict[str, object]:
    return {
        "round_id": "R1",
        "format_name": "4-Ball",
        "scoring_mode": "net",
        "allowance_percent": 100,
        "scramble_mode": "",
        "stableford_mode": "",
        "handicap_allocation": "",
    }


def _round_state() -> dict[str, object]:
    return {
        "player_ids": ["adam", "vincent", "alex", "andy"],
        "player_names": ["Adam", "Vincent", "Alex", "Andy"],
        "handicap_indexes": [1.0, 2.0, 3.0, 4.0],
    }


class VerifiedSaveFlowTests(unittest.TestCase):
    def test_update_saved_hole_verifies_persisted_edits(self) -> None:
        saved_calls: list[int] = []
        verified_payloads: list[list[dict[str, object]]] = []
        updated_scores = pd.DataFrame(
            [
                {
                    "hole": 1,
                    "status": "Complete",
                    "player_1": 6,
                    "player_2": 5,
                    "player_3": 4,
                    "player_4": 3,
                }
            ]
        )

        def fake_save_scores(
            _runtime: dict[str, object],
            hole: int,
            _scores: pd.DataFrame,
            _state: dict[str, object],
            **_kwargs: object,
        ) -> None:
            saved_calls.append(hole)

        def fake_verify(
            _round_id: str,
            hole: int,
            expected_rows: list[dict[str, object]],
            **_kwargs: object,
        ) -> ScoreVerificationResult:
            self.assertEqual(hole, 1)
            verified_payloads.append(expected_rows)
            return ScoreVerificationResult("R1", (1,), expected_count=4, confirmed_count=4, verified_at=None)

        with (
            patch("components.live_scoring.persistence_snapshot", lambda interactive=False: {"mode": "sheets", "scores_version": "test"}),
            patch("components.live_scoring.save_scores_for_hole", fake_save_scores),
            patch("components.live_scoring.verify_scores_for_hole", fake_verify),
            patch("components.live_scoring.save_result_payload", lambda _round_id, _payload, **_kwargs: None),
        ):
            _persist_live_scores(_round_runtime(), updated_scores, _round_state(), 1, {"status_text": "ok"})

        self.assertEqual(saved_calls, [1])
        self.assertEqual(verified_payloads[0][0]["player_id"], "adam")
        self.assertEqual(verified_payloads[0][0]["gross_score"], 6)
        self.assertEqual(verified_payloads[0][0]["status"], "Complete")

    def test_full_scorecard_edit_verifies_only_changed_holes(self) -> None:
        saved_holes: list[int] = []
        verified_holes: list[int] = []
        persisted = pd.DataFrame(
            [
                {"hole": 1, "status": "Complete", "player_1": 4, "player_2": 5, "player_3": 4, "player_4": 3},
                {"hole": 2, "status": "Complete", "player_1": 6, "player_2": 5, "player_3": 4, "player_4": 4},
            ]
        )

        def fake_save_scores(_runtime: dict[str, object], hole: int, _scores: pd.DataFrame, _state: dict[str, object]) -> None:
            saved_holes.append(hole)

        def fake_verify(_round_id: str, hole: int, _expected_rows: list[dict[str, object]]) -> ScoreVerificationResult:
            verified_holes.append(hole)
            return ScoreVerificationResult("R1", (hole,), expected_count=4, confirmed_count=4, verified_at=None)

        with (
            patch("components.score_tracker.save_scores_for_hole", fake_save_scores),
            patch("components.score_tracker.verify_scores_for_hole", fake_verify),
            patch("components.score_tracker.compute_round_results", lambda **_kwargs: {"status_text": "ok"}),
            patch("components.score_tracker.save_result_payload", lambda _round_id, _payload: None),
        ):
            _save_verified_scorecard_changes(
                course_df=pd.DataFrame(),
                round_runtime=_round_runtime(),
                round_state=_round_state(),
                tee_rating={},
                persisted=persisted,
                changed_holes=[2],
            )

        self.assertEqual(saved_holes, [2])
        self.assertEqual(verified_holes, [2])


if __name__ == "__main__":
    unittest.main()
