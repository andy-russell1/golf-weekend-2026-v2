from __future__ import annotations

from typing import Any

import pandas as pd

from domain.formatting import format_match_status
from domain.result_serialization import export_dataframe_bytes
from domain.weekend_config import SINGLES_MATCHUPS, TEAM_CONFIG, build_team_label
from support.session import TEAM_A_PLAYERS, TEAM_B_PLAYERS
from domain.handicap import build_shot_allocation_table


def _coerce_int_series(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    coerced = frame.copy()
    for column in columns:
        if column in coerced.columns:
            coerced[column] = pd.to_numeric(coerced[column], errors="coerce").astype("Int64")
    return coerced


def _sum_scores(series: pd.Series) -> int | None:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    return int(numeric.sum())


def _sum_optional(values: list[int | None]) -> int | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return int(sum(present))


def _export_csv(frame: pd.DataFrame) -> bytes:
    return export_dataframe_bytes(frame)


def _is_match_complete(balance: int, holes_played: int, total_holes: int) -> bool:
    if holes_played <= 0:
        return False
    holes_remaining = total_holes - holes_played
    return holes_played == total_holes or abs(balance) > holes_remaining


def _winner_from_balance(balance: int, positive_label: str, negative_label: str) -> str | None:
    if balance > 0:
        return positive_label
    if balance < 0:
        return negative_label
    return None


def _team_points_from_balance(balance: int, complete: bool, positive_team: str, negative_team: str, point_value: float) -> dict[str, float]:
    if not complete:
        return {positive_team: 0.0, negative_team: 0.0}
    if balance == 0:
        return {positive_team: point_value / 2, negative_team: point_value / 2}
    if balance > 0:
        return {positive_team: point_value, negative_team: 0.0}
    return {positive_team: 0.0, negative_team: point_value}


def _projection_points_from_balance(balance: int, positive_team: str, negative_team: str, point_value: float) -> dict[str, float]:
    if balance == 0:
        return {positive_team: point_value / 2, negative_team: point_value / 2}
    if balance > 0:
        return {positive_team: point_value, negative_team: 0.0}
    return {positive_team: 0.0, negative_team: point_value}


def _winner_from_totals(red_value: int, blue_value: int) -> str:
    if red_value > blue_value:
        return "red"
    if blue_value > red_value:
        return "blue"
    return ""


def _points_from_totals(red_value: int, blue_value: int, complete: bool) -> dict[str, float]:
    if not complete:
        return {"red": 0.0, "blue": 0.0}
    if red_value > blue_value:
        return {"red": 1.0, "blue": 0.0}
    if blue_value > red_value:
        return {"red": 0.0, "blue": 1.0}
    return {"red": 0.5, "blue": 0.5}


def _projected_points_from_totals(red_value: int, blue_value: int) -> dict[str, float]:
    if red_value > blue_value:
        return {"red": 1.0, "blue": 0.0}
    if blue_value > red_value:
        return {"red": 0.0, "blue": 1.0}
    return {"red": 0.5, "blue": 0.5}


def _add_points(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    return {
        "red": float(left.get("red", 0.0) + right.get("red", 0.0)),
        "blue": float(left.get("blue", 0.0) + right.get("blue", 0.0)),
    }


def _build_momentum(sequence: pd.Series) -> list[str]:
    return [value if isinstance(value, str) and value else "Pending" for value in sequence.tolist()]


def _split_wins(frame: pd.DataFrame, team_a_label: str, team_b_label: str, result_column: str) -> dict[str, dict[str, int]]:
    front = frame[frame["hole"] <= 9]
    back = frame[frame["hole"] >= 10]
    return {
        "front": {
            team_a_label: int(front[result_column].eq(team_a_label).sum()),
            team_b_label: int(front[result_column].eq(team_b_label).sum()),
            "Halved": int(front[result_column].eq("Halved").sum()),
        },
        "back": {
            team_a_label: int(back[result_column].eq(team_a_label).sum()),
            team_b_label: int(back[result_column].eq(team_b_label).sum()),
            "Halved": int(back[result_column].eq("Halved").sum()),
        },
    }


def _last_completed_hole(frame: pd.DataFrame, hole_result_column: str) -> dict[str, Any] | None:
    completed = frame[frame[hole_result_column] != "Pending"]
    if completed.empty:
        return None
    row = completed.iloc[-1]
    return {"hole": int(row["hole"]), "result": row[hole_result_column]}


def _build_team_better_ball_summary(
    course_df: pd.DataFrame,
    score_df: pd.DataFrame,
    player_rows: pd.DataFrame,
    player_names: list[str],
) -> dict[str, Any]:
    summary = course_df[["hole", "par", "si", "section", "hole_name"]].copy()
    summary = summary.merge(score_df, on="hole", how="left")
    summary = _coerce_int_series(summary, ["player_1", "player_2", "player_3", "player_4"])
    team_a_label = build_team_label("red", player_names)
    team_b_label = build_team_label("blue", player_names)
    handicap_lookup = {row["Player"]: int(row["Playing Handicap"]) for _, row in player_rows.iterrows()}
    shot_info = build_shot_allocation_table(course_df[["hole", "si"]], handicap_lookup)
    allocations = shot_info["table"].pivot(index="hole", columns="Player", values="shots_received").reset_index()
    summary = summary.merge(allocations, on="hole", how="left")

    for index, player_name in enumerate(player_names):
        score_column = f"player_{index + 1}"
        shot_column = f"{player_name}_shots"
        net_column = f"{player_name}_net"
        summary[shot_column] = pd.to_numeric(summary.get(player_name), errors="coerce").fillna(0).astype(int)
        summary[net_column] = pd.to_numeric(summary[score_column], errors="coerce") - summary[shot_column]

    gross_columns_a = [f"player_{TEAM_A_PLAYERS[0] + 1}", f"player_{TEAM_A_PLAYERS[1] + 1}"]
    gross_columns_b = [f"player_{TEAM_B_PLAYERS[0] + 1}", f"player_{TEAM_B_PLAYERS[1] + 1}"]
    net_columns_a = [f"{player_names[TEAM_A_PLAYERS[0]]}_net", f"{player_names[TEAM_A_PLAYERS[1]]}_net"]
    net_columns_b = [f"{player_names[TEAM_B_PLAYERS[0]]}_net", f"{player_names[TEAM_B_PLAYERS[1]]}_net"]

    summary["team_a_best_gross"] = summary[gross_columns_a].min(axis=1, skipna=True)
    summary["team_b_best_gross"] = summary[gross_columns_b].min(axis=1, skipna=True)
    summary["team_a_best_net"] = summary[net_columns_a].min(axis=1, skipna=True)
    summary["team_b_best_net"] = summary[net_columns_b].min(axis=1, skipna=True)
    played = summary[gross_columns_a + gross_columns_b].notna().all(axis=1)
    summary["team_a_contributor"] = pd.NA
    summary["team_b_contributor"] = pd.NA
    summary.loc[played, "team_a_contributor"] = summary.loc[played, net_columns_a].idxmin(axis=1).str.replace("_net", "", regex=False)
    summary.loc[played, "team_b_contributor"] = summary.loc[played, net_columns_b].idxmin(axis=1).str.replace("_net", "", regex=False)
    summary["hole_result"] = "Pending"
    summary.loc[played & (summary["team_a_best_net"] < summary["team_b_best_net"]), "hole_result"] = team_a_label
    summary.loc[played & (summary["team_b_best_net"] < summary["team_a_best_net"]), "hole_result"] = team_b_label
    summary.loc[played & (summary["team_b_best_net"] == summary["team_a_best_net"]), "hole_result"] = "Halved"

    player_totals = pd.DataFrame(
        {
            "Player": player_names,
            "Gross Total": [_sum_scores(summary[f"player_{index + 1}"]) for index in range(4)],
            "Net Total": [_sum_scores(summary[f"{player_names[index]}_net"]) for index in range(4)],
            "Counters": [
                int(summary["team_a_contributor"].eq(player_names[index]).sum())
                if index in TEAM_A_PLAYERS
                else int(summary["team_b_contributor"].eq(player_names[index]).sum())
                for index in range(4)
            ],
        }
    )
    team_totals = pd.DataFrame(
        {
            "Team": [team_a_label, team_b_label],
            "Best Gross Total": [_sum_scores(summary["team_a_best_gross"]), _sum_scores(summary["team_b_best_gross"])],
            "Best Net Total": [_sum_scores(summary["team_a_best_net"]), _sum_scores(summary["team_b_best_net"])],
        }
    )
    return {
        "summary": summary,
        "played": played,
        "team_a_label": team_a_label,
        "team_b_label": team_b_label,
        "shot_info": shot_info,
        "player_totals": player_totals,
        "team_totals": team_totals,
    }


def score_singles(
    course_df: pd.DataFrame,
    score_df: pd.DataFrame,
    player_rows: pd.DataFrame,
    player_names: list[str],
) -> dict[str, Any]:
    summary = course_df[["hole", "par", "si", "section", "hole_name"]].copy()
    summary = summary.merge(score_df, on="hole", how="left")
    summary = _coerce_int_series(summary, ["player_1", "player_2", "player_3", "player_4"])

    matches: list[dict[str, Any]] = []
    combined_export_parts: list[pd.DataFrame] = []
    awarded_points = {"red": 0.0, "blue": 0.0}
    projected_points = {"red": 0.0, "blue": 0.0}

    for match in SINGLES_MATCHUPS:
        left_idx, right_idx = match["players"]
        left_name = player_names[left_idx]
        right_name = player_names[right_idx]
        left_column = f"player_{left_idx + 1}"
        right_column = f"player_{right_idx + 1}"
        match_frame = summary[["hole", "par", "si", "section", "hole_name", left_column, right_column, "status"]].copy()
        handicap_lookup = {
            left_name: int(player_rows.loc[player_rows["Player Index"] == left_idx, "Playing Handicap"].iloc[0]),
            right_name: int(player_rows.loc[player_rows["Player Index"] == right_idx, "Playing Handicap"].iloc[0]),
        }
        shot_info = build_shot_allocation_table(course_df[["hole", "si"]], handicap_lookup)
        allocation = shot_info["table"].pivot(index="hole", columns="Player", values="shots_received").reset_index()
        match_frame = match_frame.merge(allocation, on="hole", how="left")
        match_frame["left_shots"] = pd.to_numeric(match_frame[left_name], errors="coerce").fillna(0).astype(int)
        match_frame["right_shots"] = pd.to_numeric(match_frame[right_name], errors="coerce").fillna(0).astype(int)
        match_frame["left_net"] = pd.to_numeric(match_frame[left_column], errors="coerce") - match_frame["left_shots"]
        match_frame["right_net"] = pd.to_numeric(match_frame[right_column], errors="coerce") - match_frame["right_shots"]

        played = match_frame[left_column].notna() & match_frame[right_column].notna()
        match_frame["hole_result"] = "Pending"
        match_frame.loc[played & (match_frame["left_net"] < match_frame["right_net"]), "hole_result"] = left_name
        match_frame.loc[played & (match_frame["right_net"] < match_frame["left_net"]), "hole_result"] = right_name
        match_frame.loc[played & (match_frame["right_net"] == match_frame["left_net"]), "hole_result"] = "Halved"
        match_frame["match_delta"] = 0
        match_frame.loc[match_frame["hole_result"] == left_name, "match_delta"] = 1
        match_frame.loc[match_frame["hole_result"] == right_name, "match_delta"] = -1
        match_frame["match_balance"] = match_frame["match_delta"].cumsum()
        match_frame["status_text"] = [
            format_match_status(int(balance), left_name, right_name, int(hole), len(match_frame))
            if result != "Pending"
            else "Pending"
            for balance, hole, result in zip(match_frame["match_balance"], match_frame["hole"], match_frame["hole_result"])
        ]
        holes_played = int(played.sum())
        current_balance = int(match_frame.loc[played, "match_delta"].sum()) if holes_played else 0
        complete = _is_match_complete(current_balance, holes_played, len(match_frame))
        awarded = _team_points_from_balance(
            current_balance,
            complete,
            "red" if left_idx in TEAM_A_PLAYERS else "blue",
            "red" if right_idx in TEAM_A_PLAYERS else "blue",
            match["point_value"],
        )
        projected = _projection_points_from_balance(
            current_balance,
            "red" if left_idx in TEAM_A_PLAYERS else "blue",
            "red" if right_idx in TEAM_A_PLAYERS else "blue",
            match["point_value"],
        )
        awarded_points = _add_points(awarded_points, awarded)
        projected_points = _add_points(projected_points, projected)

        exported = match_frame.rename(
            columns={
                left_column: f"{left_name} Gross",
                right_column: f"{right_name} Gross",
                left_name: f"{left_name} Shots",
                right_name: f"{right_name} Shots",
                "left_net": f"{left_name} Net",
                "right_net": f"{right_name} Net",
                "hole_result": "Hole Result",
                "status_text": "Match Status",
            }
        )
        combined_export_parts.append(exported)
        matches.append(
            {
                "label": f"{left_name} vs {right_name}",
                "players": (left_name, right_name),
                "relative_to": shot_info["relative_to"],
                "holes_played": holes_played,
                "current_balance": current_balance,
                "current_status": format_match_status(current_balance, left_name, right_name, holes_played, len(match_frame)),
                "is_complete": complete,
                "winner": _winner_from_balance(current_balance, left_name, right_name),
                "awarded_points": awarded,
                "projected_points": projected,
                "last_hole": _last_completed_hole(match_frame, "hole_result"),
                "momentum": _build_momentum(match_frame["hole_result"]),
                "splits": _split_wins(match_frame, left_name, right_name, "hole_result"),
                "summary_df": match_frame,
            }
        )

    player_totals = pd.DataFrame(
        {
            "Player": player_names,
            "Gross Total": [_sum_scores(summary[f"player_{index + 1}"]) for index in range(4)],
        }
    )
    player_totals = player_totals.merge(player_rows[["Player", "Playing Handicap"]], on="Player", how="left")
    player_totals["Net Total"] = player_totals.apply(
        lambda row: None if row["Gross Total"] is None else int(row["Gross Total"] - row["Playing Handicap"]),
        axis=1,
    )
    team_totals = pd.DataFrame(
        {
            "Team": [build_team_label("red", player_names), build_team_label("blue", player_names)],
            "Gross Total": [
                _sum_optional(player_totals.iloc[list(TEAM_A_PLAYERS)]["Gross Total"].tolist()),
                _sum_optional(player_totals.iloc[list(TEAM_B_PLAYERS)]["Gross Total"].tolist()),
            ],
            "Net Total": [
                _sum_optional(player_totals.iloc[list(TEAM_A_PLAYERS)]["Net Total"].tolist()),
                _sum_optional(player_totals.iloc[list(TEAM_B_PLAYERS)]["Net Total"].tolist()),
            ],
        }
    )
    export_df = pd.concat(combined_export_parts, axis=1)
    export_df = export_df.loc[:, ~export_df.columns.duplicated()]
    return {
        "format_name": "Singles",
        "matches": matches,
        "player_totals": player_totals,
        "team_totals": team_totals,
        "summary_df": summary,
        "awarded_points": awarded_points,
        "projected_points": projected_points,
        "status_text": " / ".join(match["current_status"] for match in matches) if matches else "Awaiting scores",
        "winner": "red" if awarded_points["red"] > awarded_points["blue"] else "blue" if awarded_points["blue"] > awarded_points["red"] else "",
        "is_complete": all(match["is_complete"] for match in matches) if matches else False,
        "export_df": export_df,
        "export_bytes": _export_csv(export_df),
    }


def score_four_ball(
    course_df: pd.DataFrame,
    score_df: pd.DataFrame,
    player_rows: pd.DataFrame,
    player_names: list[str],
) -> dict[str, Any]:
    context = _build_team_better_ball_summary(course_df, score_df, player_rows, player_names)
    summary = context["summary"]
    played = context["played"]
    team_a_label = context["team_a_label"]
    team_b_label = context["team_b_label"]
    shot_info = context["shot_info"]
    player_totals = context["player_totals"].copy()
    team_totals = context["team_totals"].copy()

    summary["match_delta"] = 0
    summary.loc[summary["hole_result"] == team_a_label, "match_delta"] = 1
    summary.loc[summary["hole_result"] == team_b_label, "match_delta"] = -1
    summary["match_balance"] = summary["match_delta"].cumsum()
    summary["match_status"] = [
        format_match_status(int(balance), team_a_label, team_b_label, int(hole), len(summary))
        if result != "Pending"
        else "Pending"
        for balance, hole, result in zip(summary["match_balance"], summary["hole"], summary["hole_result"])
    ]

    holes_played = int(played.sum())
    current_balance = int(summary.loc[played, "match_delta"].sum()) if holes_played else 0
    complete = _is_match_complete(current_balance, holes_played, len(summary))
    awarded = _team_points_from_balance(current_balance, complete, "red", "blue", 1.0)
    projected = _projection_points_from_balance(current_balance, "red", "blue", 1.0)
    player_totals["Holes Won For Team"] = [
        int((summary["hole_result"].eq(team_a_label) & summary["team_a_contributor"].eq(player_names[index])).sum())
        if index in TEAM_A_PLAYERS
        else int((summary["hole_result"].eq(team_b_label) & summary["team_b_contributor"].eq(player_names[index])).sum())
        for index in range(4)
    ]

    export_df = summary.rename(
        columns={
            "team_a_best_gross": f"{team_a_label} Best Gross",
            "team_b_best_gross": f"{team_b_label} Best Gross",
            "team_a_best_net": f"{team_a_label} Best Net",
            "team_b_best_net": f"{team_b_label} Best Net",
            "hole_result": "Hole Result",
            "match_status": "Match Status",
        }
    )
    return {
        "format_name": "4-Ball",
        "match": {
            "label": f"{team_a_label} vs {team_b_label}",
            "relative_to": shot_info["relative_to"],
            "holes_played": holes_played,
            "current_balance": current_balance,
            "current_status": format_match_status(current_balance, team_a_label, team_b_label, holes_played, len(summary)),
            "is_complete": complete,
            "winner": _winner_from_balance(current_balance, team_a_label, team_b_label),
            "awarded_points": awarded,
            "projected_points": projected,
            "last_hole": _last_completed_hole(summary, "hole_result"),
            "momentum": _build_momentum(summary["hole_result"]),
            "splits": _split_wins(summary, team_a_label, team_b_label, "hole_result"),
            "summary_df": summary,
        },
        "player_totals": player_totals,
        "team_totals": team_totals,
        "summary_df": summary,
        "awarded_points": awarded,
        "projected_points": projected,
        "status_text": format_match_status(current_balance, team_a_label, team_b_label, holes_played, len(summary)),
        "winner": _winner_from_totals(int(awarded["red"]), int(awarded["blue"])),
        "is_complete": complete,
        "export_df": export_df,
        "export_bytes": _export_csv(export_df),
    }


def _stroke_play_status(team_a_label: str, team_b_label: str, red_total: int, blue_total: int, holes_played: int, complete: bool) -> str:
    if holes_played <= 0:
        return "Scoring not started"
    if red_total == blue_total:
        return "Round tied on net better ball" if complete else f"All square on net better ball through {holes_played}"
    leader = team_a_label if red_total < blue_total else team_b_label
    margin = abs(red_total - blue_total)
    return f"{leader} won by {margin} net shots" if complete else f"{leader} lead by {margin} net shots through {holes_played}"


def score_stroke_play(
    course_df: pd.DataFrame,
    score_df: pd.DataFrame,
    player_rows: pd.DataFrame,
    player_names: list[str],
) -> dict[str, Any]:
    context = _build_team_better_ball_summary(course_df, score_df, player_rows, player_names)
    summary = context["summary"]
    played = context["played"]
    team_a_label = context["team_a_label"]
    team_b_label = context["team_b_label"]
    player_totals = context["player_totals"].copy()
    team_totals = context["team_totals"].copy()

    summary["red_running_total"] = summary["team_a_best_net"].fillna(0).cumsum()
    summary["blue_running_total"] = summary["team_b_best_net"].fillna(0).cumsum()
    holes_played = int(played.sum())
    red_total = int(summary.loc[played, "team_a_best_net"].sum()) if holes_played else 0
    blue_total = int(summary.loc[played, "team_b_best_net"].sum()) if holes_played else 0
    complete = holes_played == len(summary)
    awarded = _points_from_totals(red_total, blue_total, complete)
    projected = _projected_points_from_totals(red_total, blue_total)
    player_totals["Counting Holes"] = [
        int(summary["team_a_contributor"].eq(player_names[index]).sum())
        if index in TEAM_A_PLAYERS
        else int(summary["team_b_contributor"].eq(player_names[index]).sum())
        for index in range(4)
    ]
    team_totals["Result"] = [_stroke_play_status(team_a_label, team_b_label, red_total, blue_total, holes_played, complete), ""]
    status_text = _stroke_play_status(team_a_label, team_b_label, red_total, blue_total, holes_played, complete)

    export_df = summary.rename(
        columns={
            "team_a_best_gross": f"{team_a_label} Best Gross",
            "team_b_best_gross": f"{team_b_label} Best Gross",
            "team_a_best_net": f"{team_a_label} Best Net",
            "team_b_best_net": f"{team_b_label} Best Net",
            "team_a_contributor": "Red Counter",
            "team_b_contributor": "Blue Counter",
            "red_running_total": "Red Running Total",
            "blue_running_total": "Blue Running Total",
            "hole_result": "Hole Result",
        }
    )
    return {
        "format_name": "Stroke Play",
        "stroke_play": {
            "holes_played": holes_played,
            "red_total": red_total,
            "blue_total": blue_total,
            "current_status": status_text,
            "last_hole": _last_completed_hole(summary, "hole_result"),
        },
        "player_totals": player_totals,
        "team_totals": team_totals,
        "summary_df": summary,
        "awarded_points": awarded,
        "projected_points": projected,
        "status_text": status_text,
        "winner": _winner_from_totals(red_total, blue_total),
        "is_complete": complete,
        "export_df": export_df,
        "export_bytes": _export_csv(export_df),
    }


def _skins_status(team_a_label: str, team_b_label: str, red_skins: int, blue_skins: int, holes_played: int, carryover: int, complete: bool) -> str:
    if holes_played <= 0:
        return "Scoring not started"
    if red_skins == blue_skins:
        base = f"All square on skins through {holes_played}"
    else:
        leader = team_a_label if red_skins > blue_skins else team_b_label
        margin = abs(red_skins - blue_skins)
        base = f"{leader} lead by {margin} skins through {holes_played}"
    if complete:
        if red_skins == blue_skins:
            base = f"Skins tied {red_skins}-{blue_skins}"
        else:
            leader = team_a_label if red_skins > blue_skins else team_b_label
            margin = abs(red_skins - blue_skins)
            base = f"{leader} won by {margin} skins"
    if carryover > 1 and not complete:
        return f"{base} • {carryover} skins in the pot"
    if carryover > 1 and complete:
        return f"{base} • {carryover} skins left unresolved after 18"
    return base


def score_skins(
    course_df: pd.DataFrame,
    score_df: pd.DataFrame,
    player_rows: pd.DataFrame,
    player_names: list[str],
) -> dict[str, Any]:
    context = _build_team_better_ball_summary(course_df, score_df, player_rows, player_names)
    summary = context["summary"]
    played = context["played"]
    team_a_label = context["team_a_label"]
    team_b_label = context["team_b_label"]
    player_totals = context["player_totals"].copy()
    team_totals = context["team_totals"].copy()

    red_skins = 0
    blue_skins = 0
    pot = 1
    awarded_red: list[int] = []
    awarded_blue: list[int] = []
    running_red: list[int] = []
    running_blue: list[int] = []
    pot_sizes: list[int] = []
    carryovers: list[int] = []
    for is_played, hole_result in zip(played.tolist(), summary["hole_result"].tolist()):
        pot_sizes.append(pot)
        award_red = 0
        award_blue = 0
        if is_played:
            if hole_result == team_a_label:
                award_red = pot
                red_skins += pot
                pot = 1
            elif hole_result == team_b_label:
                award_blue = pot
                blue_skins += pot
                pot = 1
            else:
                pot += 1
        awarded_red.append(award_red)
        awarded_blue.append(award_blue)
        running_red.append(red_skins)
        running_blue.append(blue_skins)
        carryovers.append(pot)

    summary["skins_pot"] = pot_sizes
    summary["red_skins_awarded"] = awarded_red
    summary["blue_skins_awarded"] = awarded_blue
    summary["red_running_skins"] = running_red
    summary["blue_running_skins"] = running_blue
    summary["next_pot"] = carryovers

    holes_played = int(played.sum())
    complete = holes_played == len(summary)
    carryover = pot
    awarded = _points_from_totals(red_skins, blue_skins, complete)
    projected = _projected_points_from_totals(red_skins, blue_skins)
    player_totals["Skins Won For Team"] = [
        int(summary.loc[summary["team_a_contributor"].eq(player_names[index]), "red_skins_awarded"].sum())
        if index in TEAM_A_PLAYERS
        else int(summary.loc[summary["team_b_contributor"].eq(player_names[index]), "blue_skins_awarded"].sum())
        for index in range(4)
    ]
    team_totals["Skins Won"] = [red_skins, blue_skins]
    status_text = _skins_status(team_a_label, team_b_label, red_skins, blue_skins, holes_played, carryover, complete)

    export_df = summary.rename(
        columns={
            "team_a_best_gross": f"{team_a_label} Best Gross",
            "team_b_best_gross": f"{team_b_label} Best Gross",
            "team_a_best_net": f"{team_a_label} Best Net",
            "team_b_best_net": f"{team_b_label} Best Net",
            "team_a_contributor": "Red Counter",
            "team_b_contributor": "Blue Counter",
            "skins_pot": "Skins Pot",
            "red_skins_awarded": "Red Skins Awarded",
            "blue_skins_awarded": "Blue Skins Awarded",
            "red_running_skins": "Red Running Skins",
            "blue_running_skins": "Blue Running Skins",
            "next_pot": "Next Pot",
            "hole_result": "Hole Result",
        }
    )
    return {
        "format_name": "Skins",
        "skins": {
            "holes_played": holes_played,
            "red_skins": red_skins,
            "blue_skins": blue_skins,
            "carryover_skins": carryover,
            "current_status": status_text,
            "last_hole": _last_completed_hole(summary, "hole_result"),
        },
        "player_totals": player_totals,
        "team_totals": team_totals,
        "summary_df": summary,
        "awarded_points": awarded,
        "projected_points": projected,
        "status_text": status_text,
        "winner": _winner_from_totals(red_skins, blue_skins),
        "is_complete": complete,
        "export_df": export_df,
        "export_bytes": _export_csv(export_df),
    }
