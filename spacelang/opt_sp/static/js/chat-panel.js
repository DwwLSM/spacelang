/**
 * The SpaceLang assistant panel.
 *
 * One transcript per page, kept in `localStorage` so a reload does not lose the
 * conversation, and one request in flight at a time. The server owns the system
 * prompt: this module only sends the page name plus the transcript, which is
 * also why the transcript is capped before it is sent.
 *
 * Two shapes share the code: a column that fills its container (home page) and
 * a drawer pinned to the right edge (editor and studio), where the page keeps
 * its full width until the assistant is asked for.
 */

const HISTORY_LIMIT = 40;
const SEND_HISTORY = 12;

// The model writes light Markdown whatever the prompt says. Rendering it is a
// kindness to the reader, so a tiny renderer covers fenced code, inline code and
// bold; everything else stays text, and nothing here builds HTML from a string.
const FENCE = /```[^\n]*\n?([\s\S]*?)```/g;
const INLINE = /(`[^`\n]+`|\*\*[^*\n]+\*\*)/g;

function appendProse(target, text) {
  if (!text) return;
  let cursor = 0;
  for (const match of text.matchAll(INLINE)) {
    if (match.index > cursor) {
      target.append(document.createTextNode(text.slice(cursor, match.index)));
    }
    const token = match[0];
    const element = document.createElement(token.startsWith("`") ? "code" : "strong");
    element.textContent = token.startsWith("`") ? token.slice(1, -1) : token.slice(2, -2);
    target.append(element);
    cursor = match.index + token.length;
  }
  if (cursor < text.length) target.append(document.createTextNode(text.slice(cursor)));
}

function renderRich(target, text) {
  let cursor = 0;
  for (const match of text.matchAll(FENCE)) {
    appendProse(target, text.slice(cursor, match.index));
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.textContent = match[1].replace(/\n$/, "");
    pre.append(code);
    target.append(pre);
    cursor = match.index + match[0].length;
  }
  appendProse(target, text.slice(cursor));
}

function storageKey(page) {
  return `opt-sp-chat:${page}`;
}

function loadHistory(page) {
  try {
    const raw = localStorage.getItem(storageKey(page));
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (message) =>
          message &&
          (message.role === "user" || message.role === "assistant") &&
          typeof message.content === "string" &&
          message.content.trim(),
      )
      .slice(-HISTORY_LIMIT);
  } catch {
    return [];
  }
}

function saveHistory(page, messages) {
  try {
    localStorage.setItem(storageKey(page), JSON.stringify(messages.slice(-HISTORY_LIMIT)));
  } catch {
    // Storage is a convenience; the transcript still lives in the DOM.
  }
}

