# Architecture

## End-to-end thin slice (today)

```
┌──────────┐     ┌───────────────┐     ┌────────────────┐     ┌──────────────┐
│  Popup   │──▶─│  Background SW │──▶─│  Content script │──▶─│   Live page  │
│ (popup.tsx)   │ (background.ts) │     │ (form-detector) │     │  (any URL)   │
└──────────┘     └───────┬───────┘     └────────┬────────┘     └──────────────┘
                         │ HTTPS                │  in-page DOM
                         ▼                      ▼
                ┌──────────────────────────────────────────┐
                │           FastAPI backend                │
                │  POST /api/v1/forms/map  → FieldMapping[]│
                │  POST /api/v1/cv/parse   → CVProfile     │
                │  GET/PUT /api/v1/profiles/{persona}      │
                │  GET /health                             │
                └──────────────────────────────────────────┘
```

### Round-trip when user clicks "Scan & fill"

1. **popup.tsx** → `chrome.runtime.sendMessage({ type: "SCAN_AND_FILL", persona })`
2. **background.ts** picks the active tab, sends `SCAN_PAGE` to the content script.
3. **form-detector.ts** runs `extractFormFields()` and returns `FormField[]`.
4. **background.ts** calls `POST /api/v1/forms/map` with the field list + persona; Bearer dev-token attached.
5. **forms.py** (`_dummy_map`) does substring matching, returns `FieldMapping[]` with tiers.
6. **background.ts** sends `FILL_FIELDS` to the content script with the mappings.
7. **form-detector.ts** calls `fillMappings()`, which only injects `tier === "auto"` (the rest will surface in the popup as suggestions in phase 2).
8. **popup.tsx** displays the summary (scanned/mapped/filled/skipped/unresolved).

The Submit button on the page is **never** clicked by the extension.

## Why a service worker between popup and content script?

- The popup unmounts every time it closes. The SW persists (within MV3 limits).
- Content scripts can't directly call backend HTTPS endpoints with credentials cleanly (CORS quirks vary). The SW bypasses this with `host_permissions: ["<all_urls>"]`.
- Centralized message hub: a future autofill-on-page-load trigger fires from the SW, not the popup.

## Where each phase plugs in

| Phase | What changes |
|---|---|
| 1 | `cv.py::parse_cv` → real extractor + LLM call. Add `db.py` (SQLAlchemy + Postgres + Alembic). Add `auth.py` (Supabase JWT). |
| 2 | `forms.py::_dummy_map` → port `fuzzy.py` + `llm_mapper.py` from filling-agent. Popup grows a "suggestions" panel for `tier=suggest/approve`. |
| 3 | New `personas.py` router. Popup grows a persona switcher. JD analyzer endpoint `POST /api/v1/jd/analyze`. |
| 4 | New `writer.py` — `POST /api/v1/ai/generate` for "Why this role" / cover letter / etc. Popup grows an inline draft card. |
| 5 | Embeddings store (sqlite-vss → pgvector). `GET /api/v1/profiles/{persona}/relevant?role_desc=…`. |
| 6 | `apps/extension/src/contents/adapters/{workday,greenhouse,lever,ashby}.ts` — per-platform overrides for messy DOMs. |
| 7 | `analytics/` module on backend, dashboard pages in extension. |

## Stable contracts

The TS types in `apps/extension/src/types/shared.ts` are a hand-maintained
mirror of `apps/backend/src/job_copilot_api/schemas/`. Phase 1 will generate
them from OpenAPI to remove the drift risk. Until then: edit Pydantic →
update TS by hand.
