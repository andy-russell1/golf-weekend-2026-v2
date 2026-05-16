from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

try:
    import gspread
    import google.auth
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound
    GOOGLE_SHEETS_IMPORT_ERROR: Exception | None = None
except ModuleNotFoundError as exc:
    gspread = None
    google = None
    Request = None
    service_account = None
    Credentials = Any
    InstalledAppFlow = None
    APIError = Exception
    SpreadsheetNotFound = Exception
    WorksheetNotFound = Exception
    GOOGLE_SHEETS_IMPORT_ERROR = exc

from domain.result_serialization import to_serializable
from domain.weekend_config import (
    DEFAULT_WORKBOOK_NAME,
    default_players_sheet_rows,
    default_rounds_sheet_rows,
    default_settings_sheet_rows,
)


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

PLAYERS_HEADERS = (
    "player_id",
    "player_name",
    "team_id",
    "team_name",
    "handicap_index",
    "display_order",
    "is_active",
    "updated_at",
)
ROUNDS_HEADERS = (
    "round_id",
    "round_order",
    "title",
    "course",
    "date_label",
    "time_label",
    "sort_key",
    "format_key",
    "format_label",
    "tee",
    "points_available",
    "allowance_percent",
    "handicap_allocation",
    "scoring_mode",
    "scramble_mode",
    "stableford_mode",
    "link",
    "par",
    "length_label",
    "is_active",
    "updated_at",
)
SCORES_HEADERS = (
    "round_id",
    "hole",
    "player_id",
    "player_name",
    "entity_type",
    "gross_score",
    "stableford_points",
    "bbb_bingo",
    "bbb_bango",
    "bbb_bongo",
    "bbb_total",
    "status",
    "updated_at",
)
RESULTS_HEADERS = (
    "round_id",
    "format_key",
    "status_text",
    "winner",
    "red_points",
    "blue_points",
    "is_complete",
    "payload_json",
    "updated_at",
)
SETTINGS_HEADERS = ("key", "value", "updated_at")

REQUIRED_HEADERS: dict[str, tuple[str, ...]] = {
    "players": PLAYERS_HEADERS,
    "rounds": ROUNDS_HEADERS,
    "scores": SCORES_HEADERS,
    "results": RESULTS_HEADERS,
    "settings": SETTINGS_HEADERS,
}
VOLATILE_SHEET_CACHE_TTL_SECONDS = 5
SERVICE_ACCOUNT_REQUIRED_FIELDS = (
    "type",
    "project_id",
    "private_key_id",
    "private_key",
    "client_email",
    "client_id",
    "auth_uri",
    "token_uri",
    "auth_provider_x509_cert_url",
    "client_x509_cert_url",
)

AUTH_MODE_AUTO = "auto"
AUTH_MODE_ADC = "adc"
AUTH_MODE_SERVICE_ACCOUNT = "service_account"
AUTH_MODE_OAUTH_DESKTOP = "oauth_desktop"
AUTH_MODES = {AUTH_MODE_AUTO, AUTH_MODE_ADC, AUTH_MODE_SERVICE_ACCOUNT, AUTH_MODE_OAUTH_DESKTOP}


class GoogleSheetsError(RuntimeError):
    """Base error for local Google Sheets integration."""


class SheetsSetupError(GoogleSheetsError):
    """Configuration or local file issue."""


class SheetsAuthRequiredError(GoogleSheetsError):
    """Raised when an interactive login is required."""


class SheetsWorkbookError(GoogleSheetsError):
    """Workbook or worksheet lookup issue."""


class SheetsWriteError(GoogleSheetsError):
    """Write operation failure."""


@dataclass(frozen=True)
class GoogleSheetsConfig:
    workbook_name: str
    workbook_id: str
    auth_mode: str
    service_account_file: Path
    service_account_info_json: str
    service_account_source: str
    oauth_client_file: Path
    token_file: Path


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_bool_string(value: Any) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, str) and value.strip():
        return "TRUE" if value.strip().lower() in {"true", "1", "yes"} else "FALSE"
    return "FALSE"


