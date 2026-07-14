"""Google Sheets work-log reader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Expected header names (case-insensitive match).
# Real work-log sheet uses: [Timestamp,] Start, End, Time(min), Research, Output, Link
# (no Date column; work type header is "Research", not "Type")
HEADER_ALIASES = {
    "date": "date",
    "timestamp": "timestamp",
    "start": "start",
    "end": "end",
    "time(min)": "duration_min",
    "time (min)": "duration_min",
    "time_min": "duration_min",
    "duration": "duration_min",
    "type": "type",
    "research": "type",  # actual sheet header for work category
    "category": "type",
    "work type": "type",
    "output": "output",
    "link": "link",
}

_DATETIME_FORMATS = (
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%m/%d/%Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
)


@dataclass
class WorkLog:
    date: date
    start: str
    end: str
    duration_min: int
    type: str
    output: str
    link: str
    row_number: int  # 1-based sheet row for warnings


def _normalize_header(value: str) -> str:
    return value.strip().lower()


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = str(value).strip()
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    # Serial date/time from Sheets sometimes arrives as number-like string
    try:
        serial = float(text)
        # Google Sheets serial epoch: 1899-12-30
        return datetime(1899, 12, 30) + timedelta(days=serial)
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    dt = _parse_datetime(value)
    return dt.date() if dt else None


def _parse_duration(value: Any) -> int:
    if value is None or value == "":
        return 0
    text = str(value).strip().replace(",", "")
    try:
        return int(round(float(text)))
    except ValueError:
        return 0


def _map_headers(header_row: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(header_row):
        key = HEADER_ALIASES.get(_normalize_header(str(raw)))
        if key and key not in mapping:
            mapping[key] = idx

    # Positional fallback: blank header before Start is usually Timestamp
    if "timestamp" not in mapping and "start" in mapping:
        start_idx = mapping["start"]
        if start_idx > 0 and not str(header_row[start_idx - 1]).strip():
            mapping["timestamp"] = start_idx - 1

    # Between Time(min) and Output is the work-type column when header is odd
    if "type" not in mapping and "duration_min" in mapping and "output" in mapping:
        left, right = mapping["duration_min"], mapping["output"]
        if right - left == 2:
            mapping["type"] = left + 1

    required = {"duration_min", "output", "link"}
    missing = required - set(mapping)
    if missing:
        raise ValueError(
            f"Sheet is missing required columns: {', '.join(sorted(missing))}. "
            f"Found headers: {header_row}"
        )
    if "date" not in mapping and "start" not in mapping and "timestamp" not in mapping:
        raise ValueError(
            "Sheet needs a Date, Start, or Timestamp column to determine work date. "
            f"Found headers: {header_row}"
        )
    return mapping


def _row_date(row: list[str], mapping: dict[str, int]) -> date | None:
    for field in ("date", "start", "timestamp"):
        parsed = _parse_date(_cell(row, mapping, field))
        if parsed is not None:
            return parsed
    return None


def _cell(row: list[str], mapping: dict[str, int], field: str) -> str:
    idx = mapping.get(field)
    if idx is None or idx >= len(row):
        return ""
    return str(row[idx]).strip()


def _looks_like_oauth_client(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return "installed" in data or "web" in data


def get_credentials(
    auth_mode: str,
    credentials_path: str | Path,
    token_path: str | Path,
):
    """Return Google credentials for gspread.

    auth_mode:
      - oauth: Desktop OAuth (recommended when SA JSON keys are blocked)
      - service_account: service account key JSON
    """
    creds_file = Path(credentials_path)
    token_file = Path(token_path)
    mode = (auth_mode or "oauth").strip().lower()

    if mode in ("service_account", "sa"):
        if not creds_file.exists():
            raise FileNotFoundError(
                f"Service account key not found: {creds_file}. "
                "If your org blocks SA key creation, set auth_mode: oauth "
                "and follow docs/user_manual.md."
            )
        return ServiceAccountCredentials.from_service_account_file(
            str(creds_file), scopes=SCOPES
        )

    # Default: OAuth installed-app flow
    if not creds_file.exists():
        raise FileNotFoundError(
            f"OAuth client secret not found: {creds_file}. "
            "Create an OAuth Desktop client in Google Cloud Console and "
            "download it here (see docs/user_manual.md)."
        )
    if not _looks_like_oauth_client(creds_file):
        raise ValueError(
            f"{creds_file} does not look like an OAuth client secret JSON "
            "(expected keys 'installed' or 'web'). "
            "Download OAuth client ID → Desktop app, not a service account key."
        )

    creds: UserCredentials | None = None
    if token_file.exists():
        creds = UserCredentials.from_authorized_user_file(str(token_file), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")
    elif not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
        creds = flow.run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return creds


def fetch_work_logs(
    sheet_id: str,
    credentials_path: str | Path,
    worksheet: str = "",
    auth_mode: str = "oauth",
    token_path: str | Path = "credentials/token.json",
) -> list[WorkLog]:
    creds = get_credentials(auth_mode, credentials_path, token_path)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(sheet_id)
    ws = spreadsheet.worksheet(worksheet) if worksheet else spreadsheet.sheet1
    rows = ws.get_all_values()
    if not rows:
        return []

    header_map = _map_headers(rows[0])
    logs: list[WorkLog] = []
    for i, row in enumerate(rows[1:], start=2):
        if not any(str(c).strip() for c in row):
            continue
        parsed_date = _row_date(row, header_map)
        if parsed_date is None:
            continue
        logs.append(
            WorkLog(
                date=parsed_date,
                start=_cell(row, header_map, "start"),
                end=_cell(row, header_map, "end"),
                duration_min=_parse_duration(_cell(row, header_map, "duration_min")),
                type=_cell(row, header_map, "type"),
                output=_cell(row, header_map, "output"),
                link=_cell(row, header_map, "link"),
                row_number=i,
            )
        )
    return logs


def filter_by_period(logs: list[WorkLog], period: str) -> list[WorkLog]:
    """Filter logs to YYYY-MM."""
    year_s, month_s = period.split("-", 1)
    year, month = int(year_s), int(month_s)
    return [log for log in logs if log.date.year == year and log.date.month == month]
