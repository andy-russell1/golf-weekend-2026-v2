from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from components.layout import load_css, render_chip_row, render_connection_panel
from domain.scoring import build_hole_shot_views, compute_round_results, compute_weekend_race
from domain.weekend_config import FIXTURES, format_fixture_label, get_fixture
from support.data_loader import data_package_exists, get_tee_rating, load_course_data
from support.paths import ASSETS_ROOT
from support.session import ensure_ui_state, set_active_hole
from support.state_helpers import (
    build_round_state,
    get_round_runtime,
    load_app_store,
    load_saved_results,
    round_row_map,
    save_setting,
    selected_fixture_id_for_ui,
)


FORMAT_OPTIONS = ("4-Ball", "Stroke Play", "Skins", "Singles")
TEE_OPTIONS = ("White", "Yellow")
PAGE_LINKS: tuple[tuple[str, str], ...] = (
    ("app.py", "Home"),
    ("pages/1_Weekend_Hub.py", "Weekend Hub"),
    ("pages/2_Live_Scoring.py", "Live Scoring"),
    ("pages/3_Match_Centre.py", "Match Centre"),
    ("pages/4_Course_Guide.py", "Course Guide"),
    ("pages/5_Setup_Admin.py", "Setup / Admin"),
)


def initialize_page(page_title: str) -> bool:
    st.set_page_config(page_title=f"{page_title} | Golf Weekend 2026", layout="wide")
    load_css(ASSETS_ROOT / "styles.css")

    if not data_package_exists():
        st.error("The required `golf_trip_data/` package is missing or incomplete in the working directory.")
        return False

    ensure_ui_state()
    return True


def team_format_label(format_name: str, scramble_mode: str = "", scoring_mode: str = "standard") -> str:
    if format_name in {"Singles", "4-Ball"}:
        return "match play"
    if format_name == "Stroke Play":
        return "net better ball"
    if format_name == "Skins":
        return "net skins"
    return format_name.lower()


def empty_result(format_name: str) -> dict[str, object]:
    return {
        "format_name": format_name,
        "summary_df": pd.DataFrame(),
        "player_handicaps": pd.DataFrame(),
        "awarded_points": {"red": 0.0, "blue": 0.0},
        "projected_points": {"red": 0.0, "blue": 0.0},
        "export_bytes": b"",
        "status_text": "Awaiting scores",
        "winner": "",
        "is_complete": False,
    }


def fixture_status_text(result: dict[str, Any]) -> str:
    if result.get("status_text"):
        return str(result["status_text"])
    if result.get("format_name") == "Singles" and result.get("matches"):
        return " / ".join(match["current_status"] for match in result["matches"])
    if result.get("match"):
        return str(result["match"]["current_status"])
    return "Awaiting scores"


def render_shared_sidebar() -> dict[str, Any]:
    store = load_app_store()
    weekend_state = store["weekend_state"]
    fixture_ids = [fixture["id"] for fixture in FIXTURES]
    current_fixture_id = selected_fixture_id_for_ui(weekend_state)

    with st.sidebar:
        st.header("Weekend Context")
        selected_fixture_id = st.selectbox(
            "Round",
            options=fixture_ids,
            index=fixture_ids.index(current_fixture_id),
            format_func=lambda fixture_id: format_fixture_label(get_fixture(fixture_id)),
        )
        if selected_fixture_id != current_fixture_id:
            save_setting("selected_fixture_id", selected_fixture_id)
            st.rerun()

        selected_fixture = get_fixture(selected_fixture_id)
        round_runtime = get_round_runtime(store["round_rows"], selected_fixture["id"])
        course_df = load_course_data(selected_fixture["course"])
        holes = [int(hole) for hole in course_df["hole"].dropna().tolist()]
        round_state = build_round_state(
            round_id=selected_fixture["id"],
            holes=holes,
            format_name=round_runtime["format_name"],
            runtime_players=store["runtime_players"],
            snapshot=store["persistence"],
        )
        completed_holes = int(round_state["scores"]["status"].eq("Complete").sum())

        render_connection_panel(store["persistence"]["status"], compact=True)
        st.caption("Round setup changes live on Setup / Admin. This selector keeps the same fixture context across pages.")
        st.markdown(f"**{selected_fixture['title']}**")
        st.caption(f"{round_runtime['format_name']} • {round_runtime['tee_label']} tees")
        st.caption(f"Active hole: {int(round_state['active_hole'])} • Completed: {completed_holes}")
    return store


