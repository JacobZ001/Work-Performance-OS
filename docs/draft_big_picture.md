# Work Performance OS (MVP)

Version: 0.2  
Author: BlueOcean

---

# Objective

Build a Python tool that automatically generates a monthly employee performance report from a Google Sheets work log.

This is the first MVP of BlueOcean Work Performance OS.

The MVP should eliminate manual monthly review work and provide managers with a structured report including:

- Work hour statistics
- Project summaries
- Activity log (what the employee said they did)
- Submissions (what the employee said they submitted)
- Data quality warnings

AI evaluation of hours vs. described work, and GitHub commit verification, are **later phases** — not part of this MVP.

---

# Scope

This MVP ONLY supports:

**Input:** Google Sheets Daily Work Log  
**Output:** Markdown Report

No GUI.  
No database.  
No authentication system.  
No Lark integration.  
No AI evaluation (Phase 2).  
No GitHub integration (Phase 3).

---

# Input

Google Sheet columns (actual work-log layout; no sheet edits required):

| Column | Header |
|--------|--------|
| A | _(blank Timestamp)_ |
| B | Start |
| C | End |
| D | Time(min) |
| E | Research _(work type / category)_ |
| F | Output |
| G | Link |

- Work **date** is derived from `Start` (no separate Date column).
- Header `Research` maps to work type (values such as Dev / Research / Meeting).

Example:

- Start: `5/31/2026 16:21:30`
- End: `5/31/2026 20:34:18`
- Time(min): `253.00`
- Research: `Dev`
- Output: `Integrated Groq AI Review Engine…`
- Link: GitHub URL

---

# Report Period

User specifies `YYYY-MM` as a required CLI argument.  
System filters all records within that month.

---

# Functional Requirements

## FR1 — Read Google Sheet

Read the sheet via a service account and produce `List[WorkLog]`.

## FR2 — Calculate Statistics

- Total Hours
- Working Days
- Average Hours Per Day
- Hours by Type (+ percentage)

## FR3 — Project Detection

**MVP (temporary):** group logs via configurable `project_keywords` in `config.yaml` (substring match on `Output`).  
Unmatched → `Uncategorized`.

**Phase 2:** AI dynamically maintains project mapping (replace / supersede static keywords). Do not invest in a large hand-maintained keyword catalog.

## FR4 — Activity & Deliverable Summary

- Activity Log: what they said they did (`Output`)
- Submissions: rows with a `Link`
- Per-project outputs and links in Project Summary

## FR5 — Data Quality Validation

Warnings for:

- Missing Link / Output / Type
- Very long session (`> max_session_minutes`, default 360)
- Repeated similar Outputs

## FR6 — Markdown Report

Write `output/Monthly_Report_YYYY_MM.md`.

---

# Report Structure

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

# Folder Structure

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
  credentials/
  output/
  docs/
    user_manual.md
    draft_big_picture.md
```

---

# Config

`config.yaml` contains:

- Google Sheet ID
- Credentials path
- Employee name
- `project_keywords` — **MVP temporary**; Phase 2.2 AI maintains project mapping dynamically
- Validation threshold (`max_session_minutes`)
- `ai.enabled` / `ai.provider` (`openai` \| `gemini`) / `ai.model`
- API keys in project-root `.env`: `OPENAI_API_KEY`, `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) — see `.env.example`

---

# Data Model

**WorkLog:** date, start, end, duration_min, type, output, link  

**Monthly report data:** statistics, projects, activities, submissions, warnings, evaluation (optional)

---

# Phase 2 — AI

**Done in this phase:**

- OpenAI + Gemini provider adapters (`llm.py`)
- Config-selected provider/model
- AI Evaluation section in the Markdown report (hours vs described work, summary, strengths, improvements)

**Phase 2.2 (next):**

- Dynamically maintain project mapping (replace static `project_keywords`)

**Deferred:** thin frontend

---

# Phase 3 — GitHub

GitHub API: commit / PR analysis against described work and reported duration.

---

# Phase 4 — Platform

Lark integration, dashboard / web UI, performance trends, historical reports.
