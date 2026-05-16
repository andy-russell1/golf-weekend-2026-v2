from __future__ import annotations

from typing import Any

import streamlit as st

from components.layout import (
    render_chip_row,
    render_connection_panel,
    render_metric_card,
    render_section_header,
    render_session_fallback_warning,
    render_status_card,
)
from components.score_tracker import render_player_handicap_editor, render_round_summary_metrics
from domain.bonus_competitions import (
    BONUS_COMPETITIONS_SETTING_KEY,
    bonus_competitions_to_json,
    configured_bonus_competition,
    competition_hole_label,
    eligible_holes,
    normalize_bonus_competitions,
)
from domain.handicap import HANDICAP_ALLOCATION_OPTIONS, normalize_handicap_allocation
from support.data_loader import load_course_data
from support.app_context import FORMAT_OPTIONS, TEE_OPTIONS
from support.google_sheets import GoogleSheetsError
from support.google_sheets import get_credentials, get_google_sheets_config, refresh_sheet_caches
from support.state_helpers import clear_round, save_round_config, save_setting
from domain.weekend_config import (
    FIXTURES,
    SINGLES_MATCHUPS_SETTING_KEY,
    TEAM_CONFIG,
    format_fixture_label,
    normalize_singles_matchups,
    points_available_for_format,
    singles_matchups_to_json,
    team_for_player,
)


def _player_name(player_names: list[str], player_index: int) -> str:
    if 0 <= player_index < len(player_names):
        return player_names[player_index]
    return f"Player {player_index + 1}"


def _match_player_for_team(match: dict[str, Any], team_id: str, fallback: int) -> int:
    for player_index in match.get("players", []):
        if team_for_player(int(player_index)) == team_id:
            return int(player_index)
    return fallback


def _fixture_label(fixture_id: str) -> str:
    fixture = next((candidate for candidate in FIXTURES if candidate["id"] == fixture_id), FIXTURES[0])
    return format_fixture_label(fixture)


def _fixture_for_round_id(round_id: str) -> dict[str, Any]:
    return next((candidate for candidate in FIXTURES if candidate["id"] == round_id), FIXTURES[0])


def _handicap_allocation_label(value: str) -> str:
    if value == "relative":
        return "Relative shots"
    return "Full shots"


def _render_bonus_competition_editor(
    bonus_competitions: list[dict[str, Any]],
    fixture_tees: dict[str, str],
) -> None:
    st.caption("These are weekend-level bonus points. Each competition is configured once for the whole trip.")
    edited_competitions: list[dict[str, Any]] = []
    fixture_ids = [fixture["id"] for fixture in FIXTURES]

    for competition in normalize_bonus_competitions(bonus_competitions):
        st.markdown(f"#### {competition['label']}")
        current_round_id = str(competition.get("round_id") or fixture_ids[0])
        if current_round_id not in fixture_ids:
            current_round_id = fixture_ids[0]

        columns = st.columns([1.0, 1.45, 1.45])
        with columns[0]:
            enabled = st.toggle(
                "Enabled",
                value=bool(competition.get("enabled", True)),
                key=f"bonus-enabled::{competition['id']}",
            )
            point_value = st.number_input(
                "Point value",
                min_value=0.0,
                max_value=5.0,
                value=float(
                    competition.get("point_value")
                    if competition.get("point_value") not in (None, "")
                    else 1.0
                ),
                step=0.5,
                key=f"bonus-points::{competition['id']}",
            )
        with columns[1]:
            selected_round_id = st.selectbox(
                "Round",
                options=fixture_ids,
                index=fixture_ids.index(current_round_id),
                format_func=_fixture_label,
                key=f"bonus-round::{competition['id']}",
            )
        selected_fixture = _fixture_for_round_id(selected_round_id)
        tee_label = fixture_tees.get(selected_round_id, selected_fixture["default_tee"])
        course_df = load_course_data(selected_fixture["course"])
        eligible = eligible_holes(course_df, str(competition["type"]), tee_label=tee_label)
        hole_options = [int(hole) for hole in eligible["hole"].dropna().tolist()]
        if not hole_options:
            hole_options = [int(hole) for hole in course_df["hole"].dropna().tolist()]
        current_hole = int(competition.get("hole") or hole_options[0])
        if current_hole not in hole_options:
            current_hole = hole_options[0]

        with columns[2]:
            selected_hole = st.selectbox(
                "Hole",
                options=hole_options,
                index=hole_options.index(current_hole),
                format_func=lambda hole: competition_hole_label(
                    eligible[eligible["hole"].eq(hole)].iloc[0].to_dict()
                    if not eligible[eligible["hole"].eq(hole)].empty
                    else course_df[course_df["hole"].eq(hole)].iloc[0].to_dict(),
                    tee_label=tee_label,
                ),
                key=f"bonus-hole::{competition['id']}",
            )

        edited_competitions.append(
            configured_bonus_competition(
                competition,
                round_id=str(selected_round_id),
                course=str(selected_fixture["course"]),
                hole=int(selected_hole),
                point_value=float(point_value),
                enabled=bool(enabled),
            )
        )

    if st.button("Save Bonus Competitions", width="stretch"):
        save_setting(BONUS_COMPETITIONS_SETTING_KEY, bonus_competitions_to_json(edited_competitions))
        st.rerun()


