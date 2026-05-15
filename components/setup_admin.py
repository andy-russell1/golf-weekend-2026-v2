from __future__ import annotations

from typing import Any

import streamlit as st

from components.layout import render_chip_row, render_connection_panel, render_metric_card, render_section_header, render_status_card
from components.score_tracker import render_player_handicap_editor, render_round_summary_metrics
from support.app_context import FORMAT_OPTIONS, TEE_OPTIONS
from support.google_sheets import GoogleSheetsError
from support.google_sheets import get_credentials, get_google_sheets_config, refresh_sheet_caches
from support.state_helpers import clear_round, save_round_config, save_setting
from domain.weekend_config import format_fixture_label


def render_setup_admin(
    selected_fixture: dict[str, Any],
    persistence: dict[str, Any],
    show_gross_secondary: bool,
    round_runtime: dict[str, Any],
    round_state: dict[str, Any],
    holes: list[int],
    tee_rating: dict[str, Any],
    players_rows: list[dict[str, Any]],
) -> None:
    fixture_id = selected_fixture["id"]
    format_name = round_runtime["format_name"]
    tee_label = round_runtime["tee_label"]
    allowance_percent = int(round_runtime["allowance_percent"])

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
        ],
        tone="accent",
    )

    connection_tab, setup_tab, players_tab, admin_tab = st.tabs(["Connection", "Round Setup", "Players & Handicaps", "Admin Actions"])

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
                else "Shared mode is active. Add service-account credentials in Streamlit secrets or as a local JSON file to enable shared Google Sheets access."
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

        with control_columns[1]:
            show_gross_secondary_value = st.toggle("Show Gross Best Ball In Match Centre", value=show_gross_secondary)

        if st.button("Save Round Setup", width="stretch"):
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
                "points_available": selected_fixture["points_available"],
                "allowance_percent": updated_allowance,
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
            st.rerun()

        summary_columns = st.columns(4)
        with summary_columns[0]:
            render_metric_card("Round", selected_fixture["title"], selected_fixture["date_label"])
        with summary_columns[1]:
            render_metric_card("Format", format_name, "saved to workbook")
        with summary_columns[2]:
            render_metric_card("Tee", tee_label, "course rating source")
        with summary_columns[3]:
            render_metric_card("Allowance", f"{allowance_percent}%", "WHS playing handicap")

        if not tee_rating:
            st.info(f"No tee rating metadata is available for {tee_label} tees on this course.")
        else:
            render_status_card(
                "Scoring Engine",
                "Ready",
                "Handicap, shot allocation, and round result calculations are active for the selected round.",
            )

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
