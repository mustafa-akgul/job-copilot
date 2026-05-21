# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Job Copilot — a Chrome extension + cloud FastAPI backend that fills job application forms from the user's parsed CV. Two halves:

- **`apps/backend/`** — FastAPI. Parses CVs (PDF/DOCX → `CVProfile` via cloud LLM), maps form fields to profile paths (fuzzy + LLM residuals), stores profiles in SQLite (local) or Postgres (production).
- **`apps/extension/`** — Plasmo Chrome MV3 extension. Google OAuth login via Supabase, scans forms in the active tab, sends fields to the backend, injects values and shows inline suggestions.

**No local backend required.** The extension connects to a deployed cloud API. Local development uses SQLite + dev-token auth; production uses Supabase Postgres + JWT auth.

Reference repo at `../filling-agent/` (Playwright prototype) — `mapping/llm_mapper.py` and `cv_parser/llm_parser.py` are source-of-truth for ports. Check there before reinventing.

## Common commands

### Backend (local dev)

```powershell
cd apps\backend
pip install -e ".[dev]"
cp .env.example .env          # fill in OPENAI_API_KEY

uvicorn job_copilot_api.main:app --reload --port 8000

python -m pytest tests/ -v   # all 54 tests
python -m pytest tests/ -q   # quiet summary
```

Local dev uses SQLite (no Postgres needed) and `Bearer dev-token` auth (no Supabase needed). Set `JOB_COPILOT_OPENAI_API_KEY` in `.env` to test real LLM calls; tests mock the LLM so no key is required for the test suite.

Tests use an **in-memory SQLite DB** — `tests/conftest.py` sets `JOB_COPILOT_DATABASE_URL=sqlite+aiosqlite:///:memory:` before any app import. Never touch the real DB file during tests.

OpenAPI docs: `http://localhost:8000/docs`. Profile DB: `apps/backend/data/jobcopilot.db` (delete to reset; schema recreates on startup via `lifespan`).

### Extension

```powershell
cd apps\extension
npm install --ignore-scripts   # use --ignore-scripts on Windows to skip native builds
npm run dev                    # → build/chrome-mv3-dev (hot reload)
npm run build                  # → build/chrome-mv3-prod
npm run package                # zip for Chrome Web Store
```

Load `build/chrome-mv3-prod` via `chrome://extensions → Developer mode → Load unpacked`. Plasmo regenerates the manifest from `package.json`'s `manifest` field — don't edit `manifest.json` in `build/`.

### LLM provider

Two cloud providers are supported. Set in `.env`:

```env
JOB_COPILOT_LLM_PROVIDER=openai       # default, gpt-4o-mini
JOB_COPILOT_LLM_PROVIDER=anthropic    # claude-haiku-4-5-20251001
```

`services/llm.py::call_json` is the single dispatch point. It enforces a **60-second hard timeout** via `asyncio.wait_for`.

## Architecture — things requiring multiple files to understand

### The full Scan & Fill round trip

One user click spans 6 files across 3 process contexts:

```
popup.tsx
  └─ sendBg({type: "SCAN_AND_FILL", persona})
      └─ background.ts :: scanAndFill()
          ├─ sendToTab({type: "CLEAR_SUGGEST"})          ← clears stale overlays
          ├─ notifyPopup("Scanning page fields…")        ← progress step to popup
          ├─ sendToTab({type: "SCAN_PAGE"})
          │   └─ form-detector.ts → lib/dom.ts :: extractFormFields()  → FormField[]
          ├─ notifyPopup("Mapping fields to your profile…")
          ├─ lib/api.ts :: mapFields()  → POST /api/v1/forms/map
          │   └─ routers/forms.py → services/mapping.py :: map_fields()
          │       ├─ Stage 1: rapidfuzz against SYNONYMS table
          │       └─ Stage 2: _llm_map_residuals() — LLM batch for skip-tier fields
          ├─ notifyPopup("Filling matched fields…")
          ├─ sendToTab({type: "FILL_FIELDS", mappings: autoMappings})
          │   └─ form-detector.ts → lib/inject.ts :: fillMappings() + flashGreen()
          ├─ sendToTab({type: "SHOW_SUGGEST", mappings: suggestMappings})
          │   └─ form-detector.ts :: injectSuggestOverlay() per field
          └─ returns ScanSummary {filled, suggestCount, approveMappings, …} to popup
```

The popup listens for `STATUS_UPDATE` messages from the SW to show live progress steps. The SW sends these via `chrome.runtime.sendMessage` during processing (fire-and-forget).

### The mapping tier system

`services/mapping.py::_tier_for` assigns a tier to every `FieldMapping`:

