// Toolbar popup — phases:
//   loading → unauthenticated → signing-in → ready (no profile) → ready (profile)

import { useCallback, useEffect, useRef, useState } from "react";

import {
  analyzeJd,
  generateCoverLetter,
  getProfile,
  listApplications,
  listPersonas,
  updateApplication,
  uploadCv,
} from "~lib/api";
import { clearSession, getSession, type AuthSession } from "~lib/auth";
import { loadSettings, saveSettings } from "~lib/settings";
import type {
  ApplicationRecord,
  ApplicationStatus,
  CVProfile,
  CoverLetterTone,
  FieldMapping,
  JDAnalysis,
  PersonaMeta,
  RuntimeMessage,
  ScanSummary,
} from "~types/shared";

type AppPhase = "loading" | "unauthenticated" | "signing-in" | "ready" | "error";

function sendBg<T>(message: RuntimeMessage): Promise<T> {
  return new Promise((resolve, reject) =>
    chrome.runtime.sendMessage(message, (r) => {
      if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
      else resolve(r as T);
    }),
  );
}

const PATH_LABELS: Record<string, string> = {
  "personal_info.first_name": "First Name",
  "personal_info.last_name": "Last Name",
  "personal_info.full_name": "Full Name",
  "personal_info.email": "Email",
  "personal_info.phone": "Phone",
  "personal_info.headline": "Headline",
  "personal_info.summary": "About Me",
  "personal_info.address.street": "Street",
  "personal_info.address.city": "City",
  "personal_info.address.state": "State",
  "personal_info.address.postal_code": "Postal Code",
  "personal_info.address.country": "Country",
  "social_links.linkedin": "LinkedIn",
  "social_links.github": "GitHub",
  "social_links.portfolio": "Portfolio",
  "social_links.website": "Website",
  "preferences.expected_salary": "Expected Salary",
  "preferences.notice_period": "Notice Period",
  "preferences.available_start_date": "Start Date",
  "preferences.willing_to_relocate": "Willing to Relocate",
  "preferences.requires_visa_sponsorship": "Visa Sponsorship",
  "preferences.work_authorization": "Work Authorization",
  "preferences.preferred_work_mode": "Work Mode",
};

