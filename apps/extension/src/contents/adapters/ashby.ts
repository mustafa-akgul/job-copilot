// Ashby ATS adapter — React-heavy forms with test-id attributes.

import type { FormField } from "~types/shared";
import { extractFormFields } from "~lib/dom";

const TESTID_LABELS: Record<string, string> = {
  "first-name-input": "First Name",
  "last-name-input": "Last Name",
  "email-input": "Email",
  "phone-input": "Phone",
  "linkedin-input": "LinkedIn",
  "website-input": "Website",
  "resume-upload": "Resume",
  "cover-letter-input": "Cover Letter",
};

function enrichFromTestId(field: FormField): FormField {
  const el = document.querySelector(field.selector);
  if (!el) return field;
  const testId = el.getAttribute("data-testid");
  if (testId && TESTID_LABELS[testId]) {
    return { ...field, label: TESTID_LABELS[testId] };
  }
  return field;
}

export function extractAshbyFields(): FormField[] {
  const root =
    document.querySelector("[data-ashby-job], .ashby-job-posting-form, main form") ??
    document;
  const fields = extractFormFields(root);
  return fields.map(enrichFromTestId);
}
