from __future__ import annotations

from typing import Any

import streamlit as st

from components.layout import render_chip_row, render_metric_card, render_section_header, render_status_card
from support.data_loader import get_course_summary_record, load_course_data
from domain.formatting import format_handicap_index
from domain.handicap import build_player_handicap_table


def render_course_briefing(
    course: str,
    course_title: str,
    tee_label: str,
    format_name: str,
) -> None:
    course_df = load_course_data(course)
    summary = get_course_summary_record(course)

    render_section_header(
        "Course Guide",
        "Quick round briefing for the selected venue, with hole data kept close to live scoring needs.",
    )

    if course_df.empty:
        st.warning("No course data is available for this selection.")
        return

    render_chip_row([course_title, format_name, f"{tee_label} tees"])
    dash = "\u2014"

    metric_columns = st.columns(3)
    selected_yard_total_key = "yards_white_total" if tee_label.lower() == "white" else "yards_yellow_total"
    metrics = [
        ("Total Par", summary.get("par_total", dash), None),
        (f"{tee_label} Total", summary.get(selected_yard_total_key, dash), "yards"),
        ("Format", format_name, None),
    ]
    for column, (label, value, supporting) in zip(metric_columns, metrics):
        with column:
            render_metric_card(label, value, supporting)
    render_chip_row(
        [
            f"Front 9 par {summary.get('par_out', dash)}",
            f"Back 9 par {summary.get('par_in', dash)}",
        ],
        tone="accent",
    )


def render_playing_handicap_summary(
    player_names: list[str],
    handicap_indexes: list[float],
    tee_rating: dict[str, Any],
    allowance_percent: int,
    tee_label: str,
) -> None:
    st.markdown("#### Playing Handicaps")

    player_rows = build_player_handicap_table(
        player_names=player_names,
        handicap_indexes=handicap_indexes,
        tee_rating=tee_rating,
        allowance=allowance_percent / 100,
    )
    if player_rows.empty:
        st.info(f"No tee rating metadata is available for {tee_label} tees, so playing handicaps cannot be shown.")
        return

    card_columns = st.columns(2)
    for index, (_, row) in enumerate(player_rows.iterrows()):
        with card_columns[index % 2]:
            render_status_card(
                str(row["Player"]),
                f"Playing {int(row['Playing Handicap'])}",
                f"HI {format_handicap_index(row['Handicap Index'])} • Course {int(row['Course Handicap'])}",
                tone=str(row["Team Id"]),
            )

    display = player_rows.copy()
    display["Handicap Index"] = display["Handicap Index"].apply(format_handicap_index)
    display["Allowance"] = display["Allowance"].apply(lambda value: f"{int(float(value) * 100)}%")
    with st.expander("Detailed handicap table", expanded=False):
        st.dataframe(
            display[["Player", "Team", "Handicap Index", "Course Handicap", "Playing Handicap", "Allowance"]],
            width="stretch",
            hide_index=True,
        )


def render_course_scorecard(course: str, tee_label: str) -> None:
    course_df = load_course_data(course)
    if course_df.empty:
        st.warning("No course data is available for this selection.")
        return

    preview = course_df.copy()
    selected_yardage_column = "yards_white" if tee_label.lower() == "white" else "yards_yellow"
    selected_yard_label = f"{tee_label} Yards"
    preview = preview.rename(
        columns={
            "hole": "Hole",
            "par": "Par",
            selected_yardage_column: selected_yard_label,
            "si": "SI",
        }
    )
    st.markdown("#### Scorecard")
    st.dataframe(preview[["Hole", "Par", selected_yard_label, "SI"]], width="stretch", hide_index=True)


def render_course_overview(
    course: str,
    course_title: str,
    tee_label: str,
    format_name: str,
) -> None:
    render_course_briefing(
        course=course,
        course_title=course_title,
        tee_label=tee_label,
        format_name=format_name,
    )
    render_course_scorecard(course=course, tee_label=tee_label)
