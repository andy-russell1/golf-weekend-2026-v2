from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from support.data_loader import (
    _resolve_image_path,
    apply_tee_par,
    get_course_summary_record,
    get_hole_image,
    load_course_data,
)


class DataLoaderRegressionTests(unittest.TestCase):
    def test_clyne_yellow_tees_use_tee_specific_par(self) -> None:
        raw = load_course_data("clyne")
        yellow = apply_tee_par(raw, "Yellow")
        white = apply_tee_par(raw, "White")

        yellow_par_by_hole = yellow.set_index("hole")["par"].to_dict()
        white_par_by_hole = white.set_index("hole")["par"].to_dict()

        self.assertEqual(int(yellow_par_by_hole[7]), 4)
        self.assertEqual(int(yellow_par_by_hole[16]), 4)
        self.assertEqual(int(white_par_by_hole[7]), 5)
        self.assertEqual(int(white_par_by_hole[16]), 5)
        self.assertEqual(int(yellow["par"].sum()), 70)
        self.assertEqual(int(white["par"].sum()), 72)

    def test_clyne_yellow_course_summary_resolves_to_par_70(self) -> None:
        summary = get_course_summary_record("clyne", "Yellow")

        self.assertEqual(int(summary["par_out"]), 35)
        self.assertEqual(int(summary["par_in"]), 35)
        self.assertEqual(int(summary["par_total"]), 70)

    def test_resolve_image_path_accepts_repo_relative_data_prefix(self) -> None:
        resolved = _resolve_image_path("golf_trip_data/images/rolls_monmouth/hole_1.jpg")
        self.assertIsNotNone(resolved)
        self.assertTrue(resolved.exists())

    def test_get_hole_image_handles_bad_metadata_without_crashing(self) -> None:
        with (
            patch(
                "support.data_loader.get_hole_record",
                return_value={"image_path": object(), "image_source_url": None, "source_url": None, "image_notes": None},
            ),
            patch(
                "support.data_loader.load_hole_enrichment",
                return_value=pd.DataFrame([{"hole": 1, "image_path": "images/missing.jpg"}]),
            ),
            patch(
                "support.data_loader.load_image_mapping",
                return_value=pd.DataFrame(columns=["hole", "image_path"]),
            ),
        ):
            image = get_hole_image("rolls_monmouth", 1)

        self.assertFalse(image["available"])
        self.assertEqual(image["path"], None)
        self.assertIn("message", image)

    def test_st_pierre_generic_course_image_stays_hidden(self) -> None:
        image = get_hole_image("st_pierre_old", 1)
        self.assertFalse(image["available"])
        self.assertEqual(image["message"], "No hole-specific image available")


if __name__ == "__main__":
    unittest.main()
