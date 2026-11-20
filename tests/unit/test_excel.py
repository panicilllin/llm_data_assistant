"""Excel loading: unusable uploads are rejected; the first sheet is described correctly."""

from __future__ import annotations

import pandas as pd
import pytest

from llm_data_assistant.errors import InvalidFileError
from llm_data_assistant.excel import MAX_SAMPLE_VALUES, load_first_sheet
from llm_data_assistant.store import StoredSheet


# Test plan: A3 (docs/TESTING.md)
@pytest.mark.parametrize(
    ("filename", "content_kind"),
    [
        ("sales.csv", "valid"),
        ("sales.xlsx", "empty"),
        ("sales.xlsx", "garbage"),
        ("sales.xlsx", "header_only"),
    ],
)
def test_unusable_upload_is_rejected(
    make_xlsx, sales_xlsx: bytes, filename: str, content_kind: str
) -> None:
    content = {
        "valid": sales_xlsx,
        "empty": b"",
        "garbage": b"definitely not a zip archive",
        "header_only": make_xlsx({"Sales": pd.DataFrame(columns=["Country", "Revenue"])}),
    }[content_kind]
    with pytest.raises(InvalidFileError):
        load_first_sheet("wb", filename, content)


# Test plan: A2, B2 (docs/TESTING.md)
def test_first_sheet_is_read_and_columns_are_classified(
    sales_sheet: StoredSheet, sales_df: pd.DataFrame
) -> None:
    assert sales_sheet.sheet_name == "Sales"  # the second sheet is ignored
    assert sales_sheet.column_names == list(sales_df.columns)
    assert {c.name: c.kind for c in sales_sheet.columns} == {
        "Country": "text",
        "Quantity": "numeric",
        "Revenue": "numeric",
        "Order_Date": "datetime",
        "Status": "text",
        "Active": "bool",
    }
    # Low-cardinality text columns list their values (sorted, no missing); others do not.
    assert sales_sheet.column("Country").sample_values == ["France", "Germany", "Spain"]
    assert sales_sheet.column("Status").sample_values == ["Completed", "Pending"]
    assert sales_sheet.column("Quantity").sample_values == []


# Test plan: B2 (docs/TESTING.md)
def test_text_column_with_many_values_lists_none(make_xlsx) -> None:
    ids = [f"ORD-{n}" for n in range(MAX_SAMPLE_VALUES + 1)]
    sheet = load_first_sheet("wb", "orders.xlsx", make_xlsx({"Orders": pd.DataFrame({"ID": ids})}))
    assert sheet.column("ID").sample_values == []
