from __future__ import annotations

import streamlit as st

from components.layout import render_chip_row, render_metric_card, render_section_header, render_status_card
from components.leaderboard import render_leaderboard, render_match_centre_empty_state
from support.app_context import build_page_context, fixture_status_text, initialize_page, render_shared_sidebar
from domain.formatting import format_points


def main() -> None:
    if not initialize_page("Match Centre"):
        return

    store = render_shared_sidebar()
    context = build_page_context(store)
    render_section_header(
        "Match Centre",
        "Live match state, momentum, totals, and weekend points impact for the selected fixture, with the current answer first.",
    )
    render_chip_row(
        [
            context["selected_fixture"]["title"],
            context["format_name"],
            f"{context['tee_label']} tees",
            context["round_focus"]["progress_text"],
        ],
        tone="accent",
    )

    if not context["tee_rating"]:
        st.info(f"No tee rating metadata is available for {context['tee_label']} tees on this course.")
        return

    if int(context["round_focus"]["completed_holes"]) <= 0:
        render_match_centre_empty_state(
            selected_fixture=context["selected_fixture"],
            format_name=context["format_name"],
            tee_label=context["tee_label"],
            round_focus=context["round_focus"],
        )
        return

    race = context["weekend_race"]
    summary_columns = st.columns(4)
    with summary_columns[0]:
        render_metric_card("Red Weekend", format_points(race["red_points"]), "overall", tone="red")
    with summary_columns[1]:
        render_metric_card("Blue Weekend", format_points(race["blue_points"]), "overall", tone="blue")
    with summary_columns[2]:
        render_metric_card("Remaining", format_points(race["remaining_points"]), "points left")
    with summary_columns[3]:
        render_status_card("Weekend Race", race["status"], "selected round stays in sync with weekend totals")

    render_status_card(
        "Current Round",
        fixture_status_text(context["selected_result"]),
        f"{context['selected_fixture']['date_label']} • {context['selected_fixture']['time_label']} • {context['round_focus']['progress_text']}",
    )

    render_leaderboard(
        context["selected_result"],
        show_gross_secondary=bool(context["weekend_state"]["show_gross_secondary"]),
        show_header=False,
    )


if __name__ == "__main__":
    main()