def render_page_links(current_page: str) -> None:
    for row_start in range(0, len(PAGE_LINKS), 3):
        columns = st.columns(3)
        row_items = PAGE_LINKS[row_start : row_start + 3]
        for column, (path, label) in zip(columns, row_items):
            with column:
                if label == current_page:
                    st.caption("Current page")
                st.page_link(path, label=label, use_container_width=True)


def build_results_by_fixture(store: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results_by_fixture: dict[str, dict[str, Any]] = {}
    runtime_players = store["runtime_players"]
    snapshot = store["persistence"]
    for fixture in FIXTURES:
        round_runtime = get_round_runtime(store["round_rows"], fixture["id"])
        fixture_course_df = load_course_data(fixture["course"])
        fixture_holes = [int(hole) for hole in fixture_course_df["hole"].dropna().tolist()]
        fixture_round_state = build_round_state(
            round_id=fixture["id"],
            holes=fixture_holes,
            format_name=round_runtime["format_name"],
            runtime_players=runtime_players,
            snapshot=snapshot,
        )
        fixture_tee_rating = get_tee_rating(fixture["course"], round_runtime["tee_label"])
        result: dict[str, Any]
        if fixture_tee_rating:
            result = compute_round_results(
                course_df=fixture_course_df,
                format_name=round_runtime["format_name"],
                score_df=fixture_round_state["scores"],
                player_names=list(runtime_players["player_names"]),
                player_ids=list(runtime_players["player_ids"]),
                handicap_indexes=list(runtime_players["handicap_indexes"]),
                tee_rating=fixture_tee_rating,
                allowance_percent=round_runtime["allowance_percent"],
                scramble_mode=round_runtime["scramble_mode"],
                scoring_mode=round_runtime["scoring_mode"],
                stableford_mode=round_runtime["stableford_mode"],
            )
        else:
            result = empty_result(round_runtime["format_name"])
        results_by_fixture[fixture["id"]] = result
    return results_by_fixture


def build_page_context(store: dict[str, Any] | None = None) -> dict[str, Any]:
    store = store or load_app_store()
    weekend_state = store["weekend_state"]
    snapshot = store["persistence"]
    selected_fixture_id = selected_fixture_id_for_ui(weekend_state)
    selected_fixture = get_fixture(selected_fixture_id)
    round_runtime = get_round_runtime(store["round_rows"], selected_fixture_id)
    course = selected_fixture["course"]
    course_df = load_course_data(course)
    holes = [int(hole) for hole in course_df["hole"].dropna().tolist()]
    round_state = build_round_state(
        round_id=selected_fixture_id,
        holes=holes,
        format_name=round_runtime["format_name"],
        runtime_players=store["runtime_players"],
        snapshot=snapshot,
    )
    tee_rating = get_tee_rating(course, round_runtime["tee_label"])

    results_by_fixture = build_results_by_fixture(store)
    selected_result = results_by_fixture.get(selected_fixture_id, empty_result(round_runtime["format_name"]))
    player_names = list(round_state["player_names"])
    handicap_indexes = list(round_state["handicap_indexes"])
    shot_views = build_hole_shot_views(
        course_df=course_df,
        format_name=round_runtime["format_name"],
        player_rows=selected_result.get("player_handicaps", pd.DataFrame()),
        player_names=player_names,
    )

    set_active_hole(selected_fixture_id, int(round_state["active_hole"]))
    saved_results = load_saved_results(snapshot=snapshot)

    return {
        "store": store,
        "persistence": store["persistence"],
        "weekend_state": weekend_state,
        "selected_fixture": selected_fixture,
        "round_runtime": round_runtime,
        "format_name": round_runtime["format_name"],
        "tee_label": round_runtime["tee_label"],
        "allowance_percent": round_runtime["allowance_percent"],
        "scramble_mode": round_runtime["scramble_mode"],
        "scoring_mode": round_runtime["scoring_mode"],
        "stableford_mode": round_runtime["stableford_mode"],
        "course": course,
        "course_df": course_df,
        "holes": holes,
        "round_state": round_state,
        "tee_rating": tee_rating,
        "player_names": player_names,
        "player_ids": list(round_state["player_ids"]),
        "handicap_indexes": handicap_indexes,
        "selected_result": selected_result,
        "results_by_fixture": results_by_fixture,
        "saved_results": saved_results,
        "shot_views": shot_views,
        "weekend_race": compute_weekend_race(results_by_fixture),
        "round_rows_by_id": round_row_map(store["round_rows"]),
    }
