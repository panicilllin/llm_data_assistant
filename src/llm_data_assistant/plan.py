"""The structured plan the LLM must return. Nothing here touches data."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _LlmModel(BaseModel):
    # LLM-facing models reject unknown keys, so a hallucinated field triggers a retry.
    model_config = ConfigDict(extra="forbid")


class ExactFilter(_LlmModel):
    column: str = Field(description="Exact column name from the worksheet.")
    value: str | int | float | bool = Field(description="Value the column must equal.")


class FilterQuery(_LlmModel):
    operation: Literal["filter"]
    filter: ExactFilter


class SumQuery(_LlmModel):
    operation: Literal["sum"]
    column: str = Field(description="Numeric column to add up.")
    filter: ExactFilter | None = None


class CountQuery(_LlmModel):
    operation: Literal["count"]
    filter: ExactFilter | None = None


class Unsupported(_LlmModel):
    operation: Literal["unsupported"]
    reason: str = Field(description="Short explanation for the user.")


QueryPlan = Annotated[
    FilterQuery | SumQuery | CountQuery | Unsupported,
    Field(discriminator="operation"),
]