| tier | condition | backend returns | extension does |
|---|---|---|---|
| `auto` | confidence ≥ 0.92 AND value present | value filled | inject + green flash |
| `suggest` | confidence ≥ 0.78 AND value present | value filled | blue "✓ [value]" button injected next to field |
| `approve` | low confidence OR value missing | value may be null | HITL card in popup — user types value |
| `skip` | no fuzzy match, LLM also failed | value null | left blank |

**Two-stage mapping:** fuzzy pass first (fast, no LLM cost), then `_llm_map_residuals()` for unmatched fields. The LLM stage has its own 20-second budget (`_LLM_RESIDUAL_TIMEOUT`) so it never blocks auto-fills.

### The HITL flow (approve tier)

```
background.ts :: scanAndFill()
  └─ returns approveMappings[] in ScanSummary
      └─ popup.tsx :: HITLCard component
          └─ user fills inputs, clicks "Fill N fields"
              └─ sendBg({type: "FILL_APPROVE", values: [{selector, value}]})
                  └─ background.ts :: fillApprove()
                      └─ converts to tier="auto" FieldMappings
                          └─ sendToTab({type: "FILL_FIELDS", …})
```

### The Pydantic ↔ TypeScript contract

`apps/backend/src/job_copilot_api/schemas/` is the source of truth. `apps/extension/src/types/shared.ts` is a **hand-maintained mirror** — edit both or runtime breaks silently (TS sees `unknown` from `fetch`).

`packages/shared-types/` is reserved for future `openapi-typescript` codegen output. Until then, change schemas in pairs.

Key types to keep in sync: `FieldMapping`, `MapRequest`, `MapResponse`, `ScanSummary`, `ApplicationRecord`, `RuntimeMessage`.

### Value coercion before injection

`services/mapping.py::_coerce_value()` normalises resolved profile values before they reach the extension:
- `HttpUrl` → `str().rstrip("/")` — Pydantic v2 adds trailing slash to bare domains
- `bool` → `"Yes"` / `"No"` — form-friendly string
- Everything else → `str()`

This is the only place to add new type coercions. Don't add them in the router or the extension.

### LLM response sanitization before Pydantic validation

`services/cv_parser.py::_sanitize_raw()` fixes predictable LLM formatting quirks **before** `CVProfile.model_validate()`:
- Bare URLs in `social_links` (e.g. `linkedin.com/…`) → prepends `https://`
- GPA strings like `"3.7/4.0"` → `float` (takes first token before `/`)
- `preferred_work_mode` capitalized (e.g. `"Remote"`) → lowercased
- `work_authorization` free text (e.g. `"Not required"`) → nearest valid literal or `"other"`

This is the only place to add new LLM output normalisations for CV parsing.

### Application tracking

`services/db.py` contains two independent stores:
- `ProfileStore` / `get_store()` — one row per `(user_id, persona)`, profile as JSON column.
- `ApplicationStore` / `get_app_store()` — `ApplicationRow` table with `(id, user_id, company, role, url, status, filled_at, notes)`.

`routers/applications.py` exposes CRUD at `/api/v1/applications`. The extension's `TrackApplicationCard` (in `popup.tsx`) auto-shows after a successful fill when at least one field was injected. It pre-populates company/role using `parsePageTitle()`, which handles patterns like "Role at Company | LinkedIn", "Role - Company - Board" from major job boards.

### Store pattern

`services/store.py` exposes a `ProfileStore` Protocol; `services/db.py` implements it on SQLite (one row per `(user_id, persona)`, profile stored as a JSON column). Swap `JOB_COPILOT_DATABASE_URL` to Postgres when adding multi-tenancy — the JSON column is portable and the Protocol is the only thing routers depend on. Don't add raw SQL to routers.

`user_id` comes from `deps.py::require_user`. In production (when `SUPABASE_JWT_SECRET` is set) it verifies the Supabase JWT and returns the UUID. In local dev / tests (no JWT secret) it compares against `DEV_TOKEN` and returns `"dev-user"`. Routes take `user_id: str = Depends(require_user)` — no other changes needed to add real auth.

### LLM prompt location

The field-mapping prompt lives at `apps/backend/src/job_copilot_api/prompts/field_mapping.md`. The CV parsing prompt is inlined in `services/cv_parser.py::_SYSTEM_PROMPT`. Edit the markdown file for mapping tweaks; edit the string constant for CV parsing tweaks.

### Health check in the popup

`popup.tsx` calls `GET /health` **directly via `fetch`** (with a 5-second `AbortController` timeout) rather than routing through the background service worker. This avoids MV3 service-worker wake-up latency that previously caused the popup to hang indefinitely on "connecting". All other API calls still go through the SW (`lib/api.ts` + `background.ts`).

