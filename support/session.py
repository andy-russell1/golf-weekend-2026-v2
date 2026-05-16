from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from domain.bonus_competitions import BONUS_COMPETITIONS_SETTING_KEY, bonus_competitions_from_json
from domain.weekend_config import (
    DEFAULT_ALLOWANCE_PERCENT,
    DEFAULT_SHOW_GROSS_SECONDARY,
    FIXTURES,
    SINGLES_MATCHUPS_SETTING_KEY,
    TEAM_CONFIG,
    default_handicap_indexes,
    default_player_ids,
    default_player_names,
    default_players_sheet_rows,
    default_rounds_sheet_rows,
    default_settings_sheet_rows,
    singles_matchups_from_json,
)


FORMAT_CONFIG: dict[str, dict[str, Any]] = {
    "Singles": {
        "active_player_count": 4,
        "score_columns": ("player_1", "player_2", "player_3", "player_4"),
    },
    "4-Ball": {
        "active_player_count": 4,
        "score_columns": ("player_1", "player_2", "player_3", "player_4"),
    },
    "Stroke Play": {
        "active_player_count": 4,
        "score_columns": ("player_1", "player_2", "player_3", "player_4"),
    },
    "Skins": {
        "active_player_count": 4,
        "score_columns": ("player_1", "player_2", "player_3", "player_4"),
    },
}

TEAM_A_PLAYERS = TEAM_CONFIG["red"]["player_indices"]
TEAM_B_PLAYERS = TEAM_CONFIG["blue"]["player_indices"]
DEFAULT_PLAYER_NAMES = tuple(default_player_names())
DEFAULT_PLAYER_IDS = tuple(default_player_ids())
DEFAULT_HANDICAP_INDEXES = tuple(default_handicap_indexes())
DEFAULT_SCRAMBLE_MODE = ""
DEFAULT_SCORING_MODE = "net"
DEFAULT_STABLEFORD_MODE = ""


def get_format_config(format_name: str) -> dict[str, Any]:
    return FORMAT_CONFIG.get(format_name, FORMAT_CONFIG["4-Ball"])


def ensure_ui_state() -> dict[str, Any]:
    if "selected_fixture_id" not in st.session_state:
        st.session_state["selected_fixture_id"] = FIXTURES[0]["id"]
    if "round_active_holes" not in st.session_state:
        st.session_state["round_active_holes"] = {}
    if "local_persistence" not in st.session_state:
        st.session_state["local_persistence"] = _build_local_store()
    return {
        "selected_fixture_id": st.session_state["selected_fixture_id"],
        "round_active_holes": st.session_state["round_active_holes"],
    }


def _build_local_store() -> dict[str, Any]:
    return {
        "players": default_players_sheet_rows(),
        "rounds": default_rounds_sheet_rows(),
        "settings": default_settings_sheet_rows(),
        "scores": [],
        "results": {},
    }


def get_local_store() -> dict[str, Any]:
    ensure_ui_state()
    return st.session_state["local_persistence"]


def get_selected_fixture_id() -> str:
    ensure_ui_state()
    return str(st.session_state["selected_fixture_id"])


def set_selected_fixture_id(fixture_id: str) -> None:
    ensure_ui_state()
    st.session_state["selected_fixture_id"] = fixture_id


def get_active_hole(round_id: str, holes: list[int]) -> int:
    ensure_ui_state()
    active_holes = st.session_state["round_active_holes"]
    active_hole = int(active_holes.get(round_id, holes[0] if holes else 1))
    if holes and active_hole not in holes:
        active_hole = holes[0]
        active_holes[round_id] = active_hole
    return active_hole


def set_active_hole(round_id: str, hole: int) -> None:
    ensure_ui_state()
    st.session_state["round_active_holes"][round_id] = int(hole)


def parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip():
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return default


def _round_row(round_id: str) -> dict[str, Any]:
    store = get_local_store()
    for row in store["rounds"]:
        if str(row.get("round_id")) == round_id:
            return row
    return {}


