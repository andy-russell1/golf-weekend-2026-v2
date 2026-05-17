from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
    get_active_hole_source,
    get_format_config,
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
from support.round_progress import build_round_progress
from support.score_status import derive_score_status


@dataclass(frozen=True)
class ScoreVerificationResult:
    round_id: str
    holes: tuple[int, ...]
    expected_count: int
    confirmed_count: int
    verified_at: datetime | None
    duplicate_count: int = 0


def _score_row_identity(row: dict[str, Any]) -> tuple[str, int, str]:
    try:
        hole = int(float(row.get("hole") or row.get("hole_number") or 0))
    except (TypeError, ValueError):
        hole = 0
    return (
        str(row.get("round_id") or row.get("fixture_id") or "").strip(),
        hole,
        str(row.get("player_id", "")).strip().casefold(),
    )


def persistence_snapshot(interactive: bool = False) -> dict[str, Any]:
    status = google_sheets.get_connection_status(interactive=interactive)
    if status.get("ok"):
        try:
            return {
                "mode": "sheets",
                "status": status,
                "scores_version": google_sheets.scores_version(),
                "results_version": google_sheets.results_version(),
            }
        except GoogleSheetsError as exc:
            return {
                "mode": "session",
                "status": {
                    **status,
                    "ok": False,
                    "state": "error",
                    "message": str(exc),
                },
            }
    return {"mode": "session", "status": status}


def load_app_store() -> dict[str, Any]:
    snapshot = persistence_snapshot(interactive=False)
    if snapshot["mode"] == "sheets":
        try:
            players_rows = google_sheets.load_players()
            round_rows = google_sheets.load_rounds()
            settings_rows = google_sheets.load_settings()
            result_rows = google_sheets.load_result_payloads(version=str(snapshot.get("results_version", "")))
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


def load_round_score_rows(round_id: str, snapshot: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    snapshot = snapshot or persistence_snapshot(interactive=False)
    if snapshot["mode"] == "sheets":
        try:
            return google_sheets.load_scores(round_id, version=str(snapshot.get("scores_version", "")))
        except GoogleSheetsError:
            return local_scores(round_id)
    return local_scores(round_id)


def load_round_scores(
    round_id: str,
    holes: list[int],
    format_name: str,
    player_ids: list[str],
    snapshot: dict[str, Any] | None = None,
) -> pd.DataFrame:
    score_rows = load_round_score_rows(round_id, snapshot=snapshot)
    frame = _score_rows_to_round_frame(score_rows, holes=holes, format_name=format_name, player_ids=player_ids)
    return coerce_score_frame(frame, holes=holes, format_name=format_name)


def _parse_score_updated_at(value: object) -> datetime:
    if value in (None, "") or pd.isna(value):
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def duplicate_score_identities(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for index, row in enumerate(rows):
        key = _score_row_identity(row)
        if not key[0] or not key[1] or not key[2]:
            continue
        grouped.setdefault(key, []).append({"row_index": index, "row": row})
    duplicates: list[dict[str, Any]] = []
    for (round_id, hole, player_id), matches in grouped.items():
        if len(matches) <= 1:
            continue
        duplicates.append(
            {
                "round_id": round_id,
                "hole": hole,
                "player_id": player_id,
                "count": len(matches),
            }
        )
    return sorted(duplicates, key=lambda item: (str(item["round_id"]), int(item["hole"]), str(item["player_id"])))


def _latest_score_rows_by_identity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, int, str], tuple[int, datetime, dict[str, Any]]] = {}
    for index, row in enumerate(rows):
        key = _score_row_identity(row)
        round_id, hole, player_id_key = key
        player_id = str(row.get("player_id", "")).strip()
        if not round_id or not hole or not player_id_key:
            continue
        updated_at = _parse_score_updated_at(row.get("updated_at"))
        current = latest.get(key)
        if current is None or (updated_at, index) >= (current[1], current[0]):
            latest[key] = (
                index,
                updated_at,
                {
                    **row,
                    "round_id": round_id,
                    "hole": hole,
                    "player_id": player_id,
                },
            )
    return [item[2] for item in sorted(latest.values(), key=lambda item: (int(item[2]["hole"]), item[0]))]


