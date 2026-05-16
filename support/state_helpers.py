from __future__ import annotations

from typing import Any

import pandas as pd

from support import google_sheets
from support.google_sheets import GoogleSheetsError
from domain.result_serialization import from_serializable, summary_payload_for_storage
from support.session import (
    blank_scores,
    clear_local_round_scores,
    coerce_score_frame,
    get_active_hole,
    get_local_store,
    get_selected_fixture_id,
    local_players,
    local_results,
    local_rounds,
    local_scores,
    local_settings,
    parse_bool,
    players_to_runtime,
    save_local_hole_scores,
    save_local_players,
    save_local_result,
    save_local_round,
    set_selected_fixture_id,
    update_local_setting,
    weekend_state_from_round_rows,
)
from domain.handicap import normalize_handicap_allocation
from domain.weekend_config import FIXTURES, TEAM_CONFIG, get_fixture


def persistence_snapshot(interactive: bool = False) -> dict[str, Any]:
    status = google_sheets.get_connection_status(interactive=interactive)
    if status.get("ok"):
        return {"mode": "sheets", "status": status}
    return {"mode": "session", "status": status}


def load_app_store() -> dict[str, Any]:
    snapshot = persistence_snapshot(interactive=False)
    if snapshot["mode"] == "sheets":
        try:
            players_rows = google_sheets.load_players()
            round_rows = google_sheets.load_rounds()
            settings_rows = google_sheets.load_settings()
            result_rows = google_sheets.load_result_payloads()
        except GoogleSheetsError as exc:
            snapshot = {
                "mode": "session",
                "status": {
                    **snapshot["status"],
                    "ok": False,
                    "state": "error",
                    "message": str(exc),
                },
            }
            players_rows = local_players()
            round_rows = local_rounds()
            settings_rows = local_settings()
            result_rows = local_results()
    else:
        players_rows = local_players()
        round_rows = local_rounds()
        settings_rows = local_settings()
        result_rows = local_results()

    runtime_players = players_to_runtime(players_rows)
    weekend_state = weekend_state_from_round_rows(round_rows, settings_rows)
    selected_fixture_id = weekend_state["selected_fixture_id"]
    valid_fixture_ids = {fixture["id"] for fixture in FIXTURES}
    if selected_fixture_id not in valid_fixture_ids:
        selected_fixture_id = FIXTURES[0]["id"]
        weekend_state["selected_fixture_id"] = selected_fixture_id
    if get_selected_fixture_id() not in valid_fixture_ids:
        set_selected_fixture_id(selected_fixture_id)

    return {
        "persistence": snapshot,
        "players_rows": players_rows,
        "round_rows": round_rows,
        "settings_rows": settings_rows,
        "results_rows": result_rows,
        "runtime_players": runtime_players,
        "weekend_state": weekend_state,
    }


def round_row_map(round_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("round_id", "")): row for row in round_rows}


def get_round_runtime(round_rows: list[dict[str, Any]], fixture_id: str) -> dict[str, Any]:
    fixture = get_fixture(fixture_id)
    row = round_row_map(round_rows).get(fixture_id, {})
    format_name = str(row.get("format_label") or row.get("format_key") or fixture["default_format"])
    return {
        "round_id": fixture_id,
        "round_order": int(float(row.get("round_order") or fixture.get("round_order", 0))),
        "format_name": format_name,
        "tee_label": str(row.get("tee") or fixture["default_tee"]),
        "allowance_percent": int(float(row.get("allowance_percent") or 100)),
        "handicap_allocation": normalize_handicap_allocation(
            row.get("handicap_allocation") or fixture.get("handicap_allocation", ""),
            format_name,
        ),
        "scramble_mode": str(row.get("scramble_mode") or fixture.get("scramble_mode", "")),
        "scoring_mode": str(row.get("scoring_mode") or fixture.get("scoring_mode", "standard")),
        "stableford_mode": str(row.get("stableford_mode") or fixture.get("stableford_mode", "")),
        "points_available": float(row.get("points_available") or fixture["points_available"]),
        "link": str(row.get("link") or fixture.get("link", "")),
        "par": row.get("par") or fixture.get("par"),
        "length_label": str(row.get("length_label") or fixture.get("length_label", "")),
    }


def load_round_scores(
    round_id: str,
    holes: list[int],
    format_name: str,
    snapshot: dict[str, Any] | None = None,
) -> pd.DataFrame:
    snapshot = snapshot or persistence_snapshot(interactive=False)
    if snapshot["mode"] == "sheets":
        try:
            score_rows = google_sheets.load_scores(round_id)
        except GoogleSheetsError:
            score_rows = local_scores(round_id)
    else:
        score_rows = local_scores(round_id)
    frame = _score_rows_to_round_frame(score_rows, holes=holes, format_name=format_name)
    return coerce_score_frame(frame, holes=holes, format_name=format_name)


