from __future__ import annotations

from typing import Any

import pandas as pd

from domain.handicap import build_player_handicap_table, build_shot_allocation_table
from domain.matchplay import score_four_ball, score_singles, score_skins, score_stroke_play
from domain.weekend_config import FIXTURES, SINGLES_MATCHUPS, build_team_label, normalize_singles_matchups, points_available_for_format, team_name, team_short_name


def compute_round_results(
    course_df: pd.DataFrame,
    format_name: str,
    score_df: pd.DataFrame,
    player_names: list[str],
    handicap_indexes: list[float],
    tee_rating: dict[str, Any],
    allowance_percent: int = 100,
    scramble_mode: str = "",
    scoring_mode: str = "net",
    stableford_mode: str = "",
    player_ids: list[str] | None = None,
    singles_matchups: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if course_df.empty:
        return {"format_name": format_name, "summary_df": pd.DataFrame(), "player_handicaps": pd.DataFrame()}

    player_rows = build_player_handicap_table(
        player_names=player_names,
        handicap_indexes=handicap_indexes,
        tee_rating=tee_rating,
        allowance=allowance_percent / 100,
    )
    if player_rows.empty:
        return {"format_name": format_name, "summary_df": pd.DataFrame(), "player_handicaps": player_rows}

    if format_name == "Singles":
        result = score_singles(course_df, score_df, player_rows, player_names, singles_matchups=singles_matchups)
    elif format_name == "4-Ball":
        result = score_four_ball(course_df, score_df, player_rows, player_names)
    elif format_name == "Stroke Play":
        result = score_stroke_play(course_df, score_df, player_rows, player_names)
    elif format_name == "Skins":
        result = score_skins(course_df, score_df, player_rows, player_names)
    else:
        result = {
            "format_name": format_name,
            "summary_df": score_df.copy(),
            "awarded_points": {"red": 0.0, "blue": 0.0},
            "projected_points": {"red": 0.0, "blue": 0.0},
            "export_df": score_df.copy(),
            "export_bytes": b"",
            "status_text": "Unsupported format",
            "winner": "",
            "is_complete": False,
        }

    result["player_handicaps"] = player_rows
    result["allowance_percent"] = allowance_percent
    result["scramble_mode"] = scramble_mode
    result["scoring_mode"] = scoring_mode
    result.setdefault("status_text", "Awaiting scores")
    result.setdefault("winner", "")
    result.setdefault("is_complete", False)
    return result


def build_hole_shot_views(
    course_df: pd.DataFrame,
    format_name: str,
    player_rows: pd.DataFrame,
    player_names: list[str],
    scramble_mode: str = "",
    scoring_mode: str = "net",
    singles_matchups: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if course_df.empty or player_rows.empty:
        return []

    if format_name == "Singles":
        groups: list[dict[str, Any]] = []
        for match in normalize_singles_matchups(singles_matchups or list(SINGLES_MATCHUPS), player_count=len(player_names)):
            left_idx, right_idx = match["players"]
            left_name = player_names[left_idx]
            right_name = player_names[right_idx]
            handicap_lookup = {
                left_name: int(player_rows.loc[player_rows["Player"] == left_name, "Playing Handicap"].iloc[0]),
                right_name: int(player_rows.loc[player_rows["Player"] == right_name, "Playing Handicap"].iloc[0]),
            }
            shot_info = build_shot_allocation_table(course_df[["hole", "si"]], handicap_lookup)
            hole_rows = shot_info["table"].groupby("hole").apply(
                lambda frame: {row["Player"]: int(row["shots_received"]) for _, row in frame.iterrows()}
            )
            groups.append(
                {
                    "label": f"{left_name} vs {right_name}",
                    "relative_to": shot_info["relative_to"],
                    "holes": hole_rows.to_dict() if not hole_rows.empty else {},
                }
            )
        return groups

    handicap_lookup = {row["Player"]: int(row["Playing Handicap"]) for _, row in player_rows.iterrows()}
    shot_info = build_shot_allocation_table(course_df[["hole", "si"]], handicap_lookup)
    hole_rows = shot_info["table"].groupby("hole").apply(
        lambda frame: {row["Player"]: int(row["shots_received"]) for _, row in frame.iterrows()}
    )
    return [
        {
            "label": build_team_label("red", player_names) + " vs " + build_team_label("blue", player_names),
            "relative_to": shot_info["relative_to"],
            "holes": hole_rows.to_dict() if not hole_rows.empty else {},
        }
    ]


def get_hole_shots_for_display(shot_views: list[dict[str, Any]], hole: int) -> list[dict[str, Any]]:
    return [
        {
            "label": group["label"],
            "relative_to": group["relative_to"],
            "shots": group.get("holes", {}).get(hole, {}),
        }
        for group in shot_views
    ]


def round_points_summary(result: dict[str, Any]) -> dict[str, float]:
    return {
        "red": float(result.get("awarded_points", {}).get("red", 0.0)),
        "blue": float(result.get("awarded_points", {}).get("blue", 0.0)),
    }


def _result_points_available(result: dict[str, Any], fallback_format: str) -> float:
    if "points_available" in result:
        try:
            return float(result.get("points_available") or 0.0)
        except (TypeError, ValueError):
            pass
    return points_available_for_format(str(result.get("format_name") or fallback_format))


def compute_weekend_points(
    results_by_fixture: dict[str, dict[str, Any]],
    bonus_rows: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    totals = {"red": 0.0, "blue": 0.0}

    for fixture in FIXTURES:
        fixture_result = results_by_fixture.get(fixture["id"], {})
        awarded = round_points_summary(fixture_result)
        totals["red"] += awarded["red"]
        totals["blue"] += awarded["blue"]
        rows.append(
            {
                "Fixture": fixture["title"],
                "Format": fixture_result.get("format_name", fixture["default_format"]),
                "Red": awarded["red"],
                "Blue": awarded["blue"],
                "Points Available": _result_points_available(fixture_result, fixture["default_format"]),
            }
        )

    rows.extend(bonus_rows or [])
    rows.append(
        {
            "Fixture": "Weekend Total",
            "Format": "Overall",
            "Red": totals["red"] + sum(float(row.get("Red", 0.0) or 0.0) for row in bonus_rows or []),
            "Blue": totals["blue"] + sum(float(row.get("Blue", 0.0) or 0.0) for row in bonus_rows or []),
            "Points Available": sum(
                _result_points_available(results_by_fixture.get(fixture["id"], {}), fixture["default_format"])
                for fixture in FIXTURES
            )
            + sum(float(row.get("Points Available", 0.0) or 0.0) for row in bonus_rows or []),
        }
    )
    return pd.DataFrame(rows)


def compute_weekend_race(
    results_by_fixture: dict[str, dict[str, Any]],
    bonus_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    points_table = compute_weekend_points(results_by_fixture, bonus_rows=bonus_rows)
    awarded_rows = points_table.iloc[:-1].copy()
    total_available = float(awarded_rows["Points Available"].sum()) if not awarded_rows.empty else 0.0
    red_points = float(awarded_rows["Red"].sum()) if not awarded_rows.empty else 0.0
    blue_points = float(awarded_rows["Blue"].sum()) if not awarded_rows.empty else 0.0
    awarded_total = red_points + blue_points
    remaining_points = max(0.0, total_available - awarded_total)
    winning_target = (total_available / 2.0) + 0.5 if total_available else 0.0

    red_needed = max(0.0, winning_target - red_points)
    blue_needed = max(0.0, winning_target - blue_points)
    red_can_win = red_points + remaining_points >= winning_target
    blue_can_win = blue_points + remaining_points >= winning_target

    if red_points >= winning_target and red_points > blue_points:
        status = f"{team_name('red')} have won the weekend"
    elif blue_points >= winning_target and blue_points > red_points:
        status = f"{team_name('blue')} have won the weekend"
    elif remaining_points == 0 and red_points == blue_points:
        status = "Weekend tied"
    elif remaining_points == 0:
        status = "Weekend complete"
    else:
        leader = team_name("red") if red_points > blue_points else team_name("blue") if blue_points > red_points else "All Square"
        if leader == "All Square":
            status = f"All square with {remaining_points:.1f} points left"
        else:
            lead = abs(red_points - blue_points)
            status = f"{leader} lead by {lead:.1f} with {remaining_points:.1f} points left"

    def _path_text(team_name: str, needed: float, can_win: bool, current: float) -> str:
        if current >= winning_target and total_available:
            return f"{team_name} already have the winning number"
        if not can_win:
            return f"{team_name} can no longer win outright"
        return f"{team_name} need {needed:.1f} more to win outright"

    return {
        "points_table": points_table,
        "red_points": red_points,
        "blue_points": blue_points,
        "remaining_points": remaining_points,
        "winning_target": winning_target,
        "red_needed": red_needed,
        "blue_needed": blue_needed,
        "red_can_win": red_can_win,
        "blue_can_win": blue_can_win,
        "status": status,
        "red_path": _path_text(team_short_name("red"), red_needed, red_can_win, red_points),
        "blue_path": _path_text(team_short_name("blue"), blue_needed, blue_can_win, blue_points),
    }


def compute_optional_awards(result: dict[str, Any]) -> list[dict[str, str]]:
    awards: list[dict[str, str]] = []
    player_totals = result.get("player_totals")
    if isinstance(player_totals, pd.DataFrame) and not player_totals.empty:
        gross_rows = player_totals.dropna(subset=["Gross Total"]) if "Gross Total" in player_totals.columns else pd.DataFrame()
        net_rows = player_totals.dropna(subset=["Net Total"]) if "Net Total" in player_totals.columns else pd.DataFrame()
        if not gross_rows.empty:
            best_gross = gross_rows.sort_values("Gross Total").iloc[0]
            awards.append({"title": "Best Gross", "value": f"{best_gross['Player']} ({int(best_gross['Gross Total'])})"})
        if not net_rows.empty:
            best_net = net_rows.sort_values("Net Total").iloc[0]
            awards.append({"title": "Best Net", "value": f"{best_net['Player']} ({int(best_net['Net Total'])})"})

    summary = result.get("summary_df")
    if isinstance(summary, pd.DataFrame) and not summary.empty and "par" in summary.columns:
        gross_columns = [column for column in summary.columns if column.startswith("player_")]
        blowup_candidates: list[tuple[int, int]] = []
        for _, row in summary.iterrows():
            for column in gross_columns:
                if pd.notna(row.get(column)):
                    blowup_candidates.append((int(row["hole"]), int(row[column] - row["par"])))
        if blowup_candidates:
            hole, delta = max(blowup_candidates, key=lambda item: item[1])
            awards.append({"title": "Blow-up Hole", "value": f"Hole {hole} ({delta:+d})"})
    return awards[:4]
