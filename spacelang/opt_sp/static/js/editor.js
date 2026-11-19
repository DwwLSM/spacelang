const pairs = {
  "(": ")",
  "[": "]",
  "{": "}",
  "\"": "\"",
  "'": "'",
};

const closingCharacters = new Set(Object.values(pairs));
const maxUndoStates = 100;

function getEditorState(editor) {
  return {
    value: editor.value,
    selectionStart: editor.selectionStart,
    selectionEnd: editor.selectionEnd,
    scrollTop: editor.scrollTop,
    scrollLeft: editor.scrollLeft,
  };
}

function canCoalesceInput(previous, next, event, elapsed, previousInputType) {
  if (!event.isTrusted || event.inputType !== previousInputType ||
      elapsed === null || elapsed > 750 || !previous || !next) return false;
  if (previous.selectionStart !== previous.selectionEnd ||
      next.selectionStart !== next.selectionEnd) return false;

  if (event.inputType === "insertText" && event.data?.length === 1) {
    const position = next.selectionStart;
    return position === previous.selectionStart + 1 &&
      next.value === previous.value.slice(0, position - 1) +
        event.data +
        previous.value.slice(position - 1);
  }

  if (event.inputType === "deleteContentBackward") {
    const position = next.selectionStart;
    return position === previous.selectionStart - 1 &&
      next.value === previous.value.slice(0, position) +
        previous.value.slice(position + 1);
  }

  if (event.inputType === "deleteContentForward") {
    const position = next.selectionStart;
    return position === previous.selectionStart &&
      next.value === previous.value.slice(0, position) +
        previous.value.slice(position + 1);
  }
  return false;
}

export function bindUndoRedo(editor) {
  let history = [getEditorState(editor)];
  let historyIndex = 0;
  let lastInputAt = null;
  let lastInputType = null;
  let applyingHistory = false;

  const restore = (index, inputType) => {
    historyIndex = index;
    const state = history[historyIndex];
    editor.value = state.value;
    editor.setSelectionRange(state.selectionStart, state.selectionEnd);
    editor.scrollTop = state.scrollTop;
    editor.scrollLeft = state.scrollLeft;
    applyingHistory = true;
    editor.dispatchEvent(new InputEvent("input", {
      bubbles: true,
      inputType,
    }));
    applyingHistory = false;
    lastInputAt = null;
    lastInputType = null;
  };

  editor.addEventListener("input", (event) => {
    if (applyingHistory) return;
    const next = getEditorState(editor);
    const previous = history[historyIndex];
    if (next.value === previous.value) return;

    const now = performance.now();
    const elapsed = lastInputAt === null ? null : now - lastInputAt;
    const coalesce = canCoalesceInput(previous, next, event, elapsed, lastInputType);
    if (historyIndex < history.length - 1) {
      history = history.slice(0, historyIndex + 1);
    }

    if (coalesce) {
      history[historyIndex] = next;
    } else {
      history.push(next);
      historyIndex += 1;
      if (history.length > maxUndoStates) {
        history.shift();
        historyIndex -= 1;
      }
    }
    const canStartInputGroup = event.inputType !== "insertText" || event.data?.length === 1;
    lastInputAt = event.isTrusted && canStartInputGroup ? now : null;
    lastInputType = lastInputAt === null ? null : event.inputType;
  });

  editor.addEventListener("keydown", (event) => {
    if (event.isComposing || event.altKey) return;
    const key = event.key.toLowerCase();
    const commandKey = event.ctrlKey || event.metaKey;
    if (!commandKey) return;

    if (key === "z") {
      event.preventDefault();
      if (event.shiftKey) {
        if (historyIndex < history.length - 1) restore(historyIndex + 1, "historyRedo");
      } else if (historyIndex > 0) {
        restore(historyIndex - 1, "historyUndo");
      }
    } else if (key === "y" && event.ctrlKey && !event.metaKey) {
      event.preventDefault();
      if (historyIndex < history.length - 1) restore(historyIndex + 1, "historyRedo");
    }
  });

  return () => {
    history = [getEditorState(editor)];
    historyIndex = 0;
    lastInputAt = null;
    lastInputType = null;
  };
}

