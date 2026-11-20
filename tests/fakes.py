"""Test doubles: a scripted LLM and small in-memory workbooks."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel


def plan_model(*plans: dict[str, Any]) -> FunctionModel:
    """A model that answers each successive request with the next plan dict.

    Several plans let a test script a retry: first an invalid plan, then a valid one.
    """
    remaining = list(plans)

    def respond(_: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        plan = remaining.pop(0) if len(remaining) > 1 else remaining[0]
        wanted = {
            "filter": "FilterQuery",
            "sum": "SumQuery",
            "count": "CountQuery",
            "unsupported": "Unsupported",
        }[plan["operation"]]
        tool = next(t for t in info.output_tools if t.name.endswith(wanted))
        return ModelResponse(parts=[ToolCallPart(tool_name=tool.name, args=plan)])

    return FunctionModel(respond)


def xlsx_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Build an .xlsx in memory; dict order = sheet order."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return buffer.getvalue()


def sales_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Country": ["Germany", "France", "Germany"],
            "Revenue": [100.0, 50.5, 25.0],
            "Status": ["Completed", "Pending", "Completed"],
        }
    )
