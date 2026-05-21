// Extension settings stored in chrome.storage.local.

import { Storage } from "@plasmohq/storage";

const storage = new Storage({ area: "local" });

const DEFAULT_API_URL =
  process.env.PLASMO_PUBLIC_API_URL ?? "https://api.jobcopilot.io";

export interface CopilotSettings {
  apiUrl: string;
  persona: string;
}

export async function loadSettings(): Promise<CopilotSettings> {
  const [apiUrl, persona] = await Promise.all([
    storage.get<string>("apiUrl"),
    storage.get<string>("persona"),
  ]);
  return {
    apiUrl: apiUrl || DEFAULT_API_URL,
    persona: persona || "default",
  };
}

export async function saveSettings(s: Partial<CopilotSettings>): Promise<void> {
  if (s.apiUrl !== undefined) await storage.set("apiUrl", s.apiUrl);
  if (s.persona !== undefined) await storage.set("persona", s.persona);
}