export function bindAutoCompletion(editor) {
  editor.addEventListener("keydown", (event) => {
    if (event.isComposing || event.ctrlKey || event.metaKey || event.altKey) return;

    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    if (event.key === "Tab") {
      event.preventDefault();
      const indentWidth = 4;
      if (start === end) {
        const lineStart = editor.value.lastIndexOf("\n", start - 1) + 1;
        if (event.shiftKey) {
          const lineEnd = editor.value.indexOf("\n", lineStart);
          const line = editor.value.slice(
            lineStart,
            lineEnd === -1 ? editor.value.length : lineEnd,
          );
          const indentationToRemove = line.startsWith("\t")
            ? 1
            : Math.min(indentWidth, line.match(/^ */)[0].length);
          if (indentationToRemove > 0) {
            editor.setRangeText(
              "",
              lineStart,
              lineStart + indentationToRemove,
              "preserve",
            );
            const caret = Math.max(lineStart, start - indentationToRemove);
            editor.setSelectionRange(caret, caret);
            editor.dispatchEvent(new InputEvent("input", {
              bubbles: true,
              inputType: "deleteContentBackward",
            }));
          }
          return;
        }

        const spaces = " ".repeat(indentWidth);
        editor.setRangeText(spaces, start, end, "end");
        editor.dispatchEvent(new InputEvent("input", {
          bubbles: true,
          inputType: "insertText",
          data: spaces,
        }));
        return;
      }

      const lineStart = editor.value.lastIndexOf("\n", start - 1) + 1;
      const selectedEnd = end > start && editor.value[end - 1] === "\n"
        ? end - 1
        : end;
      const lineEnd = editor.value.indexOf("\n", selectedEnd);
      const replaceEnd = lineEnd === -1 ? editor.value.length : lineEnd;
      const source = editor.value.slice(lineStart, replaceEnd);
      const lines = source.split("\n");
      const changedLines = lines.map((line) => {
        if (!event.shiftKey) return `${" ".repeat(indentWidth)}${line}`;
        if (line.startsWith("\t")) return line.slice(1);
        const spaces = line.match(/^ */)[0].length;
        return line.slice(Math.min(spaces, indentWidth));
      });
      if (changedLines.some((line, index) => line !== lines[index])) {
        const lineChanges = [];
        let oldOffset = lineStart;
        let newOffset = lineStart;
        for (let index = 0; index < lines.length; index += 1) {
          lineChanges.push({
            oldStart: oldOffset,
            oldEnd: oldOffset + lines[index].length,
            newStart: newOffset,
            delta: changedLines[index].length - lines[index].length,
          });
          oldOffset += lines[index].length + 1;
          newOffset += changedLines[index].length + 1;
        }
        const mapPosition = (position) => {
          let previousDelta = 0;
          for (const change of lineChanges) {
            if (position <= change.oldEnd) {
              const relative = position - change.oldStart;
              return change.newStart + Math.max(
                0,
                relative + change.delta,
              );
            }
            previousDelta += change.delta;
          }
          return position + previousDelta;
        };
        const selectionStart = mapPosition(start);
        const selectionEnd = mapPosition(end);
        const direction = editor.selectionDirection;
        editor.setRangeText(changedLines.join("\n"), lineStart, replaceEnd, "preserve");
        editor.setSelectionRange(
          selectionStart,
          selectionEnd,
          direction,
        );
        editor.dispatchEvent(new InputEvent("input", {
          bubbles: true,
          inputType: event.shiftKey ? "deleteContentBackward" : "insertText",
          data: event.shiftKey ? null : " ".repeat(indentWidth),
        }));
      }
      return;
    }

    if (
      closingCharacters.has(event.key) &&
      start === end &&
      editor.value[start] === event.key
    ) {
      event.preventDefault();
      editor.setSelectionRange(start + 1, start + 1);
      return;
    }

    const closing = pairs[event.key];
    if (closing) {
      event.preventDefault();
      const selectedText = editor.value.slice(start, end);
      editor.setRangeText(`${event.key}${selectedText}${closing}`, start, end, "select");
      editor.setSelectionRange(start + 1, end + 1);
      editor.dispatchEvent(new InputEvent("input", {
        bubbles: true,
        inputType: "insertText",
        data: event.key,
      }));
      return;
    }

    if (
      event.key === "Backspace" &&
      start === end &&
      pairs[editor.value[start - 1]] === editor.value[start]
    ) {
      event.preventDefault();
      editor.setRangeText("", start - 1, start + 1, "start");
      editor.dispatchEvent(new InputEvent("input", {
        bubbles: true,
        inputType: "deleteContentBackward",
      }));
    }
  });
}

