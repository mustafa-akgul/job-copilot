// Hand-maintained mirror of apps/backend schemas.
// Phase 1 will codegen this from the FastAPI OpenAPI spec (openapi-typescript).

export type FieldKind =
  | "text"
  | "textarea"
  | "select"
  | "checkbox"
  | "radio"
  | "file"
  | "contenteditable";

export interface SelectOption {
  value: string;
  label: string;
}

export interface FormField {
  selector: string;
  kind: FieldKind;
  input_type: string | null;
  name: string | null;
  id: string | null;
  label: string | null;
  placeholder: string | null;
  required: boolean;
  options: SelectOption[];
  group: string | null;
  value: string | null;
}

export type Tier = "auto" | "suggest" | "approve" | "skip";
export type MappingSource = "fuzzy" | "llm" | "user" | "dummy" | "skip";

export interface FieldMapping {
  selector: string;
  json_path: string | null;
  value: string | null;
  confidence: number;
  tier: Tier;
  source: MappingSource;
  rationale: string | null;
}

export interface MapRequest {
  persona: string;
  page_url?: string;
  fields: FormField[];
}

export interface MapResponse {
  mappings: FieldMapping[];
  unresolved: string[];
}

// Mirror of CVProfile — keep in sync with apps/backend/.../schemas/cv_profile.py.
export interface CVProfile {
  schema_version: string;
  persona: string;
  personal_info: {
    first_name?: string | null;
    last_name?: string | null;
    full_name?: string | null;
    email?: string | null;
    phone?: string | null;
    headline?: string | null;
    summary?: string | null;
  };
  social_links: {
    linkedin?: string | null;
    github?: string | null;
    portfolio?: string | null;
    website?: string | null;
  };
  education: unknown[];
  work_experience: unknown[];
  projects: unknown[];
  skills: {
    technical: string[];
    tools: string[];
    frameworks: string[];
    soft: string[];
  };
  preferences: Record<string, unknown>;
  custom_responses: unknown[];
}

// ── Phase 3 — Personas ────────────────────────────────────────────────────────

export interface PersonaMeta {
  persona: string;
  display_name: string | null;
  skill_count: number;
  job_count: number;
  education_count: number;
}

export interface PersonaCloneRequest {
  new_persona: string;
}

// ── Phase 3 — JD Analysis ─────────────────────────────────────────────────────

export interface JDAnalyzeRequest {
  jd_text: string;
  persona: string;
}

export interface JDAnalysis {
  required_skills: string[];
  nice_to_have: string[];
  keywords: string[];
  match_score: number;
  matching_skills: string[];
  missing_skills: string[];
  experience_required: string | null;
  summary: string;
}

// ── Phase 4 — Cover Letter ────────────────────────────────────────────────────

export type CoverLetterTone = "professional" | "enthusiastic" | "concise";

export interface GenerateRequest {
  persona: string;
  jd_text: string;
  tone?: CoverLetterTone;
  max_words?: number;
}

export interface GenerateResponse {
  content: string;
  word_count: number;
}

// ── Phase 5 — Relevant Sections ───────────────────────────────────────────────

export interface RelevantSection {
  content: string;
}

// ── Message protocol between content script ↔ background ↔ popup ─────────────
export type RuntimeMessage =
  | { type: "SCAN_PAGE" }
  | { type: "FILL_FIELDS"; mappings: FieldMapping[] }
  | { type: "SCAN_AND_FILL"; persona: string }
  | { type: "FILL_APPROVE"; values: { selector: string; value: string }[] }
  | { type: "SHOW_SUGGEST"; mappings: FieldMapping[] }
  | { type: "CLEAR_SUGGEST" }
  | { type: "STATUS_UPDATE"; step: string; detail?: string }
  | { type: "SIGN_IN" }
  | { type: "SIGN_OUT" }
  | { type: "TRACK_APPLICATION"; company: string; role: string; url: string | null };

export interface ScanResult {
  url: string;
  fields: FormField[];
}

export interface FillReport {
  filled: string[];
  skipped: { selector: string; reason: string }[];
}

export interface ScanSummary {
  scanned: number;
  mapped: number;
  filled: number;
  skipped: number;
  unresolved: number;
  approveMappings: FieldMapping[];
  suggestCount: number;
  // Source breakdown — used to show "local match vs AI" trust signal.
  localMatchCount: number;
  aiMatchCount: number;
  // Page context — used to pre-fill the application tracker.
  pageTitle: string;
  pageUrl: string;
}

export type ApplicationStatus =
  | "applied"
  | "screening"
  | "interview"
  | "offer"
  | "rejected"
  | "withdrawn";

export interface ApplicationRecord {
  id: string;
  company: string;
  role: string;
  url: string | null;
  status: ApplicationStatus;
  filled_at: string; // ISO datetime
  notes: string | null;
}