function fieldLabel(m: FieldMapping): string {
  if (m.json_path && PATH_LABELS[m.json_path]) return PATH_LABELS[m.json_path];
  if (m.json_path) {
    const segment = m.json_path.split(".").pop() ?? m.json_path;
    return segment.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return m.selector;
}

// Simple heuristic: extract role/company from common job board title patterns.
function parsePageTitle(title: string): { role: string; company: string } {
  // "Role at Company | LinkedIn" or "Role at Company - Greenhouse"
  const atMatch = title.match(/^(.+?)\s+at\s+(.+?)(?:\s*[-|–]|$)/i);
  if (atMatch) return { role: atMatch[1].trim(), company: atMatch[2].trim() };
  // "Role - Company - Board" or "Company - Role"
  const cleaned = title.replace(/\s*[-|]\s*(LinkedIn|Greenhouse|Lever|Workday|Ashby|Indeed|Glassdoor|Wellfound).*$/i, "").trim();
  const dashMatch = cleaned.match(/^(.+?)\s*[-–]\s*(.+)$/);
  if (dashMatch) return { role: dashMatch[1].trim(), company: dashMatch[2].trim() };
  return { role: cleaned.slice(0, 60), company: "" };
}

// ── Design tokens ─────────────────────────────────────────────────────────────
const C = {
  brand: "#2563eb",
  brandBg: "#eff6ff",
  brandBorder: "#bfdbfe",
  text: "#111827",
  mute: "#6b7280",
  muteBg: "#f3f4f6",
  line: "#e5e7eb",
  bg: "#ffffff",
  surface: "#f9fafb",
  ok: "#059669",
  okBg: "#d1fae5",
  okText: "#065f46",
  warn: "#d97706",
  warnBg: "#fef3c7",
  warnText: "#92400e",
  bad: "#dc2626",
  badBg: "#fee2e2",
  badText: "#991b1b",
};

const S = {
  root: {
    width: 360,
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    color: C.text,
    background: C.bg,
  } as const,
  header: {
    padding: "11px 14px",
    borderBottom: `1px solid ${C.line}`,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  } as const,
  body: { padding: 16 } as const,
  primaryBtn: {
    width: "100%",
    padding: "11px 14px",
    border: "none",
    borderRadius: 9,
    background: C.brand,
    color: "#fff",
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 600,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  } as const,
  ghostBtn: {
    background: "transparent",
    border: `1px solid ${C.line}`,
    borderRadius: 6,
    color: C.mute,
    cursor: "pointer",
    fontSize: 11,
    padding: "3px 9px",
  } as const,
  card: {
    border: `1px solid ${C.line}`,
    borderRadius: 10,
    padding: "12px 14px",
    background: C.surface,
  } as const,
  input: {
    width: "100%",
    padding: "7px 9px",
    border: `1px solid ${C.line}`,
    borderRadius: 6,
    fontSize: 12,
    color: C.text,
    boxSizing: "border-box" as const,
    outline: "none",
  } as const,
};

// ── Primitives ────────────────────────────────────────────────────────────────
function Spinner({ size = 14 }: { size?: number }) {
  return (
    <>
      <span style={{ display: "inline-block", width: size, height: size, animation: "spin 0.75s linear infinite", fontSize: size }}>⟳</span>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  );
}

function Chip({ label, bg, color }: { label: string; bg: string; color: string }) {
  return (
    <span style={{ background: bg, color, padding: "3px 9px", borderRadius: 999, fontSize: 11, fontWeight: 600, whiteSpace: "nowrap" as const }}>
      {label}
    </span>
  );
}

// ── Sign in ───────────────────────────────────────────────────────────────────
function SignIn({ busy, onSignIn }: { busy: boolean; onSignIn: () => void }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div>
        <div style={{ fontSize: 18, fontWeight: 800, marginBottom: 5 }}>Welcome to Job Copilot</div>
        <div style={{ fontSize: 13, color: C.mute, lineHeight: 1.6 }}>
          Fill any job application form in one click — powered by your CV.
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        {[
          { n: 1, title: "Sign in with Google", sub: "One click, no password" },
          { n: 2, title: "Upload your CV once", sub: "We parse and save your profile" },
          { n: 3, title: "Click Fill on any job form", sub: "LinkedIn, Greenhouse, Workday, Lever…" },
        ].map(({ n, title, sub }) => (
          <div key={n} style={{ display: "flex", gap: 12, alignItems: "flex-start", padding: "8px 0", borderBottom: n < 3 ? `1px solid ${C.line}` : "none" }}>
            <span style={{ flexShrink: 0, width: 24, height: 24, borderRadius: 12, background: n === 1 ? C.brand : C.muteBg, color: n === 1 ? "#fff" : C.mute, fontSize: 12, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center" }}>
              {n}
            </span>
            <div>
              <div style={{ fontSize: 13, fontWeight: n === 1 ? 700 : 600, color: n === 1 ? C.text : C.mute }}>{title}</div>
              <div style={{ fontSize: 11, color: C.mute, marginTop: 1 }}>{sub}</div>
            </div>
          </div>
        ))}
      </div>
      <button style={{ ...S.primaryBtn, opacity: busy ? 0.75 : 1 }} disabled={busy} onClick={onSignIn}>
        {busy ? <><Spinner /> Signing in…</> : "Sign in with Google"}
      </button>
    </div>
  );
}

// ── Onboarding (CV upload) ────────────────────────────────────────────────────
function Onboarding({ busy, onPick }: { busy: boolean; onPick: (f: File) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <div style={{ fontSize: 16, fontWeight: 800, marginBottom: 4 }}>Upload your CV</div>
        <div style={{ fontSize: 13, color: C.mute, lineHeight: 1.6 }}>
          Parsed once, used everywhere. No manual re-entry ever again.
        </div>
      </div>
      <input ref={ref} type="file" accept=".pdf,.docx,.txt,.md" style={{ display: "none" }}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onPick(f); e.target.value = ""; }} />
      <div>
        <button style={{ ...S.primaryBtn, opacity: busy ? 0.75 : 1 }} disabled={busy} onClick={() => ref.current?.click()}>
          {busy ? <><Spinner /> Parsing your CV…</> : "📄  Upload your CV"}
        </button>
        <div style={{ marginTop: 6, textAlign: "center" as const, fontSize: 11, color: C.mute }}>
          {busy ? "Usually takes 5–10 seconds." : "PDF, DOCX, or plain text (.txt)"}
        </div>
      </div>
    </div>
  );
}

