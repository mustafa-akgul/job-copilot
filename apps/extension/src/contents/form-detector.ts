// Content script — runs in the page, replies to background messages.
// Responsibilities: SCAN_PAGE, FILL_FIELDS, SHOW_SUGGEST, CLEAR_SUGGEST.

import type { PlasmoCSConfig } from "plasmo";

import { extractAshbyFields } from "~contents/adapters/ashby";
import { extractGreenhouseFields } from "~contents/adapters/greenhouse";
import { extractLeverFields } from "~contents/adapters/lever";
import { extractWorkdayFields } from "~contents/adapters/workday";
import { extractFormFields } from "~lib/dom";
import { detectPlatform } from "~lib/platform-detect";
import { fillMappings } from "~lib/inject";
import type { FieldMapping, FillReport, FormField, RuntimeMessage } from "~types/shared";

export const config: PlasmoCSConfig = {
  matches: ["<all_urls>"],
  run_at: "document_idle",
  all_frames: false,
};

function extractFields(): FormField[] {
  const platform = detectPlatform(location.href);
  switch (platform) {
    case "workday":    return extractWorkdayFields();
    case "greenhouse": return extractGreenhouseFields();
    case "lever":      return extractLeverFields();
    case "ashby":      return extractAshbyFields();
    default:           return extractFormFields();
  }
}

const JC_ATTR = "data-jc-suggest";

function clearSuggestOverlays(): void {
  document.querySelectorAll(`[${JC_ATTR}]`).forEach((el) => el.remove());
}

function injectSuggestOverlay(mapping: FieldMapping): void {
  if (!mapping.value) return;
  const target = document.querySelector(mapping.selector);
  if (!target) return;

  // Remove any existing overlay for this selector.
  document.querySelectorAll(`[${JC_ATTR}]`).forEach((el) => {
    if (el.getAttribute(JC_ATTR) === mapping.selector) el.remove();
  });

  const btn = document.createElement("button");
  btn.setAttribute(JC_ATTR, mapping.selector);
  btn.type = "button";
  btn.title = `Confidence: ${Math.round(mapping.confidence * 100)}%`;
  btn.textContent = `✓ ${mapping.value}`;
  btn.style.cssText = [
    "display:inline-flex",
    "align-items:center",
    "gap:4px",
    "margin-left:6px",
    "padding:2px 8px",
    "background:#2563eb",
    "color:#fff",
    "border:none",
    "border-radius:4px",
    "font-size:11px",
    "font-family:system-ui,-apple-system,sans-serif",
    "cursor:pointer",
    "vertical-align:middle",
    "line-height:1.4",
    "white-space:nowrap",
    "z-index:2147483646",
  ].join(";");

  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    fillMappings([{ ...mapping, tier: "auto" }]);
    btn.remove();
  });

  target.insertAdjacentElement("afterend", btn);
}

chrome.runtime.onMessage.addListener((message: RuntimeMessage, _sender, sendResponse) => {
  if (message.type === "SCAN_PAGE") {
    const fields: FormField[] = extractFields();
    sendResponse({ url: location.href, fields });
    return true;
  }

  if (message.type === "FILL_FIELDS") {
    const report: FillReport = fillMappings(message.mappings);
    sendResponse(report);
    return true;
  }

  if (message.type === "SHOW_SUGGEST") {
    clearSuggestOverlays();
    for (const m of message.mappings) {
      injectSuggestOverlay(m);
    }
    sendResponse({ ok: true, count: message.mappings.length });
    return true;
  }

  if (message.type === "CLEAR_SUGGEST") {
    clearSuggestOverlays();
    sendResponse({ ok: true });
    return true;
  }

  return false;
});