def _score_rows_to_round_frame(rows: list[dict[str, Any]], holes: list[int], format_name: str) -> pd.DataFrame:
    if not rows:
        return blank_scores(holes, format_name)

    if format_name in {"Singles", "4-Ball", "Stroke Play", "Skins"}:
        player_lookup = {
            "adam": "player_1",
            "vincent": "player_2",
            "alex": "player_3",
            "andy": "player_4",
        }
        grouped: dict[int, dict[str, Any]] = {}
        for row in rows:
            hole = int(float(row.get("hole") or 0))
            hole_row = grouped.setdefault(hole, {"hole": hole, "status": row.get("status") or "Pending"})
            player_id = str(row.get("player_id", "")).strip()
            score_column = player_lookup.get(player_id)
            if score_column:
                hole_row[score_column] = row.get("gross_score")
        return pd.DataFrame(grouped.values())

    return blank_scores(holes, format_name)


def build_round_state(
    round_id: str,
    holes: list[int],
    format_name: str,
    runtime_players: dict[str, Any],
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    score_frame = load_round_scores(round_id, holes=holes, format_name=format_name, snapshot=snapshot)
    return {
        "player_ids": list(runtime_players["player_ids"]),
        "player_names": list(runtime_players["player_names"]),
        "handicap_indexes": list(runtime_players["handicap_indexes"]),
        "scores": score_frame,
        "active_hole": get_active_hole(round_id, holes),
        "version": 0,
    }


def save_scores_for_hole(round_runtime: dict[str, Any], hole: int, score_frame: pd.DataFrame, round_state: dict[str, Any]) -> None:
    rows = build_score_rows_for_hole(
        round_id=round_runtime["round_id"],
        hole=hole,
        format_name=round_runtime["format_name"],
        scoring_mode=round_runtime["scoring_mode"],
        score_frame=score_frame,
        round_state=round_state,
    )
    snapshot = persistence_snapshot(interactive=False)
    if snapshot["mode"] == "sheets":
        google_sheets.save_hole_scores(round_runtime["round_id"], hole, rows)
    else:
        save_local_hole_scores(round_runtime["round_id"], hole, rows)


def build_score_rows_for_hole(
    round_id: str,
    hole: int,
    format_name: str,
    scoring_mode: str,
    score_frame: pd.DataFrame,
    round_state: dict[str, Any],
) -> list[dict[str, Any]]:
    row = score_frame[score_frame["hole"] == hole].iloc[0]
    player_ids = round_state["player_ids"]
    player_names = round_state["player_names"]
    rows: list[dict[str, Any]] = []

    if format_name in {"Singles", "4-Ball", "Stroke Play", "Skins"}:
        for index, player_id in enumerate(player_ids):
            score_value = row.get(f"player_{index + 1}")
            rows.append(
                {
                    "player_id": player_id,
                    "player_name": player_names[index],
                    "entity_type": "player",
                    "gross_score": "" if pd.isna(score_value) else int(score_value),
                    "stableford_points": "",
                    "bbb_bingo": "",
                    "bbb_bango": "",
                    "bbb_bongo": "",
                    "bbb_total": "",
                    "status": row.get("status", "Pending"),
                }
            )
        return rows
    return rows


def save_result_payload(round_id: str, result: dict[str, Any]) -> None:
    payload = summary_payload_for_storage(result)
    snapshot = persistence_snapshot(interactive=False)
    if snapshot["mode"] == "sheets":
        google_sheets.save_round_result(round_id, payload)
    else:
        save_local_result(round_id, payload)


def load_saved_results(snapshot: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    snapshot = snapshot or persistence_snapshot(interactive=False)
    if snapshot["mode"] == "sheets":
        try:
            payloads = google_sheets.load_result_payloads()
        except GoogleSheetsError:
            payloads = local_results()
    else:
        payloads = local_results()
    normalized: dict[str, dict[str, Any]] = {}
    for round_id, payload in payloads.items():
        if "payload" in payload:
            normalized[round_id] = from_serializable(payload["payload"])
        else:
            normalized[round_id] = payload
    return normalized


def save_players(rows: list[dict[str, Any]]) -> None:
    snapshot = persistence_snapshot(interactive=False)
    if snapshot["mode"] == "sheets":
        google_sheets.save_players(rows)
    else:
        save_local_players(rows)


def save_round_config(round_id: str, payload: dict[str, Any]) -> None:
    snapshot = persistence_snapshot(interactive=False)
    if snapshot["mode"] == "sheets":
        google_sheets.save_round(round_id, payload)
    else:
        save_local_round(round_id, payload)


def save_setting(key: str, value: str) -> None:
    snapshot = persistence_snapshot(interactive=False)
    if snapshot["mode"] == "sheets":
        google_sheets.update_setting(key, value)
    else:
        update_local_setting(key, value)
    if key == "selected_fixture_id":
        set_selected_fixture_id(value)


def clear_round(round_id: str) -> None:
    snapshot = persistence_snapshot(interactive=False)
    if snapshot["mode"] == "sheets":
        google_sheets.clear_round_scores(round_id)
    else:
        clear_local_round_scores(round_id)


def workbook_refresh() -> None:
    try:
        google_sheets.refresh_sheet_caches()
    except GoogleSheetsError:
        pass


def selected_fixture_id_for_ui(weekend_state: dict[str, Any]) -> str:
    selected_fixture_id = get_selected_fixture_id()
    valid_fixture_ids = {fixture["id"] for fixture in FIXTURES}
    if selected_fixture_id in valid_fixture_ids:
        return selected_fixture_id
    return str(weekend_state.get("selected_fixture_id", FIXTURES[0]["id"]))