def local_players() -> list[dict[str, Any]]:
    return list(get_local_store()["players"])


def local_rounds() -> list[dict[str, Any]]:
    return sorted(get_local_store()["rounds"], key=lambda row: int(float(row.get("round_order") or 0)))


def local_settings() -> list[dict[str, Any]]:
    return list(get_local_store()["settings"])


def local_scores(round_id: str | None = None) -> list[dict[str, Any]]:
    rows = list(get_local_store()["scores"])
    if round_id is None:
        return rows
    return [row for row in rows if str(row.get("round_id")) == round_id]


def local_results() -> dict[str, dict[str, Any]]:
    return dict(get_local_store()["results"])


def save_local_players(rows: list[dict[str, Any]]) -> None:
    get_local_store()["players"] = list(rows)


def save_local_round(round_id: str, payload: dict[str, Any]) -> None:
    store = get_local_store()
    updated: list[dict[str, Any]] = []
    replaced = False
    for row in store["rounds"]:
        if str(row.get("round_id")) == round_id:
            updated.append({**row, **payload, "round_id": round_id})
            replaced = True
        else:
            updated.append(row)
    if not replaced:
        updated.append({**payload, "round_id": round_id})
    store["rounds"] = updated


def update_local_setting(key: str, value: str) -> None:
    store = get_local_store()
    updated: list[dict[str, Any]] = []
    replaced = False
    for row in store["settings"]:
        if str(row.get("key")) == key:
            updated.append({"key": key, "value": value})
            replaced = True
        else:
            updated.append(row)
    if not replaced:
        updated.append({"key": key, "value": value})
    store["settings"] = updated


def save_local_hole_scores(round_id: str, hole: int, rows: list[dict[str, Any]]) -> None:
    store = get_local_store()
    existing = store["scores"]
    replacements = {(round_id, hole, str(row.get("player_id", ""))): row for row in rows}
    updated: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()
    for row in existing:
        key = (str(row.get("round_id", "")), int(float(row.get("hole") or 0)), str(row.get("player_id", "")))
        if key in replacements:
            updated.append({**row, **replacements[key], "round_id": round_id, "hole": hole})
            seen.add(key)
        else:
            updated.append(row)
    for key, row in replacements.items():
        if key not in seen:
            updated.append({**row, "round_id": round_id, "hole": hole})
    store["scores"] = updated


def clear_local_round_scores(round_id: str) -> None:
    store = get_local_store()
    store["scores"] = [row for row in store["scores"] if str(row.get("round_id")) != round_id]
    store["results"].pop(round_id, None)


def save_local_result(round_id: str, payload: dict[str, Any]) -> None:
    get_local_store()["results"][round_id] = payload


def load_weekend_settings_map(settings_rows: list[dict[str, Any]]) -> dict[str, str]:
    settings_map = {str(row.get("key", "")): str(row.get("value", "")) for row in settings_rows}
    settings_map.setdefault("selected_fixture_id", FIXTURES[0]["id"])
    settings_map.setdefault("show_gross_secondary", "true" if DEFAULT_SHOW_GROSS_SECONDARY else "false")
    settings_map.setdefault(SINGLES_MATCHUPS_SETTING_KEY, "")
    settings_map.setdefault(BONUS_COMPETITIONS_SETTING_KEY, "")
    return settings_map


