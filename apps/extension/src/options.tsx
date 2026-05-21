// Options page: persona management + account info.

import { useEffect, useState } from "react";

import { clearSession, getSession, type AuthSession } from "~lib/auth";
import { loadSettings, saveSettings } from "~lib/settings";
import type { RuntimeMessage } from "~types/shared";

const C = {
  brand: "#2563eb",
  text: "#111827",
  mute: "#6b7280",
  line: "#e5e7eb",
  bad: "#dc2626",
  badBg: "#fee2e2",
};

function sendBg<T>(message: RuntimeMessage): Promise<T> {
  return new Promise((resolve, reject) =>
    chrome.runtime.sendMessage(message, (r) => {
      if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
      else resolve(r as T);
    }),
  );
}

export default function Options() {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [persona, setPersona] = useState("default");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    Promise.all([loadSettings(), getSession()]).then(([s, sess]) => {
      setPersona(s.persona);
      setSession(sess);
    });
  }, []);

  async function onSave() {
    await saveSettings({ persona });
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  async function onSignOut() {
    await sendBg({ type: "SIGN_OUT" });
    setSession(null);
  }

  const labelStyle: React.CSSProperties = {
    display: "block",
    marginTop: 20,
    marginBottom: 4,
    fontSize: 13,
    fontWeight: 600,
    color: C.text,
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "8px 10px",
    border: `1px solid ${C.line}`,
    borderRadius: 6,
    fontSize: 13,
    boxSizing: "border-box",
    outline: "none",
  };

  return (
    <div style={{ maxWidth: 480, margin: "32px auto", fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif', fontSize: 14, color: C.text, padding: "0 16px" }}>
      <h1 style={{ fontSize: 20, fontWeight: 800, color: C.brand, marginBottom: 4 }}>Job Copilot</h1>
      <p style={{ fontSize: 13, color: C.mute, marginBottom: 24 }}>Settings</p>

      {/* Account */}
      <section style={{ borderBottom: `1px solid ${C.line}`, paddingBottom: 20, marginBottom: 20 }}>
        <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 12 }}>Account</div>
        {session ? (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{session.email || "Signed in"}</div>
              <div style={{ fontSize: 11, color: C.mute, marginTop: 2 }}>User ID: {session.userId.slice(0, 8)}…</div>
            </div>
            <button
              onClick={onSignOut}
              style={{
                padding: "6px 14px",
                border: `1px solid ${C.line}`,
                borderRadius: 6,
                background: "transparent",
                fontSize: 12,
                color: C.mute,
                cursor: "pointer",
              }}
            >
              Sign out
            </button>
          </div>
        ) : (
          <div style={{ fontSize: 13, color: C.mute }}>
            Not signed in. Open the extension popup to sign in.
          </div>
        )}
      </section>

      {/* Persona */}
      <section>
        <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>Profile</div>
        <div style={{ fontSize: 12, color: C.mute, marginBottom: 12 }}>
          Personas let you maintain separate CV profiles — e.g. "engineer" vs "manager". Switching personas is coming in the next update.
        </div>

        <label style={labelStyle}>Default persona</label>
        <input
          value={persona}
          onChange={(e) => setPersona(e.target.value)}
          style={inputStyle}
          placeholder="default"
        />

        <button
          onClick={onSave}
          style={{
            marginTop: 16,
            padding: "9px 20px",
            background: C.brand,
            color: "white",
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
            fontWeight: 600,
            fontSize: 13,
          }}
        >
          Save
        </button>
        {saved && <span style={{ marginLeft: 12, color: "#059669", fontSize: 13 }}>Saved ✓</span>}
      </section>
    </div>
  );
}
