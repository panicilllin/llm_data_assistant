"""Deterministic execution of a QueryPlan with pandas. No LLM here."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, assert_never

import pandas as pd
from pandas.api import types as pt

from llm_data_assistant.errors import InvalidOperationError
from llm_data_assistant.plan import CountQuery, ExactFilter, FilterQuery, SumQuery
from llm_data_assistant.store import ColumnInfo, StoredSheet


@dataclass(slots=True)
class ExecutionResult:
    value: Any  # int | float | list[dict] -- JSON-serialisable Python values only
    message: str  # human-readable answer built from a template, not by the LLM


def execute(plan: FilterQuery | SumQuery | CountQuery, sheet: StoredSheet) -> ExecutionResult:
    """Run one plan against the sheet.

    Raises UnknownColumnError for a column the sheet does not have, and
    InvalidOperationError when the request itself cannot be answered (e.g. summing text).
    A filter that matches nothing is a valid, empty answer, not an error.
    """
    match plan:
        case SumQuery():
            column = sheet.column(plan.column)
            if column.kind != "numeric":
                raise InvalidOperationError(
                    f"Cannot sum '{column.name}': it is a {column.kind} column, not numeric."
                )
            rows = _apply_filter(sheet, plan.filter)
            values = rows[column.name].dropna()
            # Integers sum exactly. Floats are summed as decimals via str: Decimal(0.1)
            # keeps the binary error, Decimal("0.1") is the number the user typed, so
            # 0.1 + 0.2 is exactly 0.3. float() at the end because JSON has no decimals.
            if pt.is_integer_dtype(values):
                total: int | float = int(values.sum())
            else:
                total = float(sum((Decimal(str(v)) for v in values), Decimal(0)))
            return ExecutionResult(
                value=total, message=f"Total {column.name}{_describe(plan.filter)}: {total}"
            )
        case CountQuery():
            count = len(_apply_filter(sheet, plan.filter))
            return ExecutionResult(value=count, message=f"{count} records{_describe(plan.filter)}.")
        case FilterQuery():
            rows = _apply_filter(sheet, plan.filter)
            # Round-trip through JSON so dates, NaN and numpy types become plain JSON values.
            records = json.loads(rows.to_json(orient="records", date_format="iso"))
            return ExecutionResult(
                value=records, message=f"{len(records)} records{_describe(plan.filter)}."
            )
        case _:
            assert_never(plan)


def _apply_filter(sheet: StoredSheet, flt: ExactFilter | None) -> pd.DataFrame:
    """Exact, case-sensitive match; no match is a valid answer of 0 rows."""
    if flt is None:
        return sheet.df
    column = sheet.column(flt.column)
    series = sheet.df[column.name]
    match column.kind:
        case "text":
            # As "string" so missing cells and stray numbers compare cleanly with str.
            mask = series.astype("string").eq(str(flt.value)).fillna(False).astype(bool)
        case "numeric":
            mask = series == _as_number(column, flt.value)
        case "bool" | "datetime":
            raise InvalidOperationError(
                f"Filtering on {column.kind} columns such as '{column.name}' is not supported."
            )
        case _:
            assert_never(column.kind)
    return sheet.df[mask]


def _as_number(column: ColumnInfo, value: object) -> float:
    # The LLM may send 4 or "4"; both must find the rows where the column equals 4.
    try:
        if isinstance(value, bool):
            raise ValueError
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise InvalidOperationError(
            f"Column '{column.name}' is numeric, but the filter value is {value!r}."
        ) from None


def _describe(flt: ExactFilter | None) -> str:
    return "" if flt is None else f" where {flt.column} = {flt.value!r}"
