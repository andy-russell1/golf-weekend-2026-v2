from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from components.layout import render_chip_row, render_metric_card, render_section_header, render_status_card
from support.data_loader import get_hole_image, get_hole_record
from domain.formatting import format_hole_name, format_relative_to
from support.google_sheets import GoogleSheetsError
from domain.scoring import compute_round_results, get_hole_shots_for_display
from support.session import TEAM_A_PLAYERS, get_format_config, set_active_hole
from support.state_helpers import save_result_payload, save_scores_for_hole
from domain.weekend_config import build_team_label


SCORE_OPTIONS = ["—", *list(range(1, 16))]


def _coerce_score(value: object) -> pd._libs.missing.NAType | int:
    if value in (None, "", "—"):
        return pd.NA
    return int(value)


def _status_for_values(values: list[object], required_count: int | None = None) -> str:
    populated = [value for value in values if value not in (None, "", "—")]
    if not populated:
        return "Pending"
    target = required_count if required_count is not None else len(values)
    if len(populated) >= target:
        return "Complete"
    return "In Progress"


def _update_scores(
    scores: pd.DataFrame,
    hole: int,
    format_name: str,
    values: dict[str, object],
    force_pending: bool = False,
    scoring_mode: str = "net",
) -> pd.DataFrame:
    updated = scores.copy()
    mask = updated["hole"] == hole
    if force_pending:
        updated.loc[mask, "status"] = "Pending"
        for column in updated.columns:
            if column not in {"hole", "status"}:
                updated.loc[mask, column] = pd.NA
        return updated

    required_keys = [
        key
        for key, value in values.items()
        if key.startswith("player_") and value not in (None, "", "—")
    ]
    required_count = len(required_keys)
    updated.loc[mask, "status"] = _status_for_values(list(values.values()), required_count=required_count)
    for column, value in values.items():
        updated.loc[mask, column] = _coerce_score(value)
    numeric_columns = [column for column in updated.columns if column.startswith("player_")]
    for column in numeric_columns:
        updated[column] = pd.to_numeric(updated[column], errors="coerce").astype("Int64")
    return updated


def _hole_preview(result: dict[str, Any], format_name: str, hole: int) -> list[dict[str, str]]:
    if format_name == "Singles":
        previews: list[dict[str, str]] = []
        for match in result.get("matches", []):
            row = match["summary_df"][match["summary_df"]["hole"] == hole]
            if row.empty:
                continue
            hole_row = row.iloc[0]
            previews.append(
                {
                    "title": match["label"],
                    "status": str(hole_row.get("hole_result", "Pending")),
                    "support": str(hole_row.get("status_text", "Pending")),
                }
            )
        return previews

    if format_name == "Stroke Play":
        row = result.get("summary_df", pd.DataFrame())
        hole_row = row[row["hole"] == hole]
        if hole_row.empty:
            return []
        current = hole_row.iloc[0]
        return [
            {
                "title": "Stroke Play",
                "status": str(current.get("hole_result", "Pending")),
                "support": f"Running totals {int(current.get('red_running_total', 0) or 0)} / {int(current.get('blue_running_total', 0) or 0)}",
            }
        ]

    if format_name == "Skins":
        row = result.get("summary_df", pd.DataFrame())
        hole_row = row[row["hole"] == hole]
        if hole_row.empty:
            return []
        current = hole_row.iloc[0]
        return [
            {
                "title": "Skins",
                "status": str(current.get("hole_result", "Pending")),
                "support": f"Pot {int(current.get('skins_pot', 1) or 1)} • running skins {int(current.get('red_running_skins', 0) or 0)} / {int(current.get('blue_running_skins', 0) or 0)}",
            }
        ]

    match = result.get("match")
    if not match:
        return []
    row = match["summary_df"][match["summary_df"]["hole"] == hole]
    if row.empty:
        return []
    hole_row = row.iloc[0]
    return [
        {
            "title": "Hole Result",
            "status": str(hole_row.get("hole_result", "Pending")),
            "support": str(hole_row.get("match_status", "Pending")),
        }
    ]


