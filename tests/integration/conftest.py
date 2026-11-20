"""Fixtures for tests that go through the HTTP layer with a scripted LLM."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_data_assistant.api import create_app
from llm_data_assistant.config import Settings

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def app() -> FastAPI:
    # "test" can never reach a provider; every chat test overrides the model.
    return create_app(Settings(_env_file=None, llm_model="test"))


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def workbook_id(client: TestClient, sales_xlsx: bytes) -> str:
    """The sales workbook, uploaded through the real /upload endpoint."""
    response = client.post("/upload", files=[("files", ("sales.xlsx", sales_xlsx, XLSX_MIME))])
    return response.json()["workbooks"][0]["workbook_id"]


@pytest.fixture
def ask(
    app: FastAPI, client: TestClient, scripted_model: Callable[..., Any]
) -> Callable[..., httpx.Response]:
    """Factory: POST /chat while the LLM replies with the given plans (none = no LLM)."""

    def post(workbook_id: str, question: str, *replies: dict[str, Any] | str) -> httpx.Response:
        payload = {"workbook_id": workbook_id, "question": question}
        if not replies:
            return client.post("/chat", json=payload)
        with app.state.agent.override(model=scripted_model(*replies).model):
            return client.post("/chat", json=payload)

    return post
