from __future__ import annotations

import streamlit as st

from components.layout import render_chip_row, render_section_header, render_session_fallback_warning
from components.layout import render_status_card
from components.live_scoring import render_live_scoring
from components.score_tracker import render_full_card_editor, render_round_summary_metrics
from domain.weekend_config import FIXTURES, format_fixture_label
from support.app_context import build_page_context, compact_fixture_status_text, ensure_round_focus, initialize_page, render_shared_sidebar, team_format_label
from support.session import set_selected_fixture_id


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
        set_selected_fixture_id(selected_fixture_id)
        st.rerun()


def _render_live_status(context: dict[str, object]) -> None:
    persistence = context["persistence"]
    status = persistence["status"]
    last_save = st.session_state.get("last_live_save_status", {})
    if isinstance(last_save, dict) and last_save.get("round_id") == context["selected_fixture"]["id"]:
        save_status = f"Hole {last_save.get('hole')} saved at {last_save.get('saved_at')}"
    else:
        save_status = "No save in this browser session yet"

    columns = st.columns(2)
    with columns[0]:
        if persistence["mode"] == "sheets":
            render_status_card("Connection", "Google Sheets", str(status.get("message", "Connected")), tone="green")
        else:
            render_status_card("Connection", "Session fallback", "Scores are not shared or durable", tone="gold")
    with columns[1]:
        render_status_card("Last Save", save_status, "Current device session")


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
            f"Active hole {int(context['round_state']['active_hole'])}",
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
        )
        render_round_summary_metrics(format_name=context["format_name"], round_state=context["round_state"])


if __name__ == "__main__":
    main()
