// In-page DOM reducer — TS port of filling-agent's Playwright JS evaluator.
// Returns only visible, enabled, fillable controls along with resolved labels.

import type { FormField } from "~types/shared";

function isVisible(el: Element): boolean {
  const style = window.getComputedStyle(el);
  if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
    return false;
  }
  const rect = el.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

function labelFor(el: HTMLElement): string | null {
  const labelledBy = el.getAttribute("aria-labelledby");
  if (labelledBy) {
    const parts = labelledBy
      .split(/\s+/)
      .map((id) => document.getElementById(id)?.innerText)
      .filter(Boolean) as string[];
    if (parts.length) return parts.join(" ").trim();
  }
  const aria = el.getAttribute("aria-label");
  if (aria) return aria.trim();
  if (el.id) {
    const explicit = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
    if (explicit) return (explicit as HTMLElement).innerText.trim();
  }
  const wrapping = el.closest("label");
  if (wrapping) return (wrapping as HTMLElement).innerText.trim();
  const prev = el.previousElementSibling as HTMLElement | null;
  if (prev?.innerText && prev.innerText.length < 120) return prev.innerText.trim();
  return null;
}

function stableSelector(el: Element): string {
  const e = el as HTMLElement;
  if (e.id) return `#${CSS.escape(e.id)}`;
  const name = e.getAttribute("name");
  if (name) return `${e.tagName.toLowerCase()}[name="${CSS.escape(name)}"]`;
  const parent = el.parentElement;
  if (!parent) return el.tagName.toLowerCase();
  const same = [...parent.children].filter((c) => c.tagName === el.tagName);
  const idx = same.indexOf(el) + 1;
  return `${stableSelector(parent)} > ${el.tagName.toLowerCase()}:nth-of-type(${idx})`;
}

export function extractFormFields(root: ParentNode = document): FormField[] {
  const fields: FormField[] = [];
  const selector = 'input, textarea, select, [contenteditable="true"]';
  for (const el of Array.from(root.querySelectorAll(selector))) {
    const node = el as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | HTMLElement;
    if ((node as HTMLInputElement).disabled || (node as HTMLInputElement).readOnly) continue;
    if (!isVisible(node)) continue;
    const tag = node.tagName.toLowerCase();
    const type = ((node as HTMLInputElement).type || "").toLowerCase();
    if (tag === "input" && ["hidden", "submit", "button", "reset", "image"].includes(type)) continue;

    let kind: FormField["kind"] = "text";
    if (tag === "textarea") kind = "textarea";
    else if (tag === "select") kind = "select";
    else if (node.hasAttribute("contenteditable")) kind = "contenteditable";
    else if (type === "checkbox") kind = "checkbox";
    else if (type === "radio") kind = "radio";
    else if (type === "file") kind = "file";

    const field: FormField = {
      selector: stableSelector(node),
      kind,
      input_type: tag === "input" ? type : null,
      name: (node as HTMLInputElement).name || null,
      id: node.id || null,
      label: labelFor(node as HTMLElement),
      placeholder: (node as HTMLInputElement).placeholder || null,
      required:
        (node as HTMLInputElement).required ||
        node.getAttribute("aria-required") === "true",
      options: [],
      group: kind === "radio" ? (node as HTMLInputElement).name || null : null,
      value: (node as HTMLInputElement).value || null,
    };

    if (kind === "select") {
      const sel = node as HTMLSelectElement;
      for (const opt of Array.from(sel.options)) {
        field.options.push({ value: opt.value, label: (opt.textContent || "").trim() });
      }
    }
    fields.push(field);
  }
  return fields;
}
