/**
 * Per-browser LLM settings.
 *
 * Values live in localStorage and travel as per-request headers, so a user can
 * point the studio at a different model or their own key without restarting the
 * server. Nothing here is persisted server-side.
 */

const KEY = "opt-sp-llm";
const MODES = ["manual", "auto", "off"];

export function loadLLMSettings() {
  const fallback = { base_url: "", model: "", key: "", mode: "manual" };
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return fallback;
    const value = JSON.parse(raw);
    return {
      base_url: typeof value?.base_url === "string" ? value.base_url : "",
      model: typeof value?.model === "string" ? value.model : "",
      key: typeof value?.key === "string" ? value.key : "",
      mode: MODES.includes(value?.mode) ? value.mode : "manual",
    };
  } catch {
    return fallback;
  }
}

export function saveLLMSettings(settings) {
  try {
    localStorage.setItem(KEY, JSON.stringify(settings));
  } catch {
    // Settings persistence is a convenience; ignore storage failures.
  }
}

export function clearLLMSettings() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // Ignore.
  }
}

export function llmHeaders(settings = loadLLMSettings()) {
  const headers = {};
  if (settings.base_url) headers["X-LLM-Base-URL"] = settings.base_url;
  if (settings.model) headers["X-LLM-Model"] = settings.model;
  if (settings.key) headers["X-LLM-Key"] = settings.key;
  if (settings.mode) headers["X-LLM-Mode"] = settings.mode;
  return headers;
}

/**
 * Wire the settings dialog.
 *
 * `get()` is the saved configuration and is what callers should use; `read()`
 * reflects the dialog inputs and is only meaningful while editing them. Reading
 * the dialog for runtime decisions breaks after a reload, when no radio is
 * checked yet.
 */
export function initLLMSettings({ dialog, openers = [] }) {
  if (!dialog) return { get: loadLLMSettings, read: loadLLMSettings, open: () => {} };
  const baseUrl = dialog.querySelector("#llm-base-url");
  const model = dialog.querySelector("#llm-model");
  const key = dialog.querySelector("#llm-key");
  const save = dialog.querySelector("#llm-save");
  const clear = dialog.querySelector("#llm-clear");

  const fill = () => {
    const settings = loadLLMSettings();
    baseUrl.value = settings.base_url;
    model.value = settings.model;
    key.value = settings.key;
    for (const radio of dialog.querySelectorAll("input[name='llm-mode']")) {
      radio.checked = radio.value === settings.mode;
    }
  };

  const read = () => {
    const mode = [...dialog.querySelectorAll("input[name='llm-mode']")]
      .find((radio) => radio.checked)?.value ?? "manual";
    return {
      base_url: baseUrl.value.trim(),
      model: model.value.trim(),
      key: key.value.trim(),
      mode: MODES.includes(mode) ? mode : "manual",
    };
  };

  const open = () => {
    fill();
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  };

  for (const opener of openers) opener?.addEventListener("click", open);

  save?.addEventListener("click", () => {
    saveLLMSettings(read());
    dialog.close?.();
  });

  clear?.addEventListener("click", () => {
    clearLLMSettings();
    fill();
  });

  return { get: loadLLMSettings, read, open };
}
