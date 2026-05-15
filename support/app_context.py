from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from components.layout import load_css, render_chip_row, render_connection_panel
from domain.scoring import build_hole_shot_views, compute_round_results, compute_weekend_race
from domain.weekend_config import FIXTURES, format_fixture_label, get_fixture
from support.data_loader import data_package_exists, get_tee_rating, load_course_data
from support.paths import ASSETS_ROOT
from support.session import ensure_ui_state, set_active_hole, set_selected_fixture_id
from support.state_helpers import (
    build_round_state,
    get_round_runtime,
    load_app_store,
    load_saved_results,
    round_row_map,
    selected_fixture_id_for_ui,
)


FORMAT_OPTIONS = ("4-Ball", "Stroke Play", "Skins", "Singles")
TEE_OPTIONS = ("White", "Yellow")


def initialize_page(page_title: str) -> bool:
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


def _first_incomplete_hole(scores: pd.DataFrame, fallback_hole: int) -> int:
    if scores.empty or "hole" not in scores.columns:
        return fallback_hole
    incomplete = scores.loc[scores["status"].ne("Complete"), "hole"].dropna()
    if incomplete.empty:
        return fallback_hole
    return int(incomplete.iloc[0])


def build_round_focus(
    selected_fixture: dict[str, Any],
    round_runtime: dict[str, Any],
    round_state: dict[str, Any],
    selected_result: dict[str, Any],
    tee_rating: dict[str, Any],
) -> dict[str, Any]:
    total_holes = len(round_state["scores"].index)
    completed_holes = int(round_state["scores"]["status"].eq("Complete").sum())
    active_hole = int(round_state["active_hole"])
    next_hole = _first_incomplete_hole(round_state["scores"], active_hole)
    progress_text = f"{completed_holes} of {total_holes} holes saved" if total_holes else "No holes loaded"
    status_text = fixture_status_text(selected_result)

    if not tee_rating:
        return {
            "headline": "Finish round setup",
            "detail": f"No tee rating data is available for {round_runtime['tee_label']} tees yet, so scoring stays locked.",
            "status_text": status_text,
            "progress_text": progress_text,
            "primary_label": "Review setup",
            "primary_page": "pages/5_Setup_Admin.py",
            "secondary_label": "Open course guide",
            "secondary_page": "pages/4_Course_Guide.py",
            "tone": "gold",
            "completed_holes": completed_holes,
            "total_holes": total_holes,
            "active_hole": active_hole,
            "next_hole": next_hole,
        }

    if completed_holes <= 0:
        return {
            "headline": "Live scoring not started",
            "detail": f"Start on hole {active_hole} when you are ready. The live match view appears after the first save.",
            "status_text": status_text,
            "progress_text": progress_text,
            "primary_label": "Open live scoring",
            "primary_page": "pages/2_Live_Scoring.py",
            "secondary_label": "Open course guide",
            "secondary_page": "pages/4_Course_Guide.py",
            "tone": "neutral",
            "completed_holes": completed_holes,
            "total_holes": total_holes,
            "active_hole": active_hole,
            "next_hole": next_hole,
        }

    if completed_holes < total_holes:
        return {
            "headline": "Round in progress",
            "detail": f"Continue on hole {next_hole}. Match Centre fills in as more holes are saved.",
            "status_text": status_text,
            "progress_text": progress_text,
            "primary_label": "Continue live scoring",
            "primary_page": "pages/2_Live_Scoring.py",
            "secondary_label": "Open match centre",
            "secondary_page": "pages/3_Match_Centre.py",
            "tone": "blue",
            "completed_holes": completed_holes,
            "total_holes": total_holes,
            "active_hole": active_hole,
            "next_hole": next_hole,
        }

    return {
        "headline": "Round complete",
        "detail": f"{selected_fixture['title']} has all holes saved. Review the result before the next tee time.",
        "status_text": status_text,
        "progress_text": progress_text,
        "primary_label": "Review match centre",
        "primary_page": "pages/3_Match_Centre.py",
        "secondary_label": "Open weekend hub",
        "secondary_page": "pages/1_Weekend_Hub.py",
        "tone": "green",
        "completed_holes": completed_holes,
        "total_holes": total_holes,
        "active_hole": active_hole,
        "next_hole": next_hole,
    }


