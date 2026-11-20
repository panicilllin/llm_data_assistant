"""FastAPI app: wiring and HTTP only. Logic lives in excel / agent / executor."""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, File, Request, UploadFile

from llm_data_assistant.agent import build_agent, plan_question
from llm_data_assistant.config import Settings, get_settings
from llm_data_assistant.errors import AppError, register_error_handlers
from llm_data_assistant.excel import load_first_sheet
from llm_data_assistant.executor import execute
from llm_data_assistant.plan import Unsupported
from llm_data_assistant.schemas import ChatRequest, ChatResponse, UploadedWorkbook, UploadResponse
from llm_data_assistant.store import WorkbookStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="LLM Data Assistant")
    app.state.settings = settings
    app.state.store = WorkbookStore()
    app.state.agent = build_agent(settings.llm_output_retries)
    register_error_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/upload")
    async def upload(
        request: Request, files: Annotated[list[UploadFile], File()]
    ) -> UploadResponse:
        store: WorkbookStore = request.app.state.store
        results: list[UploadedWorkbook] = []
        for upload_file in files:
            filename = upload_file.filename or "unnamed.xlsx"
            # TODO: enforce settings.max_upload_bytes
            content = await upload_file.read()
            try:
                sheet = load_first_sheet(store.new_id(), filename, content)
            except AppError as exc:
                results.append(UploadedWorkbook(filename=filename, error=exc.message))
                continue
            store.add(sheet)
            results.append(
                UploadedWorkbook(
                    filename=filename,
                    workbook_id=sheet.workbook_id,
                    sheet_name=sheet.sheet_name,
                    columns=sheet.column_names,
                )
            )
        return UploadResponse(workbooks=results)

    @app.post("/chat")
    async def chat(request: Request, body: ChatRequest) -> ChatResponse:
        state = request.app.state
        sheet = state.store.get(body.workbook_id)  # 404 before spending an LLM call
        plan = await plan_question(state.agent, state.settings.llm_model, sheet, body.question)
        base = {
            "workbook_id": sheet.workbook_id,
            "filename": sheet.filename,
            "sheet_name": sheet.sheet_name,
            "operation": plan.operation,
            "plan": plan.model_dump(),
        }
        if isinstance(plan, Unsupported):
            return ChatResponse(**base, answerable=False, message=plan.reason)
        result = execute(plan, sheet)
        return ChatResponse(**base, answerable=True, result=result.value, message=result.message)

    return app
