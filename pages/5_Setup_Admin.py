from __future__ import annotations

from components.setup_admin import render_setup_admin
from support.app_context import build_page_context, initialize_page, render_shared_sidebar


def main() -> None:
    if not initialize_page("Setup / Admin"):
        return

    store = render_shared_sidebar()
    context = build_page_context(store)
    render_setup_admin(
        selected_fixture=context["selected_fixture"],
        persistence=context["persistence"],
        show_gross_secondary=bool(context["weekend_state"]["show_gross_secondary"]),
        round_runtime=context["round_runtime"],
        round_state=context["round_state"],
        holes=context["holes"],
        tee_rating=context["tee_rating"],
        players_rows=context["store"]["players_rows"],
        singles_matchups=context["singles_matchups"],
        bonus_competitions=context["bonus_competitions"],
        fixture_tees=context["weekend_state"]["fixture_tees"],
    )


if __name__ == "__main__":
    main()
