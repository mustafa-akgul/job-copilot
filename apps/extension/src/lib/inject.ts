// Native-event injection so React/Vue controlled components register input.
// Same trick as filling-agent's Playwright injector, but in-page.

import type { FieldMapping, FillReport } from "~types/shared";

function nativeSetValue(el: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const proto =
    el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
  if (setter) setter.call(el, value);
  else el.value = value;
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  el.dispatchEvent(new Event("blur", { bubbles: true }));
}

function flashGreen(el: HTMLElement): void {
  const prev = el.style.cssText;
  el.style.transition = "background-color 0.2s ease";
  el.style.backgroundColor = "#bbf7d0";
  setTimeout(() => {
    el.style.backgroundColor = "#d1fae5";
    setTimeout(() => {
      el.style.cssText = prev;
    }, 1200);
  }, 200);
}

export function fillMappings(mappings: FieldMapping[]): FillReport {
  const filled: string[] = [];
  const skipped: { selector: string; reason: string }[] = [];

  for (const m of mappings) {
    if (m.tier === "skip" || m.value == null) {
      skipped.push({ selector: m.selector, reason: m.tier === "skip" ? "skip-tier" : "no-value" });
      continue;
    }
    if (m.tier !== "auto") {
      skipped.push({ selector: m.selector, reason: `tier=${m.tier}` });
      continue;
    }

    const el = document.querySelector(m.selector) as HTMLElement | null;
    if (!el) {
      skipped.push({ selector: m.selector, reason: "not-found" });
      continue;
    }
    try {
      const tag = el.tagName.toLowerCase();
      if (tag === "input" || tag === "textarea") {
        nativeSetValue(el as HTMLInputElement, String(m.value));
        flashGreen(el);
      } else if (tag === "select") {
        const sel = el as HTMLSelectElement;
        const target = Array.from(sel.options).find(
          (o) => o.value === m.value || o.textContent?.trim() === m.value,
        );
        if (target) {
          sel.value = target.value;
          sel.dispatchEvent(new Event("change", { bubbles: true }));
          flashGreen(el);
        }
      } else if (el.isContentEditable) {
        el.innerText = String(m.value);
        el.dispatchEvent(new Event("input", { bubbles: true }));
        flashGreen(el);
      } else {
        skipped.push({ selector: m.selector, reason: `unsupported-tag-${tag}` });
        continue;
      }
      filled.push(m.selector);
    } catch (e) {
      skipped.push({ selector: m.selector, reason: `error: ${(e as Error).message}` });
    }
  }
  return { filled, skipped };
}
