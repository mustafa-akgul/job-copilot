// OAuth session management.
// The actual launchWebAuthFlow call lives in background.ts (SW context required).
// This module handles storage reads/writes and token refresh — safe from any context.

import { Storage } from "@plasmohq/storage";

const storage = new Storage({ area: "local" });

const SUPABASE_URL = process.env.PLASMO_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY = process.env.PLASMO_PUBLIC_SUPABASE_ANON_KEY ?? "";

export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  userId: string;
  email: string;
  expiresAt: number; // ms since epoch
}

export async function getSession(): Promise<AuthSession | null> {
  return (await storage.get<AuthSession>("session")) ?? null;
}

export async function setSession(session: AuthSession): Promise<void> {
  await storage.set("session", session);
}

export async function clearSession(): Promise<void> {
  await storage.remove("session");
}

// Build the Supabase OAuth URL for use in launchWebAuthFlow.
export function buildOAuthUrl(redirectUrl: string): string {
  const url = new URL(`${SUPABASE_URL}/auth/v1/authorize`);
  url.searchParams.set("provider", "google");
  url.searchParams.set("redirect_to", redirectUrl);
  return url.toString();
}

// Parse tokens from the redirect URL fragment that Supabase appends after OAuth.
export function parseOAuthRedirect(callbackUrl: string): AuthSession {
  const fragment = new URL(callbackUrl).hash.slice(1);
  const params = new URLSearchParams(fragment);
  const accessToken = params.get("access_token");
  const refreshToken = params.get("refresh_token");
  const expiresIn = parseInt(params.get("expires_in") ?? "3600", 10);

  if (!accessToken || !refreshToken) {
    throw new Error("OAuth redirect missing tokens");
  }

  // Decode JWT payload — no verification needed here (backend verifies on every call).
  const payload = JSON.parse(atob(accessToken.split(".")[1]));

  return {
    accessToken,
    refreshToken,
    userId: payload.sub as string,
    email: (payload.email as string) ?? "",
    expiresAt: Date.now() + expiresIn * 1000,
  };
}

// Silently refresh the access token via Supabase's token endpoint.
// Returns null if refresh fails (caller must re-authenticate).
export async function refreshSession(refreshToken: string): Promise<AuthSession | null> {
  try {
    const r = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=refresh_token`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        apikey: SUPABASE_ANON_KEY,
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!r.ok) return null;
    const data = await r.json();
    const payload = JSON.parse(atob(data.access_token.split(".")[1]));
    return {
      accessToken: data.access_token as string,
      refreshToken: data.refresh_token as string,
      userId: payload.sub as string,
      email: (payload.email as string) ?? "",
      expiresAt: Date.now() + (data.expires_in as number) * 1000,
    };
  } catch {
    return null;
  }
}

// Return a valid access token, refreshing silently if it's about to expire.
// Returns null when the session is absent or refresh failed (user must sign in again).
export async function getValidAccessToken(): Promise<string | null> {
  const session = await getSession();
  if (!session) return null;

  // Proactively refresh when less than 5 minutes remain.
  if (session.expiresAt - Date.now() < 5 * 60 * 1000) {
    const refreshed = await refreshSession(session.refreshToken);
    if (!refreshed) {
      await clearSession();
      return null;
    }
    await setSession(refreshed);
    return refreshed.accessToken;
  }

  return session.accessToken;
}
