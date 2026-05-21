// Background service worker — owns OAuth, orchestrates fill round trips,
// handles application tracking on behalf of the popup.

import { createApplication, mapFields } from "~lib/api";
import {
  buildOAuthUrl,
  clearSession,
  parseOAuthRedirect,
  setSession,
} from "~lib/auth";
import { loadSettings } from "~lib/settings";
import type {
  FieldMapping,
  FillReport,
  MapResponse,
  RuntimeMessage,
  ScanResult,
  ScanSummary,
} from "~types/shared";

async function activeTab(): Promise<chrome.tabs.Tab> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("No active tab");
  return tab;
}

async function sendToTab<T>(tabId: number, message: RuntimeMessage): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, message, (response) => {
      const err = chrome.runtime.lastError;
      if (err) reject(new Error(err.message));
      else resolve(response as T);
    });
  });
}

function notifyPopup(step: string, detail?: string): void {
  chrome.runtime.sendMessage({ type: "STATUS_UPDATE", step, detail } as RuntimeMessage).catch(() => {});
}

// ── OAuth ─────────────────────────────────────────────────────────────────────

async function signIn(): Promise<void> {
  const redirectUrl = chrome.identity.getRedirectURL();
  const authUrl = buildOAuthUrl(redirectUrl);

  const callbackUrl = await new Promise<string>((resolve, reject) => {
    chrome.identity.launchWebAuthFlow({ url: authUrl, interactive: true }, (url) => {
      const err = chrome.runtime.lastError;
      if (err || !url) reject(new Error(err?.message ?? "Auth flow cancelled"));
      else resolve(url);
    });
  });

  const session = parseOAuthRedirect(callbackUrl);
  await setSession(session);
}

// ── Fill orchestration ────────────────────────────────────────────────────────

async function scanAndFill(persona: string): Promise<ScanSummary> {
  const tab = await activeTab();
  const tabId = tab.id!;

  sendToTab(tabId, { type: "CLEAR_SUGGEST" }).catch(() => {});

  // Step 1 — scan
  notifyPopup("Scanning page for form fields…");
  const scan: ScanResult = await sendToTab(tabId, { type: "SCAN_PAGE" });
  notifyPopup(`Found ${scan.fields.length} field${scan.fields.length !== 1 ? "s" : ""} — mapping to your profile…`);

  // Step 2 — map
  const map: MapResponse = await mapFields({
    persona,
    page_url: scan.url,
    fields: scan.fields,
  });

  const autoMappings = map.mappings.filter((m) => m.tier === "auto");
  const suggestMappings = map.mappings.filter((m) => m.tier === "suggest" && m.value != null);
  const approveMappings = map.mappings.filter((m) => m.tier === "approve");
  const localMatchCount = map.mappings.filter((m) => m.source === "fuzzy").length;
  const aiMatchCount = map.mappings.filter((m) => m.source === "llm").length;

  const parts: string[] = [];
  if (autoMappings.length > 0) parts.push(`${autoMappings.length} auto-fill`);
  if (suggestMappings.length > 0) parts.push(`${suggestMappings.length} suggested`);
  if (approveMappings.length > 0) parts.push(`${approveMappings.length} need review`);
  notifyPopup(parts.length ? parts.join(" · ") : "No matches found — filling now…");

  // Step 3 — fill
  const report: FillReport = await sendToTab(tabId, {
    type: "FILL_FIELDS",
    mappings: autoMappings,
  });

  if (suggestMappings.length > 0) {
    sendToTab(tabId, { type: "SHOW_SUGGEST", mappings: suggestMappings }).catch(() => {});
  }

  return {
    scanned: scan.fields.length,
    mapped: map.mappings.filter((m) => m.json_path).length,
    filled: report.filled.length,
    skipped: report.skipped.length,
    unresolved: map.unresolved.length,
    approveMappings,
    suggestCount: suggestMappings.length,
    localMatchCount,
    aiMatchCount,
    pageTitle: tab.title ?? "",
    pageUrl: tab.url ?? scan.url,
  };
}

async function fillApprove(values: { selector: string; value: string }[]): Promise<number> {
  const tab = await activeTab();
  const mappings: FieldMapping[] = values.map(({ selector, value }) => ({
    selector,
    json_path: null,
    value,
    confidence: 1.0,
    tier: "auto",
    source: "user",
    rationale: "user-provided via HITL card",
  }));
  const report: FillReport = await sendToTab(tab.id!, { type: "FILL_FIELDS", mappings });
  return report.filled.length;
}

// ── Message router ────────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message: RuntimeMessage, _sender, sendResponse) => {
  (async () => {
    try {
      if (message.type === "SIGN_IN") {
        await signIn();
        sendResponse({ ok: true });
      } else if (message.type === "SIGN_OUT") {
        await clearSession();
        sendResponse({ ok: true });
      } else if (message.type === "SCAN_AND_FILL") {
        const summary = await scanAndFill(message.persona);
        sendResponse({ ok: true, summary });
      } else if (message.type === "FILL_APPROVE") {
        const filledCount = await fillApprove(message.values);
        sendResponse({ ok: true, filledCount });
      } else if (message.type === "TRACK_APPLICATION") {
        const record = await createApplication({
          company: message.company,
          role: message.role,
          url: message.url,
        });
        sendResponse({ ok: true, record });
      } else {
        sendResponse({ ok: false, error: "unknown message" });
      }
    } catch (e) {
      sendResponse({ ok: false, error: (e as Error).message });
    }
  })();
  return true;
});

chrome.runtime.onInstalled.addListener(async () => {
  const s = await loadSettings();
  console.log("[job-copilot] installed, api:", s.apiUrl);
});
