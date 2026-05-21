// Workday ATS adapter — extracts form fields from Workday's custom components.
//
// Workday uses data-automation-id attributes extensively.
// Inputs are wrapped in custom web components; standard selectors often miss them.

import type { FormField } from "~types/shared";

const LABEL_MAP: Record<string, string> = {
  "input-legalNameSection_firstName": "First Name",
  "input-legalNameSection_lastName": "Last Name",
  "input-email": "Email",
  "input-phone-number": "Phone",
  "input-addressSection_addressLine1": "Street Address",
  "input-addressSection_city": "City",
  "input-addressSection_countryRegion": "State",
  "input-addressSection_postalCode": "Postal Code",
  "input-addressSection_country": "Country",
  "input-linkedin": "LinkedIn",
  "input-portfolio": "Portfolio",
  "input-website": "Website",
  "input-howDidYouHearAboutUs": "How did you hear about us",
  "input-coverLetter": "Cover Letter",
};

function stableSelector(el: Element): string {
  const autoId = el.getAttribute("data-automation-id");
  if (autoId) return `[data-automation-id="${autoId}"]`;
  const id = (el as HTMLElement).id;
  if (id) return `#${CSS.escape(id)}`;
  const name = el.getAttribute("name");
  if (name) return `${el.tagName.toLowerCase()}[name="${CSS.escape(name)}"]`;
  const parent = el.parentElement;
  if (!parent) return el.tagName.toLowerCase();
  const same = [...parent.children].filter((c) => c.tagName === el.tagName);
  const idx = same.indexOf(el) + 1;
  return `${stableSelector(parent)} > ${el.tagName.toLowerCase()}:nth-of-type(${idx})`;
}

function labelFromAutoId(autoId: string | null): string | null {
  if (!autoId) return null;
  return LABEL_MAP[autoId] ?? autoId.replace(/^input-/, "").replace(/[-_]/g, " ");
}

export function extractWorkdayFields(): FormField[] {
  const fields: FormField[] = [];

  // Workday uses both standard inputs and custom components.
  const selector = 'input:not([type="hidden"]):not([type="submit"]), textarea, select, [data-automation-id*="input"]';

  for (const el of Array.from(document.querySelectorAll(selector))) {
    const node = el as HTMLInputElement;
    if (node.disabled || node.readOnly) continue;

    const style = window.getComputedStyle(node);
    if (style.display === "none" || style.visibility === "hidden") continue;
    const rect = node.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) continue;

    const autoId = node.getAttribute("data-automation-id");
    const tag = node.tagName.toLowerCase();
    const type = (node.type || "").toLowerCase();
    if (tag === "input" && ["hidden", "submit", "button", "reset"].includes(type)) continue;

    const label =
      labelFromAutoId(autoId) ||
      (() => {
        const la = node.getAttribute("aria-label");
        if (la) return la;
        if (node.id) {
          const lEl = document.querySelector(`label[for="${CSS.escape(node.id)}"]`);
          if (lEl) return (lEl as HTMLElement).innerText.trim();
        }
        const lEl = node.closest("label");
        if (lEl) return (lEl as HTMLElement).innerText.trim();
        return null;
      })();

    let kind: FormField["kind"] = "text";
    if (tag === "textarea") kind = "textarea";
    else if (tag === "select") kind = "select";
    else if (type === "checkbox") kind = "checkbox";
    else if (type === "radio") kind = "radio";
    else if (type === "file") kind = "file";

    const field: FormField = {
      selector: stableSelector(node),
      kind,
      input_type: tag === "input" ? type : null,
      name: node.name || null,
      id: node.id || null,
      label,
      placeholder: node.placeholder || null,
      required: node.required || node.getAttribute("aria-required") === "true",
      options: [],
      group: kind === "radio" ? (node.name || null) : null,
      value: node.value || null,
    };

    if (kind === "select") {
      const sel = node as unknown as HTMLSelectElement;
      for (const opt of Array.from(sel.options)) {
        field.options.push({ value: opt.value, label: (opt.textContent || "").trim() });
      }
    }

    fields.push(field);
  }

  return fields;
}
