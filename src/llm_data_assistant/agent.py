"""LLM step: question + sheet metadata -> QueryPlan. The LLM never sees rows or computes."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import AgentRunError

from llm_data_assistant.errors import LlmUnavailableError
from llm_data_assistant.plan import QueryPlan
from llm_data_assistant.store import StoredSheet

SYSTEM_PROMPT = """\
You translate a question about one spreadsheet table into a query plan.
Supported operations: filter (records equal to one value), sum (total of one
numeric column, optionally with one exact filter), count (number of records,
optionally with one exact filter).
Use only column names listed below, spelled exactly. Do not compute anything.
If the question needs anything else (averages, ranking, several filters,
comparisons, other sheets), return operation "unsupported" with a short reason.
"""


@dataclass(slots=True)
class PlanDeps:
    sheet: StoredSheet


def build_agent(output_retries: int) -> Agent[PlanDeps, QueryPlan]:
    # No model here: it is passed per run, so tests can override it without an API key.
    agent: Agent[PlanDeps, QueryPlan] = Agent(
        output_type=QueryPlan,  # type: ignore[arg-type]
        deps_type=PlanDeps,
        system_prompt=SYSTEM_PROMPT,
        retries=output_retries,  # also bounds output-validation retries
    )

    @agent.instructions
    def _sheet_metadata(ctx: RunContext[PlanDeps]) -> str:
        """TODO: render column names, kinds and sample values of ctx.deps.sheet."""
        return f"Columns: {ctx.deps.sheet.column_names}"

    @agent.output_validator
    def _check_against_sheet(ctx: RunContext[PlanDeps], plan: QueryPlan) -> QueryPlan:
        """Catch LLM mistakes (not user mistakes) and ask the model to retry.

        TODO:
        - every referenced column must exist in ctx.deps.sheet
          -> raise ModelRetry(f"Unknown column {name!r}. Available: {...}")
        - do NOT reject "sum of a text column" here: that is the user's request,
          the executor reports it as InvalidOperationError.
        """
        _ = ModelRetry  # remove once used
        return plan

    return agent


async def plan_question(
    agent: Agent[PlanDeps, QueryPlan], model: str, sheet: StoredSheet, question: str
) -> QueryPlan:
    try:
        result = await agent.run(question, model=model, deps=PlanDeps(sheet=sheet))
    except AgentRunError as exc:
        raise LlmUnavailableError(f"Could not interpret the question: {exc}") from exc
    return result.output