def render_live_scoring(
    course_df: pd.DataFrame,
    course: str,
    course_title: str,
    round_runtime: dict[str, Any],
    tee_rating: dict[str, Any],
    round_state: dict[str, Any],
    shot_views: list[dict[str, Any]],
) -> dict[str, Any]:
    format_name = round_runtime["format_name"]
    allowance_percent = round_runtime["allowance_percent"]
    player_names = list(round_state["player_names"])
    handicap_indexes = list(round_state["handicap_indexes"])
    player_ids = list(round_state["player_ids"])

    render_section_header(
        "Live Hole Entry",
        "Enter one hole at a time, save straight to the weekend workbook, and keep the current round state obvious on a phone.",
    )

    holes = [int(hole) for hole in course_df["hole"].dropna().tolist()]
    config = get_format_config(format_name)
    active_hole = int(round_state["active_hole"])
    if active_hole not in holes:
        active_hole = holes[0]
        set_active_hole(round_runtime["round_id"], active_hole)

    nav_columns = st.columns([0.8, 1.4, 0.8, 1.2])
    with nav_columns[0]:
        if st.button("Previous", width="stretch", disabled=active_hole == holes[0]):
            set_active_hole(round_runtime["round_id"], holes[max(0, holes.index(active_hole) - 1)])
            st.rerun()
    with nav_columns[1]:
        selected_hole = st.selectbox("Jump To Hole", options=holes, index=holes.index(active_hole), label_visibility="collapsed")
        if selected_hole != active_hole:
            set_active_hole(round_runtime["round_id"], int(selected_hole))
            active_hole = int(selected_hole)
    with nav_columns[2]:
        if st.button("Next", width="stretch", disabled=active_hole == holes[-1]):
            set_active_hole(round_runtime["round_id"], holes[min(len(holes) - 1, holes.index(active_hole) + 1)])
            st.rerun()
    with nav_columns[3]:
        render_metric_card("Hole", active_hole, "active")

    hole_record = get_hole_record(course, active_hole)
    hole_image = get_hole_image(course, active_hole)
    hole_name = format_hole_name(hole_record.get("hole_name"), active_hole)
    yardage_key = "yards_white" if round_runtime["tee_label"].lower() == "white" else "yards_yellow"

    header_columns = st.columns([1.25, 0.95], gap="large")
    with header_columns[0]:
        st.markdown(f"### {hole_name}")
        render_chip_row(
            [
                course_title,
                f"Par {hole_record.get('par', '—')}",
                f"SI {hole_record.get('si', '—')}",
                f"{round_runtime['tee_label']} {hole_record.get(yardage_key, '—')}y",
            ]
        )
        if hole_image["available"]:
            st.image(str(hole_image["path"]), use_column_width=True)
        else:
            st.caption(hole_image.get("message", "No hole image available"))
    with header_columns[1]:
        st.markdown("#### Handicap This Hole")
        for group in get_hole_shots_for_display(shot_views, active_hole):
            shot_text = [f"{label}: {shots}" for label, shots in group["shots"].items()]
            render_chip_row([group["label"], format_relative_to(group["relative_to"]), *shot_text], tone="accent")

        if isinstance(hole_record.get("pro_tip"), str) and hole_record["pro_tip"].strip():
            st.markdown("#### Tip")
            st.write(hole_record["pro_tip"].strip())

    current_row = round_state["scores"][round_state["scores"]["hole"] == active_hole].iloc[0]
    entry_values: dict[str, object] = {}

    st.markdown("#### Enter Scores")
    score_columns = list(config["score_columns"])
    defaults = []
    for column in score_columns:
        value = current_row[column]
        defaults.append("—" if pd.isna(value) else int(value))
    entry_columns = st.columns(4)
    for column, label, score_column, default in zip(entry_columns, player_names, score_columns, defaults):
        with column:
            team_tone = "red" if label in (player_names[TEAM_A_PLAYERS[0]], player_names[TEAM_A_PLAYERS[1]]) else "blue"
            render_status_card(label, current_row["status"], None, tone=team_tone)
            index = SCORE_OPTIONS.index(default) if default in SCORE_OPTIONS else 0
            entry_values[score_column] = st.selectbox(
                f"{label} Gross",
                options=SCORE_OPTIONS,
                index=index,
                key=f"live::{course}::{format_name}::{active_hole}::{label}",
            )

    preview_scores = _update_scores(
        round_state["scores"],
        active_hole,
        format_name=format_name,
        values=entry_values,
        scoring_mode=scoring_mode,
    )
    preview_result = (
        compute_round_results(
            course_df=course_df,
            format_name=format_name,
            score_df=preview_scores,
            player_names=player_names,
            player_ids=player_ids,
            handicap_indexes=handicap_indexes,
            tee_rating=tee_rating,
            allowance_percent=allowance_percent,
        )
        if tee_rating
        else {}
    )
    preview_cards = _hole_preview(preview_result, format_name, active_hole)
    if preview_cards:
        st.markdown("#### Live Preview")
        preview_columns = st.columns(len(preview_cards))
        for column, card in zip(preview_columns, preview_cards):
            with column:
                render_status_card(card["title"], card["status"], card["support"])

    action_columns = st.columns(3)
    with action_columns[0]:
        if st.button("Save Hole", width="stretch"):
            updated_scores = _update_scores(
                round_state["scores"], active_hole, format_name=format_name, values=entry_values
            )
            try:
                save_scores_for_hole(round_runtime, active_hole, updated_scores, round_state)
                if preview_result:
                    save_result_payload(round_runtime["round_id"], preview_result)
                st.rerun()
            except GoogleSheetsError as exc:
                st.error(str(exc))
    with action_columns[1]:
        if st.button("Save And Next", width="stretch"):
            updated_scores = _update_scores(
                round_state["scores"], active_hole, format_name=format_name, values=entry_values
            )
            try:
                save_scores_for_hole(round_runtime, active_hole, updated_scores, round_state)
                if preview_result:
                    save_result_payload(round_runtime["round_id"], preview_result)
                set_active_hole(round_runtime["round_id"], holes[min(len(holes) - 1, holes.index(active_hole) + 1)])
                st.rerun()
            except GoogleSheetsError as exc:
                st.error(str(exc))
    with action_columns[2]:
        if st.button("Mark Pending", width="stretch"):
            updated_scores = _update_scores(
                round_state["scores"],
                active_hole,
                format_name=format_name,
                values=entry_values,
                force_pending=True,
            )
            try:
                save_scores_for_hole(round_runtime, active_hole, updated_scores, round_state)
                if tee_rating:
                    cleared_result = compute_round_results(
                        course_df=course_df,
                        format_name=format_name,
                        score_df=updated_scores,
                        player_names=player_names,
                        player_ids=player_ids,
                        handicap_indexes=handicap_indexes,
                        tee_rating=tee_rating,
                        allowance_percent=allowance_percent,
                    )
                    save_result_payload(round_runtime["round_id"], cleared_result)
                st.rerun()
            except GoogleSheetsError as exc:
                st.error(str(exc))

    return {"active_hole": active_hole, "preview_result": preview_result}
