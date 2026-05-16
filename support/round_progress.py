from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd


def _parse_updated_at(value: object) -> datetime | None:
    if value in (None, "") or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _latest_saved_row(score_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for row in score_rows:
        updated_at = _parse_updated_at(row.get("updated_at"))
        if updated_at is not None:
            candidates.append((updated_at, row))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1]


def build_round_progress(
    scores: pd.DataFrame,
    holes: list[int],
    score_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ordered_holes = [int(hole) for hole in holes]
    completed_holes: list[int] = []
    incomplete_holes: list[int] = []

    if "hole" not in scores.columns or "status" not in scores.columns:
        incomplete_holes = list(ordered_holes)
    else:
        status_by_hole = {
            int(row["hole"]): str(row["status"])
            for _, row in scores[["hole", "status"]].dropna(subset=["hole"]).iterrows()
        }
        for hole in ordered_holes:
            if status_by_hole.get(hole) == "Complete":
                completed_holes.append(hole)
            else:
                incomplete_holes.append(hole)

    first_hole = ordered_holes[0] if ordered_holes else 1
    last_hole = ordered_holes[-1] if ordered_holes else first_hole
    round_complete = bool(ordered_holes) and len(completed_holes) == len(ordered_holes)
    first_incomplete_hole = None if round_complete else (incomplete_holes[0] if incomplete_holes else first_hole)
    resume_hole = last_hole if round_complete else int(first_incomplete_hole or first_hole)
    latest_saved_row = _latest_saved_row(score_rows or [])
    latest_saved_hole = None
    latest_saved_at = None
    if latest_saved_row is not None:
        try:
            latest_saved_hole = int(float(latest_saved_row.get("hole") or 0))
        except (TypeError, ValueError):
            latest_saved_hole = None
        latest_saved_at = _parse_updated_at(latest_saved_row.get("updated_at"))

    return {
        "completed_holes": completed_holes,
        "completed_count": len(completed_holes),
        "total_holes": len(ordered_holes),
        "last_completed_hole": completed_holes[-1] if completed_holes else None,
        "first_incomplete_hole": first_incomplete_hole,
        "resume_hole": resume_hole,
        "round_complete": round_complete,
        "latest_saved_hole": latest_saved_hole,
        "latest_saved_at": latest_saved_at,
        "has_saved_scores": bool(score_rows) or bool(completed_holes),
    }