function createTextMirror(editor) {
  const styles = getComputedStyle(editor);
  const bounds = editor.getBoundingClientRect();
  const mirror = document.createElement("div");
  const copiedProperties = [
    "boxSizing",
    "padding",
    "border",
    "font",
    "lineHeight",
    "letterSpacing",
    "wordSpacing",
    "textIndent",
    "textTransform",
    "textAlign",
    "direction",
    "tabSize",
    "whiteSpace",
    "overflowWrap",
    "wordBreak",
    "hyphens",
  ];

  for (const property of copiedProperties) {
    mirror.style[property] = styles[property];
  }
  Object.assign(mirror.style, {
    position: "fixed",
    left: `${bounds.left}px`,
    top: `${bounds.top}px`,
    width: `${bounds.width}px`,
    height: `${bounds.height}px`,
    margin: "0",
    overflowX: styles.overflowX,
    overflowY: styles.overflowY,
    opacity: "0",
    pointerEvents: "auto",
    zIndex: "2147483647",
  });
  mirror.setAttribute("aria-hidden", "true");
  mirror.textContent = editor.value;
  document.body.append(mirror);
  mirror.scrollTop = editor.scrollTop;
  mirror.scrollLeft = editor.scrollLeft;
  return mirror;
}

function createDragHighlight(editor, start, end) {
  const styles = getComputedStyle(editor);
  const bounds = editor.getBoundingClientRect();
  const highlight = document.createElement("div");
  for (const property of [
    "boxSizing",
    "padding",
    "border",
    "font",
    "lineHeight",
    "letterSpacing",
    "wordSpacing",
    "textIndent",
    "textTransform",
    "textAlign",
    "direction",
    "tabSize",
    "whiteSpace",
    "overflowWrap",
    "wordBreak",
    "hyphens",
  ]) {
    highlight.style[property] = styles[property];
  }
  Object.assign(highlight.style, {
    position: "fixed",
    left: `${bounds.left}px`,
    top: `${bounds.top}px`,
    width: `${bounds.width}px`,
    height: `${bounds.height}px`,
    margin: "0",
    overflow: "hidden",
    color: styles.color,
    background: "transparent",
    borderColor: "transparent",
    pointerEvents: "none",
    zIndex: "2147483645",
  });
  highlight.className = "editor-drag-highlight";
  highlight.setAttribute("aria-hidden", "true");
  highlight.append(
    document.createTextNode(editor.value.slice(0, start)),
    Object.assign(document.createElement("span"), {
      textContent: editor.value.slice(start, end),
    }),
    document.createTextNode(editor.value.slice(end)),
  );
  document.body.append(highlight);
  highlight.scrollTop = editor.scrollTop;
  highlight.scrollLeft = editor.scrollLeft;
  return highlight;
}

function syncDragHighlight(editor, highlight) {
  if (!highlight) return;
  const bounds = editor.getBoundingClientRect();
  highlight.style.left = `${bounds.left}px`;
  highlight.style.top = `${bounds.top}px`;
  highlight.style.width = `${bounds.width}px`;
  highlight.style.height = `${bounds.height}px`;
  highlight.scrollTop = editor.scrollTop;
  highlight.scrollLeft = editor.scrollLeft;
}

function caretOffsetAtPoint(editor, mirror, clientX, clientY) {
  const bounds = editor.getBoundingClientRect();
  const styles = getComputedStyle(editor);
  const borderLeft = parseFloat(styles.borderLeftWidth);
  const borderRight = parseFloat(styles.borderRightWidth);
  const borderTop = parseFloat(styles.borderTopWidth);
  const borderBottom = parseFloat(styles.borderBottomWidth);
  const x = Math.max(bounds.left + borderLeft, Math.min(bounds.right - borderRight, clientX));
  const y = Math.max(bounds.top + borderTop, Math.min(bounds.bottom - borderBottom, clientY));
  const previousVisibility = editor.style.visibility;
  editor.style.visibility = "hidden";
  mirror.style.left = `${bounds.left}px`;
  mirror.style.top = `${bounds.top}px`;
  mirror.style.width = `${bounds.width}px`;
  mirror.style.height = `${bounds.height}px`;
  mirror.scrollTop = editor.scrollTop;
  mirror.scrollLeft = editor.scrollLeft;

  try {
    const position = document.caretPositionFromPoint?.(x, y);
    if (position?.offsetNode === mirror.firstChild) return position.offset;
    const range = document.caretRangeFromPoint?.(x, y);
    if (range?.startContainer === mirror.firstChild) return range.startOffset;
    return null;
  } finally {
    editor.style.visibility = previousVisibility;
  }
}

