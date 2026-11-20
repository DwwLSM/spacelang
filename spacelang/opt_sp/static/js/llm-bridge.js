/**
 * Browser side of the AI mirror sync.
 *
 * The server verifies every answer against the assembly before returning it, so
 * `ok: true` here means "compiles to the same program", not "the model said so".
 */

const ERRORS = {
  no_key: "No API key configured. Add one in LLM settings.",
  bad_key: "API key rejected (401). Check LLM settings.",
  rate_limited: "Too many AI requests - retry shortly.",
  busy: "Another sync is already running - retry shortly.",
  truncated: "The model produced no code (truncated) - try again.",
  empty_completion: "The model returned nothing - try again.",
  input_too_large: "The program is too large for the model.",
  upstream_error: "Cannot reach the LLM endpoint.",
  bad_config: "The LLM endpoint or model name is not valid.",
  network_error: "Cannot reach the local server.",
  cancelled: "Sync cancelled.",
};

export function describeError(result) {
  const base = ERRORS[result.error] || `Sync failed (${result.error || "unknown"}).`;
  if ((result.error === "rate_limited" || result.error === "busy") && result.retry_after) {
    return `${base} Retry in ${Math.ceil(result.retry_after)}s.`;
  }
  if (result.error === "not_equivalent") {
    const first = result.first;
    if (first) {
      return `Mirror rejected at instruction ${Number(first.index) + 1}: `
        + `the program needs "${first.want}" but the answer compiles to "${first.got}".`;
    }
    return `Mirror rejected - ${result.got_len ?? "?"}/${result.want_len ?? "?"} instructions differ.`;
  }
  return base;
}

export async function refinePy({ py, spasm, srcKind = "spasm", headers = {}, signal } = {}) {
  let response;
  try {
    response = await fetch("api/refine-py", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ py, spasm, src_kind: srcKind }),
      signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") return { ok: false, error: "cancelled" };
    return { ok: false, error: "network_error", message: String(error?.message ?? error) };
  }

  let body = {};
  try {
    body = await response.json();
  } catch {
    body = {};
  }
  if (response.ok && body.ok) return body;
  return {
    ok: false,
    status: response.status,
    error: body.error || "request_failed",
    message: body.message || "",
    retry_after: body.retry_after,
    want_len: body.want_len,
    got_len: body.got_len,
    first: body.first,
  };
}

export async function fetchLlmStatus(headers = {}) {
  try {
    const response = await fetch("api/llm-status", { headers, cache: "no-store" });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}