export function initChatPanel({ root, page, drawer = false }) {
  if (!root) return null;
  const log = root.querySelector('[data-role="log"]');
  const form = root.querySelector('[data-role="form"]');
  const input = root.querySelector('[data-role="input"]');
  const send = root.querySelector('[data-role="send"]');
  const status = root.querySelector('[data-role="status"]');
  const clear = root.querySelector('[data-role="clear"]');
  const toggle = root.querySelector('[data-role="toggle"]');
  const headerToggle = document.querySelector("#chat-toggle");

  let messages = loadHistory(page);
  let busy = false;

  if (drawer) {
    root.dataset.drawer = "true";
    if (headerToggle) headerToggle.hidden = false;
  }

  function setStatus(text, kind = "") {
    if (!status) return;
    status.textContent = text;
    status.dataset.kind = kind;
  }

  function scrollToEnd() {
    if (log) log.scrollTop = log.scrollHeight;
  }

  function messageNode(message) {
    const node = document.createElement("div");
    node.className = `chat-message chat-message--${message.role}`;
    if (message.role === "error") {
      node.className = "chat-message chat-message--error";
      node.setAttribute("role", "alert");
      node.textContent = message.content;
      return node;
    }
    renderRich(node, message.content);
    return node;
  }

  function render() {
    if (!log) return;
    log.replaceChildren();
    if (messages.length === 0) {
      const empty = document.createElement("p");
      empty.className = "chat-empty";
      empty.textContent = drawer
        ? "Ask about the program, the trace, or the operator codes."
        : "Ask about SpaceLang, the pages, or where to start.";
      log.append(empty);
    }
    for (const message of messages) log.append(messageNode(message));
    scrollToEnd();
  }

  function setBusy(value) {
    busy = value;
    root.classList.toggle("is-busy", value);
    if (send) send.disabled = value;
    if (input) input.disabled = value;
    if (value) setStatus("Asking…");
    else setStatus("");
  }

  function persist() {
    saveHistory(page, messages);
  }

  function append(message) {
    messages = [...messages, message].slice(-HISTORY_LIMIT);
    const node = messageNode(message);
    if (messages.length === 1 && log?.querySelector(".chat-empty")) {
      log.replaceChildren(node);
    } else {
      log?.append(node);
    }
    scrollToEnd();
    persist();
  }

  async function ask(text) {
    if (busy) return;
    append({ role: "user", content: text });
    setBusy(true);
    try {
      const response = await fetch("api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page, messages: messages.slice(-SEND_HISTORY) }),
      });
      const raw = await response.text();
      let payload;
      try {
        payload = JSON.parse(raw);
      } catch {
        throw new Error(
          response.status === 404 || response.status === 405
            ? "The running server does not serve this endpoint. Restart the OPT_SP server."
            : `The server answered ${response.status} with a page instead of JSON.`,
        );
      }
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.message || payload.error || `Request failed (${response.status}).`);
      }
      append(payload.reply);
      if (payload.truncated) setStatus("The answer was cut off at the token limit.", "warn");
    } catch (error) {
      const text = error.message || String(error);
      append({ role: "error", content: text });
      setStatus("");
    } finally {
      setBusy(false);
      if (input && !input.disabled) input.focus();
    }
  }

  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = input?.value.trim() ?? "";
    if (!text) return;
    input.value = "";
    void ask(text);
  });

  input?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    form?.requestSubmit();
  });

  clear?.addEventListener("click", () => {
    messages = [];
    persist();
    render();
    setStatus("Cleared.");
    input?.focus();
  });

  function setOpen(open) {
    if (drawer) {
      root.classList.toggle("is-open", open);
      toggle?.setAttribute("aria-label", open ? "Close the assistant" : "Open the assistant");
      headerToggle?.setAttribute("aria-expanded", String(open));
      if (open) {
        input?.focus();
        scrollToEnd();
      }
    } else {
      root.classList.toggle("is-collapsed", !open);
    }
    if (toggle) {
      toggle.textContent = open ? "Hide" : "Show";
      toggle.setAttribute("aria-expanded", String(open));
    }
    try {
      localStorage.setItem(`opt-sp-chat-open:${page}`, open ? "1" : "0");
    } catch {
      // Ignore storage failures.
    }
  }

  const wasOpen = (() => {
    try {
      const stored = localStorage.getItem(`opt-sp-chat-open:${page}`);
      // A drawer covers the page, so it waits to be asked for; the home column
      // is part of the layout and starts visible.
      if (stored !== null) return stored === "1";
      return !drawer;
    } catch {
      return !drawer;
    }
  })();

  toggle?.addEventListener("click", () => {
    const open = drawer
      ? root.classList.contains("is-open")
      : !root.classList.contains("is-collapsed");
    setOpen(!open);
  });
  headerToggle?.addEventListener("click", () => {
    setOpen(!root.classList.contains("is-open"));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && drawer && root.classList.contains("is-open")) setOpen(false);
  });

  render();
  setOpen(wasOpen);

  return { open: () => setOpen(true), close: () => setOpen(false), clear: () => clear?.click() };
}