function getCaretRect(mirror, offset) {
  const text = mirror.firstChild;
  if (!text || offset < 0 || offset > text.length) return null;

  const range = document.createRange();
  if (offset < text.length && text.textContent[offset] !== "\n") {
    range.setStart(text, offset);
    range.setEnd(text, offset + 1);
    const rect = range.getBoundingClientRect();
    return { x: rect.left, y: rect.top, height: rect.height };
  }
  if (offset > 0) {
    range.setStart(text, offset - 1);
    range.setEnd(text, offset);
    const rect = range.getBoundingClientRect();
    return { x: rect.right, y: rect.top, height: rect.height };
  }
  range.setStart(text, 0);
  range.setEnd(text, Math.min(1, text.length));
  const rect = range.getBoundingClientRect();
  return { x: rect.left, y: rect.top, height: rect.height };
}

function moveText(value, start, end, destination) {
  if (destination >= start && destination <= end) return null;
  const selectedText = value.slice(start, end);
  const withoutSelection = value.slice(0, start) + value.slice(end);
  const insertion = destination > end ? destination - selectedText.length : destination;
  return {
    value: withoutSelection.slice(0, insertion) +
      selectedText +
      withoutSelection.slice(insertion),
    start: insertion,
    end: insertion + selectedText.length,
    text: selectedText,
  };
}

