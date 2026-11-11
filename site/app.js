(function () {
  const form = document.getElementById("map-form");
  const out = document.getElementById("yaml-out");
  const status = document.getElementById("gen-status");
  const copyBtn = document.getElementById("copy-yaml");

  function parseFields(raw) {
    const lines = raw
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    const fields = [];
    for (const line of lines) {
      const parts = line.split(":").map((p) => p.trim());
      if (parts.length === 1) {
        fields.push({ source: parts[0], target: parts[0] });
      } else if (parts.length === 2 && parts[0] && parts[1]) {
        fields.push({ source: parts[0], target: parts[1] });
      } else {
        throw new Error(`Bad field line: ${line}`);
      }
    }
    if (!fields.length) throw new Error("Add at least one field");
    return fields;
  }

  function toYaml(model, index, apiId, idField, fields) {
    const fieldLines = fields
      .map((f) =>
        f.source === f.target
          ? `      ${f.source}: ${f.target}`
          : `      ${f.source}: ${f.target}`
      )
      .join("\n");
    return [
      "content_types:",
      `  ${model}:`,
      `    index: ${index}`,
      `    api_id: ${apiId || index}`,
      `    id_field: ${idField}`,
      "    fields:",
      fieldLines,
      "",
    ].join("\n");
  }

  function generate(event) {
    if (event) event.preventDefault();
    try {
      const data = new FormData(form);
      const yaml = toYaml(
        String(data.get("model") || "").trim(),
        String(data.get("index") || "").trim(),
        String(data.get("api_id") || "").trim(),
        String(data.get("id_field") || "").trim(),
        parseFields(String(data.get("fields") || ""))
      );
      out.textContent = yaml;
      status.textContent = "YAML ready — copy into mapping.yaml.";
    } catch (err) {
      status.textContent = err instanceof Error ? err.message : "Could not generate";
    }
  }

  form.addEventListener("submit", generate);
  form.querySelectorAll("input, textarea").forEach((el) => {
    el.addEventListener("input", () => generate());
  });
  generate();

  async function copyText(text) {
    await navigator.clipboard.writeText(text);
  }

  copyBtn.addEventListener("click", async () => {
    try {
      await copyText(out.textContent || "");
      status.textContent = "Copied mapping YAML.";
    } catch {
      status.textContent = "Copy failed — select the YAML and copy manually.";
    }
  });

  document.querySelectorAll("[data-copy-prev]").forEach((button) => {
    button.addEventListener("click", async () => {
      const pre = button.previousElementSibling;
      if (!(pre instanceof HTMLPreElement)) return;
      try {
        await copyText(pre.innerText);
        button.textContent = "Copied";
        setTimeout(() => {
          button.textContent = "Copy";
        }, 1200);
      } catch {
        button.textContent = "Copy failed";
      }
    });
  });
})();
