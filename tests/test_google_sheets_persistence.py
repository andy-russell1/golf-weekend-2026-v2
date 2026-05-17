from __future__ import annotations

import json
import unittest

from support.google_sheets import _delete_rows_matching, _upsert_score_rows, save_round_result


class GoogleSheetsPersistenceTests(unittest.TestCase):
    def test_upsert_score_rows_updates_existing_hole_rows_without_duplicates(self) -> None:
        existing_rows = [
            {"round_id": "R1", "hole": 1, "player_id": "adam", "gross_score": 4, "status": "Complete"},
            {"round_id": "R1", "hole": 1, "player_id": "vincent", "gross_score": 5, "status": "Complete"},
            {"round_id": "R1", "hole": 2, "player_id": "adam", "gross_score": 6, "status": "Complete"},
        ]
        replacement_rows = [
            {"player_id": "adam", "gross_score": 3, "status": "Complete"},
            {"player_id": "vincent", "gross_score": 4, "status": "Complete"},
        ]

        updated_rows, appended_rows = _upsert_score_rows(existing_rows, "R1", 1, replacement_rows)
        combined_rows = updated_rows + appended_rows
        second_update, second_append = _upsert_score_rows(combined_rows, "R1", 1, replacement_rows)
        second_combined = second_update + second_append

        self.assertEqual(appended_rows, [])
        self.assertEqual(second_append, [])
        self.assertEqual(len(second_combined), 3)
        self.assertEqual(
            len([row for row in second_combined if row["round_id"] == "R1" and int(row["hole"]) == 1 and row["player_id"] == "adam"]),
            1,
        )
        adam_row = next(row for row in second_combined if row["round_id"] == "R1" and int(row["hole"]) == 1 and row["player_id"] == "adam")
        self.assertEqual(adam_row["gross_score"], 3)

    def test_upsert_score_rows_appends_new_player_once(self) -> None:
        existing_rows = [{"round_id": "R1", "hole": 1, "player_id": "adam", "gross_score": 4}]
        replacement_rows = [
            {"player_id": "adam", "gross_score": 4, "status": "Complete"},
            {"player_id": "alex", "gross_score": 5, "status": "Complete"},
        ]

        updated_rows, appended_rows = _upsert_score_rows(existing_rows, "R1", 1, replacement_rows)
        combined_rows = updated_rows + appended_rows
        second_update, second_append = _upsert_score_rows(combined_rows, "R1", 1, replacement_rows)

        self.assertEqual(len(appended_rows), 1)
        self.assertEqual(appended_rows[0]["player_id"], "alex")
        self.assertEqual(second_append, [])
        self.assertEqual(len(second_update), 2)

    def test_upsert_score_rows_updates_latest_duplicate_without_appending(self) -> None:
        existing_rows = [
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
                "gross_score": 5,
                "status": "Complete",
                "updated_at": "2026-05-16T10:02:00+00:00",
            },
        ]
        replacement_rows = [{"player_id": "adam", "gross_score": 6, "status": "Complete"}]

        updated_rows, appended_rows = _upsert_score_rows(existing_rows, "R1", 1, replacement_rows)
        second_update, second_append = _upsert_score_rows(updated_rows + appended_rows, "R1", 1, replacement_rows)

        self.assertEqual(appended_rows, [])
        self.assertEqual(second_append, [])
        self.assertEqual(len(second_update), 2)
        self.assertEqual(updated_rows[0]["gross_score"], 4)
        self.assertEqual(updated_rows[1]["gross_score"], 6)

    def test_save_round_result_strips_binary_payloads_before_json_storage(self) -> None:
        captured: dict[str, object] = {}

        class FakeWorksheet:
            def get_all_records(self, default_blank: str = "") -> list[dict[str, object]]:
                return []

            def append_rows(self, values: list[list[str]]) -> None:
                captured["values"] = values

        def fake_load_results() -> list[dict[str, object]]:
            return []

        def fake_get_worksheet(_name: str) -> FakeWorksheet:
            return FakeWorksheet()

        from unittest.mock import patch

        with (
            patch("support.google_sheets.load_results", fake_load_results),
            patch("support.google_sheets.get_worksheet", fake_get_worksheet),
            patch("support.google_sheets.refresh_sheet_caches", lambda **_kwargs: None),
        ):
            save_round_result("R1", {"format_name": "4-Ball", "payload": {"export_bytes": b"abc"}})

        payload_json = captured["values"][0][7]
        json.dumps(json.loads(payload_json))
        self.assertNotIn("export_bytes", payload_json)

    def test_delete_rows_matching_deletes_from_bottom_up(self) -> None:
        deleted_rows: list[int] = []

        class FakeWorksheet:
            def get_all_records(self, default_blank: str = "") -> list[dict[str, object]]:
                return [
                    {"round_id": "R1"},
                    {"round_id": "R2"},
                    {"round_id": "R1"},
                ]

            def delete_rows(self, row_number: int) -> None:
                deleted_rows.append(row_number)

        from unittest.mock import patch

        with patch("support.google_sheets.get_worksheet", lambda _name: FakeWorksheet()):
            _delete_rows_matching("scores", lambda row: row.get("round_id") == "R1")

        self.assertEqual(deleted_rows, [4, 2])


if __name__ == "__main__":
    unittest.main()
