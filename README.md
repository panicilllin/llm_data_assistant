# LLM Data Assistant

A small FastAPI service: upload `.xlsx` files, then ask simple natural-language
questions (filter / sum / count) about the first worksheet of each.

## Run

```bash
cp .env.example .env    # set LLM_MODEL and the matching API key (exported at startup)
uv sync
uv run llm-data-assistant          # http://127.0.0.1:8000/docs
```

### With Docker

The `Dockerfile` has two targets. `test` installs dev dependencies and runs lint
and the offline tests during the build, so the build fails if a check fails.
`deploy` (the default) has runtime dependencies only and no credentials: the API
key is passed at run time.

```bash
docker build --target test -t llm-data-assistant:test .
docker build -t llm-data-assistant .
docker run --rm -p 8000:8000 --env-file .env llm-data-assistant
```

## Test

```bash
uv run pytest -q        # offline: unit + integration, the LLM is scripted
uv run pytest -m llm    # opt-in smoke test against the real LLM in .env
uv run ruff check .
```

What is tested, why, at which layer, and the acceptance gate are defined in the
**[test plan](docs/TESTING.md)**. In short:

- `tests/unit`: business rules called directly: Excel loading, exact calculations,
  the plan audit's retry loop.
- `tests/integration`: the HTTP contract through FastAPI's TestClient: status
  codes, response shape, JSON-ready results.
- `tests/smoke`: the brief's example questions against the real model.

## Design

```text
POST /chat
  workbook lookup ──(unknown id → 404, no LLM call)
  LLM: question + column metadata → QueryPlan (filter | sum | count | unsupported)
        schema + plan audit → model retries on its own mistakes
  unsupported → 200 with answerable=false
  pandas executor → result   (sum of text column etc. → 422, no retry)
```

### Why pydantic-ai

- **Validated output.** Every LLM response is checked against the `QueryPlan`
  model; when it does not fit, the error is sent back and the model retries. The
  plan audit plugs into the same loop through `output_validator`.
- **Model-agnostic client.** Switching between DeepSeek, OpenAI or Anthropic is
  one setting (`LLM_MODEL`), no code change.
- **One modelling language.** FastAPI is built on pydantic too, so API schemas
  and the LLM's output are defined the same way.
- **Testable offline.** A scripted model replaces the LLM in tests, and real
  requests are blocked globally.

### Why not MCP

I considered wrapping the pandas executor as MCP tools and letting the LLM call
them on its own. Structured output already covers the brief: the LLM returns one
typed `QueryPlan`, and the code validates and executes it. With MCP, the model
would decide which tools to call and when, which makes auditing its output and
testing the service much more complex. The gain was small and the trade-off
clear, so I kept structured output.

### Validation layers

| Layer | Checks | On failure |
| --- | --- | --- |
| Plan schema (pydantic) | operation is one of four, fields and types are valid | model retries |
| Plan audit (`output_validator`) | columns exist; filter value appears in the question (ignoring case) | model retries; if retries run out, 422 `unanswerable_question` with the reason (e.g. the missing column) |
| Executor (pandas) | sum only on numeric columns; numeric filter value is a number | 422, no retry |

Filters are exact and case-sensitive. The prompt lists each low-cardinality text
column's values, so the model picks the stored spelling ("germany" → "Germany").
If it does not, the answer is 0 rows, and the response message and echoed plan
show the exact value that was matched, so the result is never silently wrong.

## Limitations

Deliberately out of scope for a 2–4 hour assignment:

- Data stays in process memory and is lost on restart; no upload size limit.
- No table cleanup: header-less or duplicate headers are kept as pandas names
  them (`Unnamed: 3`, `A.1`), and fully empty rows are not dropped.
- Filters work on text and numeric columns only; filtering on a date or boolean
  column returns a clear "not supported" error.
- Filters are case-sensitive. A text column with more than 20 distinct values
  (e.g. an ID column) is not listed in the prompt, so the user's exact spelling
  is used.
- A filter value must appear literally in the question, so synonyms or
  translations ("Deutschland" for "Germany") are retried and then rejected.
- Filter results are returned in full, without paging or a row limit.
- One filter per question; no averages, grouping, ranking or comparisons.
