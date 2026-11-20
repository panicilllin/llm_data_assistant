"""HTTP contract: routing, response envelopes and error mapping (LLM is scripted)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fakes import plan_model, sales_frame
from llm_data_assistant.store import ColumnInfo, StoredSheet


def _seed_sheet(app: FastAPI) -> StoredSheet:
    df = sales_frame()
    sheet = StoredSheet(
        workbook_id="wb1",
        filename="sales.xlsx",
        sheet_name="Sales",
        df=df,
        columns=[ColumnInfo(name=c, kind="text") for c in df.columns],
    )
    app.state.store.add(sheet)
    return sheet


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_unknown_workbook_is_404(client: TestClient) -> None:
    response = client.post("/chat", json={"workbook_id": "nope", "question": "How many?"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "workbook_not_found"


def test_chat_unsupported_question_is_answered_not_errored(
    app: FastAPI, client: TestClient
) -> None:
    sheet = _seed_sheet(app)
    model = plan_model({"operation": "unsupported", "reason": "Averages are not supported."})
    with app.state.agent.override(model=model):
        response = client.post(
            "/chat", json={"workbook_id": sheet.workbook_id, "question": "Average revenue?"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["answerable"] is False
    assert body["message"] == "Averages are not supported."
    assert (body["filename"], body["sheet_name"]) == (sheet.filename, sheet.sheet_name)
