from __future__ import annotations

import json
import unittest

from domain.bonus_competitions import (
    bonus_competitions_from_json,
    bonus_competitions_to_json,
    bonus_point_rows,
    configured_bonus_competition,
    default_bonus_competitions,
    eligible_holes,
    update_bonus_winner,
)
from domain.result_serialization import summary_payload_for_storage
from domain.scoring import compute_round_results, compute_weekend_race
from domain.weekend_config import (
    FIXTURES,
    DEFAULT_WORKBOOK_NAME,
    SINGLES_MATCHUPS,
    SINGLES_MATCHUPS_SETTING_KEY,
    points_available_for_format,
    singles_matchups_from_json,
    singles_matchups_to_json,
)
from support.data_loader import get_tee_rating, load_course_data
from support.session import blank_scores


PLAYER_NAMES = ["Adam", "Vincent", "Alex", "Andy"]
PLAYER_IDS = ["adam", "vincent", "alex", "andy"]
HANDICAP_INDEXES = [12.0, 15.0, 18.0, 18.0]


def _partial_score_frame(format_name: str, holes: list[int]):
    frame = blank_scores(holes, format_name)
    sample_scores = {
        1: (4, 5, 5, 6),
        2: (5, 4, 6, 5),
        3: (3, 3, 4, 4),
    }
    for hole, scores in sample_scores.items():
        if hole not in holes:
            continue
        frame.loc[frame["hole"] == hole, "status"] = "Complete"
        for index, value in enumerate(scores, start=1):
            frame.loc[frame["hole"] == hole, f"player_{index}"] = value
    return frame


def _complete_score_frame(format_name: str, holes: list[int]):
    frame = blank_scores(holes, format_name)
    for hole in holes:
        frame.loc[frame["hole"] == hole, "status"] = "Complete"
        for index, value in enumerate((4, 5, 6, 7), start=1):
            frame.loc[frame["hole"] == hole, f"player_{index}"] = value
    return frame


