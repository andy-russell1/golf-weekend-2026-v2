from __future__ import annotations

from typing import Any

import pandas as pd


def format_course_name(course: str) -> str:
    if not course:
        return "Unknown Course"
    return " ".join(part.capitalize() for part in course.split("_"))


def format_hole_name(hole_name: Any, hole: Any) -> str:
    if isinstance(hole_name, str) and hole_name.strip():
        return hole_name.strip()
    return f"Hole {int(hole)}" if pd.notna(hole) else "Hole"


def format_score_value(value: Any) -> str:
    if pd.isna(value):
        return "\u2014"
    return str(int(value))


def format_optional_text(value: Any, fallback: str = "\u2014") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if pd.notna(value) and value not in ("", None):
        return str(value)
    return fallback


def format_to_par(value: int | None) -> str:
    if value is None:
        return "\u2014"
    if value == 0:
        return "E"
    return f"{value:+d}"


def format_handicap_index(value: Any) -> str:
    if pd.isna(value):
        return "\u2014"
    return f"{float(value):.1f}"


def difficulty_label(stroke_index: Any) -> tuple[str, str]:
    if pd.isna(stroke_index):
        return "Unrated", "muted"

    si = int(stroke_index)
    if si <= 6:
        return "Demanding", "danger"
    if si <= 12:
        return "Balanced", "warning"
    return "Scoring Chance", "success"


def format_match_status(balance: int, positive_label: str, negative_label: str, holes_played: int, total_holes: int = 18) -> str:
    if holes_played <= 0:
        return "Scoring not started"

    holes_remaining = total_holes - holes_played
    if abs(balance) > holes_remaining:
        if balance == 0:
            return "Match halved"
        leader = positive_label if balance > 0 else negative_label
        return f"{leader} won {abs(balance)} & {holes_remaining}"

    if holes_played == total_holes:
        if balance == 0:
            return "Match halved"
        leader = positive_label if balance > 0 else negative_label
        return f"{leader} won {abs(balance)} Up"

    if balance == 0:
        return f"All Square through {holes_played}"

    leader = positive_label if balance > 0 else negative_label
    return f"{leader} {abs(balance)} Up through {holes_played}"


def format_points(value: float) -> str:
    if isinstance(value, int):
        return str(value)
    if value.is_integer():
        return str(int(value))
    return f"{value:.1f}"


def format_relative_to(label: str | None) -> str:
    if not label:
        return "No handicap baseline"
    return f"Playing off {label}"