def ensure_round_focus(context: dict[str, Any]) -> dict[str, Any]:
    if context.get("round_focus"):
        return context

    selected_fixture = context.get("selected_fixture")
    round_runtime = context.get("round_runtime")
    round_state = context.get("round_state")
    selected_result = context.get("selected_result")

    if (
        isinstance(selected_fixture, dict)
        and isinstance(round_runtime, dict)
        and isinstance(round_state, dict)
        and isinstance(selected_result, dict)
    ):
        context["round_focus"] = build_round_focus(
            selected_fixture=selected_fixture,
            round_runtime=round_runtime,
            round_state=round_state,
            selected_result=selected_result,
            tee_rating=context.get("tee_rating", {}),
        )
        return context

    active_hole = 1
    scores = None
    if isinstance(round_state, dict):
        active_hole = int(round_state.get("active_hole", 1) or 1)
        maybe_scores = round_state.get("scores")
        if isinstance(maybe_scores, pd.DataFrame):
            scores = maybe_scores

    completed_holes = (
        int(scores["status"].eq("Complete").sum()) if scores is not None and "status" in scores.columns else 0
    )
    total_holes = len(scores.index) if scores is not None else 0
    progress_text = f"{completed_holes} of {total_holes} holes saved" if total_holes else "Round progress unavailable"
    context["round_focus"] = {
        "headline": "Round overview",
        "detail": "Open Live Scoring to continue the selected round.",
        "status_text": fixture_status_text(selected_result) if isinstance(selected_result, dict) else "Awaiting scores",
        "progress_text": progress_text,
        "primary_label": "Open live scoring",
        "primary_page": "pages/2_Live_Scoring.py",
        "secondary_label": "Open weekend hub",
        "secondary_page": "pages/1_Weekend_Hub.py",
        "tone": "blue",
        "completed_holes": completed_holes,
        "total_holes": total_holes,
        "active_hole": active_hole,
        "next_hole": _first_incomplete_hole(scores, active_hole) if scores is not None else active_hole,
    }
    return context


def render_shared_sidebar() -> dict[str, Any]:
    store = load_app_store()
    weekend_state = store["weekend_state"]
    fixture_ids = [fixture["id"] for fixture in FIXTURES]
    current_fixture_id = selected_fixture_id_for_ui(weekend_state)

    with st.sidebar:
        st.header("Round Context")
        selected_fixture_id = st.selectbox(
            "Round",
            options=fixture_ids,
            index=fixture_ids.index(current_fixture_id),
            format_func=lambda fixture_id: format_fixture_label(get_fixture(fixture_id)),
        )
        if selected_fixture_id != current_fixture_id:
            set_selected_fixture_id(selected_fixture_id)
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
        next_hole = _first_incomplete_hole(round_state["scores"], int(round_state["active_hole"]))

        render_connection_panel(store["persistence"]["status"], compact=True)
        st.caption("Use the sidebar to move around. The selected round stays in sync across each page.")
        st.markdown(f"**{selected_fixture['title']}**")
        st.caption(f"{round_runtime['format_name']} • {round_runtime['tee_label']} tees")
        st.caption(f"Active hole {int(round_state['active_hole'])} • Next to score {next_hole} • Completed {completed_holes}")
    return store


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
    round_focus = build_round_focus(
        selected_fixture=selected_fixture,
        round_runtime=round_runtime,
        round_state=round_state,
        selected_result=selected_result,
        tee_rating=tee_rating,
    )
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

    return ensure_round_focus(
        {
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
            "round_focus": round_focus,
            "results_by_fixture": results_by_fixture,
            "saved_results": saved_results,
            "shot_views": shot_views,
            "weekend_race": compute_weekend_race(results_by_fixture),
            "round_rows_by_id": round_row_map(store["round_rows"]),
        }
    )