// ── [Feature 1] CV parse success ──────────────────────────────────────────────
function CVParseSuccess({ profile, onContinue }: { profile: CVProfile; onContinue: () => void }) {
  const pi = profile.personal_info;
  const name = pi.full_name || `${pi.first_name ?? ""} ${pi.last_name ?? ""}`.trim() || "Your Profile";
  const latestJob = (profile.work_experience as any[])[0];
  const topSkills = [...profile.skills.technical, ...profile.skills.frameworks].slice(0, 5);
  const extraSkills = profile.skills.technical.length + profile.skills.frameworks.length - topSkills.length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Success header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 40, height: 40, borderRadius: 20, background: C.okBg, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, flexShrink: 0 }}>
          ✓
        </div>
        <div>
          <div style={{ fontWeight: 800, fontSize: 16, color: C.ok }}>CV parsed!</div>
          <div style={{ fontSize: 12, color: C.mute }}>Your profile is ready to fill any form</div>
        </div>
      </div>

      {/* Profile card */}
      <div style={{ ...S.card, gap: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 13 }}>{name}</div>
        {pi.email && <div style={{ fontSize: 11, color: C.mute, marginTop: 1 }}>{pi.email}</div>}

        {latestJob && (
          <div style={{ fontSize: 12, color: C.text, marginTop: 8, paddingTop: 8, borderTop: `1px solid ${C.line}` }}>
            <span style={{ color: C.mute }}>Most recent: </span>
            {latestJob.title} at {latestJob.company}
          </div>
        )}

        <div style={{ fontSize: 11, color: C.mute, marginTop: 4 }}>
          {(profile.work_experience as any[]).length > 0 && `${(profile.work_experience as any[]).length} jobs`}
          {(profile.education as any[]).length > 0 && ` · ${(profile.education as any[]).length} education`}
          {(profile.skills.technical.length + profile.skills.frameworks.length + profile.skills.tools.length) > 0 &&
            ` · ${profile.skills.technical.length + profile.skills.frameworks.length + profile.skills.tools.length} skills`}
        </div>

        {topSkills.length > 0 && (
          <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap" as const, gap: 4 }}>
            {topSkills.map((s) => (
              <span key={s} style={{ background: C.brandBg, color: C.brand, padding: "2px 8px", borderRadius: 999, fontSize: 11, fontWeight: 500 }}>
                {s}
              </span>
            ))}
            {extraSkills > 0 && (
              <span style={{ fontSize: 11, color: C.mute, padding: "2px 4px" }}>+{extraSkills} more</span>
            )}
          </div>
        )}
      </div>

      <button style={S.primaryBtn} onClick={onContinue}>
        ⚡  Fill your first job form →
      </button>
    </div>
  );
}

// ── Profile strip ─────────────────────────────────────────────────────────────
function ProfileStrip({ profile, busy, onReplace }: { profile: CVProfile; busy: boolean; onReplace: (f: File) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  const pi = profile.personal_info;
  const name = pi.full_name || `${pi.first_name ?? ""} ${pi.last_name ?? ""}`.trim() || "Your Profile";
  const skills = profile.skills.technical.length + profile.skills.frameworks.length + profile.skills.tools.length;
  return (
    <div style={{ ...S.card, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 13, whiteSpace: "nowrap" as const, overflow: "hidden", textOverflow: "ellipsis" }}>{name}</div>
        <div style={{ fontSize: 11, color: C.mute, marginTop: 1, display: "flex", gap: 6 }}>
          {pi.email && <span>{pi.email}</span>}
          {skills > 0 && <span>· {skills} skills</span>}
          {(profile.work_experience as any[]).length > 0 && <span>· {(profile.work_experience as any[]).length} jobs</span>}
        </div>
      </div>
      <input ref={ref} type="file" accept=".pdf,.docx,.txt,.md" style={{ display: "none" }}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onReplace(f); e.target.value = ""; }} />
      <button style={S.ghostBtn} disabled={busy} onClick={() => ref.current?.click()}>
        {busy ? "…" : "Replace"}
      </button>
    </div>
  );
}

// ── [Feature 2] Fill progress with step list ──────────────────────────────────
function FillProgress({ steps }: { steps: string[] }) {
  return (
    <div style={{ ...S.card, background: C.brandBg, borderColor: C.brandBorder }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: steps.length > 1 ? 8 : 0 }}>
        <Spinner size={16} />
        <div style={{ fontSize: 13, fontWeight: 600, color: C.brand }}>{steps[steps.length - 1] ?? "Working…"}</div>
      </div>
      {steps.length > 1 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 3, paddingLeft: 26 }}>
          {steps.slice(0, -1).map((s, i) => (
            <div key={i} style={{ fontSize: 11, color: C.mute }}>✓ {s}</div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── [Feature 3] Fill summary with source breakdown ────────────────────────────
function FillSummary({ s }: { s: ScanSummary }) {
  const total = s.filled + s.suggestCount + s.approveMappings.length;
  const hasSource = s.localMatchCount + s.aiMatchCount > 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: C.mute, textTransform: "uppercase" as const, letterSpacing: 0.5 }}>
        Result — {s.scanned} fields scanned
      </div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" as const }}>
        {s.filled > 0 && <Chip label={`✓ ${s.filled} filled`} bg={C.okBg} color={C.okText} />}
        {s.suggestCount > 0 && <Chip label={`${s.suggestCount} suggested`} bg={C.warnBg} color={C.warnText} />}
        {s.approveMappings.length > 0 && <Chip label={`${s.approveMappings.length} need input`} bg={C.badBg} color={C.badText} />}
        {total === 0 && <span style={{ color: C.mute, fontSize: 12 }}>No fillable fields found on this page.</span>}
      </div>

      {/* [Feature 3] Local vs AI source breakdown */}
      {hasSource && (
        <div style={{ fontSize: 11, color: C.mute, display: "flex", gap: 10, paddingTop: 2 }}>
          {s.localMatchCount > 0 && (
            <span title="Matched instantly without AI — zero latency">
              ⚡ {s.localMatchCount} instant match
            </span>
          )}
          {s.aiMatchCount > 0 && (
            <span title="Matched by AI — semantic understanding">
              🤖 {s.aiMatchCount} AI match
            </span>
          )}
        </div>
      )}

      {s.suggestCount > 0 && (
        <div style={{ fontSize: 11, color: C.mute }}>Click the blue ✓ buttons next to fields to accept suggestions.</div>
      )}
      {s.filled > 0 && (
        <div style={{ fontSize: 11, color: C.ok }}>Fields filled with a green flash — check the page.</div>
      )}
    </div>
  );
}

