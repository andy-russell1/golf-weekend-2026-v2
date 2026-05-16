from __future__ import annotations

import json
from typing import Any

from domain.bonus_competitions import BONUS_COMPETITIONS_SETTING_KEY, bonus_competitions_to_json, default_bonus_competitions


TOURNAMENT_NAME = "Russell Kelly Invitational"
TEAM_ORDER = ("red", "blue")

TEAM_CONFIG: dict[str, dict[str, Any]] = {
    "red": {
        "name": "Team Kelly",
        "short_name": "Kelly",
        "color": "#a63a37",
        "soft_color": "#f3dfdd",
        "player_indices": (0, 1),
    },
    "blue": {
        "name": "Team Russell",
        "short_name": "Russell",
        "color": "#245a84",
        "soft_color": "#dbe9f3",
        "player_indices": (2, 3),
    },
}

PLAYER_DEFAULTS: tuple[dict[str, Any], ...] = (
    {"player_id": "adam", "name": "Adam", "handicap_index": 12.0, "team": "red", "display_order": 1},
    {"player_id": "vincent", "name": "Vincent", "handicap_index": 15.0, "team": "red", "display_order": 2},
    {"player_id": "alex", "name": "Alex", "handicap_index": 18.0, "team": "blue", "display_order": 3},
    {"player_id": "andy", "name": "Andy", "handicap_index": 18.0, "team": "blue", "display_order": 4},
)

SINGLES_MATCHUPS: tuple[dict[str, Any], ...] = (
    {"players": (3, 1), "label": "Andy vs Vincent", "point_value": 1.0},
    {"players": (0, 2), "label": "Adam vs Alex", "point_value": 1.0},
)
SINGLES_MATCHUPS_SETTING_KEY = "singles_matchups_json"

FIXTURES: tuple[dict[str, Any], ...] = (
    {
        "id": "rolls_monmouth",
        "sheet_id": "R1",
        "round_order": 1,
        "course": "rolls_monmouth",
        "title": "Rolls of Monmouth",
        "date_label": "23.05.26",
        "time_label": "13:20",
        "sort_key": "2026-05-23T13:20",
        "default_format": "4-Ball",
        "default_tee": "White",
        "points_available": 1.0,
        "scoring_mode": "net",
        "scramble_mode": "",
        "stableford_mode": "",
        "link": "https://www.therollsgolfclub.co.uk/",
        "par": 72,
        "length_label": "6733/6283",
    },
    {
        "id": "clyne",
        "sheet_id": "R2",
        "round_order": 2,
        "course": "clyne",
        "title": "Clyne",
        "date_label": "24.05.26",
        "time_label": "09:45",
        "sort_key": "2026-05-24T09:45",
        "default_format": "Stroke Play",
        "default_tee": "White",
        "points_available": 1.0,
        "scoring_mode": "net",
        "scramble_mode": "",
        "stableford_mode": "",
        "link": "https://www.clynegolfclub.com/",
        "par": 72,
        "length_label": "6432/5943",
    },
    {
        "id": "neath",
        "sheet_id": "R3",
        "round_order": 3,
        "course": "neath",
        "title": "Neath",
        "date_label": "24.05.26",
        "time_label": "15:56",
        "sort_key": "2026-05-24T15:56",
        "default_format": "Skins",
        "default_tee": "White",
        "points_available": 1.0,
        "scoring_mode": "net",
        "scramble_mode": "",
        "stableford_mode": "",
        "link": "https://www.neathgolfclub.co.uk/",
        "par": 72,
        "length_label": "6490/6393",
    },
    {
        "id": "st_pierre_old",
        "sheet_id": "R4",
        "round_order": 4,
        "course": "st_pierre_old",
        "title": "St Pierre (Old Course)",
        "date_label": "25.05.26",
        "time_label": "10:36",
        "sort_key": "2026-05-25T10:36",
        "default_format": "Singles",
        "default_tee": "White",
        "points_available": 2.0,
        "scoring_mode": "net",
        "scramble_mode": "",
        "stableford_mode": "",
        "link": "https://book.stpierre.marriottlifestyle.co.uk/golf",
        "par": 72,
        "length_label": "7028/6382",
    },
)

DEFAULT_ALLOWANCE_PERCENT = 100
DEFAULT_SHOW_GROSS_SECONDARY = True
DEFAULT_WORKBOOK_NAME = "Russell_Kelly_Invitational_2026_google_sheets_ready_v2"


def default_player_names() -> list[str]:
    return [player["name"] for player in PLAYER_DEFAULTS]


def default_player_ids() -> list[str]:
    return [player["player_id"] for player in PLAYER_DEFAULTS]


def default_handicap_indexes() -> list[float]:
    return [float(player["handicap_index"]) for player in PLAYER_DEFAULTS]


def default_players_sheet_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for player in PLAYER_DEFAULTS:
        team_id = str(player["team"])
        rows.append(
            {
                "player_id": player["player_id"],
                "player_name": player["name"],
                "team_id": team_id,
                "team_name": TEAM_CONFIG[team_id]["name"],
                "handicap_index": float(player["handicap_index"]),
                "display_order": int(player["display_order"]),
                "is_active": "TRUE",
            }
        )
    return rows


