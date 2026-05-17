from __future__ import annotations

import streamlit as st

from components.layout import render_chip_row, render_section_header, render_session_fallback_warning
from components.layout import render_status_card
from components.live_scoring import render_live_scoring
from components.score_tracker import render_full_card_editor, render_round_summary_metrics
from domain.weekend_config import FIXTURES, format_fixture_label
from support.app_context import (
    build_page_context,
    compact_fixture_status_text,
    ensure_round_focus,
    initialize_page,
    render_shared_sidebar,
    set_selected_fixture_for_ui,
    team_format_label,
)


def _render_round_switcher(current_fixture_id: str) -> None:
    fixture_ids = [fixture["id"] for fixture in FIXTURES]
    selected_fixture_id = st.selectbox(
        "Scoring round",
        options=fixture_ids,
        index=fixture_ids.index(current_fixture_id) if current_fixture_id in fixture_ids else 0,
        format_func=lambda fixture_id: format_fixture_label(next(fixture for fixture in FIXTURES if fixture["id"] == fixture_id)),
        key="live-body-round-switcher",
    )
    if selected_fixture_id != current_fixture_id:
        set_selected_fixture_for_ui(selected_fixture_id)
        st.rerun()


def _render_live_status(context: dict[str, object]) -> None:
    persistence = context["persistence"]
    status = persistence["status"]
    round_focus = context["round_focus"]
    last_save = st.session_state.get("last_live_save_status", {})
    latest_saved_hole = round_focus.get("latest_saved_hole")
    latest_saved_at = round_focus.get("latest_saved_at")
    if latest_saved_hole and latest_saved_at:
        save_status = f"Hole {latest_saved_hole} at {latest_saved_at.astimezone().strftime('%H:%M')}"
        save_detail = "Saved to workbook"
    elif int(round_focus.get("completed_holes", 0) or 0) > 0:
        save_status = f"Hole {round_focus.get('last_completed_hole', 'saved')}"
        save_detail = "Saved to workbook"
    else:
        save_status = "No saved holes yet"
        save_detail = "Workbook has no scores for this round"

    save_state = "Connected"
    save_tone = "green" if persistence["mode"] == "sheets" else "gold"
    if isinstance(last_save, dict) and last_save.get("round_id") == context["selected_fixture"]["id"]:
        if last_save.get("state") == "verification_failed":
            save_state = "Verification failed"
            save_tone = "red"
            browser_status = f"Hole {last_save.get('hole')} failed at {last_save.get('failed_at')}"
        elif last_save.get("state") == "saving":
            save_state = "Saving"
            save_tone = "gold"
            browser_status = f"Hole {last_save.get('hole')} is being saved"
        else:
            save_state = "Saved and verified"
            save_tone = "green"
            browser_status = f"This browser verified hole {last_save.get('hole')} at {last_save.get('verified_at') or last_save.get('saved_at')}"
    else:
        browser_status = "No save from this browser session"

    if persistence["mode"] != "sheets":
        if str(status.get("state", "")) in {"auth_required", "error"}:
            save_state = "Sheets unavailable"
            save_tone = "red"
        else:
            save_state = "Session fallback"
            save_tone = "gold"

    columns = st.columns(3)
    with columns[0]:
        if persistence["mode"] == "sheets":
            render_status_card("Connection", "Connected", str(status.get("message", "Google Sheets")), tone="green")
        elif str(status.get("state", "")) in {"auth_required", "error"}:
            render_status_card("Connection", "Sheets unavailable", "Live score saves are disabled until access is restored", tone="red")
        else:
            render_status_card("Connection", "Session fallback", "Scores are not shared or durable", tone="gold")
    with columns[1]:
        render_status_card("Save State", save_state, browser_status, tone=save_tone)
    with columns[2]:
        render_status_card("Last verified save" if persistence["mode"] == "sheets" else "Last local save", save_status, save_detail)


def _round_cursor_label(round_focus: dict[str, object]) -> str:
    if round_focus.get("round_complete"):
        return "Round complete"
    resume_hole = int(round_focus.get("resume_hole", 1) or 1)
    if int(round_focus.get("completed_holes", 0) or 0) > 0:
        return f"Resume scoring at hole {resume_hole}"
    return f"Start scoring at hole {resume_hole}"


def main() -> None:
    if not initialize_page("Live Scoring"):
        return

    store = render_shared_sidebar()
    context = ensure_round_focus(build_page_context(store))
    if context["persistence"]["mode"] != "sheets":
        render_session_fallback_warning()
    _render_round_switcher(context["selected_fixture"]["id"])
    _render_live_status(context)
    render_section_header(
        "Live Scoring",
        "Quick one-hole entry comes first here. Use the full card editor only when you need to fix an earlier hole.",
    )
    render_chip_row(
        [
            context["selected_fixture"]["title"],
            context["format_name"],
            f"{context['tee_label']} tees",
            _round_cursor_label(context["round_focus"]),
            context["round_focus"]["progress_text"],
            compact_fixture_status_text(context["selected_result"], context["player_names"]),
            team_format_label(context["format_name"], context["scramble_mode"], context["scoring_mode"]),
        ],
        tone="accent",
    )

    if not context["tee_rating"]:
        st.warning(
            f"No tee rating metadata is available for {context['tee_label']} tees on this course, so live WHS scoring cannot be calculated."
        )
        return

    live_tab, edit_tab = st.tabs(["Live Hole Entry", "Full Scorecard Edit"])
    with live_tab:
        render_live_scoring(
            course_df=context["course_df"],
            course=context["course"],
            course_title=context["selected_fixture"]["title"],
            round_runtime=context["round_runtime"],
            tee_rating=context["tee_rating"],
            round_state=context["round_state"],
            shot_views=context["shot_views"],
            singles_matchups=context["singles_matchups"],
            bonus_competitions=context["bonus_competitions"],
            persistence=context["persistence"],
        )

    with edit_tab:
        render_section_header(
            "Full Scorecard Edit",
            "Use this as the secondary correction view when you need to patch earlier holes without interrupting the live hole flow.",
        )
        render_full_card_editor(
            course_df=context["course_df"],
            round_runtime=context["round_runtime"],
            round_state=context["round_state"],
            tee_rating=context["tee_rating"],
            singles_matchups=context["singles_matchups"],
            persistence=context["persistence"],
        )
        render_round_summary_metrics(format_name=context["format_name"], round_state=context["round_state"])


if __name__ == "__main__":
    main()
