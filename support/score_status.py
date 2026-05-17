from __future__ import annotations

from typing import Iterable

import pandas as pd


BLANK_SCORE_VALUES = {None, "", "—"}


def _is_blank_score(value: object) -> bool:
    if pd.isna(value):
        return True
    return value in BLANK_SCORE_VALUES


def derive_score_status(values: Iterable[object], required_count: int | None = None) -> str:
    score_values = list(values)
    populated = [value for value in score_values if not _is_blank_score(value)]
    if not populated:
        return "Pending"
    target = required_count if required_count is not None else len(score_values)
    if len(populated) >= target:
        return "Complete"
    return "In Progress"


def with_derived_score_status(scores: pd.DataFrame, score_columns: list[str]) -> pd.DataFrame:
    derived = scores.copy()
    if "status" not in derived.columns:
        derived["status"] = "Pending"
    if not score_columns:
        derived["status"] = "Pending"
        return derived
    derived["status"] = [
        derive_score_status([row.get(column) for column in score_columns], required_count=len(score_columns))
        for _, row in derived.iterrows()
    ]
    return derived
