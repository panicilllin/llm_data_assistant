"""Domain errors and their mapping to HTTP responses.

Code raises these; the API layer turns them into one JSON shape:
    {"error": {"code": "...", "message": "..."}}
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code: int = 400
    code: str = "bad_request"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidFileError(AppError):
    """Upload is not a readable .xlsx, or its first sheet has no usable table."""

    status_code = 400
    code = "invalid_file"


class WorkbookNotFoundError(AppError):
    status_code = 404
    code = "workbook_not_found"


class UnknownColumnError(AppError):
    status_code = 422
    code = "unknown_column"


class InvalidOperationError(AppError):
    """The question is understood but cannot be answered, e.g. summing a text column."""

    status_code = 422
    code = "invalid_operation"


class UnanswerableQuestionError(AppError):
    """The model kept producing a plan the sheet cannot support, e.g. a column it lacks."""

    status_code = 422
    code = "unanswerable_question"


class LlmUnavailableError(AppError):
    """The model could not produce a valid plan (provider error or retries exhausted)."""

    status_code = 502
    code = "llm_unavailable"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