def _normalize_record(headers: tuple[str, ...], row: dict[str, Any]) -> dict[str, Any]:
    normalized = {header: row.get(header, "") for header in headers}
    normalized["updated_at"] = row.get("updated_at") or _utc_timestamp()
    return normalized


def _records_to_sheet_values(headers: tuple[str, ...], rows: list[dict[str, Any]]) -> list[list[str]]:
    values = [list(headers)]
    for row in rows:
        normalized = _normalize_record(headers, row)
        values.append(["" if normalized.get(header) is None else str(normalized.get(header)) for header in headers])
    return values


def _ensure_google_dependencies() -> None:
    if GOOGLE_SHEETS_IMPORT_ERROR is not None:
        raise SheetsSetupError(
            "Google Sheets dependencies are not installed. Run `pip install -r requirements.txt` to enable workbook connectivity."
        ) from GOOGLE_SHEETS_IMPORT_ERROR


def _resolve_auth_mode(raw_mode: str, service_account_file: Path, has_service_account_info: bool) -> str:
    candidate = raw_mode.strip().lower() if raw_mode else AUTH_MODE_AUTO
    if candidate not in AUTH_MODES:
        candidate = AUTH_MODE_AUTO
    if candidate == AUTH_MODE_AUTO:
        if has_service_account_info or service_account_file.exists():
            return AUTH_MODE_SERVICE_ACCOUNT
        if os.getenv("K_SERVICE") or os.getenv("GAE_ENV") or os.getenv("GOOGLE_CLOUD_PROJECT"):
            return AUTH_MODE_SERVICE_ACCOUNT
        if os.getenv("GOLF_WEEKEND_OAUTH_CLIENT_FILE") or Path("secrets/google_oauth_client.json").exists():
            return AUTH_MODE_OAUTH_DESKTOP
        return AUTH_MODE_SERVICE_ACCOUNT
    return candidate


def _read_secret_mapping(name: str) -> dict[str, Any]:
    try:
        raw = st.secrets.get(name, {})
    except Exception:
        return {}
    if not raw:
        return {}
    try:
        return dict(raw)
    except Exception:
        return {key: raw[key] for key in raw}


def _normalize_private_key(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\\n", "\n").strip()
    if normalized and not normalized.endswith("\n"):
        return f"{normalized}\n"
    return normalized


def _normalize_service_account_secrets(raw: dict[str, Any]) -> dict[str, Any]:
    if not raw:
        return {}
    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, str):
            normalized[key] = _normalize_private_key(value) if key == "private_key" else value.strip()
        else:
            normalized[key] = value
    return normalized


def _missing_service_account_fields(payload: dict[str, Any]) -> list[str]:
    return [field for field in SERVICE_ACCOUNT_REQUIRED_FIELDS if not str(payload.get(field) or "").strip()]


def get_google_sheets_config() -> GoogleSheetsConfig:
    golf_weekend_secrets = _read_secret_mapping("golf_weekend")
    service_account_secrets = _normalize_service_account_secrets(_read_secret_mapping("gcp_service_account"))
    workbook_name = str(golf_weekend_secrets.get("workbook_name") or os.getenv("GOLF_WEEKEND_WORKBOOK_NAME", DEFAULT_WORKBOOK_NAME)).strip()
    workbook_id = str(golf_weekend_secrets.get("workbook_id") or os.getenv("GOLF_WEEKEND_WORKBOOK_ID", "")).strip()
    service_account_file = Path(os.getenv("GOLF_WEEKEND_SERVICE_ACCOUNT_FILE", "secrets/google_service_account.json"))
    oauth_client_file = Path(os.getenv("GOLF_WEEKEND_OAUTH_CLIENT_FILE", "secrets/google_oauth_client.json"))
    token_file = Path(os.getenv("GOLF_WEEKEND_TOKEN_FILE", "secrets/google_token.json"))
    service_account_info_json = json.dumps(service_account_secrets, sort_keys=True) if service_account_secrets else ""
    service_account_source = "streamlit_secrets" if service_account_info_json else "service_account_file" if service_account_file.exists() else ""
    auth_mode = _resolve_auth_mode(
        os.getenv("GOLF_WEEKEND_AUTH_MODE", AUTH_MODE_AUTO),
        service_account_file,
        has_service_account_info=bool(service_account_info_json),
    )
    return GoogleSheetsConfig(
        workbook_name=workbook_name,
        workbook_id=workbook_id,
        auth_mode=auth_mode,
        service_account_file=service_account_file,
        service_account_info_json=service_account_info_json,
        service_account_source=service_account_source,
        oauth_client_file=oauth_client_file,
        token_file=token_file,
    )


