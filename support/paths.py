from __future__ import annotations

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = APP_ROOT / "assets"
DATA_ROOT = APP_ROOT / "golf_trip_data"
COURSES_ROOT = DATA_ROOT / "courses"
METADATA_ROOT = DATA_ROOT / "metadata"
IMAGES_ROOT = DATA_ROOT / "images"
