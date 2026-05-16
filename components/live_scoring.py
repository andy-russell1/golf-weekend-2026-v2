from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from components.layout import render_chip_row, render_metric_card, render_status_card
from domain.bonus_competitions import (
    BONUS_COMPETITIONS_SETTING_KEY,
    bonus_competitions_to_json,
    competitions_for_hole,
    update_bonus_winner,
)
from domain.formatting import format_hole_name, format_relative_to
from domain.scoring import compute_round_results, get_hole_shots_for_display
from support.data_loader import get_hole_record
from support.google_sheets import GoogleSheetsError
from support.session import TEAM_A_PLAYERS, TEAM_B_PLAYERS, get_format_config
from support.state_helpers import save_result_payload, save_scores_for_hole, save_setting
from domain.weekend_config import team_name
from support.app_context import compact_team_label_text, set_active_hole_for_ui


SCORE_OPTIONS = ["—", *list(range(1, 11))]


def saved_hole_action_mode(saved_hole_complete: bool, edit_saved_hole: bool) -> str:
    if saved_hole_complete and edit_saved_hole:
        return "edit_saved"
    if saved_hole_complete:
        return "protected_saved"
    return "normal"


def _score_widget_key(round_id: str, course: str, hole: int, player_id: str) -> str:
    return f"live-score::{round_id}::{course}::{hole}::{player_id}"


def _score_value_key(round_id: str, course: str, hole: int, player_id: str) -> str:
    return f"{_score_widget_key(round_id, course, hole, player_id)}::value"


def _score_select_key(round_id: str, course: str, hole: int, player_id: str) -> str:
    return f"{_score_widget_key(round_id, course, hole, player_id)}::select"


def _normalise_score_for_widget(value: object) -> str | int:
    if value in (None, "", "—") or pd.isna(value):
        return "—"
    score = int(value)
    if score < 1 or score > 10:
        return "—"
    return score


def _score_options_for_widget(current_score: object) -> list[str | int]:
    return list(SCORE_OPTIONS)


def _increment_score(current: object, par: object, delta: int) -> int:
    if current in (None, "", "—") or pd.isna(current):
        try:
            return min(10, max(1, int(par)))
        except (TypeError, ValueError):
            return 1
    return min(10, max(1, int(current) + delta))


def _set_incremented_score(value_key: str, select_key: str, par: object, delta: int) -> None:
    updated = _increment_score(st.session_state.get(value_key, "—"), par, delta)
    st.session_state[value_key] = updated
    st.session_state[select_key] = updated


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


def _score_changed(saved_value: object, entered_value: object) -> bool:
    saved = None if pd.isna(saved_value) else int(saved_value)
    entered = _coerce_score(entered_value)
    current = None if entered is pd.NA else int(entered)
    return saved != current


def _clear_active_score_widget_values(round_runtime: dict[str, Any], course: str, hole: int, player_ids: list[str]) -> None:
    for player_id in player_ids:
        value_key = _score_value_key(round_runtime["round_id"], course, hole, player_id)
        st.session_state[value_key] = "—"


def _update_scores(
    scores: pd.DataFrame,
    hole: int,
    format_name: str,
    values: dict[str, object],
    force_pending: bool = False,
) -> pd.DataFrame:
    updated = scores.copy()
    mask = updated["hole"] == hole
    if force_pending:
        updated.loc[mask, "status"] = "Pending"
        for column in updated.columns:
            if column not in {"hole", "status"}:
                updated.loc[mask, column] = pd.NA
        return updated

    player_values = [value for key, value in values.items() if key.startswith("player_")]
    updated.loc[mask, "status"] = _status_for_values(player_values, required_count=len(player_values))
    for column, value in values.items():
        updated.loc[mask, column] = _coerce_score(value)
    numeric_columns = [column for column in updated.columns if column.startswith("player_")]
    for column in numeric_columns:
        updated[column] = pd.to_numeric(updated[column], errors="coerce").astype("Int64")
    return updated


def _hole_preview(result: dict[str, Any], format_name: str, hole: int, player_names: list[str]) -> list[dict[str, str]]:
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
                    "support": compact_team_label_text(str(hole_row.get("status_text", "Pending")), player_names),
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
            "support": compact_team_label_text(str(hole_row.get("match_status", "Pending")), player_names),
        }
    ]


def _persist_live_scores(
    round_runtime: dict[str, Any],
    updated_scores: pd.DataFrame,
    round_state: dict[str, Any],
    hole: int,
    result_payload: dict[str, Any],
) -> None:
    save_scores_for_hole(round_runtime, hole, updated_scores, round_state)
    if result_payload:
        save_result_payload(round_runtime["round_id"], result_payload)
    st.session_state["last_live_save_status"] = {
        "round_id": round_runtime["round_id"],
        "hole": hole,
        "saved_at": datetime.now().strftime("%H:%M:%S"),
    }