def _service_account_email(config: GoogleSheetsConfig) -> str:
    if config.service_account_info_json:
        try:
            payload = json.loads(config.service_account_info_json)
            return str(payload.get("client_email", ""))
        except Exception:
            return ""
    if not config.service_account_file.exists():
        return ""
    try:
        payload = json.loads(config.service_account_file.read_text())
    except Exception:
        return ""
    return str(payload.get("client_email", ""))


def _adc_principal_hint() -> str:
    return str(os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL") or os.getenv("SERVICE_ACCOUNT_EMAIL") or "")


def _api_error_message(exc: Exception) -> str:
    text = str(exc)
    if "Read requests per minute per user" in text or "[429]" in text:
        return "Google Sheets quota exceeded. Wait a minute and retry, or reduce repeated reloads against the workbook."
    return text


@st.cache_resource(show_spinner=False)
def _cached_client(
    workbook_name: str,
    workbook_id: str,
    auth_mode: str,
    service_account_file: str,
    service_account_info_json: str,
    oauth_client_file: str,
    token_file: str,
) -> Any:
    _ensure_google_dependencies()
    creds = _build_credentials(
        GoogleSheetsConfig(
            workbook_name=workbook_name,
            workbook_id=workbook_id,
            auth_mode=auth_mode,
            service_account_file=Path(service_account_file),
            service_account_info_json=service_account_info_json,
            service_account_source="streamlit_secrets" if service_account_info_json else "service_account_file" if Path(service_account_file).exists() else "",
            oauth_client_file=Path(oauth_client_file),
            token_file=Path(token_file),
        ),
        interactive=False,
    )
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def _cached_workbook(
    workbook_name: str,
    workbook_id: str,
    auth_mode: str,
    service_account_file: str,
    service_account_info_json: str,
    oauth_client_file: str,
    token_file: str,
) -> Any:
    client = _cached_client(workbook_name, workbook_id, auth_mode, service_account_file, service_account_info_json, oauth_client_file, token_file)
    try:
        if workbook_id:
            workbook = client.open_by_key(workbook_id)
        else:
            workbook = client.open(workbook_name)
        ensure_workbook_seeded(workbook)
        return workbook
    except SpreadsheetNotFound as exc:
        principal = _service_account_email(
            GoogleSheetsConfig(
                workbook_name=workbook_name,
                workbook_id=workbook_id,
                auth_mode=auth_mode,
                service_account_file=Path(service_account_file),
                service_account_info_json=service_account_info_json,
                service_account_source="streamlit_secrets" if service_account_info_json else "service_account_file" if Path(service_account_file).exists() else "",
                oauth_client_file=Path(oauth_client_file),
                token_file=Path(token_file),
            )
        )
        workbook_label = f"id `{workbook_id}`" if workbook_id else f"`{workbook_name}`"
        if auth_mode == AUTH_MODE_SERVICE_ACCOUNT and principal:
            raise SheetsWorkbookError(
                f"Workbook {workbook_label} was not found for service account `{principal}`. Share the Google Sheet with that email first."
            ) from exc
        if auth_mode == AUTH_MODE_ADC:
            principal_hint = _adc_principal_hint()
            if principal_hint:
                raise SheetsWorkbookError(
                    f"Workbook {workbook_label} was not found for attached credentials `{principal_hint}`. Share the Google Sheet with that service account email first."
                ) from exc
        raise SheetsWorkbookError(f"Workbook {workbook_label} was not found in Google Sheets.") from exc
    except APIError as exc:
        raise SheetsWorkbookError(_api_error_message(exc)) from exc


def _build_service_account_credentials(config: GoogleSheetsConfig) -> Any:
    if config.service_account_info_json:
        try:
            payload = json.loads(config.service_account_info_json)
        except Exception as exc:
            raise SheetsSetupError("Streamlit service-account secrets could not be parsed as JSON.") from exc
        missing_fields = _missing_service_account_fields(payload)
        if missing_fields:
            raise SheetsSetupError(
                "Streamlit service-account secrets are incomplete. Missing fields: "
                + ", ".join(f"`{field}`" for field in missing_fields)
                + "."
            )
        try:
            return service_account.Credentials.from_service_account_info(payload, scopes=SCOPES)
        except Exception as exc:
            detail = str(exc).strip()
            hint = "Check `gcp_service_account.private_key`; it must be the full Google PEM key, including the BEGIN/END lines."
            if detail:
                raise SheetsSetupError(f"Streamlit service-account secrets could not be read. {hint} Google said: {detail}") from exc
            raise SheetsSetupError(f"Streamlit service-account secrets could not be read. {hint}") from exc
    if not config.service_account_file.exists():
        raise SheetsSetupError(
            f"Service account file not found at `{config.service_account_file}`. Add the JSON key locally or switch auth mode."
        )
    try:
        return service_account.Credentials.from_service_account_file(str(config.service_account_file), scopes=SCOPES)
    except Exception as exc:
        raise SheetsSetupError(
            f"Service account file `{config.service_account_file}` could not be read."
        ) from exc


def _build_adc_credentials() -> Any:
    try:
        creds, _project_id = google.auth.default(scopes=SCOPES)
        return creds
    except Exception as exc:
        raise SheetsSetupError(
            "Application Default Credentials were not available. On Cloud Run, attach a service account to the service; locally, use a service account file or Desktop OAuth."
        ) from exc


def _build_oauth_credentials(config: GoogleSheetsConfig, interactive: bool) -> Credentials:
    creds: Credentials | None = None

    if config.token_file.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(config.token_file), SCOPES)
        except Exception as exc:
            if not interactive:
                raise SheetsSetupError(
                    f"Saved token file `{config.token_file}` could not be read. Delete it and reconnect."
                ) from exc

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            config.token_file.parent.mkdir(parents=True, exist_ok=True)
            config.token_file.write_text(creds.to_json())
            return creds
        except Exception as exc:
            if not interactive:
                raise SheetsAuthRequiredError("Google authentication needs to be refreshed. Reconnect to continue.") from exc

    if not config.oauth_client_file.exists():
        raise SheetsSetupError(
            f"OAuth client file not found at `{config.oauth_client_file}`. Add the Desktop OAuth JSON locally first."
        )

    if not interactive:
        raise SheetsAuthRequiredError("Google Sheets is not connected yet. Use Desktop OAuth in Setup / Admin to complete access.")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(config.oauth_client_file), SCOPES)
        creds = flow.run_local_server(port=0)
    except Exception as exc:
        raise SheetsAuthRequiredError("Google OAuth sign-in did not complete successfully.") from exc

    config.token_file.parent.mkdir(parents=True, exist_ok=True)
    config.token_file.write_text(creds.to_json())
    return creds


