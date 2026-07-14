# Work Performance OS — User Manual

Generate a monthly Markdown work report from a Google Sheets daily work log.

---

## 1. First-time setup

Do this once per machine / employee sheet.

### 1.1 Install Python dependencies

From the project root:

```powershell
pip install -r requirements.txt
```

### 1.2 Choose auth mode (important)

Many companies enforce `iam.disableServiceAccountKeyCreation`, which **blocks creating Service Account JSON keys**. That popup is an org security policy — not a mistake on your side.

**Recommended for this MVP: OAuth (login with your Google account).**  
You do **not** need a service account JSON key.

| Mode | When to use |
|------|-------------|
| `oauth` (default) | Local CLI; SA keys blocked by org policy |
| `service_account` | Only if your admin allows SA JSON keys |

Set in `config.yaml`:

```yaml
auth_mode: oauth
credentials_path: "credentials/client_secret.json"
token_path: "credentials/token.json"
```

### 1.3 Enable Google APIs

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. Enable **Google Sheets API** and **Google Drive API** (APIs & Services → Library).

### 1.4 Create an OAuth Desktop client (not a service account key)

1. Go to **APIs & Services → OAuth consent screen**.
2. Choose user type carefully:
   - **External** — required if you sign in with a personal Gmail (`@gmail.com`). Recommended for this MVP.
   - **Internal** — only works with accounts on your company’s Google Workspace domain. Personal Gmail will get `403: org_internal`.
3. App name: e.g. `Work Performance OS`.
4. If Publishing status is **Testing**, under **Test users** click **Add users** and add the exact Google account you will use to sign in (e.g. `you@gmail.com`).
5. Go to **APIs & Services → Credentials → Create credentials → OAuth client ID**.
6. Application type: **Desktop app**.
7. Download the JSON and save it as:

```text
credentials/client_secret.json
```

Do **not** try to create a Service Account key if you already hit the org policy block.

If you already created the app as **Internal**, open **OAuth consent screen** and switch to **External** (or create a new Cloud project and set External from the start), then add yourself as a test user.

### 1.5 Sheet access

With OAuth, the script uses **your** Google account.

- Open the Work Log spreadsheet while logged into that same account, **or**
- Have the sheet owner share it with your account (Viewer is enough).

No need to share with a `...@....iam.gserviceaccount.com` email.

### 1.6 Confirm sheet columns

The tool adapts to the real work-log sheet (you do **not** need edit permission). Expected layout:

| Column | Header in sheet | Meaning |
|--------|-----------------|--------|
| A | _(blank / Timestamp)_ | Ignored for grouping; date fallback |
| B | Start | Start datetime → used as work **date** |
| C | End | End datetime |
| D | Time(min) | Duration in minutes (e.g. `253.00`) |
| E | Research | Work **type** / category (e.g. Dev, Research) |
| F | Output | What the employee said they did |
| G | Link | Submission URL |

Notes:

- There is **no** `Date` column; the date is taken from `Start`.
- The type column header is **`Research`** (not `Type`); values like `Dev` still work.
- Formats like `5/31/2026 16:21:30` are supported.


### 1.7 Edit `config.yaml`

```yaml
employee_name: "Alex Chen"
sheet_id: "1abc...xyz"
worksheet: ""
auth_mode: oauth
credentials_path: "credentials/client_secret.json"
token_path: "credentials/token.json"

project_keywords:
  Supplychain: ConstructProcure
  Review: AI Report Generation

max_session_minutes: 360

ai:
  enabled: true
  provider: openai
  model: gpt-4o-mini
```

**How to find `sheet_id`:**  
`https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit`

**`project_keywords`:** MVP-only manual map (substring of `Output` → project name). Unmatched → `Uncategorized`.  
**Phase 2.2 (later):** AI will maintain this mapping dynamically — keep the list small.

### 1.7b AI evaluation (Phase 2)

In `config.yaml`:

