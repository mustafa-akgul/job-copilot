// Lever ATS adapter — clean standard HTML with .application-field wrappers.

import type { FormField } from "~types/shared";
import { extractFormFields } from "~lib/dom";

export function extractLeverFields(): FormField[] {
  // Lever uses standard HTML inputs inside .application-field containers.
  // The generic extractor covers most fields; we scope it to the application
  // section to avoid noise from the job description area.
  const root =
    document.querySelector(".application-form, form[id*='application']") ??
    document;
  return extractFormFields(root);
}
