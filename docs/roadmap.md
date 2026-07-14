# Work Performance OS — Roadmap

Version: 0.3  
Author: BlueOcean

Living development plan. Update this file when scope or phase status changes.

---

## Objective

Python tool that generates a monthly employee performance report from a Google Sheets work log, with optional AI evaluation for managers.

---

## Current product (shipped)

| Capability | Status |
|------------|--------|
| Read Google Sheets work log (OAuth / service account) | Done — Phase 1 |
| Monthly stats, project grouping, activity / submissions, warnings | Done — Phase 1 |
| Markdown report under `output/` | Done — Phase 1 |
| AI evaluation (OpenAI / Gemini) in the report | Done — Phase 2 |
| Employee context for AI (role, expected hours) | **In progress — Phase 2.1** |

CLI only. No GUI, database, auth system, Lark, or GitHub verification yet.

---

## Input (Sheet layout)

| Column | Header |
|--------|--------|
| A | _(blank Timestamp)_ |
| B | Start |
| C | End |
| D | Time(min) |
| E | Research _(work type)_ |
| F | Output |
| G | Link |

Date is derived from `Start`. Period is a required CLI arg: `YYYY-MM`.

---

## Report structure

```markdown
# Employee
# Period
# Work Statistics
# Project Summary
# Activity Log
# Submissions
# Data Quality Warnings
# AI Evaluation          # when ai.enabled
```

---

## Config & secrets

| Location | Contents |
|----------|----------|
| `config.yaml` | Sheet id, auth paths, `employee_name`, `employee_context`, keywords, `ai.*` |
| `.env` | API keys only |
| `credentials/*.json` | Google OAuth / token (never commit) |

See `AGENTS.md` and `docs/user_manual.md`.

---

## Phase status

### Phase 1 — MVP report pipeline — **Done**

Sheets → stats / projects / activities / submissions / warnings → Markdown.

### Phase 2 — AI evaluation — **Done (core)**

- Provider adapters (`llm.py`): OpenAI + Gemini
- Config: `ai.enabled` / `provider` / `model`
- Evaluation section in the Markdown report

### Phase 2.1 — Employee context for AI — **Current**

Problem: without role/cadence context, models assume full-time norms and flag normal intern hours (~4h/day, ~25h/week) as suspicious.

Plan:

- [x] `employee_context` in `config.yaml` (free-text role, expected hours, constraints)
- [x] Inject context into the AI evaluation prompt; instruct model to judge against stated cadence
- [ ] Harden / iterate after real report runs (optional structured fields later if needed)

### Phase 2.2 — AI project mapping — **Next**

Replace static `project_keywords` with AI-maintained project mapping. Keep the keyword map small until then; it is temporary scaffolding.

### Phase 3 — GitHub verification

GitHub API: commit / PR analysis against described work and reported duration.

### Phase 4 — Platform

Lark integration, dashboard / web UI, performance trends, historical reports. Thin frontend remains deferred until then.

---

## Folder structure (high level)

```
work-performance-os/
  main.py
  sheets.py
  analyze.py
  report.py
  llm.py
  ai_eval.py
  config.yaml
  requirements.txt
  AGENTS.md
  credentials/
  output/
  docs/
    user_manual.md
    roadmap.md
```

---

## Data model (summary)

**WorkLog:** date, start, end, duration_min, type, output, link  

**Monthly report data:** statistics, projects, activities, submissions, warnings, evaluation (optional)
