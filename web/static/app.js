const log = document.getElementById("log"), form = document.getElementById("form");
const input = document.getElementById("input"), sendBtn = document.getElementById("send");
const errBox = document.getElementById("error");
let sessionId = null, busy = false;

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
// Safe rendering: only textContent / createElement, never innerHTML.
function inline(parent, text) {
  const re = /(\*\*[^*]+\*\*|\*(?=[^\s*])[^*\n]*[^\s*]\*|`[^`]+`|\[kb-\d+\])/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) parent.append(text.slice(last, m.index));
    const t = m[0];
    parent.append(t.startsWith("**") ? el("strong", null, t.slice(2, -2))
      : t[0] === "*" ? el("em", null, t.slice(1, -1))
      : t[0] === "`" ? el("code", null, t.slice(1, -1)) : el("span", "cite", t.slice(1, -1)));
    last = re.lastIndex;
  }
  if (last < text.length) parent.append(text.slice(last));
}
function render(parent, text) {
  let list = null;
  for (const line of text.split("\n")) {
    const li = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)/);
    if (li) {
      if (!list) { list = el("ul"); parent.append(list); }
      const item = el("li"); inline(item, li[1]); list.append(item);
    } else {
      list = null;
      if (line.trim()) { const p = el("p"); inline(p, line); parent.append(p); }
    }
  }
}
function add(role, text, tools) {
  document.getElementById("welcome")?.remove();
  const box = el("div", "msg " + role);
  if (role === "user") box.textContent = text; else render(box, text);
  if (tools && tools.length) {
    const meta = el("div", "meta");
    for (const t of tools) meta.append(el("span", "tag", t.name));
    if (tools.some(t => t.flagged)) meta.append(el("span", "tag flag", "Guard flagged an injection attempt in tool output"));
    box.append(meta);
  }
  log.append(box); log.scrollTop = log.scrollHeight;
  return box;
}
function setError(msg) { errBox.hidden = !msg; errBox.textContent = msg || ""; }

async function post(path, body) {
  const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Request failed (" + res.status + ")");
  return data;
}
async function ask(text) {
  if (busy || !text.trim()) return;
  busy = true; sendBtn.disabled = true; setError("");
  add("user", text); input.value = ""; input.style.height = "auto";
  const typing = add("bot typing", ""); typing.append(el("span"), el("span"), el("span"));
  try {
    const data = await post("/api/chat", { session_id: sessionId, message: text });
    sessionId = data.session_id; typing.remove(); add("bot", data.answer, data.tools);
  } catch (e) { typing.remove(); setError(e.message); }
  busy = false; sendBtn.disabled = false; input.focus();
}
form.addEventListener("submit", e => { e.preventDefault(); ask(input.value); });
input.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(input.value); } });
input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = input.scrollHeight + "px"; });
document.querySelectorAll(".chip").forEach(c => c.addEventListener("click", () => ask(c.textContent)));
document.getElementById("reset").addEventListener("click", async () => {
  if (sessionId) await post("/api/reset", { session_id: sessionId }).catch(() => {});
  location.reload();
});
