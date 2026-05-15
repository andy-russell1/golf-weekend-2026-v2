from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import pandas as pd

from domain.weekend_config import TEAM_CONFIG, team_for_player


def round_half_up(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_course_handicap(handicap_index: float, slope_rating: int, course_rating: float, par: int) -> int:
    value = handicap_index * (slope_rating / 113) + (course_rating - par)
    return round_half_up(value)


def calculate_playing_handicap(course_handicap: int, allowance: float = 1.0) -> int:
    return round_half_up(course_handicap * allowance)


def _normalize_index(value: Any) -> float:
    if value in (None, "") or pd.isna(value):
        return 0.0
    return float(value)


def build_player_handicap_table(
    player_names: list[str],
    handicap_indexes: list[float],
    tee_rating: dict[str, Any],
    allowance: float = 1.0,
) -> pd.DataFrame:
    if not tee_rating:
        return pd.DataFrame()

    slope_rating = int(tee_rating["slope_rating"])
    course_rating = float(tee_rating["course_rating"])
    par = int(tee_rating["par"])

    rows: list[dict[str, Any]] = []
    for index, raw_name in enumerate(player_names[:4]):
        handicap_index = _normalize_index(handicap_indexes[index] if index < len(handicap_indexes) else 0.0)
        player_name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else f"Player {index + 1}"
        course_handicap = calculate_course_handicap(handicap_index, slope_rating, course_rating, par)
        team_id = team_for_player(index)
        rows.append(
            {
                "Player": player_name,
                "Player Index": index,
                "Team Id": team_id,
                "Team": TEAM_CONFIG[team_id]["name"],
                "Handicap Index": handicap_index,
                "Course Handicap": course_handicap,
                "Playing Handicap": calculate_playing_handicap(course_handicap, allowance),
                "Allowance": allowance,
            }
        )
    return pd.DataFrame(rows)


def build_scramble_team_handicap_table(player_rows: pd.DataFrame, scramble_mode: str) -> pd.DataFrame:
    if player_rows.empty:
        return pd.DataFrame()

    team_rows: list[dict[str, Any]] = []
    for team_id, team in TEAM_CONFIG.items():
        member_rows = player_rows[player_rows["Team Id"] == team_id].sort_values("Course Handicap")
        if member_rows.empty:
            continue
        players = member_rows["Player"].tolist()
        course_handicaps = member_rows["Course Handicap"].tolist()
        low_handicap = int(course_handicaps[0])
        high_handicap = int(course_handicaps[1]) if len(course_handicaps) > 1 else int(course_handicaps[0])
        if scramble_mode == "handicap":
            playing_handicap = round_half_up(low_handicap * 0.35) + round_half_up(high_handicap * 0.15)
            method = "35% low + 15% high"
        else:
            playing_handicap = 0
            method = "Gross scramble"
        team_rows.append(
            {
                "Team Id": team_id,
                "Team": team["name"],
                "Players": " + ".join(players),
                "Low Course Handicap": low_handicap,
                "High Course Handicap": high_handicap,
                "Team Playing Handicap": playing_handicap,
                "Method": method,
            }
        )
    return pd.DataFrame(team_rows)


def strokes_on_hole(strokes_received: int, stroke_index: Any) -> int:
    if strokes_received == 0 or pd.isna(stroke_index):
        return 0

    stroke_index_value = int(stroke_index)
    if strokes_received > 0:
        full_loops = strokes_received // 18
        remainder = strokes_received % 18
        extra = 1 if remainder and stroke_index_value <= remainder else 0
        return full_loops + extra

    shots_to_give_back = abs(strokes_received)
    full_loops = shots_to_give_back // 18
    remainder = shots_to_give_back % 18
    extra = 1 if remainder and stroke_index_value > 18 - remainder else 0
    return -(full_loops + extra)


def build_shot_allocation_table(
    course_df: pd.DataFrame,
    handicap_lookup: dict[str, int],
    entity_type: str = "Player",
    relative_to_lowest: bool = True,
) -> dict[str, Any]:
    if course_df.empty or not handicap_lookup:
        return {"relative_to": None, "relative_handicaps": {}, "table": pd.DataFrame()}

    if relative_to_lowest:
        lowest_label = min(handicap_lookup, key=handicap_lookup.get)
        lowest_value = int(handicap_lookup[lowest_label])
        handicap_values = {label: int(value) - lowest_value for label, value in handicap_lookup.items()}
        relative_to = lowest_label
    else:
        handicap_values = {label: int(value) for label, value in handicap_lookup.items()}
        relative_to = None

    rows: list[dict[str, Any]] = []
    for _, hole in course_df.iterrows():
        hole_number = int(hole["hole"])
        stroke_index = hole.get("si")
        for label, handicap_value in handicap_values.items():
            rows.append(
                {
                    "hole": hole_number,
                    entity_type: label,
                    "relative_playing_handicap": handicap_value,
                    "shots_received": strokes_on_hole(handicap_value, stroke_index),
                }
            )

    return {
        "relative_to": relative_to,
        "relative_handicaps": handicap_values,
        "table": pd.DataFrame(rows),
    }
