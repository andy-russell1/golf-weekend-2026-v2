from __future__ import annotations

import streamlit as st

from domain.weekend_config import FIXTURES
from support.session import set_active_hole, set_selected_fixture_id


FIXTURE_QUERY_PARAM = "fixture"
HOLE_QUERY_PARAM = "hole"


def _query_param_value(name: str) -> str:
    value = st.query_params.get(name, "")
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _update_query_param_if_changed(name: str, value: object) -> bool:
    text_value = str(value)
    if _query_param_value(name) == text_value:
        return False
    st.query_params.update({name: text_value})
    return True


def _fixture_from_url(fixture_ids: list[str]) -> str | None:
    fixture_id = _query_param_value(FIXTURE_QUERY_PARAM)
    if fixture_id in fixture_ids:
        return fixture_id
    return None


def sync_fixture_from_url() -> None:
    fixture_ids = [fixture["id"] for fixture in FIXTURES]
    fixture_id = _fixture_from_url(fixture_ids)
    if fixture_id is not None:
        set_selected_fixture_id(fixture_id)


def set_selected_fixture_for_ui(fixture_id: str) -> bool:
    set_selected_fixture_id(fixture_id)
    st.query_params.pop(HOLE_QUERY_PARAM, None)
    return _update_query_param_if_changed(FIXTURE_QUERY_PARAM, fixture_id)


def sync_fixture_to_url(fixture_id: str) -> bool:
    return _update_query_param_if_changed(FIXTURE_QUERY_PARAM, fixture_id)


def _hole_from_url(holes: list[int]) -> int | None:
    raw_hole = _query_param_value(HOLE_QUERY_PARAM)
    if not raw_hole:
        return None
    try:
        hole = int(raw_hole)
    except ValueError:
        return None
    if hole in holes:
        return hole
    return None


def sync_active_hole_from_url(round_id: str, holes: list[int]) -> None:
    hole = _hole_from_url(holes)
    if hole is not None:
        set_active_hole(round_id, hole, source="manual")


def sync_active_hole_to_url(hole: int) -> bool:
    return _update_query_param_if_changed(HOLE_QUERY_PARAM, hole)


def set_active_hole_for_ui(round_id: str, hole: int, source: str = "manual") -> bool:
    set_active_hole(round_id, hole, source=source)
    return sync_active_hole_to_url(hole)