## Design invariants

- **Never auto-submit a form.** No `click("submit")` anywhere. The extension fills; the human submits.
- **CV → profile happens once.** The expensive LLM call is on upload. Mapping at fill time is fuzzy + cheap LLM only.
- **The orchestrator never hallucinates.** Missing profile path → `tier=approve` → ask the user. Never fabricate values.
- **SW is the only API caller** (except `/health`). Content scripts and popup never call authenticated backend endpoints directly — avoids CORS issues and keeps Bearer-token plumbing in one place (`lib/api.ts`).

### Why the service worker sits between popup and content scripts

- The popup unmounts every time it closes; the SW persists (within MV3 limits) and can hold in-flight requests across open/close cycles.
- Content scripts can't call backend HTTPS endpoints cleanly with credentials — CORS behavior varies. The SW bypasses this with `host_permissions: ["<all_urls>"]`.
- Centralized message hub: a future autofill-on-page-load trigger fires from the SW, not the popup.

## Phase status

Phases 1–2 and cloud migration are complete. What shipped:

- **Cloud-first auth** (`services/auth.py`, `deps.py::require_user`): Supabase JWT in production; dev-token fallback for local dev and tests. No Ollama, no local backend required.
- **Google OAuth in extension** (`lib/auth.ts`): `chrome.identity.launchWebAuthFlow` in the SW; silent token refresh when <5 min remaining.
- **LLM mapper** (`services/mapping.py`): two-stage async map — fuzzy first, then LLM batch for residuals with 20s timeout.
- **HITL card** (`popup.tsx::HITLCard`): approve-tier fields surface in the popup with human-readable labels and input boxes.
- **Suggest overlay** (`contents/form-detector.ts::injectSuggestOverlay`): suggest-tier fields get a blue click-to-fill button injected after the field element.
- **Live progress** (`background.ts::notifyPopup` + `popup.tsx::FillProgress`): popup shows a growing step list with ✓ completions during scanning.
- **Source breakdown** (`popup.tsx::FillSummary`): "⚡ X instant / 🤖 X AI" row using `localMatchCount`/`aiMatchCount` from `ScanSummary`.
- **CV parse preview** (`popup.tsx::CVParseSuccess`): after upload, shows parsed name, top-5 skill chips, work/education counts.
- **Application tracker** (`routers/applications.py` + `popup.tsx::TrackApplicationCard`, `ApplicationsHistory`): post-fill tracking with status updates.

Full phase roadmap (`docs/architecture.md`):

| Phase | What changes |
|---|---|
| 3 | `personas.py` router. Popup persona switcher. `POST /api/v1/jd/analyze` JD + ATS keywords. |
| 4 | `writer.py` — `POST /api/v1/ai/generate` for cover letter / "Why this role". Popup inline draft card. |
| 5 | Embeddings store (sqlite-vss → pgvector). `GET /api/v1/profiles/{persona}/relevant?role_desc=…`. |
| 6 | `apps/extension/src/contents/adapters/{workday,greenhouse,lever,ashby}.ts` — per-platform DOM overrides. |
| 7 | `analytics/` backend module + dashboard pages in extension. |

## Things that look weird but are intentional

- `services/db.py` creates the SQLAlchemy engine at **module level** from `settings.database_url`. Tests override this by setting `JOB_COPILOT_DATABASE_URL=sqlite+aiosqlite:///:memory:` in `tests/conftest.py` **before any app import**. Don't refactor to lazy init.
- `popup.tsx` uses inline styles. Plasmo's CSS-in-content-script story has caveats; inline keeps the popup self-contained. Don't migrate without a specific reason.
- `npm install --ignore-scripts` on Windows — `@parcel/watcher` requires native build tools. The package works without the native watcher (falls back to polling); `--ignore-scripts` skips the failing build.
- `pydantic[email]` is a required dependency (not just dev). Without it, `EmailStr` on `PersonalInfo.email` raises `ImportError` at startup.
- `package.json` manifest section sets `"action": { "default_popup": "popup.html" }` explicitly. Plasmo 0.88 does **not** auto-inject `default_popup` when `action` is overridden — omitting it silently drops `popup.html` from the build with no error.
- `_sanitize_raw` in `cv_parser.py` runs before `CVProfile.model_validate`. The LLM routinely returns bare URLs, fractional GPA strings, and capitalized literals that fail Pydantic. The sanitizer is not defensive programming — it fixes confirmed real model output.
- `services/auth.py::verify_token` uses `python-jose` with `audience="authenticated"` — this matches the Supabase JWT claim exactly. Changing the audience string will break all production logins.