def _build_credentials(config: GoogleSheetsConfig, interactive: bool) -> Any:
    _ensure_google_dependencies()
    if config.auth_mode == AUTH_MODE_ADC:
        return _build_adc_credentials()
    if config.auth_mode == AUTH_MODE_SERVICE_ACCOUNT:
        return _build_service_account_credentials(config)
    return _build_oauth_credentials(config, interactive=interactive)


def get_credentials(interactive: bool = False) -> Any:
    config = get_google_sheets_config()
    if interactive:
        creds = _build_credentials(config, interactive=True)
        refresh_sheet_caches()
        return creds
    return _build_credentials(config, interactive=False)


def get_client(interactive: bool = False) -> Any:
    config = get_google_sheets_config()
    if interactive:
        creds = get_credentials(interactive=True)
        return gspread.authorize(creds)
    return _cached_client(
        config.workbook_name,
        config.workbook_id,
        config.auth_mode,
        str(config.service_account_file),
        config.service_account_info_json,
        str(config.oauth_client_file),
        str(config.token_file),
    )


def get_workbook(interactive: bool = False) -> Any:
    config = get_google_sheets_config()
    if interactive:
        client = get_client(interactive=True)
        try:
            workbook = client.open_by_key(config.workbook_id) if config.workbook_id else client.open(config.workbook_name)
        except SpreadsheetNotFound as exc:
            principal = _service_account_email(config)
            if config.auth_mode == AUTH_MODE_SERVICE_ACCOUNT and principal:
                raise SheetsWorkbookError(
                    f"Workbook {'id `' + config.workbook_id + '`' if config.workbook_id else '`' + config.workbook_name + '`'} was not found for service account `{principal}`. Share the Google Sheet with that email first."
                ) from exc
            if config.auth_mode == AUTH_MODE_ADC:
                principal_hint = _adc_principal_hint()
                if principal_hint:
                    raise SheetsWorkbookError(
                        f"Workbook {'id `' + config.workbook_id + '`' if config.workbook_id else '`' + config.workbook_name + '`'} was not found for attached credentials `{principal_hint}`. Share the Google Sheet with that service account email first."
                    ) from exc
            raise SheetsWorkbookError(
                f"Workbook {'id `' + config.workbook_id + '`' if config.workbook_id else '`' + config.workbook_name + '`'} was not found in Google Sheets."
            ) from exc
        except APIError as exc:
            raise SheetsWorkbookError(_api_error_message(exc)) from exc
        ensure_workbook_seeded(workbook)
        return workbook
    workbook = _cached_workbook(
        config.workbook_name,
        config.workbook_id,
        config.auth_mode,
        str(config.service_account_file),
        config.service_account_info_json,
        str(config.oauth_client_file),
        str(config.token_file),
    )
    return workbook


