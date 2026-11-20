"""Plan audit: LLM mistakes are fed back and corrected; correct plans pass first time."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from llm_data_assistant.agent import build_agent, plan_question
from llm_data_assistant.store import StoredSheet

GERMANY = {"column": "Country", "value": "Germany"}


# Test plan: B3 (docs/TESTING.md)
@pytest.mark.parametrize(
    ("question", "replies", "expected_plan", "expected_calls"),
    [
        pytest.param(
            "What is the total revenue?",
            [{"operation": "sum", "column": "Revenu"}, {"operation": "sum", "column": "Revenue"}],
            {"operation": "sum", "column": "Revenue", "filter": None},
            2,
            id="misspelt-column-corrected",
        ),
        pytest.param(
            "What is the total revenue?",
            [
                {"operation": "sum", "column": "Revenue", "filter": GERMANY},
                {"operation": "sum", "column": "Revenue"},
            ],
            {"operation": "sum", "column": "Revenue", "filter": None},
            2,
            id="invented-filter-removed",
        ),
        pytest.param(
            "How many records for germany?",
            [{"operation": "count", "filter": GERMANY}],
            {"operation": "count", "filter": GERMANY},
            1,
            id="stored-spelling-accepted",
        ),
    ],
)
def test_audit_feeds_mistakes_back_to_the_model(
    sales_sheet: StoredSheet,
    scripted_model,
    question: str,
    replies: list[dict[str, Any]],
    expected_plan: dict[str, Any],
    expected_calls: int,
) -> None:
    agent = build_agent(output_retries=2)
    script = scripted_model(*replies)
    with agent.override(model=script.model):
        plan = asyncio.run(plan_question(agent, "test", sales_sheet, question))
    assert plan.model_dump() == expected_plan
    assert script.calls == expected_calls