export function bindDragMove(editor) {
  let drag = null;
  const targetTolerance = 8;

  editor.addEventListener("pointerdown", (event) => {
    if (event.pointerType !== "mouse" || event.button !== 0) return;
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    if (start === end) return;

    const mirror = createTextMirror(editor);
    const offset = caretOffsetAtPoint(editor, mirror, event.clientX, event.clientY);
    if (offset === null || offset < start || offset > end) {
      mirror.remove();
      return;
    }

    event.preventDefault();
    editor.focus();
    editor.setSelectionRange(offset, offset);
    mirror.remove();
    drag = {
      pointerId: event.pointerId,
      start,
      end,
      value: editor.value,
      originX: event.clientX,
      originY: event.clientY,
      moved: false,
      mirror: null,
      highlight: null,
      ghost: null,
      caret: null,
      dwellTimer: null,
      preview: null,
      destination: null,
      dwellTarget: null,
    };
  });

  const startDrag = (currentDrag, event) => {
    currentDrag.moved = true;
    currentDrag.mirror = createTextMirror(editor);
    currentDrag.highlight = createDragHighlight(
      editor,
      currentDrag.start,
      currentDrag.end,
    );
    const ghost = document.createElement("div");
    ghost.className = "editor-drag-ghost";
    ghost.textContent = currentDrag.value.slice(currentDrag.start, currentDrag.end);
    ghost.style.font = getComputedStyle(editor).font;
    ghost.style.lineHeight = getComputedStyle(editor).lineHeight;
    ghost.style.letterSpacing = getComputedStyle(editor).letterSpacing;
    ghost.setAttribute("aria-hidden", "true");
    ghost.hidden = true;
    document.body.append(ghost);
    const caret = document.createElement("div");
    caret.className = "editor-drop-caret";
    caret.setAttribute("aria-hidden", "true");
    caret.hidden = true;
    document.body.append(caret);
    currentDrag.ghost = ghost;
    currentDrag.caret = caret;
    editor.classList.add("dragging-text");
    editor.setSelectionRange(currentDrag.start, currentDrag.start);
    editor.setPointerCapture(event.pointerId);
  };

  editor.addEventListener("scroll", () => {
    if (drag?.moved) syncDragHighlight(editor, drag.highlight);
  });

  const clearDwell = (currentDrag) => {
    clearTimeout(currentDrag.dwellTimer);
    currentDrag.dwellTimer = null;
  };

  const showPreview = (currentDrag, destination) => {
    if (drag !== currentDrag || currentDrag.dwellTarget?.offset !== destination) return;
    const preview = moveText(
      currentDrag.value,
      currentDrag.start,
      currentDrag.end,
      destination,
    );
    if (!preview) return;
    currentDrag.preview = { ...preview, anchor: currentDrag.dwellTarget };
    editor.classList.add("drag-preview");
    currentDrag.caret.classList.add("preview");
  };

  const updateDropTarget = (currentDrag, clientX, clientY) => {
    syncDragHighlight(editor, currentDrag.highlight);
    const bounds = editor.getBoundingClientRect();
    const insideEditor = clientX >= bounds.left && clientX <= bounds.right &&
      clientY >= bounds.top && clientY <= bounds.bottom;
    if (!insideEditor) {
      currentDrag.ghost.hidden = true;
      currentDrag.caret.hidden = true;
      clearDwell(currentDrag);
      currentDrag.preview = null;
      currentDrag.dwellTarget = null;
      currentDrag.caret.classList.remove("preview");
      editor.classList.remove("drag-preview");
      currentDrag.destination = null;
      return null;
    }

    currentDrag.ghost.hidden = false;
    const destination = caretOffsetAtPoint(
      editor,
      currentDrag.mirror,
      clientX,
      clientY,
    );
    currentDrag.destination = destination;
    const validDestination = destination !== null && moveText(
      currentDrag.value,
      currentDrag.start,
      currentDrag.end,
      destination,
    ) !== null;
    const anchor = currentDrag.preview?.anchor ?? currentDrag.dwellTarget;
    const movedToAnotherTarget = anchor &&
      destination !== anchor.offset &&
      Math.hypot(clientX - anchor.x, clientY - anchor.y) >= targetTolerance;

    if (currentDrag.preview && !movedToAnotherTarget) {
      return destination;
    }

    if (!validDestination) {
      clearDwell(currentDrag);
      currentDrag.preview = null;
      currentDrag.dwellTarget = null;
      currentDrag.caret.classList.remove("preview");
      editor.classList.remove("drag-preview");
      currentDrag.caret.hidden = true;
      return destination;
    }

    const targetChanged = !currentDrag.dwellTarget ||
      (destination !== currentDrag.dwellTarget.offset &&
       Math.hypot(clientX - currentDrag.dwellTarget.x, clientY - currentDrag.dwellTarget.y) >= targetTolerance);
    if (targetChanged || movedToAnotherTarget) {
      clearDwell(currentDrag);
      currentDrag.dwellTarget = { offset: destination, x: clientX, y: clientY };
      currentDrag.preview = null;
      currentDrag.caret.classList.remove("preview");
      editor.classList.remove("drag-preview");
    }

    const target = currentDrag.dwellTarget;
    const caret = getCaretRect(currentDrag.mirror, target.offset);
    if (caret) {
      currentDrag.caret.hidden = false;
      currentDrag.caret.style.left = `${caret.x}px`;
      currentDrag.caret.style.top = `${caret.y}px`;
      currentDrag.caret.style.height = `${caret.height}px`;
    }
    if (targetChanged || movedToAnotherTarget) {
      currentDrag.dwellTimer = setTimeout(
        () => showPreview(currentDrag, target.offset),
        350,
      );
    }
    return destination;
  };

  const removeDragIndicators = (currentDrag) => {
    clearDwell(currentDrag);
    currentDrag.mirror.remove();
    currentDrag.highlight.remove();
    currentDrag.ghost.remove();
    currentDrag.caret.remove();
    editor.classList.remove("dragging-text", "drag-preview");
  };

  document.addEventListener("pointermove", (event) => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    if (Math.hypot(event.clientX - drag.originX, event.clientY - drag.originY) < 4) return;
    if (!drag.moved) startDrag(drag, event);
    event.preventDefault();
    drag.ghost.hidden = false;
    drag.ghost.style.left = `${event.clientX + 14}px`;
    drag.ghost.style.top = `${event.clientY + 16}px`;
    updateDropTarget(drag, event.clientX, event.clientY);
  });

  document.addEventListener("pointerup", (event) => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    const currentDrag = drag;
    drag = null;
    if (!currentDrag.moved) return;
    clearDwell(currentDrag);

    const bounds = editor.getBoundingClientRect();
    const insideEditor = event.clientX >= bounds.left && event.clientX <= bounds.right &&
      event.clientY >= bounds.top && event.clientY <= bounds.bottom;
    const destination = insideEditor
      ? caretOffsetAtPoint(editor, currentDrag.mirror, event.clientX, event.clientY)
      : null;
    const movedText = currentDrag.moved
      ? moveText(currentDrag.value, currentDrag.start, currentDrag.end, destination)
      : null;
    if (movedText) {
      editor.value = movedText.value;
      editor.setSelectionRange(movedText.start, movedText.end);
      editor.dispatchEvent(new InputEvent("input", {
        bubbles: true,
        inputType: "insertFromDrop",
        data: movedText.text,
      }));
    } else if (currentDrag.moved) {
      editor.setSelectionRange(currentDrag.start, currentDrag.end);
    }

    removeDragIndicators(currentDrag);
  });

  document.addEventListener("pointercancel", (event) => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    if (!drag.moved) {
      drag = null;
      return;
    }
    editor.setSelectionRange(drag.start, drag.end);
    removeDragIndicators(drag);
    drag = null;
  });
}
