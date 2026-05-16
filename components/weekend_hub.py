from __future__ import annotations

from typing import Any

import streamlit as st

from components.layout import (
    render_chip_row,
    render_fixture_card,
    render_metric_card,
    render_page_action,
    render_section_header,
    render_status_card,
)
from domain.formatting import format_handicap_index, format_points
from domain.weekend_config import FIXTURES, TEAM_CONFIG, team_short_name


def _fixture_index(fixture_id: str) -> int:
    for index, fixture in enumerate(FIXTURES):
        if fixture["id"] == fixture_id:
            return index
    return 0


def _next_fixture(fixture_id: str) -> dict[str, Any] | None:
    next_index = _fixture_index(fixture_id) + 1
    if next_index >= len(FIXTURES):
        return None
    return FIXTURES[next_index]


def render_weekend_hub(
    selected_fixture: dict[str, Any],
    player_names: list[str],
    handicap_indexes: list[float],
    fixture_formats: dict[str, str],
    fixture_tees: dict[str, str],
    results_by_fixture: dict[str, dict[str, Any]],
    round_focus: dict[str, Any],
    round_focus_by_fixture: dict[str, dict[str, Any]] | None,
    weekend_race: dict[str, Any],
    show_header: bool = True,
) -> None:
    if show_header:
        render_section_header(
            "Weekend Hub",
            "Lead with the live round first, then drop into the wider weekend picture when you need it.",
        )

    next_fixture = _next_fixture(selected_fixture["id"])
    show_progress = int(round_focus["completed_holes"]) > 0
    current_round_detail = (
        f"{selected_fixture['date_label']} {selected_fixture['time_label']} • "
        f"{fixture_formats[selected_fixture['id']]} • "
        f"{fixture_tees[selected_fixture['id']]} tees • "
        f"{round_focus['progress_text']}"
    )
    render_status_card("Current Round", selected_fixture["title"], current_round_detail, tone=round_focus["tone"])
    if show_progress:
        render_chip_row([round_focus["status_text"]], tone="accent")
    action_columns = st.columns(2)
    with action_columns[0]:
        render_page_action(
            round_focus["primary_page"],
            round_focus["primary_label"],
            key=f"hub-primary::{selected_fixture['id']}",
            primary=True,
        )
    with action_columns[1]:
        render_page_action(
            round_focus["secondary_page"],
            round_focus["secondary_label"],
            key=f"hub-secondary::{selected_fixture['id']}",
            primary=round_focus["secondary_page"] == "pages/4_Course_Guide.py",
        )

    if next_fixture is None:
        render_status_card("What’s Next", "Final fixture selected", "No later tee time remains on the fixture list")
    else:
        render_status_card(
            "What’s Next",
            next_fixture["title"],
            f"{fixture_formats[next_fixture['id']]} • {next_fixture['date_label']} • {next_fixture['time_label']}",
        )

    points_row_one = st.columns(2)
    with points_row_one[0]:
        render_metric_card(f"{team_short_name('red')} Points", format_points(weekend_race["red_points"]), "weekend", tone="red")
    with points_row_one[1]:
        render_metric_card(f"{team_short_name('blue')} Points", format_points(weekend_race["blue_points"]), "weekend", tone="blue")
    points_row_two = st.columns(2)
    with points_row_two[0]:
        render_metric_card("Remaining", format_points(weekend_race["remaining_points"]), "points available")
    with points_row_two[1]:
        render_metric_card("Winning Mark", format_points(weekend_race["winning_target"]), "points to win")

    with st.expander("Teams", expanded=False):
        team_columns = st.columns(2)
        with team_columns[0]:
            render_status_card(
                TEAM_CONFIG["red"]["name"],
                f"{player_names[0]} + {player_names[1]}",
                f"Indexes {format_handicap_index(handicap_indexes[0])} / {format_handicap_index(handicap_indexes[1])}",
                tone="red",
            )
        with team_columns[1]:
            render_status_card(
                TEAM_CONFIG["blue"]["name"],
                f"{player_names[2]} + {player_names[3]}",
                f"Indexes {format_handicap_index(handicap_indexes[2])} / {format_handicap_index(handicap_indexes[3])}",
                tone="blue",
            )

    with st.expander("Weekend race detail", expanded=False):
        race_columns = st.columns([1.05, 1.05, 1.35])
        with race_columns[0]:
            render_status_card(f"{team_short_name('red')} Path", format_points(weekend_race["red_needed"]), weekend_race["red_path"], tone="red")
        with race_columns[1]:
            render_status_card(f"{team_short_name('blue')} Path", format_points(weekend_race["blue_needed"]), weekend_race["blue_path"], tone="blue")
        with race_columns[2]:
            render_status_card("Weekend Race", weekend_race["status"], "Unresolved rounds stay pending until points are awarded")

        points_table = weekend_race["points_table"].copy()
        for team_label in ("Red", "Blue", "Points Available"):
            points_table[team_label] = points_table[team_label].apply(format_points)
        points_table = points_table.rename(columns={"Red": team_short_name("red"), "Blue": team_short_name("blue")})
        st.dataframe(points_table, width="stretch", hide_index=True)

    st.markdown("#### Fixtures")
    fixture_columns = st.columns(2)
    for index, fixture in enumerate(FIXTURES):
        fixture_result = results_by_fixture.get(fixture["id"], {})
        fixture_focus = (round_focus_by_fixture or {}).get(fixture["id"], {})
        awarded = fixture_result.get("awarded_points", {"red": 0.0, "blue": 0.0})
        status = str(fixture_focus.get("status_text") or "Awaiting scores")
        progress_text = str(fixture_focus.get("progress_text") or "")
        if progress_text:
            status = f"{status} • {progress_text}"

        with fixture_columns[index % 2]:
            render_fixture_card(
                title=fixture["title"],
                format_name=fixture_formats[fixture["id"]],
                schedule=f"{fixture['date_label']} • {fixture['time_label']} • {fixture_tees[fixture['id']]} tees",
                status=status,
                red_points=format_points(float(awarded.get("red", 0.0))),
                blue_points=format_points(float(awarded.get("blue", 0.0))),
            )
