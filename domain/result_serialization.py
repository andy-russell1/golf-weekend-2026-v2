from __future__ import annotations

from io import StringIO
from typing import Any

import pandas as pd

STORAGE_EXCLUDED_KEYS = {"export_bytes"}


def export_dataframe_bytes(frame: pd.DataFrame) -> bytes:
    buffer = StringIO()
    frame.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")


def to_serializable(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return {"__type__": "dataframe", "records": value.where(pd.notna(value), None).to_dict(orient="records")}
    if isinstance(value, pd.Series):
        return {"__type__": "series", "records": value.where(pd.notna(value), None).to_dict()}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    if isinstance(value, dict):
        return {
            key: to_serializable(item)
            for key, item in value.items()
            if str(key) not in STORAGE_EXCLUDED_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [to_serializable(item) for item in value]
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def from_serializable(value: Any) -> Any:
    if isinstance(value, dict):
        value_type = value.get("__type__")
        if value_type == "dataframe":
            return pd.DataFrame(value.get("records", []))
        if value_type == "series":
            return pd.Series(value.get("records", {}))
        return {key: from_serializable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [from_serializable(item) for item in value]
    return value


def summary_payload_for_storage(result: dict[str, Any]) -> dict[str, Any]:
    awarded = result.get("awarded_points", {"red": 0.0, "blue": 0.0})
    storage_payload = to_serializable(result)
    return {
        "format_name": result.get("format_name", ""),
        "status_text": result.get("status_text", ""),
        "winner": result.get("winner", ""),
        "is_complete": bool(result.get("is_complete", False)),
        "red_points": float(awarded.get("red", 0.0)),
        "blue_points": float(awarded.get("blue", 0.0)),
        "payload": storage_payload,
    }
