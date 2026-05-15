from __future__ import annotations

import streamlit as st

from components.hole_explorer import render_hole_explorer
from components.layout import render_chip_row, render_section_header
from components.overview import render_course_briefing, render_course_scorecard, render_playing_handicap_summary
from support.app_context import build_page_context, initialize_page, render_page_links, render_shared_sidebar
from support.session import set_active_hole


def main() -> None:
    if not initialize_page("Course Guide"):
        return

    store = render_shared_sidebar()
    context = build_page_context(store)
    render_section_header(
        "Course Guide",
        "Venue briefing, hole explorer, yardages, and live shot allocation support stay together on this page.",
    )
    render_page_links("Course Guide")
    render_chip_row(
        [
            context["selected_fixture"]["title"],
            context["format_name"],
            f"{context['tee_label']} tees",
            f"Active hole {int(context['round_state']['active_hole'])}",
        ],
        tone="accent",
    )

    overview_tab, explorer_tab, scorecard_tab = st.tabs(["Overview", "Hole Explorer", "Scorecard"])
    with overview_tab:
        render_course_briefing(
            course=context["course"],
            course_title=context["selected_fixture"]["title"],
            tee_label=context["tee_label"],
            format_name=context["format_name"],
        )
        render_playing_handicap_summary(
            player_names=context["player_names"],
            handicap_indexes=context["handicap_indexes"],
            tee_rating=context["tee_rating"],
            allowance_percent=context["allowance_percent"],
            tee_label=context["tee_label"],
        )

    with explorer_tab:
        explorer_state = render_hole_explorer(
            course=context["course"],
            selected_tee=context["tee_label"],
            shot_views=context["shot_views"],
            current_active_hole=int(context["round_state"]["active_hole"]),
        )
        if explorer_state["selected_hole"] != int(context["round_state"]["active_hole"]):
            set_active_hole(context["selected_fixture"]["id"], int(explorer_state["selected_hole"]))
            if explorer_state["open_live_scoring"]:
                st.switch_page("pages/2_Live_Scoring.py")
            st.rerun()
        if explorer_state["open_live_scoring"]:
            st.switch_page("pages/2_Live_Scoring.py")

    with scorecard_tab:
        render_course_scorecard(course=context["course"], tee_label=context["tee_label"])


if __name__ == "__main__":
    main()
