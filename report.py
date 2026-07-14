"""Markdown monthly report writer."""

from __future__ import annotations

from pathlib import Path

from analyze import MonthlyReportData


def render_markdown(data: MonthlyReportData) -> str:
    stats = data.stats
    lines: list[str] = [
        f"# Employee\n\n{data.employee}\n",
        f"# Period\n\n{data.period}\n",
        "# Work Statistics\n",
        f"- **Total Hours:** {stats.total_hours} ({stats.total_minutes} min)",
        f"- **Working Days:** {stats.working_days}",
        f"- **Average Hours Per Day:** {stats.avg_hours_per_day}",
        "",
        "### Type Breakdown\n",
    ]

    if stats.hours_by_type:
        lines.append("| Type | Hours | % |")
        lines.append("|------|------:|--:|")
        for type_name, hours in stats.hours_by_type.items():
            pct = stats.percent_by_type.get(type_name, 0.0)
            lines.append(f"| {type_name} | {hours} | {pct}% |")
        lines.append("")
    else:
        lines.append("_No entries for this period._\n")

    lines.append("# Project Summary\n")
    if not data.projects:
        lines.append("_No projects._\n")
    else:
        for project in data.projects:
            hours = round(project.total_minutes / 60.0, 2)
            lines.append(f"## {project.name}\n")
            lines.append(
                f"- **Entries:** {len(project.entries)} | "
                f"**Hours:** {hours} ({project.total_minutes} min)"
            )
            lines.append("- **Outputs:**")
            if project.outputs:
                for output in project.outputs:
                    lines.append(f"  - {output}")
            else:
                lines.append("  - _(none)_")
            lines.append("- **Links:**")
            if project.links:
                for link in project.links:
                    lines.append(f"  - {link}")
            else:
                lines.append("  - _(none)_")
            lines.append("")

    lines.append("# Activity Log\n")
    if not data.activities:
        lines.append("_No activities._\n")
    else:
        lines.append("| Date | Type | Time (min) | Output |")
        lines.append("|------|------|----------:|--------|")
        for log in data.activities:
            output = (log.output or "").replace("|", "\\|")
            lines.append(
                f"| {log.date.isoformat()} | {log.type or '-'} | "
                f"{log.duration_min} | {output or '-'} |"
            )
        lines.append("")

    lines.append("# Submissions\n")
    if not data.submissions:
        lines.append("_No submissions with links._\n")
    else:
        lines.append("| Date | Output | Link |")
        lines.append("|------|--------|------|")
        for log in data.submissions:
            output = (log.output or "-").replace("|", "\\|")
            link = log.link.replace("|", "\\|")
            lines.append(f"| {log.date.isoformat()} | {output} | {link} |")
        lines.append("")

    lines.append("# Data Quality Warnings\n")
    if not data.warnings:
        lines.append("_No warnings._\n")
    else:
        for w in data.warnings:
            row = f" (row {w.row_number})" if w.row_number else ""
            lines.append(f"- **[{w.rule}]** {w.message}{row}")
        lines.append("")

    if data.evaluation:
        ev = data.evaluation
        meta = ""
        if ev.provider or ev.model:
            meta = f" _(provider: {ev.provider or '-'}, model: {ev.model or '-'})_"
        lines.append(f"# AI Evaluation{meta}\n")
        lines.append("## Overall Summary\n")
        lines.append(f"{ev.overall_summary or '_None_'}\n")
        lines.append("## Hours vs Described Work\n")
        lines.append(f"{ev.hours_vs_work or '_None_'}\n")

        def _bullets(title: str, items: list[str]) -> None:
            lines.append(f"## {title}\n")
            if items:
                for item in items:
                    lines.append(f"- {item}")
            else:
                lines.append("_None_")
            lines.append("")

        _bullets("Key Contributions", ev.key_contributions)
        _bullets("Strengths", ev.strengths)
        _bullets("Improvement Areas", ev.improvement_areas)
        _bullets("Recommendations", ev.recommendations)

    return "\n".join(lines).rstrip() + "\n"


def write_report(data: MonthlyReportData, output_dir: str | Path) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    period_slug = data.period.replace("-", "_")
    path = out_dir / f"Monthly_Report_{period_slug}.md"
    path.write_text(render_markdown(data), encoding="utf-8")
    return path
