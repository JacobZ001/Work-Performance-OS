"""AI evaluation of monthly work reports."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from analyze import MonthlyReportData
from llm import LLMClient

MAX_ACTIVITIES = 80

SYSTEM_PROMPT = """\
You are a performance review assistant for engineering managers.
Given an employee's monthly work log summary and optional employee context
(role, expected hours, constraints), evaluate whether the described work
appears consistent with the reported hours, and write a concise manager-
facing evaluation.

When employee context is provided, treat it as ground truth for expected
workload and role. Do not flag shorter days or lower weekly totals as
suspicious if they match the stated expected cadence. Judge consistency
of described work against that cadence, not against a full-time baseline.

Respond with ONLY valid JSON (no markdown fences) using this schema:
{
  "overall_summary": "string",
  "hours_vs_work": "string — match assessment and risks vs expected cadence",
  "key_contributions": ["string", ...],
  "strengths": ["string", ...],
  "improvement_areas": ["string", ...],
  "recommendations": ["string", ...]
}
Be factual, specific, and skeptical of vague outputs paired with long hours
relative to the employee's expected load. If data is thin, say so clearly.
"""


@dataclass
class AIEvaluation:
    overall_summary: str
    hours_vs_work: str
    key_contributions: list[str]
    strengths: list[str]
    improvement_areas: list[str]
    recommendations: list[str]
    provider: str = ""
    model: str = ""


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _parse_evaluation(raw: str, provider: str, model: str) -> AIEvaluation:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fall back: keep raw text in summary so the report still has content
        return AIEvaluation(
            overall_summary=text,
            hours_vs_work="(Could not parse structured JSON from model.)",
            key_contributions=[],
            strengths=[],
            improvement_areas=[],
            recommendations=[],
            provider=provider,
            model=model,
        )
    return AIEvaluation(
        overall_summary=str(data.get("overall_summary") or "").strip(),
        hours_vs_work=str(data.get("hours_vs_work") or "").strip(),
        key_contributions=_as_str_list(data.get("key_contributions")),
        strengths=_as_str_list(data.get("strengths")),
        improvement_areas=_as_str_list(data.get("improvement_areas")),
        recommendations=_as_str_list(data.get("recommendations")),
        provider=provider,
        model=model,
    )


def build_eval_prompt(
    data: MonthlyReportData,
    employee_context: str = "",
) -> str:
    stats = data.stats
    type_lines = [
        f"  - {name}: {hours}h ({stats.percent_by_type.get(name, 0)}%)"
        for name, hours in stats.hours_by_type.items()
    ]
    project_blocks: list[str] = []
    for project in data.projects:
        hours = round(project.total_minutes / 60.0, 2)
        outputs = project.outputs[:12]
        out_lines = "\n".join(f"    - {o}" for o in outputs) or "    - (none)"
        project_blocks.append(
            f"- {project.name}: {len(project.entries)} entries, {hours}h\n"
            f"{out_lines}"
        )

    activities = data.activities[:MAX_ACTIVITIES]
    activity_lines = [
        f"- {log.date.isoformat()} | {log.type or '-'} | "
        f"{log.duration_min} min | {log.output or '-'}"
        for log in activities
    ]
    truncated = ""
    if len(data.activities) > MAX_ACTIVITIES:
        truncated = (
            f"\n(Showing first {MAX_ACTIVITIES} of "
            f"{len(data.activities)} activities.)"
        )

    warning_lines = [
        f"- [{w.rule}] {w.message}"
        + (f" (row {w.row_number})" if w.row_number else "")
        for w in data.warnings[:30]
    ] or ["- (none)"]

    context = (employee_context or "").strip()
    context_block = (
        f"## Employee context\n{context}\n"
        if context
        else "## Employee context\n(none provided — do not assume full-time)\n"
    )

    return f"""\
Employee: {data.employee}
Period: {data.period}

{context_block}
## Work statistics
- Total hours: {stats.total_hours} ({stats.total_minutes} min)
- Working days: {stats.working_days}
- Avg hours/day: {stats.avg_hours_per_day}
- By type:
{chr(10).join(type_lines) or '  - (none)'}

## Projects
{chr(10).join(project_blocks) or '- (none)'}

## Activities
{chr(10).join(activity_lines) or '- (none)'}{truncated}

## Data quality warnings
{chr(10).join(warning_lines)}
"""


def run_evaluation(
    data: MonthlyReportData,
    client: LLMClient,
    provider: str,
    model: str,
    employee_context: str = "",
) -> AIEvaluation:
    user_prompt = build_eval_prompt(data, employee_context=employee_context)
    raw = client.complete(SYSTEM_PROMPT, user_prompt)
    return _parse_evaluation(raw, provider=provider, model=model)