def _status_from_loaded_scores(values: list[object], statuses: list[object], required_count: int) -> str:
    return derive_score_status(values, required_count=required_count)


def _score_rows_to_round_frame(
    rows: list[dict[str, Any]],
    holes: list[int],
    format_name: str,
    player_ids: list[str],
) -> pd.DataFrame:
    if not rows:
        return blank_scores(holes, format_name)

    config = get_format_config(format_name)
    score_columns = list(config["score_columns"])
    runtime_player_ids = [str(player_id).strip() for player_id in player_ids]
    player_lookup = {
        player_id.casefold(): score_columns[index]
        for index, player_id in enumerate(runtime_player_ids[: len(score_columns)])
        if player_id
    }
    if len(player_lookup) < len(score_columns):
        return blank_scores(holes, format_name)

    if format_name in {"Singles", "4-Ball", "Stroke Play", "Skins"}:
        grouped: dict[int, dict[str, Any]] = {}
        hole_statuses: dict[int, list[object]] = {}
        for row in _latest_score_rows_by_identity(rows):
            hole = int(row["hole"])
            player_id = str(row.get("player_id", "")).strip()
            score_column = player_lookup.get(player_id.casefold())
            if score_column:
                hole_row = grouped.setdefault(hole, {"hole": hole})
                hole_row[score_column] = row.get("gross_score")
                hole_statuses.setdefault(hole, []).append(row.get("status"))
        for hole, hole_row in grouped.items():
            for column in score_columns:
                hole_row.setdefault(column, pd.NA)
            values = [hole_row.get(column) for column in score_columns]
            hole_row["status"] = _status_from_loaded_scores(values, hole_statuses.get(hole, []), len(score_columns))
        return pd.DataFrame(grouped.values())

    return blank_scores(holes, format_name)


