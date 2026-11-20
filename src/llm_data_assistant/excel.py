"""Turn an uploaded .xlsx into a StoredSheet. Only the first worksheet is read."""

from __future__ import annotations

import pandas as pd

from llm_data_assistant.store import ColumnInfo, StoredSheet

# Text columns with at most this many distinct values expose them to the LLM.
MAX_SAMPLE_VALUES = 20


def load_first_sheet(workbook_id: str, filename: str, content: bytes) -> StoredSheet:
    """Parse the first worksheet of an .xlsx file.

    TODO:
    - reject non-.xlsx filenames and empty content -> InvalidFileError
    - pd.read_excel(io.BytesIO(content), sheet_name=0); catch zipfile.BadZipFile,
      ValueError, etc. -> InvalidFileError
    - get the real sheet name (pd.ExcelFile(...).sheet_names[0])
    - reject an empty table or blank/duplicate headers ("Unnamed: n")
    - build ColumnInfo list via describe_columns
    """
    raise NotImplementedError


def describe_columns(df: pd.DataFrame) -> list[ColumnInfo]:
    """Classify each column and collect sample values.

    TODO: use pandas.api.types (is_bool_dtype before is_numeric_dtype,
    is_datetime64_any_dtype, else text).
    """
    raise NotImplementedError
