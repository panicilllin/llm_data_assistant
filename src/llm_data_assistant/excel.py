"""Turn an uploaded .xlsx into a StoredSheet. Only the first worksheet is read."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
from pandas.api import types as pt

from llm_data_assistant.errors import InvalidFileError
from llm_data_assistant.store import ColumnInfo, ColumnKind, StoredSheet

# Text columns with at most this many distinct values expose them to the LLM.
MAX_SAMPLE_VALUES = 20


def load_first_sheet(workbook_id: str, filename: str, content: bytes) -> StoredSheet:
    """Parse the first worksheet of an .xlsx file; raise InvalidFileError if it is unusable."""
    if Path(filename).suffix.lower() != ".xlsx":
        raise InvalidFileError(f"'{filename}' is not an .xlsx file.")
    if not content:
        raise InvalidFileError(f"'{filename}' is empty.")

    try:
        with pd.ExcelFile(io.BytesIO(content), engine="openpyxl") as workbook:
            sheet_name = str(workbook.sheet_names[0])
            df = pd.read_excel(workbook, sheet_name=sheet_name)
    except Exception as exc:  # any parser failure means the upload is not a readable workbook
        raise InvalidFileError(f"'{filename}' could not be read as an Excel workbook.") from exc

    # Column names are matched against the LLM's strings, so a header like 2026 must be "2026".
    df = df.rename(columns=lambda name: str(name).strip())
    if df.empty:
        raise InvalidFileError(f"The first sheet of '{filename}' has no data rows.")

    return StoredSheet(
        workbook_id=workbook_id,
        filename=filename,
        sheet_name=sheet_name,
        df=df,
        columns=_describe_columns(df),
    )


def _describe_columns(df: pd.DataFrame) -> list[ColumnInfo]:
    """Classify each column and, for low-cardinality text columns, list its values."""
    columns: list[ColumnInfo] = []
    for name, col in df.items():
        kind = _column_kind(col)
        samples = _sample_values(col) if kind == "text" else []
        columns.append(ColumnInfo(name=str(name), kind=kind, sample_values=samples))
    return columns


def _column_kind(col: pd.Series) -> ColumnKind:
    # bool first: pandas also reports bool columns as numeric.
    if pt.is_bool_dtype(col):
        return "bool"
    if pt.is_numeric_dtype(col):
        return "numeric"
    if pt.is_datetime64_any_dtype(col):
        return "datetime"
    return "text"


def _sample_values(col: pd.Series) -> list[str]:
    distinct = col.dropna().astype(str).unique()
    if len(distinct) > MAX_SAMPLE_VALUES:
        return []
    return sorted(distinct)  # sorted, so the prompt is identical across runs
