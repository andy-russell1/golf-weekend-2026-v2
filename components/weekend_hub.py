from __future__ import annotations

from typing import Any

import streamlit as st

from components.layout import (
    render_chip_row,
    render_fixture_card,
    render_metric_card,
    render_section_header,
    render_status_card,
)
from domain.formatting import format_handicap_index, format_points
from domain.scoring import compute_weekend_race
from domain.weekend_config import FIXTURES, TEAM_CONFIG, build_team_label, format_fixture_label


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
) -> None:
    render_section_header(
        "Weekend Hub",
        "Weekend race, team identities, and fixture cards built around the live Ryder Cup picture.",
    )

    race = compute_weekend_race(results_by_fixture)
    overview_columns = st.columns(4)
    with overview_columns[0]:
        render_metric_card("Weekend Points", format_points(race["red_points"]), "Red", tone="red")
    with overview_columns[1]:
        render_metric_card("Weekend Points", format_points(race["blue_points"]), "Blue", tone="blue")
    with overview_columns[2]:
        render_metric_card("Remaining", format_points(race["remaining_points"]), "points available")
    with overview_columns[3]:
        render_metric_card("Winning Mark", format_points(race["winning_target"]), "points to win")

    race_columns = st.columns([1.15, 1.15, 1.4])
    with race_columns[0]:
        render_status_card("Red Path", format_points(race["red_needed"]), race["red_path"], tone="red")
    with race_columns[1]:
        render_status_card("Blue Path", format_points(race["blue_needed"]), race["blue_path"], tone="blue")
    with race_columns[2]:
        render_status_card("Weekend Race", race["status"], "Unresolved rounds stay pending until points are awarded")

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

    selected_result = results_by_fixture.get(selected_fixture["id"], {})
    selected_status = "Awaiting scores"
    if selected_result.get("format_name") == "Singles" and selected_result.get("matches"):
        selected_status = " / ".join(match["current_status"] for match in selected_result["matches"])
    elif selected_result.get("match"):
        selected_status = selected_result["match"]["current_status"]

    next_fixture = _next_fixture(selected_fixture["id"])
    summary_columns = st.columns(2)
    with summary_columns[0]:
        render_section_header("Selected Round")
        render_chip_row(
            [
                format_fixture_label(selected_fixture),
                fixture_formats[selected_fixture["id"]],
                f"{fixture_tees[selected_fixture['id']]} tees",
                build_team_label("red", player_names),
                build_team_label("blue", player_names),
            ],
            tone="accent",
        )
        render_status_card("Current Focus", selected_status, "Live status for the selected round")
    with summary_columns[1]:
        render_section_header("What’s Next")
        if next_fixture is None:
            render_status_card("Weekend Finale", "Final fixture selected", "No later tee time remains on the fixture list")
        else:
            render_status_card(
                next_fixture["title"],
                fixture_formats[next_fixture["id"]],
                f"{next_fixture['date_label']} • {next_fixture['time_label']} • {fixture_tees[next_fixture['id']]} tees",
            )

    st.markdown("#### Weekend Points")
    points_table = race["points_table"].copy()
    for team_label in ("Red", "Blue", "Points Available"):
        points_table[team_label] = points_table[team_label].apply(format_points)
    st.dataframe(points_table, use_container_width=True, hide_index=True)

    st.markdown("#### Quick Links")
    link_columns = st.columns(4)
    with link_columns[0]:
        st.page_link("pages/2_Live_Scoring.py", label="Live Scoring", use_container_width=True)
    with link_columns[1]:
        st.page_link("pages/3_Match_Centre.py", label="Match Centre", use_container_width=True)
    with link_columns[2]:
        st.page_link("pages/4_Course_Guide.py", label="Course Guide", use_container_width=True)
    with link_columns[3]:
        st.page_link("pages/5_Setup_Admin.py", label="Setup / Admin", use_container_width=True)

    st.markdown("#### Fixtures")
    fixture_columns = st.columns(2)
    for index, fixture in enumerate(FIXTURES):
        fixture_result = results_by_fixture.get(fixture["id"], {})
        awarded = fixture_result.get("awarded_points", {"red": 0.0, "blue": 0.0})
        status = "Awaiting scores"
        if fixture_result.get("format_name") == "Singles" and fixture_result.get("matches"):
            status = " / ".join(match["current_status"] for match in fixture_result["matches"])
        elif fixture_result.get("match"):
            status = fixture_result["match"]["current_status"]

        with fixture_columns[index % 2]:
            render_fixture_card(
                title=fixture["title"],
                format_name=fixture_formats[fixture["id"]],
                schedule=f"{fixture['date_label']} • {fixture['time_label']} • {fixture_tees[fixture['id']]} tees",
                status=status,
                red_points=format_points(float(awarded.get("red", 0.0))),
                blue_points=format_points(float(awarded.get("blue", 0.0))),
            )
