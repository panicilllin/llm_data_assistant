# Test Plan

What this project tests, at which layer, and what must pass before a release.
Every test item has an ID; each test in `tests/` names the IDs it covers.

## Principles

- **Test behaviour, not code.** One behaviour gets one test, at the layer that
  implements it. Cases of the same shape are merged with `pytest.mark.parametrize`.
- **Business rules are asserted once, in unit tests.** Integration tests only
  check the HTTP contract: routes, status codes, response shape, wiring.
- **A test item must come from one of three sources:**
  - **A**: the assignment brief asks for it;
  - **B**: the modules cannot work together without it;
  - **C**: an edge case that would otherwise give a *silently wrong* answer, or
    that pins a deliberate design decision.

  Anything else is out of scope (see the end of this document).

## Layers

| Layer | Scope | LLM | Runs |
| --- | --- | --- | --- |
| `tests/unit` | Modules called directly: Excel loading, executor, plan audit | Scripted (`FunctionModel`) | Always |
| `tests/integration` | The API through FastAPI's `TestClient`: upload → store → LLM → executor | Scripted | Always |
| `tests/smoke` | The brief's example questions end to end | **Real**, from `.env` | Opt-in: `-m llm` |

Shared fixtures live in `tests/conftest.py` (sample data, `.xlsx` builder,
scripted LLM) and `tests/integration/conftest.py` (app, client, upload and chat
helpers). `tests/conftest.py` sets `ALLOW_MODEL_REQUESTS = False`, so the default
run can never reach a real LLM, even with a key in `.env`.

The sample table (`sales_df`) has four rows, so every expected value can be
checked by hand.

## Test items

### A. Required by the brief

| ID | Behaviour | Layer |
| --- | --- | --- |
| A1 | `POST /upload` accepts several `.xlsx` files and returns workbook ID, filename, worksheet name and columns for each; a bad file is reported without failing the others | integration |
| A2 | Only the first worksheet is read | unit |
| A3 | Invalid files are rejected: wrong extension, empty file, unreadable content, no data rows | unit |
| A4 | An unknown workbook ID returns 404 | integration |
| A5 | Filter, sum and count, with and without one exact-match filter, are computed correctly | unit |
| A6 | Summing a text column is an invalid operation | unit |
| A7 | A question about a column the sheet does not have gets a clear error naming the column (422) | integration |
| A8 | An unsupported question gets 200 with `answerable: false` and a reason | integration |
| A9 | The chat response carries the result, filename and worksheet name | integration |

### B. Needed for the modules to work together

| ID | Behaviour | Layer |
| --- | --- | --- |
| B1 | Results are JSON-ready: plain `int` / `float`, ISO dates, missing cells as `null` | integration |
| B2 | Columns are classified as numeric / text / datetime / bool; only text columns with at most 20 distinct values list them for the prompt | unit |
| B3 | The plan audit feeds LLM mistakes back and accepts correct plans: a misspelt column is corrected, an invented filter is removed, a stored spelling ("Germany" for "germany") passes first time | unit |
| B4 | When retries run out, an audit rejection is the user's problem (422) and unusable model output is a service problem (502) | integration |

### C. Edge cases

| ID | Behaviour | Why it matters |
| --- | --- | --- |
| C1 | A numeric filter value sent as text (`"4"`) still matches | The LLM sends either; otherwise 0 rows, silently |
| C2 | A filter with no match returns 0 / an empty list, not an error | "How many for Italy?" has the valid answer 0 |
| C3 | Filters are case-sensitive: `"germany"` does not match `"Germany"` | Pins the design decision; the prompt supplies the stored spelling |
| C4 | Float sums are exact decimal sums: 0.1 + 0.2 = 0.3, and 16 significant digits are kept | Float noise in a calculation task looks like a wrong answer |
| C5 | A non-number for a numeric column, or a filter on a date column, is an invalid operation | Clear error instead of 0 rows; date/bool filters are a documented limitation |

### S. Smoke tests (real LLM)

| ID | Behaviour |
| --- | --- |
| S1 | The five example questions from the brief are answered with the right operation and result |
| S2 | An average and a missing column are not answered; summing a text column returns 422 |

Smoke results can vary between runs. A failure means the prompt needs attention;
it is investigated, not retried until it passes.

## Out of scope

- Sheet headers & Broken file
- Exact prompt text or full message strings
- pydantic / FastAPI behaviour
- Load config
- The in-memory store
- Performance, concurrency, large files

## Acceptance gate

| Check | Command | Required |
| --- | --- | --- |
| Unit and integration tests | `uv run pytest` | Always: all pass, no network or key needed |
| Lint and format | `uv run ruff check .` and `uv run ruff format --check .` | Always: clean |
| Smoke tests | `uv run pytest -m llm` | Before submission, against the configured model |
