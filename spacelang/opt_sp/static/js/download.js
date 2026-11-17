const extensions = {
  asm: ".spasm",
  python: ".py",
  sp: ".sp",
};

export function downloadSource(source, mode, suggestedName = "program") {
  const extension = extensions[mode] || ".txt";
  const baseName = suggestedName
    .replaceAll("\\", "/")
    .split("/")
    .pop()
    .replace(/\.[^.]*$/, "")
    .replace(/[<>:"|?*\u0000-\u001f]/g, "_") || "program";
  const blob = new Blob([source], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${baseName}${extension}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
