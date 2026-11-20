# LLM Data Assistant

A small FastAPI service: upload `.xlsx` files, then ask simple natural-language
questions (filter / sum / count) about the first worksheet of each.

## Run

```bash
cp .env.example .env    # set LLM_MODEL and the matching API key
uv sync
uv run llm-data-assistant          # http://127.0.0.1:8000/docs
```

## Test

```bash
uv run pytest -q        # offline, the LLM is scripted
uv run ruff check .
```

## Design

```text
POST /chat
  workbook lookup ──(unknown id → 404, no LLM call)
  LLM: question + column metadata → QueryPlan (filter | sum | count | unsupported)
        schema + column-existence checks → model retries on its own mistakes
  unsupported → 200 with answerable=false
  pandas executor → result   (sum of text column etc. → 422, no retry)
```

TODO: why structured output instead of tool calling / MCP; validation layers;
what the LLM sees (metadata only, never rows); error codes.

## Limitations

TODO
