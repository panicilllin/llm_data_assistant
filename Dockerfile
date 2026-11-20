# syntax=docker/dockerfile:1
#
#   docker build --target test -t llm-data-assistant:test .   # lint + offline tests
#   docker build -t llm-data-assistant .                      # deploy image (default)
#   docker run --rm -p 8000:8000 --env-file .env llm-data-assistant

FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYDANTIC_AI_NO_BANNER=1
WORKDIR /app


# Test: dev dependencies, lint and the offline suite. The build fails if a check fails.
FROM base AS test
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY . .
RUN uv sync --frozen
RUN uv run --no-sync ruff check . \
 && uv run --no-sync ruff format --check . \
 && uv run --no-sync pytest -q


# Deploy: runtime dependencies only, no tests, no credentials (pass them with --env-file).
FROM base AS deploy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev \
 && useradd --create-home app
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["uvicorn", "llm_data_assistant.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
