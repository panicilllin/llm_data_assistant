from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_data_assistant.api import create_app
from llm_data_assistant.config import Settings

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")


@pytest.fixture
def app() -> FastAPI:
    # A model string that can never reach a real provider; tests override the model.
    return create_app(Settings(_env_file=None, llm_model="test"))


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)
