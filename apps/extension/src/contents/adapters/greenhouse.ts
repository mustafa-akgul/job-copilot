// Greenhouse ATS adapter — standard HTML forms with predictable id/name patterns.

import type { FormField } from "~types/shared";
import { extractFormFields } from "~lib/dom";

// Greenhouse uses predictable field IDs. Map them to human-readable labels.
const ID_LABEL_MAP: Record<string, string> = {
  first_name: "First Name",
  last_name: "Last Name",
  email: "Email",
  phone: "Phone",
  resume: "Resume",
  cover_letter: "Cover Letter",
  linkedin_profile: "LinkedIn",
  website: "Website",
  "question_[0-9]+": "Custom Question",
};

function enrichLabel(field: FormField): FormField {
  if (field.id && ID_LABEL_MAP[field.id]) {
    return { ...field, label: ID_LABEL_MAP[field.id] };
  }
  if (field.name && ID_LABEL_MAP[field.name]) {
    return { ...field, label: ID_LABEL_MAP[field.name] };
  }
  return field;
}

export function extractGreenhouseFields(): FormField[] {
  // Greenhouse uses standard HTML — the generic extractor works well.
  // We just enrich labels using known ID patterns.
  const fields = extractFormFields(
    document.querySelector("#application") ?? document,
  );
  return fields.map(enrichLabel);
}
