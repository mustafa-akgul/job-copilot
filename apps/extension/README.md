# Job Copilot — Chrome Extension (Plasmo)

## Develop

```bash
cd apps/extension
cp .env.example .env.development  # optional; defaults work for localhost
npm install
npm run dev                       # plasmo dev — outputs to build/chrome-mv3-dev
```

Then in Chrome:

1. Open `chrome://extensions`.
2. Toggle **Developer mode** (top right).
3. **Load unpacked** → select `apps/extension/build/chrome-mv3-dev`.
4. Pin the extension to the toolbar.

Plasmo auto-reloads on file change. After the first build it's safe to leave `npm run dev` running in the background.

## Build production zip

```bash
npm run build
npm run package
# → build/chrome-mv3-prod.zip
```

## File map

```
src/
├── popup.tsx              # toolbar UI — Scan & fill button + status
├── options.tsx            # settings page — API URL, dev token, persona
├── background.ts          # service worker — message hub, talks to backend
├── contents/
│   └── form-detector.ts   # content script — extracts + injects in-page
├── lib/
│   ├── api.ts             # fetch wrapper to backend (with Bearer token)
│   ├── dom.ts             # extractFormFields() — port of filling-agent JS
│   ├── inject.ts          # native-event injector (React/Vue friendly)
│   └── settings.ts        # chrome.storage.local-backed settings
└── types/
    └── shared.ts          # TS mirror of FastAPI Pydantic schemas
```

## Note on icons

Plasmo auto-generates default icons from `assets/icon.png` if present. Drop in a 512×512 PNG to brand the extension; without one Chrome shows the generic puzzle icon.

## Message protocol

```
popup ─PING─▶ background ─fetch─▶ /health
popup ─SCAN_AND_FILL─▶ background
                         ├─ tab ─SCAN_PAGE─▶ content (returns FormField[])
                         ├─ /api/v1/forms/map ─▶ backend (returns FieldMapping[])
                         └─ tab ─FILL_FIELDS─▶ content (injects, returns report)
```
