from __future__ import annotations

import streamlit as st

from components.layout import render_chip_row, render_hero, render_metric_card, render_status_card
from support.app_context import (
    build_page_context,
    fixture_status_text,
    initialize_page,
    render_page_links,
    render_shared_sidebar,
    team_format_label,
)
from domain.formatting import format_points


def main() -> None:
    if not initialize_page("Home"):
        return

    store = render_shared_sidebar()
    context = build_page_context(store)
    selected_fixture = context["selected_fixture"]
    subtitle = f"{selected_fixture['title']} • {selected_fixture['date_label']} {selected_fixture['time_label']}"
    meta = f"{context['format_name']} • {context['tee_label']} tees • {team_format_label(context['format_name'], context['scramble_mode'], context['scoring_mode'])}"
    render_hero("Ryder Cup Weekend Companion", subtitle, meta)
    render_page_links("Home")
    render_chip_row(
        [
            "Open Weekend Hub for the tournament overview",
            "Use Live Scoring during the round",
            "Keep setup changes in Setup / Admin",
        ],
        tone="accent",
    )

    race = context["weekend_race"]
    summary_columns = st.columns(4)
    with summary_columns[0]:
        render_metric_card("Weekend Points", format_points(race["red_points"]), "Red", tone="red")
    with summary_columns[1]:
        render_metric_card("Weekend Points", format_points(race["blue_points"]), "Blue", tone="blue")
    with summary_columns[2]:
        render_metric_card("Selected Round", context["format_name"], context["selected_fixture"]["title"])
    with summary_columns[3]:
        render_metric_card("Active Hole", int(context["round_state"]["active_hole"]), "shared across pages")

    status_columns = st.columns(2)
    with status_columns[0]:
        render_status_card(
            "Current Round",
            fixture_status_text(context["selected_result"]),
            f"{context['tee_label']} tees • {team_format_label(context['format_name'], context['scramble_mode'], context['scoring_mode'])}",
        )
    with status_columns[1]:
        render_status_card(
            "Shared State",
            "Google Sheets" if context["persistence"]["mode"] == "sheets" else "Session Fallback",
            "Fixture, format, tee, active hole, scores, and handicap edits stay in sync across pages.",
        )


if __name__ == "__main__":
    main()
