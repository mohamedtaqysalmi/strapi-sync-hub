// Builds mapping.yaml from form values. Pure functions, no DOM, so a Python test can run it
// under Node and feed the output to the real config loader.
(function (root) {
  const NAME = /^[A-Za-z0-9_-]+$/;
  const PLAIN = /^[A-Za-z_][A-Za-z0-9_-]*$/;
  const YAML_WORDS = /^(true|false|null|yes|no|on|off|y|n)$/i;
  // Keep in step with RESERVED_TARGET_FIELDS in src/strapi_sync_hub/mapping.py.
  const RESERVED = ["id", "_source_updated_at"];

  function scalar(value) {
    return PLAIN.test(value) && !YAML_WORDS.test(value) ? value : JSON.stringify(value);
  }

  function parseFields(text, contentType) {
    const problems = [];
    const fields = [];
    const sources = new Set();
    const targets = new Set();
    const prefix = `content type '${contentType}'`;
    const lines = String(text)
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (!lines.length) problems.push(`${prefix}: add at least one field`);
    for (const line of lines) {
      const cut = line.indexOf(":");
      const source = (cut === -1 ? line : line.slice(0, cut)).trim();
      const target = (cut === -1 ? source : line.slice(cut + 1)).trim();
      if (!source || !target) {
        problems.push(`${prefix}: cannot read the line '${line}'`);
      } else if (sources.has(source)) {
        problems.push(`${prefix}: field '${source}' is listed twice`);
      } else if (RESERVED.includes(target)) {
        problems.push(`${prefix}: field '${source}': target name '${target}' is reserved`);
      } else if (targets.has(target)) {
        problems.push(`${prefix}: field '${source}': target name '${target}' is used twice`);
      } else {
        sources.add(source);
        targets.add(target);
        fields.push({ source, target });
      }
    }
    return { fields, problems };
  }

  function generate(input) {
    const model = String(input.model || "").trim();
    const index = String(input.index || "").trim();
    const apiId = String(input.apiId || "").trim();
    const idField = String(input.idField || "").trim();
    const problems = [];

    if (!model) problems.push("Strapi model is required");
    const prefix = `content type '${model}'`;
    if (!NAME.test(index)) {
      problems.push(`${prefix}: index must be letters, digits, '-' and '_'`);
    }
    if (apiId && !NAME.test(apiId)) {
      problems.push(`${prefix}: api_id must be letters, digits, '-' and '_'`);
    }
    const parsed = parseFields(input.fields, model);
    problems.push(...parsed.problems);
    if (problems.length) return { yaml: null, problems };

    const lines = ["content_types:", `  ${scalar(model)}:`, `    index: ${scalar(index)}`];
    if (apiId) lines.push(`    api_id: ${scalar(apiId)}`);
    if (idField) lines.push(`    id_field: ${scalar(idField)}`);
    lines.push("    fields:");
    for (const { source, target } of parsed.fields) {
      lines.push(`      ${scalar(source)}: ${scalar(target)}`);
    }
    return { yaml: lines.join("\n") + "\n", problems: [] };
  }

  const api = { generate, parseFields };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MappingGenerator = api;
})(typeof window !== "undefined" ? window : globalThis);
