from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from components.layout import render_metric_card, render_section_header, render_status_card
from domain.formatting import format_handicap_index
from domain.handicap import build_player_handicap_table
from domain.scoring import compute_round_results
from support.google_sheets import GoogleSheetsError
from support.score_status import with_derived_score_status
from support.session import get_format_config
from support.state_helpers import build_score_rows_for_hole, save_players, save_result_payload, save_scores_for_hole, verify_scores_for_hole
from domain.weekend_config import TEAM_CONFIG


def _player_id_validation_error(player_ids: list[str]) -> str:
    normalized = [str(player_id or "").strip() for player_id in player_ids]
    if any(not player_id for player_id in normalized):
        return "Player setup is invalid: every active player needs a stable player ID before scorecard edits can be saved."
    if len({player_id.casefold() for player_id in normalized}) != len(normalized):
        return "Player setup is invalid: active player IDs must be unique before scorecard edits can be saved."
    return ""


def _changed_scorecard_holes(
    before: pd.DataFrame,
    after: pd.DataFrame,
    score_columns: list[str],
) -> list[int]:
    columns = ["status", *score_columns]
    before_indexed = before.set_index("hole")[columns].astype("string").fillna("")
    after_indexed = after.set_index("hole")[columns].astype("string").fillna("")
    changed: list[int] = []
    for hole in after_indexed.index:
        if hole not in before_indexed.index or not after_indexed.loc[hole].equals(before_indexed.loc[hole]):
            changed.append(int(hole))
    return changed


def _invalid_complete_holes(scores: pd.DataFrame, score_columns: list[str]) -> list[int]:
    invalid: list[int] = []
    for _, row in scores.iterrows():
        if str(row.get("status", "")).strip() != "Complete":
            continue
        if any(pd.isna(row.get(column)) for column in score_columns):
            invalid.append(int(row["hole"]))
    return invalid


def _save_verified_scorecard_changes(
    course_df: pd.DataFrame,
    round_runtime: dict[str, object],
    round_state: dict[str, object],
    tee_rating: dict[str, object],
    persisted: pd.DataFrame,
    changed_holes: list[int],
    singles_matchups: list[dict[str, object]] | None = None,
) -> None:
    format_name = str(round_runtime["format_name"])
    for hole in changed_holes:
        save_scores_for_hole(round_runtime, int(hole), persisted, round_state)
        verify_scores_for_hole(
            str(round_runtime["round_id"]),
            int(hole),
            build_score_rows_for_hole(
                round_id=str(round_runtime["round_id"]),
                hole=int(hole),
                format_name=format_name,
                scoring_mode=str(round_runtime["scoring_mode"]),
                score_frame=persisted,
                round_state=round_state,
            ),
        )
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
        handicap_allocation=str(round_runtime.get("handicap_allocation") or ""),
        singles_matchups=singles_matchups,
    )
    save_result_payload(str(round_runtime["round_id"]), result)


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
    singles_matchups: list[dict[str, object]] | None = None,
    persistence: dict[str, object] | None = None,
) -> pd.DataFrame:
    format_name = str(round_runtime["format_name"])
    config = get_format_config(format_name)
    player_names = list(round_state["player_names"])
    player_ids = list(round_state["player_ids"])
    player_id_error = _player_id_validation_error(player_ids)
    persistence_status = (persistence or {}).get("status", {}) if isinstance(persistence, dict) else {}
    save_blocked = (persistence or {}).get("mode") != "sheets" and str(persistence_status.get("state", "")) in {
        "auth_required",
        "error",
    }

    score_columns = list(config["score_columns"])
    editor_df = with_derived_score_status(round_state["scores"], score_columns)
    rename_map = {f"player_{index + 1}": player_names[index] for index in range(config["active_player_count"])}

    display_df = editor_df.rename(columns={"hole": "Hole", "status": "Status", **rename_map})
    column_config = {
        "Hole": st.column_config.NumberColumn("Hole", disabled=True, width="small"),
        "Status": st.column_config.TextColumn("Status", disabled=True),
    }
    for label in rename_map.values():
        column_config[label] = st.column_config.NumberColumn(label, min_value=1, max_value=20, step=1)
    edited = st.data_editor(
        display_df,
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        disabled=["Hole", "Status"],
        column_config=column_config,
        key=f"score_editor::{round_runtime['round_id']}::{format_name}",
    )
    persisted = edited.rename(columns={value: key for key, value in rename_map.items()}).rename(columns={"Hole": "hole", "Status": "status"})
    persisted = persisted[round_state["scores"].columns].copy()
    for column in score_columns:
        persisted[column] = pd.to_numeric(persisted[column], errors="coerce").astype("Int64")
    persisted = with_derived_score_status(persisted, score_columns)
    changed_holes = _changed_scorecard_holes(editor_df, persisted, score_columns)
    invalid_complete_holes = _invalid_complete_holes(persisted, score_columns)

    if changed_holes:
        st.info(f"Unsaved scorecard edits on hole(s): {', '.join(str(hole) for hole in changed_holes)}.")
    else:
        st.caption("No unsaved scorecard edits.")
    if player_id_error:
        st.error(player_id_error)
    duplicate_score_rows = list(round_state.get("duplicate_score_rows", []))
    if duplicate_score_rows:
        st.warning(
            f"Duplicate Google Sheets score rows detected for this round ({len(duplicate_score_rows)} player/hole identities). "
            "The latest updated_at row is shown here; older duplicate rows are left in the workbook for manual review."
        )
    if invalid_complete_holes:
        st.error(f"Complete holes must have all player scores. Check hole(s): {', '.join(str(hole) for hole in invalid_complete_holes)}.")
    if save_blocked:
        st.error("Google Sheets is unavailable. Full scorecard edits cannot be saved until workbook access is restored.")

    editor_actions = st.columns(2)
    with editor_actions[0]:
        save_clicked = st.button(
            "Save Full Scorecard",
            width="stretch",
            type="primary",
            disabled=save_blocked or bool(player_id_error) or bool(invalid_complete_holes) or not changed_holes,
        )
    with editor_actions[1]:
        reset_clicked = st.button("Discard Table Edits", width="stretch", disabled=not changed_holes)

    if reset_clicked:
        st.session_state.pop(f"score_editor::{round_runtime['round_id']}::{format_name}", None)
        st.rerun()

    if save_clicked:
        try:
            with st.spinner("Saving changed holes and verifying Google Sheets rows..."):
                _save_verified_scorecard_changes(
                    course_df=course_df,
                    round_runtime=round_runtime,
                    round_state=round_state,
                    tee_rating=tee_rating,
                    persisted=persisted,
                    changed_holes=changed_holes,
                    singles_matchups=singles_matchups,
                )
            st.session_state["last_live_save_status"] = {
                "round_id": str(round_runtime["round_id"]),
                "hole": ", ".join(str(hole) for hole in changed_holes),
                "state": "verified",
                "verified_at": datetime.now().strftime("%H:%M:%S"),
            }
            st.rerun()
        except GoogleSheetsError as exc:
            st.error(str(exc))
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
    singles_matchups: list[dict[str, object]] | None = None,
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
        render_full_card_editor(
            course_df=course_df,
            round_runtime=round_runtime,
            round_state=round_state,
            tee_rating=tee_rating,
            singles_matchups=singles_matchups,
        )

    render_round_summary_metrics(format_name=str(round_runtime["format_name"]), round_state=round_state)

    return {
        "player_names": round_state["player_names"],
        "handicap_indexes": round_state["handicap_indexes"],
        "scores": round_state["scores"],
    }
