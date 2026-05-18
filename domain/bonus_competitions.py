from __future__ import annotations

import json
from typing import Any

import pandas as pd

from domain.formatting import format_hole_name


BONUS_COMPETITIONS_SETTING_KEY = "bonus_competitions_json"
BONUS_COMPETITION_TYPES = ("longest_drive", "closest_pin")

DEFAULT_BONUS_COMPETITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "longest_drive",
        "label": "Longest Drive",
        "type": "longest_drive",
        "round_id": "rolls_monmouth",
        "course": "rolls_monmouth",
        "hole": 12,
        "point_value": 1.0,
        "winner_player_id": "",
        "enabled": True,
    },
    {
        "id": "closest_pin",
        "label": "Closest to the Pin",
        "type": "closest_pin",
        "round_id": "clyne",
        "course": "clyne",
        "hole": 8,
        "point_value": 1.0,
        "winner_player_id": "",
        "enabled": True,
    },
)


def default_bonus_competitions() -> list[dict[str, Any]]:
    return [dict(competition) for competition in DEFAULT_BONUS_COMPETITIONS]


def bonus_competitions_to_json(competitions: list[dict[str, Any]]) -> str:
    return json.dumps(normalize_bonus_competitions(competitions), separators=(",", ":"))


def bonus_competitions_from_json(raw_value: str) -> list[dict[str, Any]]:
    if not raw_value:
        return default_bonus_competitions()
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return default_bonus_competitions()
    return normalize_bonus_competitions(payload)


def normalize_bonus_competitions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return default_bonus_competitions()

    incoming_by_id = {
        str(item.get("id", "")): item
        for item in value
        if isinstance(item, dict) and str(item.get("id", "")) in {competition["id"] for competition in DEFAULT_BONUS_COMPETITIONS}
    }
    normalized: list[dict[str, Any]] = []
    for default in DEFAULT_BONUS_COMPETITIONS:
        item = incoming_by_id.get(str(default["id"]), {})
        competition_type = str(item.get("type") or default["type"])
        if competition_type not in BONUS_COMPETITION_TYPES:
            competition_type = str(default["type"])
        try:
            hole = int(item.get("hole") or default["hole"])
        except (TypeError, ValueError):
            hole = int(default["hole"])
        try:
            point_value = float(item.get("point_value") if item.get("point_value") not in (None, "") else default["point_value"])
        except (TypeError, ValueError):
            point_value = float(default["point_value"])

        normalized.append(
            {
                "id": str(default["id"]),
                "label": str(item.get("label") or default["label"]),
                "type": competition_type,
                "round_id": str(item.get("round_id") or default["round_id"]),
                "course": str(item.get("course") or default["course"]),
                "hole": max(1, hole),
                "point_value": max(0.0, point_value),
                "winner_player_id": str(item.get("winner_player_id") or ""),
                "enabled": _coerce_bool(item.get("enabled", default["enabled"])),
            }
        )
    return normalized


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def eligible_holes(course_df: pd.DataFrame, competition_type: str, tee_label: str = "White") -> pd.DataFrame:
    if course_df.empty:
        return course_df.copy()
    frame = course_df.copy()
    frame["par"] = pd.to_numeric(frame["par"], errors="coerce")
    yardage_column = _yardage_column(tee_label)
    frame[yardage_column] = pd.to_numeric(frame[yardage_column], errors="coerce")
    if competition_type == "closest_pin":
        return frame[frame["par"].eq(3)].sort_values("hole").reset_index(drop=True)
    if competition_type == "longest_drive":
        return frame[frame["par"].isin([4, 5])].sort_values(yardage_column, ascending=False).reset_index(drop=True)
    return frame.sort_values("hole").reset_index(drop=True)


def competition_hole_label(hole_record: dict[str, Any], tee_label: str = "White") -> str:
    hole = int(hole_record.get("hole") or 0)
    hole_name = format_hole_name(hole_record.get("hole_name"), hole)
    par = hole_record.get("par", "—")
    white_yards = hole_record.get("yards_white", "—")
    yellow_yards = hole_record.get("yards_yellow", "—")
    return f"Hole {hole} - {hole_name} - Par {par} - {white_yards}/{yellow_yards}y"


