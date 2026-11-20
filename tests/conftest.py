"""Shared fixtures: a hand-checkable sales table, an .xlsx builder and a scripted LLM.

No test may reach a real LLM: ALLOW_MODEL_REQUESTS is off for the whole session,
and only the opt-in smoke tests (tests/smoke, `-m llm`) switch it back on.
"""

from __future__ import annotations

import io
import os
from collections.abc import Callable
from typing import Any

import pandas as pd
import pytest
from pydantic_ai import models
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from llm_data_assistant.excel import load_first_sheet
from llm_data_assistant.store import StoredSheet

models.ALLOW_MODEL_REQUESTS = False
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

_OUTPUT_TOOL_SUFFIX = {
    "filter": "FilterQuery",
    "sum": "SumQuery",
    "count": "CountQuery",
    "unsupported": "Unsupported",
}


@pytest.fixture
def make_xlsx() -> Callable[[dict[str, pd.DataFrame]], bytes]:
    """Build an .xlsx in memory; dict order is sheet order."""

    def build(sheets: dict[str, pd.DataFrame]) -> bytes:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name, index=False)
        return buffer.getvalue()

    return build


@pytest.fixture
def sales_df() -> pd.DataFrame:
    """Small enough to check every expected value by hand.

    Germany rows: Revenue 0.1 + 0.2 (exactly 0.3 only with fsum), Status of the
    second one is missing. Quantity is an int column, Order_Date a date column.
    """
    return pd.DataFrame(
        {
            "Country": ["Germany", "France", "Germany", "Spain"],
            "Quantity": [4, 2, 1, 3],
            "Revenue": [0.1, 5.0, 0.2, None],
            "Order_Date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]),
            "Status": ["Completed", "Pending", None, "Completed"],
            "Active": [True, False, True, True],
        }
    )


@pytest.fixture
def sales_xlsx(make_xlsx: Callable[..., bytes], sales_df: pd.DataFrame) -> bytes:
    """The sales table as the first sheet, followed by a sheet that must be ignored."""
    return make_xlsx({"Sales": sales_df, "Ignored": pd.DataFrame({"Target": [1]})})


@pytest.fixture
def sales_sheet(sales_xlsx: bytes) -> StoredSheet:
    """Parsed through the real loader, so dtypes match what the service sees."""
    return load_first_sheet("wb-sales", "sales.xlsx", sales_xlsx)


class ScriptedModel:
    """A fake LLM that answers each request with the next reply.

    A reply is a plan dict (sent as the matching output-tool call) or a str (plain
    text, which the agent rejects). The last reply repeats once the script runs out,
    so one bad reply is enough to exhaust the retries.
    """

    def __init__(self, *replies: dict[str, Any] | str) -> None:
        self.calls = 0
        self._replies = list(replies)
        self.model = FunctionModel(self._respond)

    def _respond(self, _: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        reply = self._replies[min(self.calls, len(self._replies) - 1)]
        self.calls += 1
        if isinstance(reply, str):
            return ModelResponse(parts=[TextPart(reply)])
        suffix = _OUTPUT_TOOL_SUFFIX[reply["operation"]]
        tool = next(t for t in info.output_tools if t.name.endswith(suffix))
        return ModelResponse(parts=[ToolCallPart(tool_name=tool.name, args=reply)])


@pytest.fixture
def scripted_model() -> type[ScriptedModel]:
    """Factory: scripted_model(*replies) -> ScriptedModel with .model and .calls."""
    return ScriptedModel