def _ensure_headers(worksheet: Any, required_headers: tuple[str, ...]) -> None:
    values = worksheet.get_all_values()
    if not values:
        worksheet.update("A1", [list(required_headers)])
        return
    existing_headers = values[0]
    if existing_headers[: len(required_headers)] == list(required_headers):
        return
    rows = values[1:]
    existing_index = {header: idx for idx, header in enumerate(existing_headers)}
    normalized_rows: list[list[str]] = []
    for row in rows:
        normalized_rows.append(
            [row[existing_index[header]] if header in existing_index and existing_index[header] < len(row) else "" for header in required_headers]
        )
    worksheet.clear()
    worksheet.update("A1", [list(required_headers), *normalized_rows])


def get_worksheet(name: str, interactive: bool = False) -> Any:
    workbook = get_workbook(interactive=interactive)
    try:
        worksheet = workbook.worksheet(name)
    except WorksheetNotFound as exc:
        raise SheetsWorkbookError(
            f"Worksheet `{name}` is missing from workbook `{workbook.title}`. Required tabs: players, rounds, scores, results, settings."
        ) from exc
    except APIError as exc:
        raise SheetsWorkbookError(_api_error_message(exc)) from exc
    return worksheet


def ensure_workbook_seeded(workbook: Any | None = None) -> None:
    workbook = workbook or get_workbook(interactive=False)
    try:
        for name, headers in REQUIRED_HEADERS.items():
            try:
                worksheet = workbook.worksheet(name)
            except WorksheetNotFound as exc:
                raise SheetsWorkbookError(
                    f"Worksheet `{name}` is missing from workbook `{workbook.title}`. Required tabs: players, rounds, scores, results, settings."
                ) from exc
            _ensure_headers(worksheet, headers)

        players_ws = workbook.worksheet("players")
        rounds_ws = workbook.worksheet("rounds")
        settings_ws = workbook.worksheet("settings")
        if len(players_ws.get_all_values()) <= 1:
            players_ws.update("A1", _records_to_sheet_values(PLAYERS_HEADERS, default_players_sheet_rows()))
        if len(rounds_ws.get_all_values()) <= 1:
            rounds_ws.update("A1", _records_to_sheet_values(ROUNDS_HEADERS, default_rounds_sheet_rows()))
        if len(settings_ws.get_all_values()) <= 1:
            settings_ws.update("A1", _records_to_sheet_values(SETTINGS_HEADERS, default_settings_sheet_rows()))
    except APIError as exc:
        raise SheetsWorkbookError(_api_error_message(exc)) from exc