def build_round_state(
    round_id: str,
    holes: list[int],
    format_name: str,
    runtime_players: dict[str, Any],
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    score_rows = load_round_score_rows(round_id, snapshot=snapshot)
    frame = _score_rows_to_round_frame(
        score_rows,
        holes=holes,
        format_name=format_name,
        player_ids=list(runtime_players["player_ids"]),
    )
    score_frame = coerce_score_frame(frame, holes=holes, format_name=format_name)
    progress = build_round_progress(score_frame, holes=holes, score_rows=score_rows)
    stored_active_hole = get_active_hole(round_id, holes, default_hole=int(progress["resume_hole"]))
    active_hole = stored_active_hole if get_active_hole_source(round_id) == "manual" else int(progress["resume_hole"])
    return {
        "player_ids": list(runtime_players["player_ids"]),
        "player_names": list(runtime_players["player_names"]),
        "handicap_indexes": list(runtime_players["handicap_indexes"]),
        "scores": score_frame,
        "active_hole": active_hole,
        "progress": progress,
        "score_rows": score_rows,
        "duplicate_score_rows": duplicate_score_identities(score_rows),
        "version": 0,
    }


def save_scores_for_hole(
    round_runtime: dict[str, Any],
    hole: int,
    score_frame: pd.DataFrame,
    round_state: dict[str, Any],
    snapshot: dict[str, Any] | None = None,
    refresh: bool = True,
) -> None:
    rows = build_score_rows_for_hole(
        round_id=round_runtime["round_id"],
        hole=hole,
        format_name=round_runtime["format_name"],
        scoring_mode=round_runtime["scoring_mode"],
        score_frame=score_frame,
        round_state=round_state,
    )
    snapshot = snapshot or persistence_snapshot(interactive=False)
    if snapshot["mode"] == "sheets":
        google_sheets.save_hole_scores(round_runtime["round_id"], hole, rows, refresh=refresh)
    else:
        status = snapshot.get("status", {})
        if str(status.get("state", "")) in {"auth_required", "error"}:
            raise GoogleSheetsError(
                f"Scores were not saved because Google Sheets is unavailable: {status.get('message', 'connection failed')}"
            )
        save_local_hole_scores(round_runtime["round_id"], hole, rows)


def _normalise_score_value(value: object) -> str:
    if value in (None, "") or pd.isna(value):
        return ""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return str(value).strip()


def _normalise_status_value(value: object) -> str:
    return str(value or "").strip()


def verify_scores_for_hole(
    round_id: str,
    hole: int,
    expected_rows: list[dict[str, Any]],
    snapshot: dict[str, Any] | None = None,
    force_fresh: bool = False,
) -> ScoreVerificationResult:
    snapshot = snapshot or persistence_snapshot(interactive=False)
    if snapshot["mode"] != "sheets":
        status = snapshot.get("status", {})
        if str(status.get("state", "")) in {"auth_required", "error"}:
            raise GoogleSheetsError(
                f"Scores could not be verified because Google Sheets is unavailable: {status.get('message', 'connection failed')}"
            )
        return ScoreVerificationResult(round_id=round_id, holes=(int(hole),), expected_count=len(expected_rows), confirmed_count=len(expected_rows), verified_at=None)

    if force_fresh:
        loaded_rows = google_sheets.load_scores_fresh(round_id)
    else:
        loaded_rows = google_sheets.load_scores(round_id, version=str(snapshot.get("scores_version", "")))
    duplicate_count = len(duplicate_score_identities(loaded_rows))
    latest_rows = _latest_score_rows_by_identity(loaded_rows)
    loaded_by_player = {
        str(row.get("player_id", "")).strip().casefold(): row
        for row in latest_rows
        if int(float(row.get("hole") or 0)) == int(hole)
    }
    missing: list[str] = []
    mismatched: list[str] = []
    confirmed = 0
    verified_at_values: list[datetime] = []
    for expected in expected_rows:
        player_id = str(expected.get("player_id", "")).strip()
        loaded = loaded_by_player.get(player_id.casefold())
        if loaded is None:
            missing.append(player_id)
            continue
        expected_score = _normalise_score_value(expected.get("gross_score", ""))
        loaded_score = _normalise_score_value(loaded.get("gross_score", ""))
        expected_status = _normalise_status_value(expected.get("status", ""))
        loaded_status = _normalise_status_value(loaded.get("status", ""))
        if loaded_score != expected_score or loaded_status != expected_status:
            mismatched.append(player_id)
            continue
        confirmed += 1
        verified_at = _parse_score_updated_at(loaded.get("updated_at"))
        if verified_at != datetime.min.replace(tzinfo=timezone.utc):
            verified_at_values.append(verified_at)
    if missing or mismatched:
        expected_count = len(expected_rows)
        if confirmed < expected_count:
            raise GoogleSheetsError(
                f"Save verification failed: only {confirmed} of {expected_count} expected scores were confirmed in Google Sheets."
            )
        detail = []
        if missing:
            detail.append(f"missing rows for {', '.join(missing)}")
        if mismatched:
            detail.append(f"mismatched rows for {', '.join(mismatched)}")
        raise GoogleSheetsError(f"Save verification failed for hole {hole}: {'; '.join(detail)}.")

    return ScoreVerificationResult(
        round_id=round_id,
        holes=(int(hole),),
        expected_count=len(expected_rows),
        confirmed_count=confirmed,
        verified_at=max(verified_at_values) if verified_at_values else None,
        duplicate_count=duplicate_count,
    )


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


def save_result_payload(
    round_id: str,
    result: dict[str, Any],
    snapshot: dict[str, Any] | None = None,
    refresh: bool = True,
) -> None:
    payload = summary_payload_for_storage(result)
    snapshot = snapshot or persistence_snapshot(interactive=False)
    if snapshot["mode"] == "sheets":
        google_sheets.save_round_result(round_id, payload, refresh=refresh)
    else:
        save_local_result(round_id, payload)


def load_saved_results(snapshot: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    snapshot = snapshot or persistence_snapshot(interactive=False)
    if snapshot["mode"] == "sheets":
        try:
            payloads = google_sheets.load_result_payloads(version=str(snapshot.get("results_version", "")))
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
