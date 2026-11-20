"""Executor: filter / sum / count are computed exactly; impossible requests raise.

Expected values are worked out by hand from the `sales_df` fixture.
"""

from __future__ import annotations

import pandas as pd
import pytest

from llm_data_assistant.errors import InvalidOperationError
from llm_data_assistant.excel import load_first_sheet
from llm_data_assistant.executor import execute
from llm_data_assistant.plan import CountQuery, ExactFilter, FilterQuery, SumQuery
from llm_data_assistant.store import StoredSheet


def where(column: str, value: str | int | float) -> ExactFilter:
    return ExactFilter(column=column, value=value)


# Test plan: A5, B1, C1, C2, C3, C4 (docs/TESTING.md)
@pytest.mark.parametrize(
    ("plan", "expected"),
    [
        pytest.param(SumQuery(operation="sum", column="Revenue"), 5.3, id="sum-skips-missing"),
        pytest.param(
            SumQuery(operation="sum", column="Revenue", filter=where("Country", "Germany")),
            0.3,  # 0.1 + 0.2 without float noise
            id="sum-filtered-exact-float",
        ),
        pytest.param(SumQuery(operation="sum", column="Quantity"), 10, id="sum-int-column"),
        pytest.param(CountQuery(operation="count"), 4, id="count-all"),
        pytest.param(
            CountQuery(operation="count", filter=where("Country", "France")), 1, id="count-filtered"
        ),
        pytest.param(
            CountQuery(operation="count", filter=where("Quantity", "4")),
            1,
            id="numeric-value-sent-as-text",
        ),
        pytest.param(
            CountQuery(operation="count", filter=where("Country", "Italy")), 0, id="no-match"
        ),
        pytest.param(
            CountQuery(operation="count", filter=where("Country", "germany")),
            0,
            id="case-sensitive",
        ),
    ],
)
def test_aggregate_is_exact(
    sales_sheet: StoredSheet, plan: SumQuery | CountQuery, expected: float
) -> None:
    value = execute(plan, sales_sheet).value
    assert value == expected
    assert type(value) is type(expected)  # plain int / float, never a numpy scalar


# Test plan: C4 (docs/TESTING.md)
def test_float_sum_keeps_every_significant_digit(make_xlsx) -> None:
    # 16 significant digits: a sum rounded to Excel's 15 display digits would give ...234.6.
    df = pd.DataFrame({"Amount": [12345678901234.56, 0.01]})
    sheet = load_first_sheet("wb", "big.xlsx", make_xlsx({"Big": df}))
    assert execute(SumQuery(operation="sum", column="Amount"), sheet).value == 12345678901234.57


# Test plan: A5, C2 (docs/TESTING.md)
@pytest.mark.parametrize(
    ("value", "expected_quantities"),
    [("Germany", [4, 1]), ("Italy", [])],
)
def test_filter_returns_matching_records(
    sales_sheet: StoredSheet, value: str, expected_quantities: list[int]
) -> None:
    plan = FilterQuery(operation="filter", filter=where("Country", value))
    records = execute(plan, sales_sheet).value
    assert [r["Quantity"] for r in records] == expected_quantities
    assert all(r["Country"] == value for r in records)


# Test plan: A6, C5 (docs/TESTING.md)
@pytest.mark.parametrize(
    ("plan", "message_part"),
    [
        pytest.param(SumQuery(operation="sum", column="Country"), "not numeric", id="sum-text"),
        pytest.param(
            CountQuery(operation="count", filter=where("Quantity", "lots")),
            "numeric",
            id="non-number-for-numeric",
        ),
        pytest.param(
            CountQuery(operation="count", filter=where("Order_Date", "2026-01-01")),
            "not supported",
            id="filter-on-date",
        ),
    ],
)
def test_impossible_request_raises(
    sales_sheet: StoredSheet, plan: SumQuery | CountQuery, message_part: str
) -> None:
    with pytest.raises(InvalidOperationError, match=message_part):
        execute(plan, sales_sheet)
