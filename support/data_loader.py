from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from support.paths import APP_ROOT, COURSES_ROOT, DATA_ROOT, IMAGES_ROOT, METADATA_ROOT

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

COURSE_COLUMNS = (
    "course",
    "hole",
    "hole_name",
    "par",
    "par_white",
    "par_yellow",
    "yards_white",
    "yards_yellow",
    "si",
    "section",
)
HOLE_ENRICHMENT_COLUMNS = (
    "course",
    "hole",
    "hole_name",
    "pro_tip",
    "source_type",
    "source_url",
    "image_path",
    "image_caption",
    "official_hole_url",
)
COURSE_SUMMARY_COLUMNS = (
    "course",
    "par_out",
    "par_in",
    "par_total",
    "yards_white_out",
    "yards_white_in",
    "yards_white_total",
    "yards_yellow_out",
    "yards_yellow_in",
    "yards_yellow_total",
)
TEE_RATINGS_COLUMNS = (
    "course",
    "tee",
    "gender_basis",
    "par",
    "course_rating",
    "slope_rating",
    "source_url",
    "source_type",
    "notes",
)
IMAGE_MAPPING_COLUMNS = (
    "course",
    "hole",
    "image_path",
    "source_url",
    "image_type",
    "notes",
)
SOURCE_LOG_COLUMNS = (
    "course",
    "hole",
    "field",
    "value",
    "source_url",
    "source_type",
    "notes",
)
DATA_GAPS_COLUMNS = (
    "course",
    "hole",
    "field",
    "issue",
    "action_needed",
)


def data_package_exists() -> bool:
    return DATA_ROOT.exists() and COURSES_ROOT.exists() and METADATA_ROOT.exists()


