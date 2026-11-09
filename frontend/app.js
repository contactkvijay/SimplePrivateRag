const findElement = (selector) => document.querySelector(selector);
const conversation = findElement("#conversation");
function makeElement(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}
async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}
function addMessage(label, text, kind) {
  conversation.querySelector(".welcome")?.remove();
  const box = makeElement("article", `message ${kind}`, "");
  box.append(makeElement("div", "label", label), makeElement("div", "", text));
  conversation.append(box);
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  return box;
}
async function refreshDocuments() {
  const list = findElement("#documents");
  const documents = await requestJson("documents");
  list.replaceChildren();
  findElement("#doc-count").textContent = `${documents.length} ${documents.length === 1 ? "file" : "files"}`;
  for (const doc of documents) {
    const item = document.createElement("li");
    const remove = makeElement("button", "delete", "Delete");
    remove.type = "button";
    remove.setAttribute("aria-label", `Delete ${doc.filename}`);
    remove.addEventListener("click", async () => {
      if (!confirm(`Delete ${doc.filename} and its indexed text?`)) return;
      try {
        await requestJson(`documents/${encodeURIComponent(doc.id)}`, { method: "DELETE" });
        conversation.replaceChildren();
        await refreshDocuments();
      }
      catch (error) { alert(error.message); }
    });
    item.append(makeElement("span", "doc-name", doc.filename), remove);
    list.append(item);
  }
}
findElement("#question").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    if (!findElement("#ask-form button[type=submit]").disabled) findElement("#ask-form").requestSubmit();
  }
});
findElement("#ask-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (event.currentTarget.querySelector("button[type=submit]").disabled) return;
  const input = findElement("#question");
  const question = input.value.trim();
  if (!question) return;
  addMessage("You", question, "user");
  input.value = "";
  const button = findElement("#ask-form button[type=submit]");
  button.disabled = true;
  const answer = addMessage("Searching your files…", "", "answer");
  try {
    const result = await requestJson("ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) });
    answer.querySelector(".label").textContent = "Answer";
    answer.children[1].textContent = result.answer.replace(/\*\*(.*?)\*\*/gs, "$1");
    const sources = document.createElement("details");
    sources.className = "sources";
    sources.append(makeElement("summary", "", `View source excerpts (${result.sources.length})`));
    for (const source of result.sources) {
      sources.append(makeElement("div", "source", `${source.filename} · ${source.reference}: “${source.excerpt}”`));
    }
    answer.append(sources);
  } catch (error) {
    answer.querySelector(".label").textContent = "Could not answer";
    answer.children[1].textContent = error.message;
  } finally { button.disabled = false; }
});
findElement("#file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  findElement("#upload-status").textContent = `Indexing ${file.name}…`;
  const form = new FormData();
  form.append("file", file);
  try {
    const result = await requestJson("upload", { method: "POST", body: form });
    findElement("#upload-status").textContent = `${result.filename} is ready.`;
    await refreshDocuments();
  } catch (error) { findElement("#upload-status").textContent = error.message; }
  event.target.value = "";
});
findElement("#clear-chat").addEventListener("click", () => {
  conversation.replaceChildren(makeElement("div", "welcome", "👋 Welcome! Upload a file, then ask questions about your documents."));
});
requestJson("health").then((health) => {
  const ready = health.ok && health.chat_model && health.embedding_model;
  findElement("#status-dot").classList.toggle("ok", ready);
  findElement("#status-text").textContent = ready ? "Models ready" : "Check Ollama models";
}).catch(() => { findElement("#status-text").textContent = "Backend unavailable"; });
refreshDocuments().catch((error) => { findElement("#upload-status").textContent = error.message; });
