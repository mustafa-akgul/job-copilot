# Job Copilot

> Fill any job application form in one click — powered by your CV.

Job Copilot is a Chrome extension backed by a cloud API. Upload your CV once, then auto-fill LinkedIn, Workday, Greenhouse, Lever, Ashby, and any other application form. You always control the Submit button.

---

## Features

- **One-click fill** — scans visible form fields and maps them to your parsed CV profile
- **Three fill modes** — instant auto-fill, inline suggestion overlay, and a manual-review card for low-confidence fields
- **Multi-persona** — maintain separate profiles (e.g. "backend-engineer", "product-manager") and switch with one click
- **JD Analyzer** — paste a job description to see a match score against your profile and a list of missing skills
- **Cover letter generator** — generate a tailored cover letter from your profile and the JD, with tone control
- **Application tracker** — log every application with status (applied → screening → interview → offer)
- **Platform adapters** — native field detection for Workday, Greenhouse, Lever, and Ashby

---

## How it works

```
CV upload (PDF / DOCX)
  └─ Cloud API parses → structured profile stored in your account
       └─ Open any job application page
            └─ Extension scans form fields
                 └─ Fuzzy match + AI maps each field to your profile
                      └─ Fields auto-filled — you review and submit
```

**Fill tiers:**

| Tier | Condition | Result |
|---|---|---|
| Auto | Confidence ≥ 92 % + value present | Filled instantly with a green flash |
| Suggest | Confidence ≥ 78 % | Blue "✓ [value]" button appears next to the field |
| Approve | Low confidence or missing value | Card in the popup — you type the value |

---

## Tech stack

| Layer | Technology |
|---|---|
| Extension | Plasmo (Chrome MV3), React, TypeScript |
| Backend | FastAPI, Python 3.11, SQLAlchemy (async) |
| Auth | Google OAuth via Supabase (`chrome.identity`) |
| Database | SQLite (dev) · Postgres via Supabase (production) |
| AI | OpenAI `gpt-4o-mini` (default) · Anthropic `claude-haiku` |
| Deployment | Railway (backend) · Chrome Web Store (extension) |

---

## Project structure

```
job-copilot/
├── apps/
│   ├── backend/
│   │   ├── src/job_copilot_api/
│   │   │   ├── routers/        # cv, profiles, forms, personas, jd, ai, applications
│   │   │   ├── services/       # cv_parser, mapping, llm, writer, embeddings, db
│   │   │   └── schemas/        # CVProfile, FieldMapping, JDAnalysis, GenerateResponse
│   │   └── tests/              # 71 passing tests
│   └── extension/
│       └── src/
│           ├── popup.tsx
│           ├── background.ts
│           ├── contents/
│           │   ├── form-detector.ts
│           │   └── adapters/   # workday, greenhouse, lever, ashby
│           └── lib/            # api, auth, dom, inject, platform-detect
└── packages/shared-types/
```

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/cv/parse` | Upload CV → parse and store profile |
| `GET` | `/api/v1/profiles` | List all profiles |
| `PUT` | `/api/v1/profiles/{persona}` | Upsert a profile |
| `GET` | `/api/v1/personas` | List personas with metadata |
| `POST` | `/api/v1/personas/{persona}/clone` | Clone a persona |
| `POST` | `/api/v1/forms/map` | Map form fields → profile values |
| `POST` | `/api/v1/jd/analyze` | Analyze job description + match score |
| `POST` | `/api/v1/ai/generate` | Generate cover letter |
| `GET` | `/api/v1/profiles/{persona}/relevant` | Semantic CV section search |
| `CRUD` | `/api/v1/applications` | Application tracking |

Full interactive docs available at `/docs` when running locally.

---

## Local development

**Backend**

```bash
cd apps/backend
pip install -e ".[dev]"
cp .env.example .env   # add OPENAI_API_KEY
uvicorn job_copilot_api.main:app --reload --port 8000
```

**Extension**

```bash
cd apps/extension
npm install --ignore-scripts
npm run dev
```

Load `apps/extension/build/chrome-mv3-dev` via `chrome://extensions → Developer mode → Load unpacked`.

**Tests**

```bash
cd apps/backend
python -m pytest tests/ -v   # 71 tests
```

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `JOB_COPILOT_OPENAI_API_KEY` | Yes | OpenAI API key |
| `JOB_COPILOT_SUPABASE_JWT_SECRET` | Production | Supabase JWT secret for auth |
| `JOB_COPILOT_DATABASE_URL` | Production | Postgres connection string |
| `JOB_COPILOT_LLM_PROVIDER` | No | `openai` (default) or `anthropic` |
| `JOB_COPILOT_FUZZY_THRESHOLD` | No | Match threshold 0–100 (default: 82) |

---

## Privacy

- Your CV data is stored only in your account — never shared or used for training.
- The extension never auto-submits a form. Every submission is your explicit action.
- API keys are stored server-side and never exposed to the browser.
