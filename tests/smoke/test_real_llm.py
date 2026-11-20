"""Opt-in smoke test against the real LLM configured in .env / the environment.

Run with `uv run pytest -m llm`. Skipped when the provider key is missing.
Answers can vary between runs; a failure here means the prompt needs attention,
not necessarily that the code is wrong.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import models

from llm_data_assistant.api import create_app
from llm_data_assistant.config import get_settings

pytestmark = pytest.mark.llm

_PROVIDER_KEYS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


@pytest.fixture
def real_client(monkeypatch: pytest.MonkeyPatch, sales_xlsx: bytes) -> tuple[TestClient, str]:
    settings = get_settings()  # also exports .env into the environment
    provider = settings.llm_model.split(":", 1)[0]
    key = _PROVIDER_KEYS.get(provider)
    if key and not os.environ.get(key):
        pytest.skip(f"{key} is not set")
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", True)
    client = TestClient(create_app(settings))
    upload = client.post("/upload", files=[("files", ("sales.xlsx", sales_xlsx, "x"))])
    return client, upload.json()["workbooks"][0]["workbook_id"]


# Test plan: S1, S2 (docs/TESTING.md)
@pytest.mark.parametrize(
    ("question", "expected"),
    [
        # The five example questions from the brief, on the `sales_df` fixture.
        ("Show all records for Germany.", {"operation": "filter", "rows": 2}),
        ("What is the total revenue?", {"operation": "sum", "result": 5.3}),
        ("What is the total revenue for Germany?", {"operation": "sum", "result": 0.3}),
        ("How many records are there?", {"operation": "count", "result": 4}),
        ("How many records are there for France?", {"operation": "count", "result": 1}),
        # Must not be answered.
        ("What is the average revenue?", {"answerable": False}),
        ("What is the total salary?", {"answerable": False}),
        ("Sum the country column.", {"status": 422, "code": "invalid_operation"}),
    ],
)
def test_real_model_answers_example_questions(
    real_client: tuple[TestClient, str], question: str, expected: dict[str, Any]
) -> None:
    client, workbook_id = real_client
    response = client.post("/chat", json={"workbook_id": workbook_id, "question": question})
    body = response.json()

    if "status" in expected:
        assert response.status_code == expected["status"], body
        assert body["error"]["code"] == expected["code"]
        return
    assert response.status_code == 200, body
    if expected.get("answerable") is False:
        assert body["answerable"] is False, body
        return
    assert body["operation"] == expected["operation"], body
    if "rows" in expected:
        assert len(body["result"]) == expected["rows"], body
    else:
        assert body["result"] == expected["result"], body