def render_setup_admin(
    selected_fixture: dict[str, Any],
    persistence: dict[str, Any],
    show_gross_secondary: bool,
    round_runtime: dict[str, Any],
    round_state: dict[str, Any],
    holes: list[int],
    tee_rating: dict[str, Any],
    players_rows: list[dict[str, Any]],
    singles_matchups: list[dict[str, Any]],
    bonus_competitions: list[dict[str, Any]],
    fixture_tees: dict[str, str],
) -> None:
    fixture_id = selected_fixture["id"]
    format_name = round_runtime["format_name"]
    tee_label = round_runtime["tee_label"]
    allowance_percent = int(round_runtime["allowance_percent"])
    handicap_allocation = normalize_handicap_allocation(round_runtime.get("handicap_allocation", ""), format_name)

    render_section_header(
        "Setup / Admin",
        "Round setup, Google Sheets diagnostics, handicap edits, and safe admin controls live here so the fan-facing pages stay focused.",
    )
    render_chip_row(
        [
            format_fixture_label(selected_fixture),
            format_name,
            f"{tee_label} tees",
            f"Allowance {allowance_percent}%",
            _handicap_allocation_label(handicap_allocation),
        ],
        tone="accent",
    )
    if persistence["mode"] != "sheets":
        render_session_fallback_warning()

    setup_tab, players_tab, connection_tab, admin_tab = st.tabs(
        ["Round Setup", "Players & Handicaps", "Connection", "Admin Actions"]
    )

    with connection_tab:
        render_connection_panel(persistence["status"], compact=False)
        config = get_google_sheets_config()
        auth_mode = persistence["status"].get("auth_mode")
        if auth_mode == "adc":
            principal = str(persistence["status"].get("principal") or "")
            st.info(
                f"Hosted shared mode is active. The deployed app should use its attached Google service account{f' `{principal}`' if principal else ''}."
            )
            st.caption("Share the workbook with the Cloud Run service account email and deploy with Application Default Credentials enabled.")
        elif auth_mode == "service_account":
            principal = str(persistence["status"].get("principal") or persistence["status"].get("service_account_email") or "")
            st.info(
                f"Shared mode is active. Share the workbook `{config.workbook_name}` with `{principal}` and the app can use Sheets without each player signing in."
                if principal
                else "Shared mode is active. Add service-account credentials in Streamlit secrets or an environment-managed secret path outside the repo to enable shared Google Sheets access."
            )
        else:
            if not config.service_account_file.exists():
                st.warning(
                    f"Service account file not found at `{config.service_account_file}`. The app has fallen back to Desktop OAuth."
                )
            st.caption("Desktop OAuth is still available as a fallback for one-user local development.")
        action_columns = st.columns(2)
        with action_columns[0]:
            button_label = (
                "Check Attached Credentials"
                if auth_mode == "adc"
                else "Check Service Account Access"
                if auth_mode == "service_account"
                else "Run Desktop OAuth"
            )
            if st.button(button_label, width="stretch"):
                try:
                    if auth_mode == "oauth_desktop":
                        get_credentials(interactive=True)
                    refresh_sheet_caches()
                    st.rerun()
                except GoogleSheetsError as exc:
                    st.error(str(exc))
        with action_columns[1]:
            if st.button("Refresh Workbook", width="stretch"):
                refresh_sheet_caches()
                st.rerun()

    with setup_tab:
        st.caption("These settings drive Live Scoring, Match Centre, and the course guide for the selected fixture.")
        control_columns = st.columns(2)
        with control_columns[0]:
            updated_format = st.selectbox(
                "Round format",
                options=list(FORMAT_OPTIONS),
                index=list(FORMAT_OPTIONS).index(format_name),
            )
            updated_tee = st.radio(
                "Tee used for scoring",
                options=list(TEE_OPTIONS),
                index=list(TEE_OPTIONS).index(tee_label),
                horizontal=True,
            )
            updated_allowance = st.slider("Handicap allowance %", min_value=0, max_value=100, value=allowance_percent, step=5)
            updated_handicap_allocation = st.radio(
                "Handicap allocation",
                options=list(HANDICAP_ALLOCATION_OPTIONS),
                index=list(HANDICAP_ALLOCATION_OPTIONS).index(
                    normalize_handicap_allocation(handicap_allocation, updated_format)
                ),
                format_func=_handicap_allocation_label,
                horizontal=True,
            )
            st.caption("Full uses each player's playing handicap. Relative plays everyone from the lowest handicap in the group.")

        with control_columns[1]:
            show_gross_secondary_value = st.toggle("Show Gross Best Ball In Match Centre", value=show_gross_secondary)
            updated_singles_matchups = normalize_singles_matchups(singles_matchups, player_count=len(round_state["player_names"]))
            singles_setup_valid = True
            if updated_format == "Singles":
                st.info("Singles is two parallel 1-point matches. Pick one Kelly player and one Russell player for each match.")
                player_names = list(round_state["player_names"])
                red_options = list(TEAM_CONFIG["red"]["player_indices"])
                blue_options = list(TEAM_CONFIG["blue"]["player_indices"])
                edited_matchups: list[dict[str, Any]] = []
                for match_index, match in enumerate(updated_singles_matchups):
                    red_default = _match_player_for_team(match, "red", red_options[min(match_index, len(red_options) - 1)])
                    blue_default = _match_player_for_team(match, "blue", blue_options[min(match_index, len(blue_options) - 1)])
                    st.caption(f"Match {match_index + 1} - 1 point")
                    matchup_columns = st.columns(2)
                    with matchup_columns[0]:
                        red_player = st.selectbox(
                            f"{TEAM_CONFIG['red']['short_name']} player",
                            options=red_options,
                            index=red_options.index(red_default) if red_default in red_options else 0,
                            format_func=lambda index: _player_name(player_names, int(index)),
                            key=f"singles-matchup::{fixture_id}::{match_index}::red",
                        )
                    with matchup_columns[1]:
                        blue_player = st.selectbox(
                            f"{TEAM_CONFIG['blue']['short_name']} player",
                            options=blue_options,
                            index=blue_options.index(blue_default) if blue_default in blue_options else 0,
                            format_func=lambda index: _player_name(player_names, int(index)),
                            key=f"singles-matchup::{fixture_id}::{match_index}::blue",
                        )
                    edited_matchups.append({"players": [int(red_player), int(blue_player)], "point_value": 1.0})

                selected_players = [player for match in edited_matchups for player in match["players"]]
                singles_setup_valid = sorted(selected_players) == list(range(len(player_names)))
                if singles_setup_valid:
                    updated_singles_matchups = edited_matchups
                else:
                    st.warning("Use each of the four players exactly once across the two Singles matches.")

        if st.button("Save Round Setup", width="stretch", disabled=updated_format == "Singles" and not singles_setup_valid):
            payload = {
                "round_order": round_runtime.get("round_order", selected_fixture.get("round_order", 0)),
                "title": selected_fixture["title"],
                "course": selected_fixture["course"],
                "date_label": selected_fixture["date_label"],
                "time_label": selected_fixture["time_label"],
                "sort_key": selected_fixture["sort_key"],
                "format_key": updated_format,
                "format_label": updated_format,
                "tee": updated_tee,
                "points_available": points_available_for_format(updated_format),
                "allowance_percent": updated_allowance,
                "handicap_allocation": normalize_handicap_allocation(updated_handicap_allocation, updated_format),
                "scoring_mode": "net",
                "scramble_mode": "",
                "stableford_mode": "",
                "link": round_runtime.get("link", ""),
                "par": round_runtime.get("par", ""),
                "length_label": round_runtime.get("length_label", ""),
                "is_active": "TRUE",
            }
            save_round_config(fixture_id, payload)
            save_setting("show_gross_secondary", "true" if show_gross_secondary_value else "false")
            if updated_format == "Singles":
                save_setting(SINGLES_MATCHUPS_SETTING_KEY, singles_matchups_to_json(updated_singles_matchups))
            st.rerun()

        summary_columns = st.columns(5)
        with summary_columns[0]:
            render_metric_card("Round", selected_fixture["title"], selected_fixture["date_label"])
        with summary_columns[1]:
            render_metric_card("Format", format_name, "saved to workbook")
        with summary_columns[2]:
            render_metric_card("Tee", tee_label, "course rating source")
        with summary_columns[3]:
            render_metric_card("Allowance", f"{allowance_percent}%", "WHS playing handicap")
        with summary_columns[4]:
            render_metric_card("Shots", _handicap_allocation_label(handicap_allocation), "net allocation")

        if not tee_rating:
            st.info(f"No tee rating metadata is available for {tee_label} tees on this course.")
        else:
            render_status_card(
                "Scoring Engine",
                "Ready",
                "Handicap, shot allocation, and round result calculations are active for the selected round.",
            )

        with st.expander("Bonus Points", expanded=False):
            _render_bonus_competition_editor(bonus_competitions, fixture_tees)

    with players_tab:
        st.caption("Keep labels explicit here so names and playing handicaps stay readable on a phone during the round.")
        render_player_handicap_editor(players_rows=players_rows, round_runtime=round_runtime, tee_rating=tee_rating)
        render_round_summary_metrics(format_name=format_name, round_state=round_state)

    with admin_tab:
        render_status_card(
            "Persistence Mode",
            persistence["mode"].capitalize(),
            "Google Sheets is preferred; local session fallback remains available if the workbook is not connected.",
        )
        st.warning("Resetting a round clears all saved scores and recalculated results for the selected fixture only.")
        confirm_reset = st.checkbox(f"I understand this will clear {selected_fixture['title']}.")
        confirmation_text = st.text_input("Type RESET to enable round reset", placeholder="RESET")
        if st.button(
            "Reset Selected Round",
            width="stretch",
            disabled=not (confirm_reset and confirmation_text.strip().upper() == "RESET"),
        ):
            clear_round(fixture_id)
            st.rerun()