```yaml
ai:
  enabled: true
  provider: openai          # openai | gemini
  model: gpt-4o-mini        # or gemini-2.0-flash
```

Put API keys in the project-root **`.env`** file (never in yaml, never commit `.env`):

```powershell
copy .env.example .env
```

Edit `.env`:

```env
# OpenAI (when ai.provider: openai)
OPENAI_API_KEY=sk-...

# Gemini (when ai.provider: gemini) — either name works
GEMINI_API_KEY=...
# GOOGLE_API_KEY=...
```

Switch provider example:

```yaml
ai:
  enabled: true
  provider: gemini
  model: gemini-2.0-flash
```

Set `ai.enabled: false` to skip AI and keep the MVP-only report.

### 1.8 First login

Sign in with the **same** Google account that can open the Work Log Sheet (and that you added as a Test user if the app is in Testing).

```powershell
python main.py 2026-06
```

A browser window opens → sign in with Google → allow Sheets/Drive read access.  
A token is saved to `credentials/token.json` so later runs usually skip the browser.

**If you see `Access blocked … only be used within its organization` / `403: org_internal`:**

Your consent screen is **Internal**, but you signed in with a personal Gmail. Fix one of:

1. **Preferred:** OAuth consent screen → change to **External** → add `your@gmail.com` as a **Test user** → retry, or  
2. Sign in with your **company Workspace** email instead (only if that account can open the Sheet).

---

## 2. Every time you generate a report

### 2.1 (Optional) update config

- Change `employee_name` or `sheet_id` as needed.
- `project_keywords` is optional MVP scaffolding (AI project mapping is Phase 2.2); only tweak if grouping is clearly wrong.
- Toggle `ai.enabled` / `ai.provider` / `ai.model` as needed.
- Usually you only pass the month on the CLI.

### 2.2 Run

`period` is **required** (`YYYY-MM`). Omitting it exits with an error.

```powershell
python main.py 2026-06
```

### 2.3 Find the output

```text
output/Monthly_Report_YYYY_MM.md
```

The report includes Work Statistics, Project Summary, Activity Log, Submissions, Warnings, and (when `ai.enabled: true`) an **AI Evaluation** section.

### 2.4 Common errors

| Message / situation | Fix |
|---------------------|-----|
| SA key creation disabled | Use `auth_mode: oauth` + Desktop OAuth client (this section) |
| `403: org_internal` / only within its organization | Consent screen is Internal; switch to **External** + add Test user, or use Workspace email |
| `OAuth client secret not found` | Save Desktop client JSON as `credentials/client_secret.json` |
| `does not look like an OAuth client secret` | You downloaded the wrong file; need OAuth client ID JSON |
| `Set sheet_id in config.yaml` | Put the real Sheet ID in config |
| Permission denied / spreadsheet not found | Share the Sheet with the Google account you logged in with |
| `missing required columns` | Fix header row names in the Sheet |
| Consent screen “app not verified” | Add yourself as a test user, or continue for testing |
| `Missing API key` / `OPENAI_API_KEY` | Add `OPENAI_API_KEY=...` to project-root `.env` |
| `Missing API key` / `GEMINI_API_KEY` | Add `GEMINI_API_KEY=...` (or `GOOGLE_API_KEY`) to `.env` |
| Unsupported `ai.provider` | Use `openai` or `gemini` in config |

---

## Optional: Service Account (only if org allows keys)

If an admin has disabled `iam.disableServiceAccountKeyCreation` and you have a SA JSON key:

```yaml
auth_mode: service_account
credentials_path: "credentials/service_account.json"
```

Share the Sheet with the service account `client_email`.

If keys stay blocked, ask IT for either:

1. Permission to use OAuth Desktop clients (usual path), or  
2. An exception / alternative for automation (Workload Identity, etc.) — overkill for this MVP.

---

## Related docs

- Product scope & roadmap: [draft_big_picture.md](draft_big_picture.md)