def refresh_sheet_caches() -> None:
    _cached_client.clear()
    _cached_workbook.clear()
    load_players.clear()
    load_rounds.clear()
    _load_all_scores.clear()
    _load_all_results.clear()
    load_settings.clear()


def _sheet_version(sheet_name: str) -> str:
    headers = REQUIRED_HEADERS[sheet_name]
    updated_at_column = headers.index("updated_at") + 1
    try:
        values = get_worksheet(sheet_name).col_values(updated_at_column)[1:]
    except APIError as exc:
        raise SheetsWorkbookError(_api_error_message(exc)) from exc
    populated = [str(value) for value in values if str(value).strip()]
    latest_updated_at = max(populated) if populated else ""
    return f"{len(values)}:{latest_updated_at}"


def scores_version() -> str:
    return _sheet_version("scores")


def results_version() -> str:
    return _sheet_version("results")


def get_connection_status(interactive: bool = False) -> dict[str, Any]:
    config = get_google_sheets_config()
    principal = _service_account_email(config)
    status = {
        "ok": False,
        "state": "disconnected",
        "workbook_name": config.workbook_name,
        "workbook_id": config.workbook_id,
        "auth_mode": config.auth_mode,
        "auth_mode_label": (
            "Service account"
            if config.auth_mode == AUTH_MODE_SERVICE_ACCOUNT
            else "Desktop OAuth"
            if config.auth_mode == AUTH_MODE_OAUTH_DESKTOP
            else "Cloud ADC"
        ),
        "service_account_file": str(config.service_account_file),
        "service_account_source": config.service_account_source,
        "service_account_email": principal,
        "oauth_client_file": str(config.oauth_client_file),
        "token_file": str(config.token_file),
        "last_checked_at": _utc_timestamp(),
        "message": "Google Sheets is not connected.",
    }
    try:
        workbook = get_workbook(interactive=interactive)
    except SheetsAuthRequiredError as exc:
        status["state"] = "auth_required"
        status["message"] = str(exc)
        return status
    except GoogleSheetsError as exc:
        status["state"] = "error"
        status["message"] = str(exc)
        return status
    status["ok"] = True
    status["state"] = "connected"
    status["message"] = "Sheets connection OK"
    status["workbook_title"] = workbook.title
    if config.auth_mode == AUTH_MODE_SERVICE_ACCOUNT and principal:
        status["principal"] = principal
    if config.auth_mode == AUTH_MODE_ADC:
        status["principal"] = _adc_principal_hint()
    return status


def _load_records(sheet_name: str) -> list[dict[str, Any]]:
    try:
        worksheet = get_worksheet(sheet_name)
        return worksheet.get_all_records(default_blank="")
    except APIError as exc:
        raise SheetsWorkbookError(_api_error_message(exc)) from exc


@st.cache_data(show_spinner=False)
def load_players() -> list[dict[str, Any]]:
    rows = _load_records("players")
    return [row for row in rows if str(row.get("is_active", "TRUE")).upper() != "FALSE"]