// ── HITL card ─────────────────────────────────────────────────────────────────
function HITLCard({ mappings, onSubmit, busy }: {
  mappings: FieldMapping[];
  onSubmit: (values: { selector: string; value: string }[]) => void;
  busy: boolean;
}) {
  const [vals, setVals] = useState<Record<string, string>>(() =>
    Object.fromEntries(mappings.map((m) => [m.selector, m.value ?? ""])),
  );
  const ready = Object.values(vals).filter((v) => v.trim()).length;
  return (
    <div style={{ ...S.card, borderColor: "#fca5a5", background: "#fff7f7" }}>
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10, color: C.bad }}>These fields need your input</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {mappings.map((m) => (
          <div key={m.selector}>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, marginBottom: 3 }}>{fieldLabel(m)}</label>
            <input value={vals[m.selector] ?? ""} placeholder="Type a value…"
              onChange={(e) => setVals((p) => ({ ...p, [m.selector]: e.target.value }))}
              style={S.input} />
          </div>
        ))}
      </div>
      <button
        style={{ ...S.primaryBtn, marginTop: 12, background: ready > 0 ? C.bad : C.muteBg, color: ready > 0 ? "#fff" : C.mute }}
        disabled={busy || ready === 0}
        onClick={() => onSubmit(Object.entries(vals).filter(([, v]) => v.trim()).map(([selector, value]) => ({ selector, value })))}
      >
        {busy ? <><Spinner /> Filling…</> : `Fill ${ready} field${ready !== 1 ? "s" : ""}`}
      </button>
    </div>
  );
}

// ── [Feature 4] Track application card ───────────────────────────────────────
function TrackApplicationCard({ pageTitle, pageUrl, onSave, onSkip, saving }: {
  pageTitle: string;
  pageUrl: string;
  onSave: (company: string, role: string) => void;
  onSkip: () => void;
  saving: boolean;
}) {
  const parsed = parsePageTitle(pageTitle);
  const [company, setCompany] = useState(parsed.company);
  const [role, setRole] = useState(parsed.role);

  return (
    <div style={{ ...S.card, borderColor: C.brandBorder, background: C.brandBg }}>
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, color: C.brand }}>Track this application?</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <input value={role} onChange={(e) => setRole(e.target.value)} placeholder="Role (e.g. Software Engineer)" style={S.input} />
        <input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Company" style={S.input} />
      </div>
      <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
        <button
          style={{ ...S.primaryBtn, flex: 1, padding: "8px 12px", fontSize: 12, opacity: saving ? 0.75 : 1 }}
          disabled={saving || (!company.trim() && !role.trim())}
          onClick={() => onSave(company.trim(), role.trim())}
        >
          {saving ? <><Spinner size={12} /> Saving…</> : "Save to tracker"}
        </button>
        <button style={{ ...S.ghostBtn, flexShrink: 0 }} onClick={onSkip}>Skip</button>
      </div>
    </div>
  );
}

