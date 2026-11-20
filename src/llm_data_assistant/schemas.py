"""Request / response models of the HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UploadedWorkbook(BaseModel):
    filename: str
    workbook_id: str | None = None
    sheet_name: str | None = None
    columns: list[str] = Field(default_factory=list)
    error: str | None = None  # set when this file was rejected; other files still succeed


class UploadResponse(BaseModel):
    workbooks: list[UploadedWorkbook]


class ChatRequest(BaseModel):
    workbook_id: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    workbook_id: str
    filename: str
    sheet_name: str
    answerable: bool
    operation: str
    plan: dict[str, Any]  # echoed for transparency / debugging
    result: Any = None
    message: str
