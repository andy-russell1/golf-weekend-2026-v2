from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from support.data_loader import _resolve_image_path, get_hole_image


class DataLoaderRegressionTests(unittest.TestCase):
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
