# Job Copilot

**Fill job application forms in one click — powered by your CV, not copy-paste.**

Job Copilot is a Chrome extension + local AI backend that reads your CV once, then automatically fills any job application form: LinkedIn, Workday, Greenhouse, Lever, company portals. You always control the Submit button.

---

## Quick start (5 minutes)

### Prerequisites
- Python 3.11+ — [python.org](https://www.python.org/downloads/)
- Node.js 18+ — [nodejs.org](https://nodejs.org/)
- [Ollama](https://ollama.com/) (free, runs locally) — or an OpenAI / Anthropic API key

### 1 — Start the backend

```powershell
# In PowerShell, from the repo root:
.\start.ps1
```

This installs dependencies, runs all tests, and starts the API at `http://localhost:8000`.

**First time only — pull the default AI model:**
```powershell
ollama pull qwen2.5-coder:7b
```

### 2 — Load the Chrome extension

```powershell
# In a second terminal:
.\start-extension.ps1
```

Then in Chrome:
1. Go to `chrome://extensions`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked**
4. Select `apps\extension\build\chrome-mv3-dev`

### 3 — Upload your CV

Click the Job Copilot icon in your toolbar → upload your PDF or DOCX. Parsing takes ~30 seconds on first run (local AI).

### 4 — Fill any form

Open any job application page → click **Scan & fill this page**. Done.

---

## How it works

```
Your CV (PDF/DOCX)
    └─ AI parses → structured profile (saved locally)
         └─ You open a job application page
              └─ Extension scans visible form fields
                   └─ Backend fuzzy-matches + AI maps each field to your profile
                        └─ Auto-filled: your name, email, phone, LinkedIn, etc.
                             └─ You review suggestions → click Submit yourself
```

**Three fill tiers:**

| Tier | Condition | What happens |
|---|---|---|
| `auto` | High confidence + value present | Filled instantly (green flash) |
| `suggest` | Medium confidence | Blue "✓ Fill: [value]" button appears next to the field |
| `approve` | Low confidence or missing value | Card appears in the popup — you type/confirm |

**You always click Submit. Nothing is ever auto-submitted.**

---

## AI providers

| Provider | Setup | Speed | Cost |
|---|---|---|---|
| **Ollama** (default) | `ollama pull qwen2.5-coder:7b` | ~15–30s/parse | Free |
| **OpenAI** | Set `OPENAI_API_KEY` in `apps/backend/.env` | ~3s/parse | ~$0.01/CV |
| **Anthropic** | Set `ANTHROPIC_API_KEY` in `apps/backend/.env` | ~5s/parse | ~$0.01/CV |

Switch provider:
```powershell
.\start.ps1 -Provider openai
# or
.\start.ps1 -Provider anthropic
```

---

## Running tests

```powershell
cd apps\backend
python -m pytest tests/ -v
```

**54 tests, 0 failures** — covers:
- Fuzzy field matching and tier logic
- Profile path resolution (nested fields, arrays)
- Boolean/URL value coercion
- LLM timeout graceful fallback
- All API endpoints (auth, CRUD, CV upload, form mapping)
- File size limit (10 MB) and format validation

---

## Project structure

```
job-copilot/
├── start.ps1                  ← one-command launcher (backend + tests)
├── start-extension.ps1        ← Chrome extension dev server
├── apps/
│   ├── backend/               ← FastAPI + SQLite
│   │   ├── src/job_copilot_api/
│   │   │   ├── routers/       ← /health /cv /profiles /forms
│   │   │   ├── services/      ← mapping, cv_parser, llm, db
│   │   │   └── schemas/       ← CVProfile, FieldMapping, FormField
│   │   └── tests/             ← 54 passing tests
│   └── extension/             ← Plasmo Chrome extension
│       └── src/
│           ├── popup.tsx      ← main UI
│           ├── background.ts  ← service worker / API calls
│           ├── contents/      ← in-page form scanner + suggest overlay
│           └── lib/           ← API client, DOM extractor, injector
└── packages/shared-types/     ← (future codegen target)
```

---

## Configuration

All settings live in `apps/backend/.env` (created automatically from `.env.example`):

```env
JOB_COPILOT_LLM_PROVIDER=ollama        # ollama | openai | anthropic
JOB_COPILOT_LLM_MODEL=qwen2.5-coder:7b
JOB_COPILOT_OPENAI_API_KEY=
JOB_COPILOT_ANTHROPIC_API_KEY=
JOB_COPILOT_FUZZY_THRESHOLD=82         # 0-100, lower = more matches
```

Extension settings (API URL, token) are in the extension's **Options** page (gear icon).

---

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Walking skeleton | ✅ |
| 1 | Real CV parsing, fuzzy mapping, SQLite, polished popup | ✅ |
| 2 | LLM mapper for residual fields, HITL card, in-page suggest overlay | ✅ |
| 3 | Multi-profile / persona switcher, JD analyzer + ATS score | next |
| 4 | AI writing — cover letter, "why this role", short bio | |
| 5 | Platform-specific adapters (Workday, Greenhouse, Lever, Ashby) | |
| 6 | Postgres + Supabase auth + multi-tenancy | |

---

## Privacy

- Your CV is parsed locally (Ollama) or via your own API key.
- Parsed data is stored only in `apps/backend/data/jobcopilot.db` on your machine.
- No data leaves your machine unless you configure OpenAI/Anthropic.
- The extension never touches any form without your click.
