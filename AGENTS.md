# Agent guidelines — Work Performance OS

Guidance for AI coding agents and contributors working in this repository.

## Project overview

Python CLI that reads a Google Sheets work log and writes a monthly Markdown report under `output/`. Optional Phase 2 AI evaluation (OpenAI or Gemini) appends an **AI Evaluation** section when `ai.enabled` is true. Phase 2.1 adds `employee_context` so the model judges hours against the employee's real role and expected cadence. Phase 2.2 uses AI to classify unmatched outputs and persist learned rules in `project_map.yaml`.

Entry point: `main.py`. Setup and usage: `docs/user_manual.md`. Development plan: `docs/roadmap.md`.

## Configuration and secrets

Keep non-secrets, string secrets, and Google credential files separate. Do not merge them.

| Location | Contents | Commit? |
|----------|----------|---------|
| `config.yaml` | App settings (sheet id, auth paths, `employee_name`, `employee_context`, seed `project_keywords`, `project_map_path`, `ai.*`) | Yes |
| `project_map.example.yaml` | Empty learned-map template | Yes |
| `project_map.yaml` | Learned keyword → project rules (AI-updated) | **Never** |
| `.env` | API keys only (`OPENAI_API_KEY`, `GEMINI_API_KEY` / `GOOGLE_API_KEY`) | **Never** |
| `credentials/*.json` | Google OAuth client secret and saved token (or service account JSON) | **Never** |

- Document required env vars in `.env.example` (empty values only).
- `config.yaml` may reference credential **paths**; never embed key material.
- Prefer `python-dotenv` loading project-root `.env` from `main.py`.

## Git and commits

### Never commit

- `.env`
- `credentials/*` (except `credentials/.gitkeep` if present)
- `project_map.yaml` (learned local map; commit `project_map.example.yaml` only)
- Generated reports under `output/` (except keepfiles)
- Virtualenvs, `__pycache__`, IDE junk

### Commit message convention (Conventional Commits)

Use [Conventional Commits](https://www.conventionalcommits.org/) 1.0.0:

```text
<type>(<optional scope>): <short summary>

[optional body]

[optional footer(s)]
```

**Rules**

- Subject line: imperative mood, ~72 characters or less, no trailing period.
- `type` is required; `scope` is optional (e.g. `ai`, `sheets`, `docs`, `config`).
- Body explains **why** when the diff is non-obvious; skip for trivial changes.
- Breaking changes: `BREAKING CHANGE:` in the footer, or `!` after type/scope.

**Types**

| Type | Use for |
|------|---------|
| `feat` | New user-facing capability |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Internal change with no behavior change |
| `chore` | Tooling, deps, ignore rules, housekeeping |
| `test` | Tests only |
| `perf` | Performance improvement |
| `ci` | CI configuration |

**Examples**

```text
feat(ai): add OpenAI and Gemini evaluation to monthly reports

fix(sheets): refresh OAuth token before spreadsheet fetch

docs: document .env API keys for AI providers

chore: add AGENTS.md with repo and commit conventions
```

## Code conventions

- Match existing style in nearby files; prefer small, focused diffs.
- Do not add unsolicited markdown docs beyond what the task needs.
- AI provider adapters live in `llm.py`; evaluation prompt/parse in `ai_eval.py`; project mapping in `project_map.py`; report rendering in `report.py`.
- Put role / expected hours in `employee_context` (`config.yaml`); the eval prompt must receive it so AI does not assume full-time norms.
- `project_keywords` is a seed only; AI-learned rules go in `project_map.yaml` via `project_map.py`. Do not grow a large hand-maintained keyword catalog.

## Running locally

```powershell
pip install -r requirements.txt
copy .env.example .env   # then fill keys if AI is enabled
python main.py 2026-06
```

See `docs/user_manual.md` for Google Cloud OAuth setup and troubleshooting.