class ScoringRegressionTests(unittest.TestCase):
    def test_supported_formats_generate_live_results(self) -> None:
        course_df = load_course_data("rolls_monmouth")
        tee_rating = get_tee_rating("rolls_monmouth", "White")
        holes = [int(hole) for hole in course_df["hole"].dropna().tolist()]

        self.assertFalse(course_df.empty)
        self.assertTrue(bool(tee_rating))

        for format_name in ("4-Ball", "Stroke Play", "Skins", "Singles"):
            with self.subTest(format_name=format_name):
                result = compute_round_results(
                    course_df=course_df,
                    format_name=format_name,
                    score_df=_partial_score_frame(format_name, holes),
                    player_names=PLAYER_NAMES,
                    player_ids=PLAYER_IDS,
                    handicap_indexes=HANDICAP_INDEXES,
                    tee_rating=tee_rating,
                    allowance_percent=100,
                )

                self.assertEqual(result["format_name"], format_name)
                self.assertFalse(result["summary_df"].empty)
                self.assertEqual(len(result["player_handicaps"]), 4)
                self.assertTrue(result["status_text"])

                if format_name == "4-Ball":
                    self.assertIn("match", result)
                    self.assertIn("current_status", result["match"])
                elif format_name == "Stroke Play":
                    self.assertIn("stroke_play", result)
                    self.assertIn("current_status", result["stroke_play"])
                elif format_name == "Skins":
                    self.assertIn("skins", result)
                    self.assertIn("current_status", result["skins"])
                else:
                    self.assertEqual(len(result["matches"]), 2)
                    self.assertTrue(all(match["current_status"] for match in result["matches"]))

    def test_result_storage_payloads_are_json_safe_for_supported_formats(self) -> None:
        course_df = load_course_data("rolls_monmouth")
        tee_rating = get_tee_rating("rolls_monmouth", "White")
        holes = [int(hole) for hole in course_df["hole"].dropna().tolist()]

        for format_name in ("4-Ball", "Stroke Play", "Skins", "Singles"):
            with self.subTest(format_name=format_name):
                result = compute_round_results(
                    course_df=course_df,
                    format_name=format_name,
                    score_df=_partial_score_frame(format_name, holes),
                    player_names=PLAYER_NAMES,
                    player_ids=PLAYER_IDS,
                    handicap_indexes=HANDICAP_INDEXES,
                    tee_rating=tee_rating,
                    allowance_percent=100,
                )
                payload = summary_payload_for_storage(result)

                json.dumps(payload)
                self.assertNotIn("export_bytes", payload["payload"])

    def test_singles_points_model_matches_two_parallel_matches(self) -> None:
        course_df = load_course_data("rolls_monmouth")
        tee_rating = get_tee_rating("rolls_monmouth", "White")
        holes = [int(hole) for hole in course_df["hole"].dropna().tolist()]

        result = compute_round_results(
            course_df=course_df,
            format_name="Singles",
            score_df=_complete_score_frame("Singles", holes),
            player_names=PLAYER_NAMES,
            player_ids=PLAYER_IDS,
            handicap_indexes=HANDICAP_INDEXES,
            tee_rating=tee_rating,
            allowance_percent=100,
        )

        self.assertEqual(len(result["matches"]), 2)
        self.assertEqual(points_available_for_format("Singles"), 2.0)
        self.assertAlmostEqual(sum(match["point_value"] for match in SINGLES_MATCHUPS), 2.0)
        self.assertAlmostEqual(sum(result["awarded_points"].values()), 2.0)
        self.assertAlmostEqual(sum(result["projected_points"].values()), 2.0)

    def test_custom_singles_matchups_are_used_by_scoring(self) -> None:
        course_df = load_course_data("rolls_monmouth")
        tee_rating = get_tee_rating("rolls_monmouth", "White")
        holes = [int(hole) for hole in course_df["hole"].dropna().tolist()]
        matchups = [
            {"players": [0, 3], "point_value": 1.0},
            {"players": [1, 2], "point_value": 1.0},
        ]

        result = compute_round_results(
            course_df=course_df,
            format_name="Singles",
            score_df=_partial_score_frame("Singles", holes),
            player_names=PLAYER_NAMES,
            player_ids=PLAYER_IDS,
            handicap_indexes=HANDICAP_INDEXES,
            tee_rating=tee_rating,
            allowance_percent=100,
            singles_matchups=matchups,
        )

        self.assertEqual([match["label"] for match in result["matches"]], ["Adam vs Andy", "Vincent vs Alex"])
        self.assertEqual([match["teams"] for match in result["matches"]], [("red", "blue"), ("red", "blue")])

    def test_singles_matchups_round_trip_through_settings_json(self) -> None:
        matchups = [
            {"players": [0, 3], "point_value": 1.0},
            {"players": [1, 2], "point_value": 1.0},
        ]

        encoded = singles_matchups_to_json(matchups)
        decoded = singles_matchups_from_json(encoded)

        self.assertEqual(SINGLES_MATCHUPS_SETTING_KEY, "singles_matchups_json")
        self.assertEqual([tuple(match["players"]) for match in decoded], [(0, 3), (1, 2)])

    def test_invalid_singles_matchups_fall_back_to_defaults(self) -> None:
        encoded = singles_matchups_to_json(
            [
                {"players": [0, 2], "point_value": 1.0},
                {"players": [0, 3], "point_value": 1.0},
            ]
        )

        decoded = singles_matchups_from_json(encoded)

        self.assertEqual([tuple(match["players"]) for match in decoded], [tuple(match["players"]) for match in SINGLES_MATCHUPS])

    def test_default_weekend_points_total_is_five(self) -> None:
        weekend_race = compute_weekend_race({fixture["id"]: {"format_name": fixture["default_format"]} for fixture in FIXTURES})

        self.assertEqual(float(weekend_race["points_table"].iloc[-1]["Points Available"]), 5.0)
        self.assertEqual(weekend_race["remaining_points"], 5.0)

    def test_default_workbook_name_matches_documented_value(self) -> None:
        self.assertEqual(DEFAULT_WORKBOOK_NAME, "Russell_Kelly_Invitational_2026_google_sheets_ready_v2")

    def test_bonus_competitions_add_weekend_level_points(self) -> None:
        competitions = default_bonus_competitions()
        players_rows = [
            {"player_id": "adam", "team_id": "red"},
            {"player_id": "vincent", "team_id": "red"},
            {"player_id": "alex", "team_id": "blue"},
            {"player_id": "andy", "team_id": "blue"},
        ]
        competitions = update_bonus_winner(competitions, "longest_drive", "adam")
        rows = bonus_point_rows(competitions, players_rows)
        weekend_race = compute_weekend_race(
            {fixture["id"]: {"format_name": fixture["default_format"]} for fixture in FIXTURES},
            bonus_rows=rows,
        )

        self.assertEqual(float(weekend_race["points_table"].iloc[-1]["Points Available"]), 7.0)
        self.assertEqual(weekend_race["red_points"], 1.0)
        self.assertEqual(weekend_race["remaining_points"], 6.0)

    def test_bonus_hole_filters_match_competition_type(self) -> None:
        clyne = load_course_data("clyne")
        rolls = load_course_data("rolls_monmouth")

        closest_holes = eligible_holes(clyne, "closest_pin")
        longest_holes = eligible_holes(rolls, "longest_drive")

        self.assertTrue(closest_holes["par"].eq(3).all())
        self.assertTrue(longest_holes["par"].isin([4, 5]).all())
        self.assertEqual(int(closest_holes.iloc[1]["hole"]), 8)
        self.assertEqual(int(longest_holes.iloc[2]["hole"]), 12)

    def test_bonus_config_preserves_zero_point_value(self) -> None:
        competitions = default_bonus_competitions()
        updated = [
            configured_bonus_competition(
                competitions[0],
                round_id="rolls_monmouth",
                course="rolls_monmouth",
                hole=12,
                point_value=0.0,
                enabled=True,
            ),
            competitions[1],
        ]

        encoded = bonus_competitions_to_json(updated)
        decoded = bonus_competitions_from_json(encoded)

        longest_drive = next(competition for competition in decoded if competition["id"] == "longest_drive")
        self.assertEqual(longest_drive["point_value"], 0.0)

    def test_bonus_config_clears_winner_when_target_changes(self) -> None:
        competition = update_bonus_winner(default_bonus_competitions(), "longest_drive", "adam")[0]

        unchanged = configured_bonus_competition(
            competition,
            round_id="rolls_monmouth",
            course="rolls_monmouth",
            hole=12,
            point_value=1.0,
            enabled=True,
        )
        moved = configured_bonus_competition(
            competition,
            round_id="clyne",
            course="clyne",
            hole=8,
            point_value=1.0,
            enabled=True,
        )
        revalued = configured_bonus_competition(
            competition,
            round_id="rolls_monmouth",
            course="rolls_monmouth",
            hole=12,
            point_value=0.5,
            enabled=True,
        )

        self.assertEqual(unchanged["winner_player_id"], "adam")
        self.assertEqual(moved["winner_player_id"], "")
        self.assertEqual(revalued["winner_player_id"], "")


if __name__ == "__main__":
    unittest.main()
