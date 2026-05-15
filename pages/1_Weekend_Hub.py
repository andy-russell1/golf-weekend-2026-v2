from __future__ import annotations

from components.layout import render_hero
from components.weekend_hub import render_weekend_hub
from domain.weekend_config import TOURNAMENT_NAME
from support.app_context import (
    build_page_context,
    ensure_round_focus,
    initialize_page,
    render_shared_sidebar,
    team_format_label,
)


def main() -> None:
    if not initialize_page("Weekend Hub"):
        return

    store = render_shared_sidebar()
    context = ensure_round_focus(build_page_context(store))
    selected_fixture = context["selected_fixture"]
    subtitle = f"{selected_fixture['title']} • {selected_fixture['date_label']} {selected_fixture['time_label']}"
    meta = f"{context['format_name']} • {context['tee_label']} tees • {team_format_label(context['format_name'], context['scramble_mode'], context['scoring_mode'])}"
    render_hero(TOURNAMENT_NAME, subtitle, meta)
    render_weekend_hub(
        selected_fixture=context["selected_fixture"],
        player_names=context["player_names"],
        handicap_indexes=context["handicap_indexes"],
        fixture_formats=context["weekend_state"]["fixture_formats"],
        fixture_tees=context["weekend_state"]["fixture_tees"],
        results_by_fixture=context["results_by_fixture"],
        round_focus=context["round_focus"],
        weekend_race=context["weekend_race"],
        show_header=False,
    )


if __name__ == "__main__":
    main()
