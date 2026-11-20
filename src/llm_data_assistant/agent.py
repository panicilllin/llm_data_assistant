"""LLM step: question + sheet metadata -> QueryPlan. The LLM never sees rows or computes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import NoReturn

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import AgentRunError, UnexpectedModelBehavior

from llm_data_assistant.errors import LlmUnavailableError, UnanswerableQuestionError
from llm_data_assistant.plan import ExactFilter, QueryPlan, SumQuery, Unsupported
from llm_data_assistant.store import StoredSheet

SYSTEM_PROMPT = """\
You translate a question about one spreadsheet table into a query plan.
Supported operations: filter (records equal to one value), sum (total of one
numeric column, optionally with one exact filter), count (number of records,
optionally with one exact filter).
Use only column names listed below, spelled exactly. Do not compute anything.
Only add a filter for a value the user actually wrote. When the column lists its
values, copy the value's exact spelling from that list.
If the question refers to a column that is not listed, return operation
"unsupported" and name the missing column in the reason. Never substitute a
different column.
Do not judge whether an operation suits a column's type (for example summing a
text column): return the plan the user asked for; the application checks types.
If the question needs anything else (averages, ranking, several filters,
comparisons, other sheets), return operation "unsupported" with a short reason.
"""


@dataclass(slots=True)
class PlanDeps:
    sheet: StoredSheet
    question: str
    # Why the validator last rejected a plan; reported to the user if retries run out.
    last_rejection: str | None = None


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
        sheet = ctx.deps.sheet
        lines = [f"Worksheet '{sheet.sheet_name}' has these columns:"]
        for column in sheet.columns:
            line = f"- {column.name} ({column.kind})"
            if column.sample_values:
                line += f", values: {json.dumps(column.sample_values, ensure_ascii=False)}"
            lines.append(line)
        return "\n".join(lines)

    @agent.output_validator
    def _audit_plan(ctx: RunContext[PlanDeps], plan: QueryPlan) -> QueryPlan:
        """Catch LLM mistakes and make the model retry; user mistakes pass through.

        "Sum of a text column" is the user's request, not an LLM mistake, so it is
        left to the executor, which answers it with InvalidOperationError.
        """
        if isinstance(plan, Unsupported):
            return plan
        sheet = ctx.deps.sheet

        referenced = [plan.column] if isinstance(plan, SumQuery) else []
        if plan.filter is not None:
            referenced.append(plan.filter.column)
        for name in referenced:
            if name not in sheet.column_names:
                _reject(
                    ctx.deps,
                    f"Column {name!r} does not exist. Use one of: {', '.join(sheet.column_names)}.",
                )

        if plan.filter is not None and not _is_grounded(plan.filter, ctx.deps.question):
            _reject(
                ctx.deps,
                f"Filter value {plan.filter.value!r} does not appear in the question. Only "
                "filter on a value the user wrote; if the question has no filter, leave it out.",
            )
        return plan

    return agent


def _reject(deps: PlanDeps, reason: str) -> NoReturn:
    deps.last_rejection = reason
    raise ModelRetry(reason)


def _is_grounded(flt: ExactFilter, question: str) -> bool:
    """The filter value must come from the question, not be invented by the model.

    Compared ignoring case on purpose: when the user writes "germany" and the model
    copies "Germany" from the listed column values, the model did the right thing.
    The executor itself matches exactly and case-sensitively.
    """
    if isinstance(flt.value, bool):
        return True  # the executor rejects bool filters anyway
    return _as_text(flt.value).casefold() in question.casefold()


def _as_text(value: str | int | float) -> str:
    # 4.0 from the model should be checked as "4", the way the user wrote it.
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


async def plan_question(
    agent: Agent[PlanDeps, QueryPlan], model: str, sheet: StoredSheet, question: str
) -> QueryPlan:
    deps = PlanDeps(sheet=sheet, question=question)
    try:
        result = await agent.run(question, model=model, deps=deps)
    except UnexpectedModelBehavior as exc:
        if deps.last_rejection is not None:
            # Retries ran out on our audit: the question asks for something this sheet
            # does not have (usually a missing column). That is the user's problem, so 422.
            raise UnanswerableQuestionError(
                f"The question cannot be answered from this worksheet. {deps.last_rejection}"
            ) from exc
        raise LlmUnavailableError(f"The model returned an unusable answer: {exc}") from exc
    except AgentRunError as exc:  # provider / network errors
        raise LlmUnavailableError(f"Could not reach the model: {exc}") from exc
    return result.output
