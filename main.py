"""Work Performance OS — CLI.

Generate a monthly Markdown work report from a Google Sheets work log,
optionally with AI evaluation (OpenAI or Gemini).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from ai_eval import run_evaluation
from analyze import build_report
from llm import create_llm
from report import write_report
from sheets import fetch_work_logs, filter_by_period

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config.yaml"
DEFAULT_OUTPUT = ROOT / "output"

# Standardize secrets on project-root .env
load_dotenv(ROOT / ".env")


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a monthly work performance Markdown report "
        "from Google Sheets."
    )
    parser.add_argument(
        "period",
        help="Report month as YYYY-MM (required)",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT),
        help="Directory for generated Markdown reports",
    )
    return parser.parse_args()


def validate_period(period: str) -> str:
    parts = period.split("-")
    if len(parts) != 2:
        raise ValueError("Period must be YYYY-MM")
    year, month = parts
    if not (year.isdigit() and month.isdigit()):
        raise ValueError("Period must be YYYY-MM")
    m = int(month)
    if m < 1 or m > 12:
        raise ValueError("Month must be 01–12")
    return f"{int(year):04d}-{m:02d}"


def _resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    try:
        config = load_config(Path(args.config))
        period = validate_period(args.period)
        sheet_id = config.get("sheet_id") or ""
        if not sheet_id or sheet_id == "YOUR_GOOGLE_SHEET_ID":
            raise ValueError(
                "Set sheet_id in config.yaml to your Google Sheet ID."
            )

        auth_mode = (config.get("auth_mode") or "oauth").strip().lower()
        default_creds = (
            "credentials/service_account.json"
            if auth_mode in ("service_account", "sa")
            else "credentials/client_secret.json"
        )
        creds_path = _resolve_path(
            config.get("credentials_path") or default_creds
        )
        token_path = _resolve_path(
            config.get("token_path") or "credentials/token.json"
        )

        employee = config.get("employee_name") or "Employee"
        employee_context = (config.get("employee_context") or "").strip()
        worksheet = config.get("worksheet") or ""
        keyword_map = config.get("project_keywords") or {}
        max_session = int(config.get("max_session_minutes") or 360)
        ai_cfg = config.get("ai") or {}
        ai_enabled = bool(ai_cfg.get("enabled"))

        print(f"Fetching work logs for {period} (auth={auth_mode})…")
        all_logs = fetch_work_logs(
            sheet_id=sheet_id,
            credentials_path=creds_path,
            worksheet=worksheet,
            auth_mode=auth_mode,
            token_path=token_path,
        )
        logs = filter_by_period(all_logs, period)
        print(f"Found {len(logs)} row(s) in {period} (of {len(all_logs)} total).")

        report_data = build_report(
            logs=logs,
            employee=employee,
            period=period,
            keyword_map=keyword_map,
            max_session_minutes=max_session,
        )

        if ai_enabled:
            provider = (ai_cfg.get("provider") or "openai").strip().lower()
            model = (ai_cfg.get("model") or "").strip()
            if not model:
                model = (
                    "gemini-2.0-flash"
                    if provider in ("gemini", "google")
                    else "gpt-4o-mini"
                )
            print(f"Running AI evaluation ({provider} / {model})…")
            client = create_llm(ai_cfg)
            report_data.evaluation = run_evaluation(
                report_data,
                client,
                provider=provider,
                model=model,
                employee_context=employee_context,
            )

        out_path = write_report(report_data, args.output_dir)
        print(f"Report written: {out_path}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
