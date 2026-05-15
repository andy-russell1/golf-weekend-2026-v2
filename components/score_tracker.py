from __future__ import annotations

import pandas as pd
import streamlit as st

from components.layout import render_metric_card, render_section_header, render_status_card
from domain.formatting import format_handicap_index
from domain.handicap import build_player_handicap_table
from domain.scoring import compute_round_results
from support.google_sheets import GoogleSheetsError
from support.session import get_format_config
from support.state_helpers import save_players, save_result_payload, save_scores_for_hole
from domain.weekend_config import TEAM_CONFIG


SCORE_OPTIONS = ["—", *list(range(1, 16))]


def render_player_handicap_editor(
    players_rows: list[dict[str, object]],
    round_runtime: dict[str, object],
    tee_rating: dict[str, object],
) -> dict[str, object]:
    ordered_rows = sorted(players_rows, key=lambda row: int(float(row.get("display_order") or 0)))
    editor_rows: list[dict[str, object]] = []

    st.caption("Edit player names and handicap indexes here. The live preview below updates against the selected tee and allowance.")
    for team_id in ("red", "blue"):
        st.markdown(f"#### {TEAM_CONFIG[team_id]['name']}")
        team_players = [row for row in ordered_rows if str(row.get("team_id")) == team_id]
        for player_number, row in enumerate(team_players, start=1):
            st.markdown(f"##### Player {player_number}")
            editor_rows.append(
                {
                    **row,
                    "player_name": st.text_input(
                        "Player name",
                        value=str(row.get("player_name", "")),
                        key=f"player_name::{team_id}::{player_number}",
                        placeholder="Player name",
                    ),
                    "handicap_index": st.number_input(
                        "Handicap index",
                        min_value=0.0,
                        max_value=54.0,
                        step=0.1,
                        value=float(row.get("handicap_index") or 0.0),
                        key=f"handicap_index::{team_id}::{player_number}",
                    ),
                }
            )
            st.caption("Used across Live Scoring, Match Centre, and the course guide.")

    player_names = [str(row.get("player_name", "")).strip() for row in editor_rows]
    handicap_indexes = [float(row.get("handicap_index") or 0.0) for row in editor_rows]
    live_handicaps = build_player_handicap_table(
        player_names=player_names,
        handicap_indexes=handicap_indexes,
        tee_rating=tee_rating,
        allowance=int(round_runtime["allowance_percent"]) / 100,
    )

    if st.button("Save Players And Handicaps", width="stretch"):
        try:
            save_players(editor_rows)
            st.rerun()
        except GoogleSheetsError as exc:
            st.error(str(exc))

    if not live_handicaps.empty:
        st.markdown("#### Playing Handicap Preview")
        card_columns = st.columns(2)
        for index, (_, row) in enumerate(live_handicaps.iterrows()):
            with card_columns[index % 2]:
                render_status_card(
                    str(row["Player"]),
                    f"Playing {int(row['Playing Handicap'])}",
                    f"HI {format_handicap_index(row['Handicap Index'])} • Course {int(row['Course Handicap'])} • Allowance {int(row['Allowance'] * 100)}%",
                    tone=str(row["Team Id"]),
                )

        handicap_display = live_handicaps.copy()
        handicap_display["Handicap Index"] = handicap_display["Handicap Index"].apply(format_handicap_index)
        handicap_display["Allowance"] = handicap_display["Allowance"].apply(lambda value: f"{int(value * 100)}%")
        with st.expander("Detailed handicap table", expanded=False):
            st.dataframe(
                handicap_display[["Player", "Team", "Handicap Index", "Course Handicap", "Playing Handicap", "Allowance"]],
                width="stretch",
                hide_index=True,
            )
    else:
        st.info(f"No tee rating metadata is available for {round_runtime['tee_label']} tees, so WHS handicaps cannot be shown.")

    return {"players_rows": editor_rows, "live_handicaps": live_handicaps}


