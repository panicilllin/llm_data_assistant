"""In-memory workbook store: the DataFrame plus the metadata the LLM is allowed to see."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from llm_data_assistant.errors import WorkbookNotFoundError

ColumnKind = Literal["numeric", "text", "datetime", "bool"]


@dataclass(slots=True)
class ColumnInfo:
    name: str
    kind: ColumnKind
    # Distinct values for low-cardinality text columns, so the LLM can pick an
    # exact filter value. Empty for numeric / high-cardinality columns.
    sample_values: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StoredSheet:
    workbook_id: str
    filename: str
    sheet_name: str
    df: pd.DataFrame
    columns: list[ColumnInfo]

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


class WorkbookStore:
    """Process-local dict. Lost on restart, which the assignment allows."""

    def __init__(self) -> None:
        self._sheets: dict[str, StoredSheet] = {}

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex

    def add(self, sheet: StoredSheet) -> None:
        self._sheets[sheet.workbook_id] = sheet

    def get(self, workbook_id: str) -> StoredSheet:
        try:
            return self._sheets[workbook_id]
        except KeyError:
            raise WorkbookNotFoundError(f"No workbook with id '{workbook_id}'.") from None
