"""AI-maintained project keyword mapping (Phase 2.2)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from analyze import assign_project
from llm import LLMClient
from sheets import WorkLog

CLASSIFY_SYSTEM_PROMPT = """\
You classify employee work-log Output lines into project names.

Rules:
- Prefer existing project names when plausible.
- Create a new concise project name only when the work is clearly distinct.
- Leave truly ambiguous rows as "Uncategorized".
- Never invent work that is not in the outputs.
- Also propose short reusable keyword hints (substrings that appear in Output)
  mapping to project names for future runs.

Respond with ONLY valid JSON (no markdown fences):
{
  "assignments": [
    {"output": "exact output text from the list", "project": "Project Name"}
  ],
  "keywords": {
    "keyword_substring": "Project Name"
  }
}
"""


def load_learned_map(path: Path) -> dict[str, str]:
    """Load keyword → project rules from a YAML file."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    keywords = data.get("keywords")
    if isinstance(keywords, dict):
        source = keywords
    else:
        # Flat map is also accepted
        source = {k: v for k, v in data.items() if k != "keywords"}
    result: dict[str, str] = {}
    for key, value in source.items():
        k = str(key).strip()
        v = str(value).strip()
        if k and v:
            result[k] = v
    return result


def save_learned_map(path: Path, keyword_map: dict[str, str]) -> None:
    """Persist keyword → project rules (sorted for stable diffs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = dict(sorted(keyword_map.items(), key=lambda kv: kv[0].lower()))
    body = yaml.safe_dump(
        {"keywords": ordered},
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    header = (
        "# Learned project keyword → project map (auto-updated by AI).\n"
        "# Seed keywords still live in config.yaml; this file accumulates hints.\n"
    )
    path.write_text(header + body, encoding="utf-8")


def merge_keyword_maps(*maps: dict[str, str]) -> dict[str, str]:
    """Merge maps; later maps override earlier ones on duplicate keywords."""
    merged: dict[str, str] = {}
    for mapping in maps:
        for key, project in (mapping or {}).items():
            k = str(key).strip()
            v = str(project).strip()
            if k and v:
                merged[k] = v
    return merged


def known_project_names(keyword_map: dict[str, str]) -> list[str]:
    names = sorted({p for p in keyword_map.values() if p and p != "Uncategorized"})
    return names


def unmatched_outputs(
    logs: list[WorkLog], keyword_map: dict[str, str]
) -> list[str]:
    """Unique Output texts that still resolve to Uncategorized."""
    seen: set[str] = set()
    result: list[str] = []
    for log in logs:
        text = (log.output or "").strip()
        if not text or text in seen:
            continue
        if assign_project(text, keyword_map) == "Uncategorized":
            seen.add(text)
            result.append(text)
    return result


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_classify_response(raw: str) -> tuple[dict[str, str], dict[str, str]]:
    """Return (output→project assignments, keyword→project hints)."""
    text = _strip_fences(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}, {}

    assignments: dict[str, str] = {}
    raw_assignments = data.get("assignments") if isinstance(data, dict) else None
    if isinstance(raw_assignments, list):
        for item in raw_assignments:
            if not isinstance(item, dict):
                continue
            output = str(item.get("output") or "").strip()
            project = str(item.get("project") or "").strip()
            if output and project:
                assignments[output] = project

    keywords: dict[str, str] = {}
    raw_keywords = data.get("keywords") if isinstance(data, dict) else None
    if isinstance(raw_keywords, dict):
        for key, value in raw_keywords.items():
            k = str(key).strip()
            v = str(value).strip()
            if k and v and v != "Uncategorized":
                keywords[k] = v

    return assignments, keywords


def build_classify_prompt(
    outputs: list[str],
    known_projects: list[str],
) -> str:
    project_lines = "\n".join(f"- {name}" for name in known_projects) or "- (none yet)"
    output_lines = "\n".join(f"{i + 1}. {text}" for i, text in enumerate(outputs))
    return f"""\
## Known projects
{project_lines}

## Unmatched Output lines to classify
{output_lines}
"""


def classify_unmatched(
    client: LLMClient,
    outputs: list[str],
    known_projects: list[str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Ask the LLM to classify unmatched outputs. Returns assignments + keywords."""
    if not outputs:
        return {}, {}
    user_prompt = build_classify_prompt(outputs, known_projects)
    raw = client.complete(CLASSIFY_SYSTEM_PROMPT, user_prompt)
    return _parse_classify_response(raw)


def keywords_from_assignments(
    assignments: dict[str, str],
    existing: dict[str, str],
) -> dict[str, str]:
    """
    Derive weak keyword hints from assignments when the model omitted keywords.

    Uses distinctive tokens (length >= 5) that are unique to one project in this batch.
    """
    if not assignments:
        return {}

    # Collect candidate tokens per project from assigned outputs
    token_projects: dict[str, set[str]] = {}
    for output, project in assignments.items():
        if project == "Uncategorized":
            continue
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{4,}", output):
            key = token.lower()
            token_projects.setdefault(key, set()).add(project)

    hints: dict[str, str] = {}
    for token, projects in token_projects.items():
        if len(projects) != 1:
            continue
        project = next(iter(projects))
        # Skip if already covered by existing map
        if any(
            token in kw.lower() or kw.lower() in token
            for kw in existing
            if existing[kw] == project
        ):
            continue
        hints[token] = project
    return hints


def apply_output_overrides(
    keyword_map: dict[str, str],
    assignments: dict[str, str],
) -> dict[str, str]:
    """
    Ensure assigned outputs match via exact-ish keywords.

    For each assignment, add a long distinctive keyword from the output if the
    current map would still leave it Uncategorized.
    """
    updated = dict(keyword_map)
    for output, project in assignments.items():
        if not project or project == "Uncategorized":
            continue
        if assign_project(output, updated) == project:
            continue
        # Use a mid-length slice of the output as a one-off keyword so this
        # exact line (and close variants) match on substring.
        # Prefer a distinctive multi-word phrase from the start.
        phrase = output.strip()
        if len(phrase) > 80:
            phrase = phrase[:80].rsplit(" ", 1)[0]
        if len(phrase) < 12:
            phrase = output.strip()
        if phrase and phrase not in updated:
            updated[phrase] = project
    return updated


def enrich_map_with_ai(
    client: LLMClient,
    logs: list[WorkLog],
    keyword_map: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    """
    Classify unmatched outputs.

    Returns (updated_keyword_map, output_overrides) where overrides map exact
    Output text → project for this run. On failure, returns (original map, {}).
    """
    pending = unmatched_outputs(logs, keyword_map)
    if not pending:
        return keyword_map, {}

    known = known_project_names(keyword_map)
    try:
        assignments, keywords = classify_unmatched(client, pending, known)
    except Exception as exc:
        print(f"AI project mapping failed ({exc}); using keyword map only.")
        return keyword_map, {}

    if not assignments and not keywords:
        print("AI project mapping returned no usable data; using keyword map only.")
        return keyword_map, {}

    updated = merge_keyword_maps(keyword_map, keywords)
    if not keywords:
        updated = merge_keyword_maps(
            updated, keywords_from_assignments(assignments, updated)
        )

    overrides: dict[str, str] = {}
    for output, project in assignments.items():
        if not project:
            continue
        if assign_project(output, updated) != project:
            overrides[output.strip()] = project

    return updated, overrides