@st.cache_data(show_spinner=False)
def load_rounds() -> list[dict[str, Any]]:
    rows = _load_records("rounds")
    active_rows = [row for row in rows if str(row.get("is_active", "TRUE")).upper() != "FALSE"]
    return sorted(active_rows, key=lambda row: int(float(row.get("round_order") or 0)))


@st.cache_data(show_spinner=False, ttl=VOLATILE_SHEET_CACHE_TTL_SECONDS)
def _load_all_scores(version: str) -> list[dict[str, Any]]:
    return _load_records("scores")


def load_scores(round_id: str | None = None, version: str | None = None) -> list[dict[str, Any]]:
    rows = _load_all_scores(version or scores_version())
    if round_id is None:
        return rows
    return [row for row in rows if str(row.get("round_id", "")) == round_id]


@st.cache_data(show_spinner=False, ttl=VOLATILE_SHEET_CACHE_TTL_SECONDS)
def _load_all_results(version: str) -> list[dict[str, Any]]:
    return _load_records("results")


def load_results(version: str | None = None) -> list[dict[str, Any]]:
    return _load_all_results(version or results_version())


@st.cache_data(show_spinner=False)
def load_settings() -> list[dict[str, Any]]:
    return _load_records("settings")


def _replace_rows(worksheet_name: str, headers: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    worksheet = get_worksheet(worksheet_name)
    try:
        worksheet.clear()
        worksheet.update("A1", _records_to_sheet_values(headers, rows))
    except Exception as exc:
        raise SheetsWriteError(f"Failed to update worksheet `{worksheet_name}`.") from exc


def _score_row_key(row: dict[str, Any]) -> tuple[str, int, str]:
    return (str(row.get("round_id", "")), int(float(row.get("hole") or 0)), str(row.get("player_id", "")))


def _normalise_score_replacement(round_id: str, hole: int, row: dict[str, object]) -> dict[str, Any]:
    return {
        **row,
        "round_id": round_id,
        "hole": hole,
        "status": row.get("status", "Pending"),
        "updated_at": _utc_timestamp(),
    }


def _upsert_score_rows(
    existing_rows: list[dict[str, Any]],
    round_id: str,
    hole: int,
    rows: list[dict[str, object]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    replacements: dict[tuple[str, int, str], dict[str, Any]] = {}
    for row in rows:
        replacement = _normalise_score_replacement(round_id, hole, row)
        replacements[_score_row_key(replacement)] = replacement
    updated_rows: list[dict[str, Any]] = []
    appended_rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int, str]] = set()

    for existing in existing_rows:
        key = _score_row_key(existing)
        if key in replacements:
            updated_rows.append({**existing, **replacements[key]})
            seen_keys.add(key)
        else:
            updated_rows.append(existing)

    for key, replacement in replacements.items():
        if key not in seen_keys:
            appended_rows.append(replacement)

    return updated_rows, appended_rows


def save_players(rows: list[dict[str, Any]]) -> None:
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        normalized = dict(row)
        normalized["is_active"] = _normalize_bool_string(row.get("is_active", "TRUE"))
        normalized_rows.append(normalized)
    _replace_rows("players", PLAYERS_HEADERS, normalized_rows)
    refresh_sheet_caches()


def save_round(round_id: str, payload: dict[str, Any]) -> None:
    rounds = load_rounds()
    normalized_payload = {key: payload.get(key, "") for key in ROUNDS_HEADERS if key != "updated_at"}
    normalized_payload["round_id"] = round_id
    normalized_payload["is_active"] = _normalize_bool_string(payload.get("is_active", "TRUE"))
    updated_rows: list[dict[str, Any]] = []
    replaced = False
    for row in rounds:
        if str(row.get("round_id")) == round_id:
            updated_rows.append({**row, **normalized_payload})
            replaced = True
        else:
            updated_rows.append(row)
    if not replaced:
        updated_rows.append(normalized_payload)
    _replace_rows("rounds", ROUNDS_HEADERS, updated_rows)
    refresh_sheet_caches()


def update_setting(key: str, value: str) -> None:
    rows = load_settings()
    updated_rows: list[dict[str, Any]] = []
    replaced = False
    for row in rows:
        if str(row.get("key")) == key:
            updated_rows.append({"key": key, "value": value})
            replaced = True
        else:
            updated_rows.append(row)
    if not replaced:
        updated_rows.append({"key": key, "value": value})
    _replace_rows("settings", SETTINGS_HEADERS, updated_rows)
    refresh_sheet_caches()


def save_hole_scores(round_id: str, hole: int, rows: list[dict[str, object]]) -> None:
    worksheet = get_worksheet("scores")
    try:
        existing_rows = worksheet.get_all_records(default_blank="")
        updated_rows, appended_rows = _upsert_score_rows(existing_rows, round_id, hole, rows)
        existing_index = {_score_row_key(row): index + 2 for index, row in enumerate(existing_rows)}
        original_by_key = {_score_row_key(row): row for row in existing_rows}

        for row in updated_rows:
            key = _score_row_key(row)
            if key not in existing_index or row == original_by_key.get(key):
                continue
            worksheet.update(
                f"A{existing_index[key]}",
                _records_to_sheet_values(SCORES_HEADERS, [row])[1:],
            )

        if appended_rows:
            worksheet.append_rows(_records_to_sheet_values(SCORES_HEADERS, appended_rows)[1:])
    except Exception as exc:
        raise SheetsWriteError("Failed to save hole scores.") from exc
    refresh_sheet_caches()


def _delete_rows_matching(worksheet_name: str, predicate: Any) -> None:
    worksheet = get_worksheet(worksheet_name)
    rows = worksheet.get_all_records(default_blank="")
    row_numbers = [index + 2 for index, row in enumerate(rows) if predicate(row)]
    for row_number in sorted(row_numbers, reverse=True):
        worksheet.delete_rows(row_number)


def clear_round_scores(round_id: str) -> None:
    try:
        _delete_rows_matching("scores", lambda row: str(row.get("round_id", "")) == round_id)
        _delete_rows_matching("results", lambda row: str(row.get("round_id", "")) == round_id)
    except Exception as exc:
        raise SheetsWriteError(f"Failed to clear round `{round_id}`.") from exc
    refresh_sheet_caches()


def save_round_result(round_id: str, result_payload: dict[str, object]) -> None:
    safe_payload = to_serializable(result_payload)
    serialized_payload = json.dumps(safe_payload)
    new_row = {
        "round_id": round_id,
        "format_key": str(safe_payload.get("format_name", "")),
        "status_text": str(safe_payload.get("status_text", "")),
        "winner": str(safe_payload.get("winner", "")),
        "red_points": safe_payload.get("red_points", 0),
        "blue_points": safe_payload.get("blue_points", 0),
        "is_complete": _normalize_bool_string(safe_payload.get("is_complete", False)),
        "payload_json": serialized_payload,
    }
    worksheet = get_worksheet("results")
    try:
        results = worksheet.get_all_records(default_blank="")
        row_number = next((index + 2 for index, row in enumerate(results) if str(row.get("round_id")) == round_id), None)
        if row_number is None:
            worksheet.append_rows(_records_to_sheet_values(RESULTS_HEADERS, [new_row])[1:])
        else:
            existing = results[row_number - 2]
            worksheet.update(
                f"A{row_number}",
                _records_to_sheet_values(RESULTS_HEADERS, [{**existing, **new_row}])[1:],
            )
    except Exception as exc:
        raise SheetsWriteError("Failed to save round result.") from exc
    refresh_sheet_caches()


def load_result_payloads(version: str | None = None) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for row in load_results(version=version):
        round_id = str(row.get("round_id", ""))
        raw_payload = row.get("payload_json")
        if not round_id or not raw_payload:
            continue
        try:
            payloads[round_id] = json.loads(str(raw_payload))
        except json.JSONDecodeError:
            continue
    return payloads


def scores_to_dataframe(round_id: str | None = None, version: str | None = None) -> pd.DataFrame:
    rows = load_scores(round_id, version=version)
    return pd.DataFrame(rows)