def _render_bonus_competition_winners(
    bonus_competitions: list[dict[str, Any]],
    round_runtime: dict[str, Any],
    active_hole: int,
    player_ids: list[str],
    player_names: list[str],
) -> None:
    active_competitions = competitions_for_hole(bonus_competitions, round_runtime["round_id"], active_hole)
    if not active_competitions:
        return

    st.markdown("#### Bonus Point")
    winner_options = ["", *player_ids]
    for competition in active_competitions:
        current_winner = str(competition.get("winner_player_id") or "")
        if current_winner not in winner_options:
            current_winner = ""
        render_status_card(
            str(competition.get("label") or "Bonus Point"),
            f"{float(competition.get('point_value') or 0.0):g} point",
            "Pick the winner when the group has agreed it.",
            tone="gold",
        )
        selected_winner = st.selectbox(
            "Winner",
            options=winner_options,
            index=winner_options.index(current_winner),
            format_func=lambda player_id: "No winner yet"
            if not player_id
            else player_names[player_ids.index(player_id)]
            if player_id in player_ids
            else str(player_id),
            key=f"bonus-winner::{round_runtime['round_id']}::{active_hole}::{competition['id']}",
        )
        if st.button(
            "Save Bonus Winner",
            width="stretch",
            disabled=selected_winner == current_winner,
            key=f"bonus-save::{round_runtime['round_id']}::{active_hole}::{competition['id']}",
        ):
            updated_competitions = update_bonus_winner(
                bonus_competitions,
                str(competition["id"]),
                str(selected_winner),
            )
            save_setting(BONUS_COMPETITIONS_SETTING_KEY, bonus_competitions_to_json(updated_competitions))
            st.rerun()