// ── [Feature 4] Applications history ─────────────────────────────────────────
const STATUS_LABELS: Record<ApplicationStatus, string> = {
  applied: "Applied",
  screening: "Screening",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

const STATUS_STYLE: Record<ApplicationStatus, { bg: string; color: string }> = {
  applied: { bg: C.muteBg, color: C.mute },
  screening: { bg: C.warnBg, color: C.warnText },
  interview: { bg: C.brandBg, color: C.brand },
  offer: { bg: C.okBg, color: C.okText },
  rejected: { bg: C.badBg, color: C.badText },
  withdrawn: { bg: C.muteBg, color: C.mute },
};

function ApplicationsHistory({ applications, onStatusChange }: {
  applications: ApplicationRecord[];
  onStatusChange: (id: string, status: ApplicationStatus) => void;
}) {
  if (applications.length === 0) return null;

  return (
    <div style={{ borderTop: `1px solid ${C.line}`, paddingTop: 12 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: C.mute, textTransform: "uppercase" as const, letterSpacing: 0.5, marginBottom: 8 }}>
        Recent Applications
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
        {applications.slice(0, 5).map((app) => (
          <div key={app.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "7px 0", borderBottom: `1px solid ${C.line}` }}>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>
                {app.role || "—"}
              </div>
              <div style={{ fontSize: 11, color: C.mute }}>{app.company || "—"}</div>
            </div>
            <select
              value={app.status}
              onChange={(e) => onStatusChange(app.id, e.target.value as ApplicationStatus)}
              style={{
                flexShrink: 0,
                marginLeft: 8,
                background: STATUS_STYLE[app.status].bg,
                color: STATUS_STYLE[app.status].color,
                border: "none",
                borderRadius: 999,
                padding: "2px 6px",
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
                outline: "none",
                appearance: "none",
              }}
            >
              {(Object.keys(STATUS_LABELS) as ApplicationStatus[]).map((s) => (
                <option key={s} value={s}>{STATUS_LABELS[s]}</option>
              ))}
            </select>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── [Phase 3] Persona switcher ────────────────────────────────────────────────
function PersonaSwitcher({
  personas,
  current,
  onChange,
}: {
  personas: PersonaMeta[];
  current: string;
  onChange: (p: string) => void;
}) {
  if (personas.length <= 1) return null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ fontSize: 11, color: C.mute, flexShrink: 0 }}>Profile:</span>
      <select
        value={current}
        onChange={(e) => onChange(e.target.value)}
        style={{
          flex: 1,
          fontSize: 11,
          padding: "3px 6px",
          border: `1px solid ${C.line}`,
          borderRadius: 5,
          background: C.bg,
          color: C.text,
          cursor: "pointer",
          outline: "none",
        }}
      >
        {personas.map((p) => (
          <option key={p.persona} value={p.persona}>
            {p.display_name ? `${p.display_name} (${p.persona})` : p.persona}
          </option>
        ))}
      </select>
    </div>
  );
}

// ── [Phase 3] JD Analyzer card ────────────────────────────────────────────────
function JDAnalyzerCard({
  persona,
  onAnalyzed,
}: {
  persona: string;
  onAnalyzed: (analysis: JDAnalysis, jdText: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [jdText, setJdText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze() {
    if (jdText.trim().length < 10) return;
    setBusy(true);
    setError(null);
    try {
      const result = await analyzeJd({ jd_text: jdText, persona });
      onAnalyzed(result, jdText);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ ...S.card }}>
      <button
        onClick={() => setExpanded((v) => !v)}
        style={{
          width: "100%",
          background: "none",
          border: "none",
          cursor: "pointer",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: 0,
          color: C.text,
          fontSize: 13,
          fontWeight: 600,
        }}
      >
        <span>Analyze Job Description</span>
        <span style={{ fontSize: 11, color: C.mute }}>{expanded ? "▲" : "▼"}</span>
      </button>

      {expanded && (
        <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste the full job description here…"
            rows={5}
            style={{
              ...S.input,
              resize: "vertical" as const,
              fontFamily: "inherit",
              lineHeight: 1.5,
            }}
          />
          <button
            style={{
              ...S.primaryBtn,
              opacity: busy || jdText.trim().length < 10 ? 0.6 : 1,
            }}
            disabled={busy || jdText.trim().length < 10}
            onClick={handleAnalyze}
          >
            {busy ? <><Spinner /> Analyzing…</> : "Analyze JD"}
          </button>
          {error && (
            <div style={{ fontSize: 11, color: C.bad }}>⚠ {error}</div>
          )}
        </div>
      )}
    </div>
  );
}

// ── [Phase 3] JD Analysis result ─────────────────────────────────────────────
function JDAnalysisResult({
  analysis,
  jdText,
  persona,
  onCoverLetterGenerated,
}: {
  analysis: JDAnalysis;
  jdText: string;
  persona: string;
  onCoverLetterGenerated: (content: string) => void;
}) {
  const [clBusy, setClBusy] = useState(false);
  const [clError, setClError] = useState<string | null>(null);
  const [tone, setTone] = useState<CoverLetterTone>("professional");

  const scoreColor =
    analysis.match_score >= 70 ? C.ok :
    analysis.match_score >= 40 ? C.warn : C.bad;

  async function handleGenerate() {
    setClBusy(true);
    setClError(null);
    try {
      const resp = await generateCoverLetter({ persona, jd_text: jdText, tone, max_words: 300 });
      onCoverLetterGenerated(resp.content);
    } catch (e) {
      setClError((e as Error).message);
    } finally {
      setClBusy(false);
    }
  }

  return (
    <div style={{ ...S.card, display: "flex", flexDirection: "column", gap: 10 }}>
      {/* Match score */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: C.text }}>Match Score</span>
        <span
          style={{
            fontSize: 20,
            fontWeight: 800,
            color: scoreColor,
          }}
        >
          {analysis.match_score}%
        </span>
      </div>

      {analysis.summary && (
        <div style={{ fontSize: 11, color: C.mute, lineHeight: 1.5 }}>{analysis.summary}</div>
      )}

      {/* Skills breakdown */}
      {analysis.matching_skills.length > 0 && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: C.ok, marginBottom: 4 }}>
            ✓ Matching ({analysis.matching_skills.length})
          </div>
          <div style={{ display: "flex", flexWrap: "wrap" as const, gap: 4 }}>
            {analysis.matching_skills.slice(0, 8).map((s) => (
              <span key={s} style={{ background: C.okBg, color: C.okText, padding: "2px 7px", borderRadius: 999, fontSize: 11 }}>
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {analysis.missing_skills.length > 0 && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: C.bad, marginBottom: 4 }}>
            ✗ Missing ({analysis.missing_skills.length})
          </div>
          <div style={{ display: "flex", flexWrap: "wrap" as const, gap: 4 }}>
            {analysis.missing_skills.slice(0, 8).map((s) => (
              <span key={s} style={{ background: C.badBg, color: C.badText, padding: "2px 7px", borderRadius: 999, fontSize: 11 }}>
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {analysis.experience_required && (
        <div style={{ fontSize: 11, color: C.mute }}>
          <span style={{ fontWeight: 600 }}>Experience required:</span> {analysis.experience_required}
        </div>
      )}

      {/* Cover letter generation (Phase 4) */}
      <div style={{ borderTop: `1px solid ${C.line}`, paddingTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
        <div style={{ fontSize: 12, fontWeight: 700 }}>Generate Cover Letter</div>
        <div style={{ display: "flex", gap: 6 }}>
          {(["professional", "enthusiastic", "concise"] as CoverLetterTone[]).map((t) => (
            <button
              key={t}
              onClick={() => setTone(t)}
              style={{
                flex: 1,
                padding: "5px 4px",
                border: `1px solid ${tone === t ? C.brand : C.line}`,
                borderRadius: 6,
                background: tone === t ? C.brandBg : C.bg,
                color: tone === t ? C.brand : C.mute,
                cursor: "pointer",
                fontSize: 10,
                fontWeight: tone === t ? 700 : 400,
              }}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        <button
          style={{ ...S.primaryBtn, opacity: clBusy ? 0.7 : 1 }}
          disabled={clBusy}
          onClick={handleGenerate}
        >
          {clBusy ? <><Spinner /> Writing…</> : "Generate Cover Letter"}
        </button>
        {clError && <div style={{ fontSize: 11, color: C.bad }}>⚠ {clError}</div>}
      </div>
    </div>
  );
}

// ── [Phase 4] Cover letter card ───────────────────────────────────────────────
function CoverLetterCard({ content, onClose }: { content: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div style={{ ...S.card, borderColor: C.ok, background: "#f0fdf4" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: C.ok }}>Cover Letter</span>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            onClick={handleCopy}
            style={{ ...S.ghostBtn, background: copied ? C.okBg : undefined, color: copied ? C.ok : undefined }}
          >
            {copied ? "✓ Copied" : "Copy"}
          </button>
          <button onClick={onClose} style={{ ...S.ghostBtn }}>✕</button>
        </div>
      </div>
      <textarea
        readOnly
        value={content}
        rows={10}
        style={{
          ...S.input,
          resize: "vertical" as const,
          fontFamily: "inherit",
          lineHeight: 1.6,
          fontSize: 11,
          color: C.text,
        }}
      />
    </div>
  );
}

// ── Error toast ───────────────────────────────────────────────────────────────
function friendlyError(raw: string): string {
  if (raw.includes("CV parsing failed")) return "Couldn't parse your CV. Try a different file or convert to .txt and upload again.";
  if (raw.includes("TimeoutError") || raw.includes("timeout")) return "The AI took too long. Please try again.";
  if (raw.includes("404") || raw.includes("profile not found")) return "No profile found — upload your CV first.";
  if (raw.includes("Session expired") || raw.includes("Not signed in")) return "Session expired — please sign in again.";
  if (raw.includes("fetch") || raw.includes("network") || raw.includes("Failed to fetch")) return "Connection error. Check your internet and try again.";
  return raw.length > 120 ? raw.slice(0, 117) + "…" : raw;
}

function ErrorToast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  return (
    <div style={{ background: C.badBg, border: `1px solid #fca5a5`, color: C.badText, padding: "10px 12px", borderRadius: 8, fontSize: 12, lineHeight: 1.5, display: "flex", gap: 8, alignItems: "flex-start" }}>
      <span style={{ flex: 1 }}>⚠ {friendlyError(message)}</span>
      <button onClick={onDismiss} style={{ background: "transparent", border: "none", color: C.badText, cursor: "pointer", fontSize: 16, padding: 0, lineHeight: 1, flexShrink: 0 }}>×</button>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function Popup() {
  const [phase, setPhase] = useState<AppPhase>("loading");
  const [session, setSession] = useState<AuthSession | null>(null);
  const [persona, setPersona] = useState("default");
  const [profile, setProfile] = useState<CVProfile | null>(null);
  const [justUploaded, setJustUploaded] = useState(false); // Feature 1

  const [busy, setBusy] = useState(false);
  const [approveBusy, setApproveBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [summary, setSummary] = useState<ScanSummary | null>(null);
  const [statusSteps, setStatusSteps] = useState<string[]>([]); // Feature 2

  // Feature 4 — application tracking
  const [applications, setApplications] = useState<ApplicationRecord[]>([]);
  const [showTrackCard, setShowTrackCard] = useState(false);
  const [trackSaving, setTrackSaving] = useState(false);

  // Phase 3 — personas
  const [personas, setPersonas] = useState<PersonaMeta[]>([]);

  // Phase 3 — JD analysis / Phase 4 — cover letter
  const [jdAnalysis, setJdAnalysis] = useState<JDAnalysis | null>(null);
  const [jdText, setJdText] = useState("");
  const [coverLetter, setCoverLetter] = useState<string | null>(null);

  const loadApps = useCallback(async () => {
    try {
      const apps = await listApplications(5);
      setApplications(apps);
    } catch {
      /* non-critical */
    }
  }, []);

  const loadPersonaList = useCallback(async () => {
    try {
      const ps = await listPersonas();
      setPersonas(ps);
    } catch {
      /* non-critical */
    }
  }, []);

  useEffect(() => {
    (async () => {
      const s = await loadSettings();
      setPersona(s.persona);
      const sess = await getSession();
      if (!sess) { setPhase("unauthenticated"); return; }
      setSession(sess);
      try {
        const [p] = await Promise.all([getProfile(s.persona), loadApps(), loadPersonaList()]);
        setProfile(p);
        setPhase("ready");
      } catch (e) {
        const msg = (e as Error).message;
        if (msg.includes("Session expired") || msg.includes("Not signed in")) {
          setPhase("unauthenticated");
        } else {
          setError(msg);
          setPhase("error");
        }
      }
    })();
  }, [loadApps, loadPersonaList]);

  useEffect(() => {
    const listener = (msg: RuntimeMessage) => {
      if (msg.type === "STATUS_UPDATE") {
        setStatusSteps((prev) => [...prev, msg.step]);
      }
    };
    chrome.runtime.onMessage.addListener(listener);
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, []);

  async function onSignIn() {
    setPhase("signing-in");
    setError(null);
    try {
      const r = await sendBg<{ ok: boolean; error?: string }>({ type: "SIGN_IN" });
      if (!r.ok) throw new Error(r.error || "Sign-in failed");
      const sess = await getSession();
      setSession(sess);
      const s = await loadSettings();
      const [p] = await Promise.all([getProfile(s.persona), loadApps(), loadPersonaList()]);
      setProfile(p);
      setPhase("ready");
    } catch (e) {
      setError((e as Error).message);
      setPhase("unauthenticated");
    }
  }

  async function onPersonaChange(newPersona: string) {
    setPersona(newPersona);
    await saveSettings({ persona: newPersona });
    setSummary(null);
    setJdAnalysis(null);
    setCoverLetter(null);
    try {
      const p = await getProfile(newPersona);
      setProfile(p);
    } catch { /* non-critical */ }
  }

  async function onSignOut() {
    await sendBg({ type: "SIGN_OUT" });
    setSession(null); setProfile(null); setSummary(null); setError(null);
    setApplications([]); setJustUploaded(false); setShowTrackCard(false);
    setPersonas([]); setJdAnalysis(null); setCoverLetter(null);
    setPhase("unauthenticated");
  }

  async function onUpload(file: File) {
    setBusy(true); setError(null);
    try {
      const fresh = await uploadCv(file, persona);
      setProfile(fresh);
      setJustUploaded(true); // Feature 1 — show parse success
      // Refresh personas list since a new profile may have been created.
      loadPersonaList().catch(() => {});
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onFill() {
    setBusy(true); setError(null); setSummary(null);
    setStatusSteps([]); setShowTrackCard(false);
    try {
      const r = await sendBg<{ ok: boolean; summary?: ScanSummary; error?: string }>({
        type: "SCAN_AND_FILL",
        persona,
      });
      if (!r.ok) throw new Error(r.error || "unknown error");
      if (r.summary) {
        setSummary(r.summary);
        // Auto-show track card if at least one field was filled.
        if (r.summary.filled > 0) setShowTrackCard(true);
      }
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      if (msg.includes("Session expired") || msg.includes("Not signed in")) setPhase("unauthenticated");
    } finally {
      setBusy(false); setStatusSteps([]);
    }
  }

  async function onFillApprove(values: { selector: string; value: string }[]) {
    setApproveBusy(true); setError(null);
    try {
      const r = await sendBg<{ ok: boolean; filledCount?: number; error?: string }>({
        type: "FILL_APPROVE", values,
      });
      if (!r.ok) throw new Error(r.error || "unknown error");
      const done = new Set(values.map((v) => v.selector));
      setSummary((prev) => prev ? {
        ...prev,
        filled: prev.filled + (r.filledCount ?? 0),
        approveMappings: prev.approveMappings.filter((m) => !done.has(m.selector)),
      } : prev);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setApproveBusy(false);
    }
  }

  async function onTrackSave(company: string, role: string) {
    if (!summary) return;
    setTrackSaving(true);
    try {
      const r = await sendBg<{ ok: boolean; record?: ApplicationRecord; error?: string }>({
        type: "TRACK_APPLICATION",
        company,
        role,
        url: summary.pageUrl || null,
      });
      if (r.ok && r.record) {
        setApplications((prev) => [r.record!, ...prev].slice(0, 5));
      }
    } catch { /* non-critical */ }
    setTrackSaving(false);
    setShowTrackCard(false);
  }

  async function onStatusChange(id: string, status: ApplicationStatus) {
    try {
      const updated = await updateApplication(id, { status });
      setApplications((prev) => prev.map((a) => a.id === id ? updated : a));
    } catch { /* non-critical */ }
  }

  return (
    <div style={S.root}>
      {/* Header */}
      <header style={S.header}>
        <span style={{ fontSize: 14, fontWeight: 800, color: C.brand, letterSpacing: -0.3 }}>Job Copilot</span>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {session?.email && (
            <span style={{ fontSize: 11, color: C.mute, maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>
              {session.email}
            </span>
          )}
          {phase === "ready" && (
            <button title="Settings" style={{ background: "none", border: "none", cursor: "pointer", color: C.mute, fontSize: 16, padding: "0 2px", lineHeight: 1 }}
              onClick={() => chrome.runtime.openOptionsPage()}>⚙</button>
          )}
        </div>
      </header>

      {/* Body */}
      <div style={S.body}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

          {phase === "loading" && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: C.mute, fontSize: 13 }}>
              <Spinner /> Loading…
            </div>
          )}

          {(phase === "unauthenticated" || phase === "signing-in") && (
            <SignIn busy={phase === "signing-in"} onSignIn={onSignIn} />
          )}

          {phase === "error" && (
            <div style={{ fontSize: 13, color: C.bad }}>
              Connection error. Check your internet and try again.
              <br />
              <button style={{ marginTop: 8, ...S.ghostBtn }} onClick={() => window.location.reload()}>Retry</button>
            </div>
          )}

          {phase === "ready" && !profile && (
            <Onboarding busy={busy} onPick={onUpload} />
          )}

          {/* [Feature 1] CV parse success state */}
          {phase === "ready" && profile && justUploaded && (
            <CVParseSuccess profile={profile} onContinue={() => setJustUploaded(false)} />
          )}

          {phase === "ready" && profile && !justUploaded && (
            <>
              {/* [Phase 3] Persona switcher */}
              <PersonaSwitcher personas={personas} current={persona} onChange={onPersonaChange} />

              <ProfileStrip profile={profile} busy={busy} onReplace={onUpload} />

              {/* [Feature 2] Step list during fill */}
              {busy ? (
                <FillProgress steps={statusSteps.length ? statusSteps : ["Working…"]} />
              ) : (
                <button style={S.primaryBtn} onClick={onFill}>⚡  Fill this page</button>
              )}

              {!busy && !summary && (
                <div style={{ textAlign: "center" as const, fontSize: 11, color: C.mute }}>
                  Navigate to a job application, then click Fill.
                </div>
              )}

              {!busy && summary && (
                <>
                  {/* [Feature 3] Source breakdown */}
                  <FillSummary s={summary} />

                  {summary.approveMappings.length > 0 && (
                    <HITLCard mappings={summary.approveMappings} onSubmit={onFillApprove} busy={approveBusy} />
                  )}

                  {/* [Feature 4] Track card */}
                  {showTrackCard && (
                    <TrackApplicationCard
                      pageTitle={summary.pageTitle}
                      pageUrl={summary.pageUrl}
                      onSave={onTrackSave}
                      onSkip={() => setShowTrackCard(false)}
                      saving={trackSaving}
                    />
                  )}
                </>
              )}

              {/* [Phase 3] JD Analyzer */}
              {!busy && (
                <JDAnalyzerCard
                  persona={persona}
                  onAnalyzed={(analysis, text) => {
                    setJdAnalysis(analysis);
                    setJdText(text);
                    setCoverLetter(null);
                  }}
                />
              )}

              {/* [Phase 3+4] JD analysis result + cover letter generator */}
              {!busy && jdAnalysis && (
                <JDAnalysisResult
                  analysis={jdAnalysis}
                  jdText={jdText}
                  persona={persona}
                  onCoverLetterGenerated={(content) => setCoverLetter(content)}
                />
              )}

              {/* [Phase 4] Cover letter */}
              {!busy && coverLetter && (
                <CoverLetterCard content={coverLetter} onClose={() => setCoverLetter(null)} />
              )}

              {/* [Feature 4] Recent applications */}
              {!busy && (
                <ApplicationsHistory applications={applications} onStatusChange={onStatusChange} />
              )}

              {!busy && (
                <div style={{ textAlign: "center" as const }}>
                  <button style={{ background: "none", border: "none", fontSize: 11, color: C.mute, cursor: "pointer", padding: 0 }} onClick={onSignOut}>
                    Sign out
                  </button>
                </div>
              )}
            </>
          )}

          {error && <ErrorToast message={error} onDismiss={() => setError(null)} />}
        </div>
      </div>
    </div>
  );
}
