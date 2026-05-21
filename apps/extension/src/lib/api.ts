// Thin fetch wrapper. Runs in background SW (no CORS issues).

import type {
  ApplicationRecord,
  CVProfile,
  GenerateRequest,
  GenerateResponse,
  JDAnalysis,
  JDAnalyzeRequest,
  MapRequest,
  MapResponse,
  PersonaMeta,
} from "~types/shared";
import { loadSettings } from "~lib/settings";
import { clearSession, getValidAccessToken } from "~lib/auth";

async function authedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const { apiUrl } = await loadSettings();
  const token = await getValidAccessToken();
  if (!token) throw new Error("Not signed in. Please sign in to continue.");

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const r = await fetch(`${apiUrl}${path}`, { ...init, headers });

  if (r.status === 401) {
    // Token expired and silent refresh already failed in getValidAccessToken — force re-login.
    await clearSession();
    throw new Error("Session expired. Please sign in again.");
  }

  return r;
}

export async function checkHealth(): Promise<boolean> {
  try {
    const { apiUrl } = await loadSettings();
    const r = await fetch(`${apiUrl}/health`);
    return r.ok;
  } catch {
    return false;
  }
}

export async function mapFields(req: MapRequest): Promise<MapResponse> {
  const r = await authedFetch("/api/v1/forms/map", {
    method: "POST",
    body: JSON.stringify(req),
  });
  if (!r.ok) throw new Error(`map failed: ${r.status} ${await r.text()}`);
  return r.json();
}

export async function uploadCv(file: File, persona: string): Promise<CVProfile> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await authedFetch(
    `/api/v1/cv/parse?persona=${encodeURIComponent(persona)}`,
    { method: "POST", body: fd },
  );
  if (!r.ok) throw new Error(await friendlyError(r, "Upload failed"));
  return r.json();
}

export async function getProfile(persona: string): Promise<CVProfile | null> {
  const r = await authedFetch(`/api/v1/profiles/${encodeURIComponent(persona)}`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(await friendlyError(r, "Could not load profile"));
  return r.json();
}

export async function createApplication(data: {
  company: string;
  role: string;
  url: string | null;
  notes?: string;
}): Promise<ApplicationRecord> {
  const r = await authedFetch("/api/v1/applications", {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (!r.ok) throw new Error(await friendlyError(r, "Could not save application"));
  return r.json();
}

export async function listApplications(limit = 10): Promise<ApplicationRecord[]> {
  const r = await authedFetch(`/api/v1/applications?limit=${limit}`);
  if (!r.ok) return [];
  return r.json();
}

export async function updateApplication(
  id: string,
  patch: { status?: string; notes?: string },
): Promise<ApplicationRecord> {
  const r = await authedFetch(`/api/v1/applications/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(await friendlyError(r, "Could not update application"));
  return r.json();
}

export async function deleteApplication(id: string): Promise<void> {
  await authedFetch(`/api/v1/applications/${id}`, { method: "DELETE" });
}

// ── Phase 3 — Personas ────────────────────────────────────────────────────────

export async function listPersonas(): Promise<PersonaMeta[]> {
  const r = await authedFetch("/api/v1/personas");
  if (!r.ok) return [];
  return r.json();
}

export async function clonePersona(persona: string, newPersona: string): Promise<CVProfile> {
  const r = await authedFetch(`/api/v1/personas/${encodeURIComponent(persona)}/clone`, {
    method: "POST",
    body: JSON.stringify({ new_persona: newPersona }),
  });
  if (!r.ok) throw new Error(await friendlyError(r, "Could not clone persona"));
  return r.json();
}

// ── Phase 3 — JD Analysis ─────────────────────────────────────────────────────

export async function analyzeJd(req: JDAnalyzeRequest): Promise<JDAnalysis> {
  const r = await authedFetch("/api/v1/jd/analyze", {
    method: "POST",
    body: JSON.stringify(req),
  });
  if (!r.ok) throw new Error(await friendlyError(r, "JD analysis failed"));
  return r.json();
}

// ── Phase 4 — Cover Letter ────────────────────────────────────────────────────

export async function generateCoverLetter(req: GenerateRequest): Promise<GenerateResponse> {
  const r = await authedFetch("/api/v1/ai/generate", {
    method: "POST",
    body: JSON.stringify(req),
  });
  if (!r.ok) throw new Error(await friendlyError(r, "Cover letter generation failed"));
  return r.json();
}

async function friendlyError(r: Response, fallback: string): Promise<string> {
  try {
    const data = await r.json();
    if (typeof data?.detail === "string") return data.detail;
  } catch {
    /* ignore */
  }
  return `${fallback} (HTTP ${r.status})`;
}
