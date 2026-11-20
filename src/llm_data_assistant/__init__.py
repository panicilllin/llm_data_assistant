from __future__ import annotations


def main() -> None:
    """Entry point for `uv run llm-data-assistant`."""
    import uvicorn

    uvicorn.run("llm_data_assistant.api:create_app", factory=True, reload=True)
