// Platform detection — returns the ATS platform name from the current URL/DOM.

export type Platform = "workday" | "greenhouse" | "lever" | "ashby" | null;

export function detectPlatform(url: string): Platform {
  try {
    const { hostname, pathname } = new URL(url);

    if (/\.wd\d+\.myworkdayjobs\.com|myworkday\.com/.test(hostname)) return "workday";
    if (/boards\.greenhouse\.io|grnh\.se/.test(hostname)) return "greenhouse";
    if (/jobs\.lever\.co/.test(hostname)) return "lever";
    if (/jobs\.ashbyhq\.com/.test(hostname)) return "ashby";

    // DOM-based fallback detection
    if (document.querySelector("[data-automation-id]")) return "workday";
    if (document.querySelector("#greenhouse-app, #application")) return "greenhouse";
    if (document.querySelector(".lever-job-description, .postings-btn")) return "lever";
    if (document.querySelector("[data-ashby-job]")) return "ashby";
  } catch {
    // Invalid URL — fall through to null
  }
  return null;
}