def competitions_for_hole(competitions: list[dict[str, Any]], round_id: str, hole: int) -> list[dict[str, Any]]:
    return [
        competition
        for competition in normalize_bonus_competitions(competitions)
        if bool(competition.get("enabled")) and str(competition.get("round_id")) == round_id and int(competition.get("hole") or 0) == int(hole)
    ]


def update_bonus_winner(
    competitions: list[dict[str, Any]],
    competition_id: str,
    winner_player_id: str,
) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for competition in normalize_bonus_competitions(competitions):
        if str(competition.get("id")) == competition_id:
            updated.append({**competition, "winner_player_id": str(winner_player_id or "")})
        else:
            updated.append(competition)
    return updated


def bonus_competition_summaries(competitions: list[dict[str, Any]], players_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    player_lookup = {
        str(row.get("player_id", "")): {
            "name": str(row.get("player_name") or row.get("name") or row.get("player_id") or ""),
            "team_id": str(row.get("team_id") or row.get("team") or ""),
            "team_name": str(row.get("team_name") or ""),
        }
        for row in players_rows
    }
    summaries: list[dict[str, Any]] = []
    for competition in normalize_bonus_competitions(competitions):
        if not competition.get("enabled"):
            continue
        winner_player_id = str(competition.get("winner_player_id") or "")
        winner = player_lookup.get(winner_player_id, {})
        winner_team_id = str(winner.get("team_id") or "")
        summaries.append(
            {
                "id": str(competition.get("id") or ""),
                "label": str(competition.get("label") or "Bonus Point"),
                "round_id": str(competition.get("round_id") or ""),
                "course": str(competition.get("course") or ""),
                "hole": int(competition.get("hole") or 0),
                "point_value": float(competition.get("point_value") or 0.0),
                "winner_player_id": winner_player_id,
                "winner_player_name": str(winner.get("name") or winner_player_id),
                "winner_team_id": winner_team_id,
                "winner_team_name": str(winner.get("team_name") or winner_team_id),
                "awarded": bool(winner_player_id and winner_team_id),
            }
        )
    return summaries


def configured_bonus_competition(
    competition: dict[str, Any],
    *,
    round_id: str,
    course: str,
    hole: int,
    point_value: float,
    enabled: bool,
) -> dict[str, Any]:
    target_changed = (
        str(competition.get("round_id")) != str(round_id)
        or str(competition.get("course")) != str(course)
        or int(competition.get("hole") or 0) != int(hole)
        or float(competition.get("point_value") or 0.0) != float(point_value)
    )
    return {
        **competition,
        "round_id": str(round_id),
        "course": str(course),
        "hole": int(hole),
        "point_value": max(0.0, float(point_value)),
        "enabled": bool(enabled),
        "winner_player_id": "" if target_changed else str(competition.get("winner_player_id") or ""),
    }


def bonus_point_rows(competitions: list[dict[str, Any]], players_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    player_team_lookup = {
        str(row.get("player_id", "")): str(row.get("team_id", ""))
        for row in players_rows
    }
    rows: list[dict[str, Any]] = []
    for competition in normalize_bonus_competitions(competitions):
        if not competition.get("enabled"):
            continue
        winner_player_id = str(competition.get("winner_player_id") or "")
        winner_team = player_team_lookup.get(winner_player_id, "")
        point_value = float(competition.get("point_value") or 0.0)
        rows.append(
            {
                "Fixture": str(competition.get("label") or "Bonus Point"),
                "Format": "Bonus",
                "Red": point_value if winner_team == "red" else 0.0,
                "Blue": point_value if winner_team == "blue" else 0.0,
                "Points Available": point_value,
            }
        )
    return rows


def _yardage_column(tee_label: str) -> str:
    return "yards_white" if str(tee_label).casefold() == "white" else "yards_yellow"