def render_full_card_editor(
    course_df: pd.DataFrame,
    round_runtime: dict[str, object],
    round_state: dict[str, object],
    tee_rating: dict[str, object],
) -> pd.DataFrame:
    format_name = str(round_runtime["format_name"])
    config = get_format_config(format_name)
    player_names = list(round_state["player_names"])

    editor_df = round_state["scores"].copy()
    score_columns = list(config["score_columns"])
    holes = [int(hole) for hole in editor_df["hole"].tolist()]
    selected_hole = st.selectbox(
        "Hole to correct",
        options=holes,
        index=holes.index(int(round_state["active_hole"])) if int(round_state["active_hole"]) in holes else 0,
        key=f"full-card-hole::{round_runtime['round_id']}",
    )
    current_row = editor_df[editor_df["hole"] == selected_hole].iloc[0]
    status_value = st.selectbox(
        "Hole status",
        options=["Pending", "In Progress", "Complete"],
        index=["Pending", "In Progress", "Complete"].index(str(current_row["status"])),
        key=f"full-card-status::{round_runtime['round_id']}::{selected_hole}",
    )

    entry_values: dict[str, object] = {}
    for player_index, score_column in enumerate(score_columns):
        label = player_names[player_index]
        current_value = current_row[score_column]
        default = "—" if pd.isna(current_value) else int(current_value)
        score_row = st.columns([1.1, 1], gap="small")
        with score_row[0]:
            st.markdown(f"**{label}**")
            st.caption("No saved score" if default == "—" else f"Saved gross {default}")
        with score_row[1]:
            entry_values[score_column] = st.selectbox(
                f"{label} score",
                options=SCORE_OPTIONS,
                index=SCORE_OPTIONS.index(default) if default in SCORE_OPTIONS else 0,
                key=f"full-card-score::{round_runtime['round_id']}::{selected_hole}::{score_column}",
                label_visibility="collapsed",
            )

    persisted = editor_df.copy()
    hole_mask = persisted["hole"] == selected_hole
    persisted.loc[hole_mask, "status"] = status_value
    for column in score_columns:
        persisted.loc[hole_mask, column] = pd.NA if entry_values[column] in ("—", None, "") else int(entry_values[column])
    for column in score_columns:
        persisted[column] = pd.to_numeric(persisted[column], errors="coerce").astype("Int64")
    persisted["status"] = persisted["status"].fillna("Pending").astype(str)

    if status_value == "Pending":
        persisted.loc[hole_mask, score_columns] = pd.NA

    if st.button("Save Hole Correction", width="stretch", type="primary"):
        try:
            save_scores_for_hole(round_runtime, int(selected_hole), persisted, round_state)
            result = compute_round_results(
                course_df=course_df,
                format_name=format_name,
                score_df=persisted,
                player_names=list(round_state["player_names"]),
                player_ids=list(round_state["player_ids"]),
                handicap_indexes=list(round_state["handicap_indexes"]),
                tee_rating=tee_rating,
                allowance_percent=int(round_runtime["allowance_percent"]),
                scramble_mode=str(round_runtime["scramble_mode"]),
                scoring_mode=str(round_runtime["scoring_mode"]),
                stableford_mode=str(round_runtime["stableford_mode"]),
            )
            save_result_payload(str(round_runtime["round_id"]), result)
            st.rerun()
        except GoogleSheetsError as exc:
            st.error(str(exc))

    with st.expander("Scorecard snapshot", expanded=False):
        rename_map = {f"player_{index + 1}": player_names[index] for index in range(config["active_player_count"])}
        display_df = persisted.rename(columns={"hole": "Hole", "status": "Status", **rename_map})
        st.dataframe(display_df, width="stretch", hide_index=True)
    return persisted


def render_round_summary_metrics(format_name: str, round_state: dict[str, object]) -> None:
    summary_columns = st.columns(3)
    with summary_columns[0]:
        render_metric_card("Format", format_name, None)
    with summary_columns[1]:
        completed = int(round_state["scores"]["status"].eq("Complete").sum())
        render_metric_card("Completed Holes", completed, "persisted")
    with summary_columns[2]:
        render_metric_card("Active Hole", int(round_state["active_hole"]), "live entry")


def render_score_tracker(
    course_df: pd.DataFrame,
    round_runtime: dict[str, object],
    round_state: dict[str, object],
    players_rows: list[dict[str, object]],
    tee_rating: dict[str, object],
) -> dict[str, object]:
    render_section_header(
        "Round Controls",
        "Use these panels for player edits, handicap checks, and full-card corrections. Live hole entry stays above as the primary workflow.",
    )

    with st.expander("Players And Handicaps", expanded=False):
        render_player_handicap_editor(
            players_rows=players_rows,
            round_runtime=round_runtime,
            tee_rating=tee_rating,
        )

    with st.expander("Full Card Edit", expanded=False):
        render_full_card_editor(course_df=course_df, round_runtime=round_runtime, round_state=round_state, tee_rating=tee_rating)

    render_round_summary_metrics(format_name=str(round_runtime["format_name"]), round_state=round_state)

    return {
        "player_names": round_state["player_names"],
        "handicap_indexes": round_state["handicap_indexes"],
        "scores": round_state["scores"],
    }
