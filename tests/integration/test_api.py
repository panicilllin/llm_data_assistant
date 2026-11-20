"""HTTP contract: routes, status codes, response envelopes and wiring (LLM is scripted).

Business rules (what is computed, what is rejected) are tested in tests/unit.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

GERMANY = {"column": "Country", "value": "Germany"}


# Test plan: A1 (docs/TESTING.md)
def test_upload_reports_each_file_and_isolates_bad_ones(
    client: TestClient, sales_xlsx: bytes
) -> None:
    response = client.post(
        "/upload",
        files=[
            ("files", ("sales.xlsx", sales_xlsx, "application/octet-stream")),
            ("files", ("notes.txt", b"not a workbook", "text/plain")),
        ],
    )
    assert response.status_code == 200
    good, bad = response.json()["workbooks"]
    assert good["workbook_id"]
    assert (good["filename"], good["sheet_name"]) == ("sales.xlsx", "Sales")
    assert good["columns"] == ["Country", "Quantity", "Revenue", "Order_Date", "Status", "Active"]
    assert good["error"] is None
    assert bad["filename"] == "notes.txt"
    assert bad["workbook_id"] is None
    assert bad["error"]


# Test plan: A4 (docs/TESTING.md)
def test_chat_unknown_workbook_is_404(ask) -> None:
    response = ask("no-such-id", "How many records are there?")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "workbook_not_found"


# Test plan: A9, B1 (docs/TESTING.md)
@pytest.mark.parametrize(
    ("question", "plan", "expected_result"),
    [
        pytest.param(
            "What is the total quantity?",
            {"operation": "sum", "column": "Quantity"},
            10,
            id="sum",
        ),
        pytest.param(
            "Show all records for Germany.",
            {"operation": "filter", "filter": GERMANY},
            [
                {
                    "Country": "Germany",
                    "Quantity": 4,
                    "Revenue": 0.1,
                    "Order_Date": "2026-01-01T00:00:00.000",
                    "Status": "Completed",
                    "Active": True,
                },
                {
                    "Country": "Germany",
                    "Quantity": 1,
                    "Revenue": 0.2,
                    "Order_Date": "2026-01-03T00:00:00.000",
                    "Status": None,  # missing cell -> null, not NaN
                    "Active": True,
                },
            ],
            id="filter-with-dates-and-missing",
        ),
    ],
)
def test_chat_answer_carries_result_and_source(
    ask, workbook_id: str, question: str, plan: dict[str, Any], expected_result: Any
) -> None:
    response = ask(workbook_id, question, plan)
    assert response.status_code == 200
    body = response.json()
    assert body["answerable"] is True
    assert body["result"] == expected_result
    assert (body["filename"], body["sheet_name"]) == ("sales.xlsx", "Sales")


# Test plan: A8 (docs/TESTING.md)
def test_chat_unsupported_question_is_answered_not_errored(ask, workbook_id: str) -> None:
    plan = {"operation": "unsupported", "reason": "Averages are not supported."}
    response = ask(workbook_id, "What is the average revenue?", plan)
    assert response.status_code == 200
    body = response.json()
    assert body["answerable"] is False
    assert body["message"] == "Averages are not supported."


# Test plan: A7, B4 (docs/TESTING.md)
@pytest.mark.parametrize(
    ("reply", "status", "code", "message_part"),
    [
        pytest.param(
            {"operation": "sum", "column": "Salary"},
            422,
            "unanswerable_question",
            "'Salary'",
            id="audit-rejects-missing-column",
        ),
        pytest.param(
            "I think the answer is 42.",  # plain text instead of a plan
            502,
            "llm_unavailable",
            "",
            id="model-output-unusable",
        ),
    ],
)
def test_chat_exhausted_retries_separate_user_and_model_failures(
    ask, workbook_id: str, reply: dict[str, Any] | str, status: int, code: str, message_part: str
) -> None:
    response = ask(workbook_id, "What is the total salary?", reply)
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert message_part in error["message"]
