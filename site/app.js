(function () {
  const form = document.getElementById("map-form");
  const output = document.getElementById("yaml-out");
  const problems = document.getElementById("problems");
  const status = document.getElementById("gen-status");
  const copyButton = document.getElementById("copy-yaml");

  function read() {
    return {
      model: form.elements.model.value,
      index: form.elements.index.value,
      apiId: form.elements.api_id.value,
      idField: form.elements.id_field.value,
      fields: form.elements.fields.value,
    };
  }

  function render() {
    const result = window.MappingGenerator.generate(read());
    problems.replaceChildren();
    if (result.yaml === null) {
      result.problems.forEach((message) => {
        const item = document.createElement("li");
        item.className = "tag-no";
        item.textContent = message;
        problems.appendChild(item);
      });
      status.textContent = "Fix the problems above and the YAML will appear.";
      copyButton.disabled = true;
      return;
    }
    output.textContent = result.yaml;
    status.textContent = "This is the shape the hub's own loader accepts.";
    copyButton.disabled = false;
  }

  form.addEventListener("input", render);
  form.addEventListener("submit", (event) => event.preventDefault());
  render();
})();
