"""Deterministic execution of a QueryPlan with pandas. No LLM here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from llm_data_assistant.plan import CountQuery, FilterQuery, SumQuery
from llm_data_assistant.store import StoredSheet


@dataclass(slots=True)
class ExecutionResult:
    value: Any  # int | float | list[dict] -- must be JSON-serialisable
    message: str  # human-readable answer built from a template, not by the LLM


def execute(plan: FilterQuery | SumQuery | CountQuery, sheet: StoredSheet) -> ExecutionResult:
    """Run one plan against the sheet.

    TODO:
    - unknown column -> UnknownColumnError (defensive; the agent should catch it first)
    - sum on a non-numeric column -> InvalidOperationError
    - filter value: coerce to the column's type; for text, match case-insensitively
      and use the stored spelling; no match -> empty result, not an error
    - filter rows -> JSON-safe records (df.to_json(orient="records", date_format="iso"))
    - convert numpy scalars to int/float before returning
    """
    raise NotImplementedError
