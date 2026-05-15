from __future__ import annotations

import streamlit as st

from components.layout import render_chip_row, render_metric_card, render_section_header, render_status_card
from components.live_scoring import render_live_scoring
from components.score_tracker import render_full_card_editor, render_round_summary_metrics
from support.app_context import build_page_context, ensure_round_focus, fixture_status_text, initialize_page, render_shared_sidebar, team_format_label


def main() -> None:
    if not initialize_page("Live Scoring"):
        return

    store = render_shared_sidebar()
    context = ensure_round_focus(build_page_context(store))
    render_section_header(
        "Live Scoring",
        "Fast in-round entry stays primary here, with one-hole phone entry first and the full-card editor kept as a secondary correction path.",
    )
    render_chip_row(
        [
            context["selected_fixture"]["title"],
            context["format_name"],
            f"{context['tee_label']} tees",
            f"Active hole {int(context['round_state']['active_hole'])}",
            team_format_label(context["format_name"], context["scramble_mode"], context["scoring_mode"]),
        ],
        tone="accent",
    )

    summary_columns = st.columns(3)
    with summary_columns[0]:
        render_metric_card("Active Hole", int(context["round_state"]["active_hole"]), "shared with course guide")
    with summary_columns[1]:
        render_metric_card("Round Progress", context["round_focus"]["progress_text"], None)
    with summary_columns[2]:
        render_status_card("Match State", fixture_status_text(context["selected_result"]), "updates with saved holes")

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
        )
        render_round_summary_metrics(format_name=context["format_name"], round_state=context["round_state"])


if __name__ == "__main__":
    main()
