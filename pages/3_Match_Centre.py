from __future__ import annotations

import streamlit as st

from components.layout import render_chip_row, render_metric_card, render_section_header, render_status_card
from components.leaderboard import render_leaderboard
from support.app_context import build_page_context, fixture_status_text, initialize_page, render_page_links, render_shared_sidebar
from domain.formatting import format_points


def main() -> None:
    if not initialize_page("Match Centre"):
        return

    store = render_shared_sidebar()
    context = build_page_context(store)
    render_section_header(
        "Match Centre",
        "Live match state, momentum, totals, and weekend points impact for the selected fixture.",
    )
    render_page_links("Match Centre")
    render_chip_row(
        [
            context["selected_fixture"]["title"],
            context["format_name"],
            f"{context['tee_label']} tees",
            f"Active hole {int(context['round_state']['active_hole'])}",
        ],
        tone="accent",
    )

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

    if not context["tee_rating"]:
        st.info(f"No tee rating metadata is available for {context['tee_label']} tees on this course.")
        return

    render_status_card(
        "Current Round",
        fixture_status_text(context["selected_result"]),
        f"{context['selected_fixture']['date_label']} • {context['selected_fixture']['time_label']}",
    )
    render_leaderboard(
        context["selected_result"],
        show_gross_secondary=bool(context["weekend_state"]["show_gross_secondary"]),
        show_header=False,
    )


if __name__ == "__main__":
    main()
