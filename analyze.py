"""Statistics, project grouping, and data-quality warnings."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from sheets import WorkLog

if TYPE_CHECKING:
    from ai_eval import AIEvaluation


@dataclass
class MonthlyStats:
    total_minutes: int
    working_days: int
    avg_hours_per_day: float
    hours_by_type: dict[str, float]
    percent_by_type: dict[str, float]

    @property
    def total_hours(self) -> float:
        return round(self.total_minutes / 60.0, 2)


@dataclass
class ProjectBucket:
    name: str
    entries: list[WorkLog] = field(default_factory=list)

    @property
    def total_minutes(self) -> int:
        return sum(e.duration_min for e in self.entries)

    @property
    def outputs(self) -> list[str]:
        return [e.output for e in self.entries if e.output]

    @property
    def links(self) -> list[str]:
        return [e.link for e in self.entries if e.link]


@dataclass
class WarningItem:
    rule: str
    message: str
    row_number: int | None = None


@dataclass
class MonthlyReportData:
    employee: str
    period: str
    stats: MonthlyStats
    projects: list[ProjectBucket]
    activities: list[WorkLog]
    submissions: list[WorkLog]
    warnings: list[WarningItem]
    evaluation: AIEvaluation | None = None


def compute_stats(logs: list[WorkLog]) -> MonthlyStats:
    total_minutes = sum(log.duration_min for log in logs)
    days = {log.date for log in logs}
    working_days = len(days)
    avg_hours = (
        round((total_minutes / 60.0) / working_days, 2) if working_days else 0.0
    )

    minutes_by_type: dict[str, int] = defaultdict(int)
    for log in logs:
        label = log.type or "Unknown"
        minutes_by_type[label] += log.duration_min

    hours_by_type = {
        k: round(v / 60.0, 2) for k, v in sorted(minutes_by_type.items())
    }
    percent_by_type: dict[str, float] = {}
    if total_minutes:
        percent_by_type = {
            k: round(100.0 * minutes_by_type[k] / total_minutes, 1)
            for k in hours_by_type
        }
    else:
        percent_by_type = {k: 0.0 for k in hours_by_type}

    return MonthlyStats(
        total_minutes=total_minutes,
        working_days=working_days,
        avg_hours_per_day=avg_hours,
        hours_by_type=hours_by_type,
        percent_by_type=percent_by_type,
    )


def assign_project(output: str, keyword_map: dict[str, str]) -> str:
    """MVP: static keyword map. Phase 2: AI-maintained project mapping."""
    text = (output or "").lower()
    for keyword, project in keyword_map.items():
        if keyword.lower() in text:
            return project
    return "Uncategorized"


def group_by_project(
    logs: list[WorkLog], keyword_map: dict[str, str]
) -> list[ProjectBucket]:
    buckets: dict[str, ProjectBucket] = {}
    order: list[str] = []
    for log in logs:
        name = assign_project(log.output, keyword_map)
        if name not in buckets:
            buckets[name] = ProjectBucket(name=name)
            order.append(name)
        buckets[name].entries.append(log)
    # Uncategorized last if present
    if "Uncategorized" in order:
        order = [n for n in order if n != "Uncategorized"] + ["Uncategorized"]
    return [buckets[n] for n in order]


def collect_warnings(
    logs: list[WorkLog], max_session_minutes: int = 360
) -> list[WarningItem]:
    warnings: list[WarningItem] = []
    outputs_seen: list[tuple[int, str]] = []

    for log in logs:
        if not log.output:
            warnings.append(
                WarningItem(
                    rule="missing_output",
                    message="Missing Output",
                    row_number=log.row_number,
                )
            )
        if not log.link:
            warnings.append(
                WarningItem(
                    rule="missing_link",
                    message="Missing Link",
                    row_number=log.row_number,
                )
            )
        if not log.type:
            warnings.append(
                WarningItem(
                    rule="missing_type",
                    message="Missing Type",
                    row_number=log.row_number,
                )
            )
        if log.duration_min > max_session_minutes:
            warnings.append(
                WarningItem(
                    rule="long_session",
                    message=(
                        f"Very long session ({log.duration_min} min > "
                        f"{max_session_minutes} min)"
                    ),
                    row_number=log.row_number,
                )
            )
        if log.output:
            for prev_row, prev_text in outputs_seen:
                ratio = SequenceMatcher(
                    None, log.output.lower(), prev_text.lower()
                ).ratio()
                if ratio >= 0.85:
                    warnings.append(
                        WarningItem(
                            rule="repeated_output",
                            message=(
                                f"Repeated similar Output "
                                f"(similar to row {prev_row}, similarity "
                                f"{ratio:.0%})"
                            ),
                            row_number=log.row_number,
                        )
                    )
                    break
            outputs_seen.append((log.row_number, log.output))

    return warnings


def build_report(
    logs: list[WorkLog],
    employee: str,
    period: str,
    keyword_map: dict[str, str],
    max_session_minutes: int = 360,
) -> MonthlyReportData:
    sorted_logs = sorted(logs, key=lambda x: (x.date, x.row_number))
    return MonthlyReportData(
        employee=employee,
        period=period,
        stats=compute_stats(sorted_logs),
        projects=group_by_project(sorted_logs, keyword_map),
        activities=sorted_logs,
        submissions=[log for log in sorted_logs if log.link],
        warnings=collect_warnings(sorted_logs, max_session_minutes),
    )