def _empty_dataframe(columns: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def _coerce_schema(df: pd.DataFrame, required_columns: tuple[str, ...]) -> pd.DataFrame:
    frame = df.copy()
    for column in required_columns:
        if column not in frame.columns:
            frame[column] = pd.NA

    if "course" in frame.columns:
        frame["course"] = frame["course"].astype("string").str.strip()
    if "hole" in frame.columns:
        frame["hole"] = pd.to_numeric(frame["hole"], errors="coerce").astype("Int64")

    numeric_columns = {
        "par",
        "par_white",
        "par_yellow",
        "yards_white",
        "yards_yellow",
        "si",
        "par_out",
        "par_in",
        "par_total",
        "yards_white_out",
        "yards_white_in",
        "yards_white_total",
        "yards_yellow_out",
        "yards_yellow_in",
        "yards_yellow_total",
    }
    for column in numeric_columns.intersection(frame.columns):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Int64")

    return frame[list(required_columns)]


@st.cache_data(show_spinner=False)
def _read_csv(path: str, required_columns: tuple[str, ...]) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        return _empty_dataframe(required_columns)

    try:
        df = pd.read_csv(file_path)
    except Exception:
        return _empty_dataframe(required_columns)
    return _coerce_schema(df, required_columns)


@st.cache_data(show_spinner=False)
def load_courses() -> list[str]:
    if not COURSES_ROOT.exists():
        return []
    return sorted(path.stem for path in COURSES_ROOT.glob("*.csv"))


@st.cache_data(show_spinner=False)
def load_course_data(course: str) -> pd.DataFrame:
    course_path = COURSES_ROOT / f"{course}.csv"
    df = _read_csv(str(course_path), COURSE_COLUMNS)
    return df[df["course"] == course].sort_values("hole").reset_index(drop=True)


def tee_par_column(tee: str) -> str:
    if str(tee).casefold() == "white":
        return "par_white"
    if str(tee).casefold() == "yellow":
        return "par_yellow"
    return ""


def apply_tee_par(course_df: pd.DataFrame, tee: str) -> pd.DataFrame:
    if course_df.empty:
        return course_df.copy()

    frame = course_df.copy()
    tee_column = tee_par_column(tee)
    if not tee_column or tee_column not in frame.columns:
        return frame

    fallback_par = pd.to_numeric(frame.get("par"), errors="coerce").astype("Int64")
    tee_par = pd.to_numeric(frame[tee_column], errors="coerce").astype("Int64")
    frame["par"] = tee_par.combine_first(fallback_par).astype("Int64")
    return frame


def resolve_hole_par(hole_record: dict[str, Any], tee: str) -> Any:
    tee_column = tee_par_column(tee)
    if tee_column:
        tee_value = hole_record.get(tee_column)
        try:
            if pd.notna(tee_value):
                return tee_value
        except (TypeError, ValueError):
            pass
    return hole_record.get("par", "—")


@st.cache_data(show_spinner=False)
def load_hole_enrichment(course: str) -> pd.DataFrame:
    df = _read_csv(str(METADATA_ROOT / "hole_enrichment.csv"), HOLE_ENRICHMENT_COLUMNS)
    return df[df["course"] == course].sort_values("hole").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_course_summary(course: str) -> pd.DataFrame:
    df = _read_csv(str(METADATA_ROOT / "course_summary.csv"), COURSE_SUMMARY_COLUMNS)
    return df[df["course"] == course].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_tee_ratings(course: str) -> pd.DataFrame:
    df = _read_csv(str(METADATA_ROOT / "tee_ratings.csv"), TEE_RATINGS_COLUMNS)
    if "tee" in df.columns:
        df["tee"] = df["tee"].astype("string").str.strip()
    if "gender_basis" in df.columns:
        df["gender_basis"] = df["gender_basis"].astype("string").str.strip()
    if "course_rating" in df.columns:
        df["course_rating"] = pd.to_numeric(df["course_rating"], errors="coerce")
    if "slope_rating" in df.columns:
        df["slope_rating"] = pd.to_numeric(df["slope_rating"], errors="coerce").astype("Int64")
    return df[df["course"] == course].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_image_mapping(course: str) -> pd.DataFrame:
    df = _read_csv(str(METADATA_ROOT / "image_mapping.csv"), IMAGE_MAPPING_COLUMNS)
    return df[df["course"] == course].sort_values("hole").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_source_log(course: str) -> pd.DataFrame:
    df = _read_csv(str(METADATA_ROOT / "source_log.csv"), SOURCE_LOG_COLUMNS)
    return df[df["course"] == course].sort_values(["hole", "field"]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_data_gaps(course: str) -> pd.DataFrame:
    df = _read_csv(str(METADATA_ROOT / "data_gaps_report.csv"), DATA_GAPS_COLUMNS)
    return df[df["course"] == course].sort_values(["hole", "field"]).reset_index(drop=True)


def get_course_summary_record(course: str, tee: str | None = None) -> dict[str, Any]:
    summary = load_course_summary(course)
    if tee is None and not summary.empty:
        return summary.iloc[0].to_dict()

    course_df = apply_tee_par(load_course_data(course), tee) if tee else load_course_data(course)
    if course_df.empty:
        return summary.iloc[0].to_dict() if not summary.empty else {}

    out_mask = course_df["section"].fillna("").astype(str).str.upper().eq("OUT")
    in_mask = course_df["section"].fillna("").astype(str).str.upper().eq("IN")

    return {
        "course": course,
        "par_out": course_df.loc[out_mask, "par"].sum(min_count=1),
        "par_in": course_df.loc[in_mask, "par"].sum(min_count=1),
        "par_total": course_df["par"].sum(min_count=1),
        "yards_white_out": course_df.loc[out_mask, "yards_white"].sum(min_count=1),
        "yards_white_in": course_df.loc[in_mask, "yards_white"].sum(min_count=1),
        "yards_white_total": course_df["yards_white"].sum(min_count=1),
        "yards_yellow_out": course_df.loc[out_mask, "yards_yellow"].sum(min_count=1),
        "yards_yellow_in": course_df.loc[in_mask, "yards_yellow"].sum(min_count=1),
        "yards_yellow_total": course_df["yards_yellow"].sum(min_count=1),
    }


def get_tee_rating(course: str, tee: str) -> dict[str, Any]:
    ratings = load_tee_ratings(course)
    if ratings.empty:
        return {}

    tee_mask = ratings["tee"].fillna("").astype(str).str.casefold().eq(tee.casefold())
    rating = ratings[tee_mask]
    if rating.empty:
        return {}
    return rating.iloc[0].to_dict()


def get_hole_record(course: str, hole: int) -> dict[str, Any]:
    course_df = load_course_data(course)
    enrichment_df = load_hole_enrichment(course)
    mapping_df = load_image_mapping(course)

    base_row = course_df[course_df["hole"] == hole]
    enrich_row = enrichment_df[enrichment_df["hole"] == hole]
    image_row = mapping_df[mapping_df["hole"] == hole]

    record: dict[str, Any] = {}
    if not base_row.empty:
        record.update(base_row.iloc[0].to_dict())
    if not enrich_row.empty:
        for key, value in enrich_row.iloc[0].to_dict().items():
            if pd.notna(value) and value != "":
                record[key] = value
    if not image_row.empty:
        image_dict = image_row.iloc[0].to_dict()
        record.setdefault("image_path", image_dict.get("image_path"))
        record["image_source_url"] = image_dict.get("source_url")
        record["image_type"] = image_dict.get("image_type")
        record["image_notes"] = image_dict.get("notes")

    return record


def _resolve_image_path(image_path: Any) -> Path | None:
    if not isinstance(image_path, str) or not image_path.strip():
        return None

    normalized_path = Path(image_path.strip())
    if normalized_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        return None

    candidates: list[Path] = []
    if normalized_path.is_absolute():
        candidates.append(normalized_path)
    else:
        parts = normalized_path.parts
        if parts and parts[0] == DATA_ROOT.name:
            candidates.append(APP_ROOT / normalized_path)
        elif parts and parts[0] == IMAGES_ROOT.name:
            candidates.append(DATA_ROOT / normalized_path)
        else:
            candidates.extend(
                [
                    DATA_ROOT / normalized_path,
                    IMAGES_ROOT / normalized_path,
                    APP_ROOT / normalized_path,
                ]
            )

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def get_hole_image(course: str, hole: int) -> dict[str, Any]:
    hole_record = get_hole_record(course, hole)
    enrichment_df = load_hole_enrichment(course)
    mapping_df = load_image_mapping(course)

    image_path = hole_record.get("image_path")
    # St Pierre only has a reused generic course image; hide it rather than showing a non-hole-specific placeholder.
    if course == "st_pierre_old" and isinstance(image_path, str) and image_path.strip().endswith("course_generic.jpg"):
        return {
            "available": False,
            "path": None,
            "caption": None,
            "source_url": hole_record.get("image_source_url") or hole_record.get("source_url"),
            "notes": hole_record.get("image_notes"),
            "message": "No hole-specific image available",
        }

    resolved = _resolve_image_path(image_path)
    if resolved is not None:
        return {
            "available": True,
            "path": resolved,
            "caption": hole_record.get("image_caption"),
            "source_url": hole_record.get("image_source_url") or hole_record.get("source_url"),
            "notes": hole_record.get("image_notes"),
        }

    enrich_row = enrichment_df[enrichment_df["hole"] == hole]
    mapping_row = mapping_df[mapping_df["hole"] == hole]
    referenced_path = None
    if not enrich_row.empty and pd.notna(enrich_row.iloc[0].get("image_path")):
        referenced_path = enrich_row.iloc[0].get("image_path")
    elif not mapping_row.empty and pd.notna(mapping_row.iloc[0].get("image_path")):
        referenced_path = mapping_row.iloc[0].get("image_path")

    message = "No official image available"
    if isinstance(referenced_path, str) and referenced_path.strip():
        message = "Image referenced in metadata is not available locally"

    return {
        "available": False,
        "path": None,
        "caption": None,
        "source_url": hole_record.get("image_source_url") or hole_record.get("source_url"),
        "notes": hole_record.get("image_notes"),
        "message": message,
    }