def players_to_runtime(players_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(players_rows, key=lambda row: int(float(row.get("display_order") or 0)))
    player_ids = [str(row.get("player_id", "")).strip() for row in ordered][:4]
    player_names = [str(row.get("player_name", "")).strip() or DEFAULT_PLAYER_NAMES[index] for index, row in enumerate(ordered[:4])]
    handicap_indexes = [
        float(row.get("handicap_index") or DEFAULT_HANDICAP_INDEXES[index]) for index, row in enumerate(ordered[:4])
    ]
    while len(player_ids) < 4:
        player_ids.append(DEFAULT_PLAYER_IDS[len(player_ids)])
    while len(player_names) < 4:
        player_names.append(DEFAULT_PLAYER_NAMES[len(player_names)])
    while len(handicap_indexes) < 4:
        handicap_indexes.append(DEFAULT_HANDICAP_INDEXES[len(handicap_indexes)])
    return {
        "player_ids": player_ids,
        "player_names": player_names,
        "handicap_indexes": handicap_indexes,
    }


def weekend_state_from_round_rows(round_rows: list[dict[str, Any]], settings_rows: list[dict[str, Any]]) -> dict[str, Any]:
    settings_map = load_weekend_settings_map(settings_rows)
    fixture_formats: dict[str, str] = {}
    fixture_tees: dict[str, str] = {}
    fixture_allowances: dict[str, int] = {}
    fixture_scramble_modes: dict[str, str] = {}
    fixture_scoring_modes: dict[str, str] = {}
    fixture_stableford_modes: dict[str, str] = {}

    for fixture in FIXTURES:
        row = next((candidate for candidate in round_rows if str(candidate.get("round_id")) == fixture["id"]), fixture)
        fixture_id = fixture["id"]
        fixture_formats[fixture_id] = str(row.get("format_label") or row.get("format_key") or fixture["default_format"])
        fixture_tees[fixture_id] = str(row.get("tee") or fixture["default_tee"])
        fixture_allowances[fixture_id] = int(float(row.get("allowance_percent") or DEFAULT_ALLOWANCE_PERCENT))
        fixture_scramble_modes[fixture_id] = str(row.get("scramble_mode") or fixture.get("scramble_mode", DEFAULT_SCRAMBLE_MODE))
        fixture_scoring_modes[fixture_id] = str(row.get("scoring_mode") or fixture.get("scoring_mode", DEFAULT_SCORING_MODE))
        fixture_stableford_modes[fixture_id] = str(row.get("stableford_mode") or fixture.get("stableford_mode", DEFAULT_STABLEFORD_MODE))

    return {
        "selected_fixture_id": settings_map["selected_fixture_id"],
        "fixture_formats": fixture_formats,
        "fixture_tees": fixture_tees,
        "fixture_allowances": fixture_allowances,
        "fixture_scramble_modes": fixture_scramble_modes,
        "fixture_scoring_modes": fixture_scoring_modes,
        "fixture_stableford_modes": fixture_stableford_modes,
        "show_gross_secondary": parse_bool(settings_map.get("show_gross_secondary"), DEFAULT_SHOW_GROSS_SECONDARY),
        "singles_matchups": singles_matchups_from_json(settings_map.get(SINGLES_MATCHUPS_SETTING_KEY, "")),
        "bonus_competitions": bonus_competitions_from_json(settings_map.get(BONUS_COMPETITIONS_SETTING_KEY, "")),
    }


def blank_scores(holes: list[int], format_name: str) -> pd.DataFrame:
    config = get_format_config(format_name)
    frame = pd.DataFrame({"hole": holes, "status": ["Pending"] * len(holes)})
    for column in config["score_columns"]:
        frame[column] = pd.Series([pd.NA] * len(holes), dtype="Int64")
    return frame


def coerce_score_frame(scores: pd.DataFrame, holes: list[int], format_name: str) -> pd.DataFrame:
    config = get_format_config(format_name)
    base = pd.DataFrame({"hole": holes})
    merged = base.merge(scores, on="hole", how="left") if "hole" in scores.columns else base
    if "status" not in merged.columns:
        merged["status"] = "Pending"
    merged["status"] = merged["status"].fillna("Pending").astype(str)
    for column in config["score_columns"]:
        if column not in merged.columns:
            merged[column] = pd.NA
        merged[column] = pd.to_numeric(merged[column], errors="coerce").astype("Int64")
    ordered_columns = ["hole", "status", *config["score_columns"]]
    return merged[ordered_columns]