def default_rounds_sheet_rows() -> list[dict[str, Any]]:
    return [
        {
            "round_id": fixture["id"],
            "round_order": fixture["round_order"],
            "title": fixture["title"],
            "course": fixture["course"],
            "date_label": fixture["date_label"],
            "time_label": fixture["time_label"],
            "sort_key": fixture["sort_key"],
            "format_key": fixture["default_format"],
            "format_label": fixture["default_format"],
            "tee": fixture["default_tee"],
            "points_available": fixture["points_available"],
            "allowance_percent": DEFAULT_ALLOWANCE_PERCENT,
            "handicap_allocation": "relative" if fixture["default_format"] in {"Singles", "4-Ball"} else "full",
            "scoring_mode": fixture["scoring_mode"],
            "scramble_mode": fixture["scramble_mode"],
            "stableford_mode": fixture["stableford_mode"],
            "link": fixture["link"],
            "par": fixture["par"],
            "length_label": fixture["length_label"],
            "is_active": "TRUE",
        }
        for fixture in FIXTURES
    ]


def default_settings_sheet_rows() -> list[dict[str, Any]]:
    return [
        {"key": "selected_fixture_id", "value": FIXTURES[0]["id"]},
        {"key": "show_gross_secondary", "value": "true" if DEFAULT_SHOW_GROSS_SECONDARY else "false"},
        {"key": SINGLES_MATCHUPS_SETTING_KEY, "value": singles_matchups_to_json(default_singles_matchups())},
        {"key": BONUS_COMPETITIONS_SETTING_KEY, "value": bonus_competitions_to_json(default_bonus_competitions())},
    ]


def get_fixture(fixture_id: str) -> dict[str, Any]:
    for fixture in FIXTURES:
        if fixture["id"] == fixture_id:
            return fixture
    return FIXTURES[0]


def get_fixture_by_course(course: str) -> dict[str, Any]:
    for fixture in FIXTURES:
        if fixture["course"] == course:
            return fixture
    return FIXTURES[0]


def team_for_player(index: int) -> str:
    for team_id, team in TEAM_CONFIG.items():
        if index in team["player_indices"]:
            return team_id
    return "red"


def build_team_label(team_id: str, player_names: list[str]) -> str:
    team = TEAM_CONFIG[team_id]
    first_idx, second_idx = team["player_indices"]
    return f"{team['name']}: {player_names[first_idx]} + {player_names[second_idx]}"


def team_name(team_id: str) -> str:
    return str(TEAM_CONFIG[team_id]["name"])


def team_short_name(team_id: str) -> str:
    return str(TEAM_CONFIG[team_id]["short_name"])


def format_fixture_label(fixture: dict[str, Any]) -> str:
    return f"{fixture['title']} • {fixture['date_label']} {fixture['time_label']}"


def points_available_for_format(format_name: str) -> float:
    if format_name == "Singles":
        return sum(float(match.get("point_value", 0.0)) for match in SINGLES_MATCHUPS)
    return 1.0


def default_singles_matchups() -> list[dict[str, Any]]:
    return [
        {
            "players": list(match["players"]),
            "label": str(match.get("label", "")),
            "point_value": float(match.get("point_value", 1.0)),
        }
        for match in SINGLES_MATCHUPS
    ]


def singles_matchups_to_json(matchups: list[dict[str, Any]]) -> str:
    storage_rows = [
        {
            "players": [int(match["players"][0]), int(match["players"][1])],
            "point_value": float(match.get("point_value", 1.0)),
        }
        for match in matchups
    ]
    return json.dumps(storage_rows, separators=(",", ":"))


def normalize_singles_matchups(matchups: Any, player_count: int = 4) -> list[dict[str, Any]]:
    if not isinstance(matchups, list) or len(matchups) != 2:
        return default_singles_matchups()

    normalized: list[dict[str, Any]] = []
    used_players: list[int] = []
    for match in matchups:
        if not isinstance(match, dict):
            return default_singles_matchups()
        raw_players = match.get("players", [])
        if not isinstance(raw_players, (list, tuple)) or len(raw_players) != 2:
            return default_singles_matchups()
        try:
            players = (int(raw_players[0]), int(raw_players[1]))
            point_value = float(match.get("point_value", 1.0))
        except (TypeError, ValueError):
            return default_singles_matchups()
        if any(player < 0 or player >= player_count for player in players):
            return default_singles_matchups()
        if team_for_player(players[0]) == team_for_player(players[1]):
            return default_singles_matchups()
        used_players.extend(players)
        normalized.append(
            {
                "players": players,
                "point_value": point_value,
            }
        )

    if sorted(used_players) != list(range(player_count)):
        return default_singles_matchups()
    return normalized


def singles_matchups_from_json(raw_value: str, player_count: int = 4) -> list[dict[str, Any]]:
    if not raw_value:
        return default_singles_matchups()
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return default_singles_matchups()
    return normalize_singles_matchups(payload, player_count=player_count)
