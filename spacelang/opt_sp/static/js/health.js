/**
 * Report missing static assets (Pyodide runtime, bundled SpaceLang modules).
 *
 * A page whose Pyodide assets are absent looks alive but cannot compile or run
 * anything, which is hard to diagnose from the browser alone. The health
 * endpoint answers that question directly, and this module surfaces it as a
 * banner without ever blocking the page.
 */

export async function checkAssets() {
  try {
    const response = await fetch("__opt_sp/health", { cache: "no-store" });
    if (!response.ok) return;
    const report = await response.json();
    if (report.ok) return;

    const missing = Object.entries(report.checks)
      .filter(([, present]) => !present)
      .map(([name]) => name)
      .join(", ");
    const banner = document.createElement("div");
    banner.className = "asset-banner";
    banner.setAttribute("role", "alert");
    banner.textContent =
      `Static assets incomplete (${missing}). ${report.hint ?? ""}`.trim();
    document.body.prepend(banner);
  } catch {
    // Health is advisory only: a failing check must never break the page.
  }
}