def render_live_scoring(
    course_df: pd.DataFrame,
    course: str,
    course_title: str,
    round_runtime: dict[str, Any],
    tee_rating: dict[str, Any],
    round_state: dict[str, Any],
    shot_views: list[dict[str, Any]],
    singles_matchups: list[dict[str, Any]] | None = None,
    bonus_competitions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    format_name = round_runtime["format_name"]
    allowance_percent = round_runtime["allowance_percent"]
    scoring_mode = str(round_runtime.get("scoring_mode") or "net")
    scramble_mode = str(round_runtime.get("scramble_mode") or "")
    stableford_mode = str(round_runtime.get("stableford_mode") or "")
    handicap_allocation = str(round_runtime.get("handicap_allocation") or "")
    player_names = list(round_state["player_names"])
    handicap_indexes = list(round_state["handicap_indexes"])
    player_ids = list(round_state["player_ids"])

    holes = [int(hole) for hole in course_df["hole"].dropna().tolist()]
    config = get_format_config(format_name)
    progress = round_state.get("progress", {})
    resume_hole = int(progress.get("resume_hole", round_state["active_hole"]) or round_state["active_hole"])
    active_hole = int(round_state["active_hole"])
    if active_hole not in holes:
        active_hole = holes[0]
        set_active_hole_for_ui(round_runtime["round_id"], active_hole, source="derived")

    if progress.get("round_complete"):
        render_status_card("Round complete", "All 18 holes saved", "Use full scorecard edit if a correction is needed.", tone="green")
    elif int(progress.get("completed_count", 0) or 0) > 0:
        if st.button(
            f"Continue from hole {resume_hole}",
            width="stretch",
            type="primary",
            disabled=active_hole == resume_hole,
        ):
            set_active_hole_for_ui(round_runtime["round_id"], resume_hole, source="derived")
            st.rerun()

    nav_columns = st.columns(2)
    with nav_columns[0]:
        if st.button("Previous", width="stretch", disabled=active_hole == holes[0]):
            set_active_hole_for_ui(round_runtime["round_id"], holes[max(0, holes.index(active_hole) - 1)], source="manual")
            st.rerun()
    with nav_columns[1]:
        if st.button("Next", width="stretch", disabled=active_hole == holes[-1]):
            set_active_hole_for_ui(round_runtime["round_id"], holes[min(len(holes) - 1, holes.index(active_hole) + 1)], source="manual")
            st.rerun()

    selector_columns = st.columns([1.5, 0.75])
    with selector_columns[0]:
        selected_hole = st.selectbox("Jump To Hole", options=holes, index=holes.index(active_hole))
        if selected_hole != active_hole:
            set_active_hole_for_ui(round_runtime["round_id"], int(selected_hole), source="manual")
            active_hole = int(selected_hole)
    with selector_columns[1]:
        render_metric_card("Hole", active_hole, "active")

    hole_record = get_hole_record(course, active_hole)
    hole_name = format_hole_name(hole_record.get("hole_name"), active_hole)
    yardage_key = "yards_white" if round_runtime["tee_label"].lower() == "white" else "yards_yellow"
    hole_par = hole_record.get("par", 4)

    current_row = round_state["scores"][round_state["scores"]["hole"] == active_hole].iloc[0]
    saved_hole_complete = str(current_row.get("status", "")) == "Complete"
    edit_key = f"edit-saved-hole::{round_runtime['round_id']}::{active_hole}"
    edit_saved_hole = bool(st.session_state.get(edit_key, False))
    entry_values: dict[str, object] = {}

    render_chip_row(
        [
            hole_name,
            f"Par {hole_record.get('par', '—')}",
            f"SI {hole_record.get('si', '—')}",
            f"{round_runtime['tee_label']} {hole_record.get(yardage_key, '—')}y",
        ]
    )
    action_mode = saved_hole_action_mode(saved_hole_complete, edit_saved_hole)

    if action_mode == "protected_saved":
        render_status_card(
            "Saved Hole",
            f"Viewing saved hole {active_hole}",
            "Use Edit saved hole before updating workbook scores.",
            tone="gold",
        )
        if st.button("Edit saved hole", width="stretch", type="primary"):
            st.session_state[edit_key] = True
            st.rerun()
    elif action_mode == "edit_saved":
        st.warning(f"Editing saved hole {active_hole}. Saving will update the existing workbook rows.")

    _render_bonus_competition_winners(
        bonus_competitions or [],
        round_runtime=round_runtime,
        active_hole=active_hole,
        player_ids=player_ids,
        player_names=player_names,
    )
    score_columns = list(config["score_columns"])
    defaults = []
    for column in score_columns:
        value = current_row[column]
        defaults.append("—" if pd.isna(value) else int(value))
    team_groups = (("red", TEAM_A_PLAYERS), ("blue", TEAM_B_PLAYERS))
    for team_id, player_indexes in team_groups:
        render_status_card(
            "",
            team_name(team_id),
            "Enter gross scores for this side",
            tone=team_id,
        )
        for player_index in player_indexes:
            label = player_names[player_index]
            player_id = player_ids[player_index]
            score_column = score_columns[player_index]
            default = defaults[player_index]
            widget_key = _score_widget_key(round_runtime["round_id"], course, active_hole, player_id)
            value_key = _score_value_key(round_runtime["round_id"], course, active_hole, player_id)
            select_key = _score_select_key(round_runtime["round_id"], course, active_hole, player_id)
            current_score = st.session_state.get(value_key, _normalise_score_for_widget(default))
            score_options = _score_options_for_widget(current_score)
            if select_key not in st.session_state or st.session_state[select_key] not in score_options:
                st.session_state[select_key] = current_score if current_score in score_options else "—"
            score_row = st.columns([1.25, 0.35, 0.85, 0.35], gap="small")
            with score_row[0]:
                st.markdown(f"**{label}**")
                st.caption("No saved score" if default == "—" else f"Saved gross {default}")
            with score_row[1]:
                st.button(
                    "-1",
                    key=f"{widget_key}::minus",
                    width="stretch",
                    disabled=action_mode == "protected_saved",
                    help=f"Decrease {label}'s gross score",
                    on_click=_set_incremented_score,
                    args=(value_key, select_key, hole_par, -1),
                )
            with score_row[2]:
                index = score_options.index(st.session_state[select_key])
                selected_score = st.selectbox(
                    f"{label} gross score",
                    options=score_options,
                    index=index,
                    key=select_key,
                    label_visibility="collapsed",
                    disabled=action_mode == "protected_saved",
                )
                st.session_state[value_key] = selected_score
                entry_values[score_column] = selected_score
            with score_row[3]:
                st.button(
                    "+1",
                    key=f"{widget_key}::plus",
                    width="stretch",
                    disabled=action_mode == "protected_saved",
                    help=f"Increase {label}'s gross score",
                    on_click=_set_incremented_score,
                    args=(value_key, select_key, hole_par, 1),
                )

    preview_scores = _update_scores(
        round_state["scores"],
        active_hole,
        format_name=format_name,
        values=entry_values,
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
            scramble_mode=scramble_mode,
            scoring_mode=scoring_mode,
            stableford_mode=stableford_mode,
            handicap_allocation=handicap_allocation,
            singles_matchups=singles_matchups,
        )
        if tee_rating
        else {}
    )
    has_unsaved_changes = any(_score_changed(current_row[column], entry_values[column]) for column in score_columns)
    preview_cards = _hole_preview(preview_result, format_name, active_hole, player_names)
    hole_is_complete = _status_for_values(list(entry_values.values()), required_count=len(score_columns)) == "Complete"

    protected_saved_hole = action_mode == "protected_saved"

    if protected_saved_hole:
        st.info("Saved scores are protected from accidental overwrite.")
    elif not hole_is_complete:
        st.warning("Enter all required gross scores before using Save + Next. Use Save Hole if you intentionally need to keep this hole pending or in progress.")

    if action_mode == "edit_saved":
        if st.button("Update Saved Hole", width="stretch", type="primary", disabled=not has_unsaved_changes):
            updated_scores = _update_scores(round_state["scores"], active_hole, format_name=format_name, values=entry_values)
            try:
                _persist_live_scores(round_runtime, updated_scores, round_state, active_hole, preview_result)
                st.session_state[edit_key] = False
                set_active_hole_for_ui(round_runtime["round_id"], resume_hole, source="derived")
                st.rerun()
            except GoogleSheetsError as exc:
                st.error(str(exc))
    elif st.button("Save + Next", width="stretch", type="primary", disabled=not hole_is_complete):
        updated_scores = _update_scores(round_state["scores"], active_hole, format_name=format_name, values=entry_values)
        try:
            _persist_live_scores(round_runtime, updated_scores, round_state, active_hole, preview_result)
            set_active_hole_for_ui(
                round_runtime["round_id"],
                holes[min(len(holes) - 1, holes.index(active_hole) + 1)],
                source="derived",
            )
            st.rerun()
        except GoogleSheetsError as exc:
            st.error(str(exc))

    if action_mode == "normal" and st.button("Save Hole", width="stretch"):
        updated_scores = _update_scores(round_state["scores"], active_hole, format_name=format_name, values=entry_values)
        try:
            _persist_live_scores(round_runtime, updated_scores, round_state, active_hole, preview_result)
            st.rerun()
        except GoogleSheetsError as exc:
            st.error(str(exc))

    with st.expander("Clear this hole", expanded=False):
        st.warning("This clears all gross scores for the active hole and marks it pending.")
        confirm_clear = st.checkbox(
            f"I understand this will clear hole {active_hole}.",
            key=f"confirm-clear-hole::{round_runtime['round_id']}::{active_hole}",
        )
        clear_disabled = not confirm_clear or (saved_hole_complete and not edit_saved_hole)
        if saved_hole_complete and not edit_saved_hole:
            st.caption("Enable Edit saved hole before clearing saved workbook rows.")
        if st.button("Clear Scores And Mark Pending", width="stretch", disabled=clear_disabled):
            updated_scores = _update_scores(
                round_state["scores"],
                active_hole,
                format_name=format_name,
                values=entry_values,
                force_pending=True,
            )
            try:
                cleared_result = (
                    compute_round_results(
                        course_df=course_df,
                        format_name=format_name,
                        score_df=updated_scores,
                        player_names=player_names,
                        player_ids=player_ids,
                        handicap_indexes=handicap_indexes,
                        tee_rating=tee_rating,
                        allowance_percent=allowance_percent,
                        scramble_mode=scramble_mode,
                        scoring_mode=scoring_mode,
                        stableford_mode=stableford_mode,
                        handicap_allocation=handicap_allocation,
                        singles_matchups=singles_matchups,
                    )
                    if tee_rating
                    else {}
                )
                _persist_live_scores(round_runtime, updated_scores, round_state, active_hole, cleared_result)
                _clear_active_score_widget_values(round_runtime, course, active_hole, player_ids)
                st.rerun()
            except GoogleSheetsError as exc:
                st.error(str(exc))

    if has_unsaved_changes and preview_cards:
        st.markdown("#### Live Preview")
        preview_columns = st.columns(len(preview_cards))
        for column, card in zip(preview_columns, preview_cards):
            with column:
                render_status_card(card["title"], card["status"], card["support"])

    with st.expander("Hole details", expanded=False):
        render_chip_row(
            [
                course_title,
                f"Par {hole_record.get('par', '—')}",
                f"SI {hole_record.get('si', '—')}",
                f"{round_runtime['tee_label']} {hole_record.get(yardage_key, '—')}y",
            ]
        )
        st.caption("Hole images stay in Course Guide so live scoring stays lighter on phones and lower-memory devices.")

        st.markdown("#### Handicap This Hole")
        for group in get_hole_shots_for_display(shot_views, active_hole):
            shot_text = [f"{label}: {shots}" for label, shots in group["shots"].items()]
            render_chip_row([group["label"], format_relative_to(group["relative_to"]), *shot_text], tone="accent")

        if isinstance(hole_record.get("pro_tip"), str) and hole_record["pro_tip"].strip():
            st.markdown("#### Tip")
            st.write(hole_record["pro_tip"].strip())

    return {"active_hole": active_hole, "preview_result": preview_result}
