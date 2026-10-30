"use strict";

// ---------------------------------------------------------------- utilities
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

async function api(route, body = {}) {
  const r = await fetch("/api/" + route, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({ error: r.statusText }));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

let toastTimer;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 3500);
}

// ---------------------------------------------------------------- state
const S = {
  game: null,         // /api/state
  level: null,        // /api/open
  dirty: false,
  breakpoints: new Set(),
  errors: new Map(),  // line -> message
  debug: null,        // last debugger view
  session: null,
  hideLevels: false,
};

// ---------------------------------------------------------------- markdown (just what briefs use)
function inline(s) {
  // Protect `code` spans first so emphasis can wrap around them.
  const codes = [];
  s = s.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*\s][^*]*)\*/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${esc(codes[Number(i)])}</code>`);
}

function markdown(md) {
  const lines = md.split("\n");
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("```")) {
      const buf = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]);
      i++;
      out.push(`<pre><code>${esc(buf.join("\n"))}</code></pre>`);
      continue;
    }
    const h = line.match(/^(#{1,3})\s+(.*)/);
    if (h) { out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`); i++; continue; }
    if (line.startsWith("|")) {
      const rows = [];
      while (i < lines.length && lines[i].startsWith("|")) rows.push(lines[i++]);
      const cells = (r) => r.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const body = rows.filter((r) => !/^\|[\s|:-]+\|$/.test(r));
      const [head, ...rest] = body;
      out.push("<table><thead><tr>" + cells(head).map((c) => `<th>${inline(c)}</th>`).join("") + "</tr></thead><tbody>" +
        rest.map((r) => "<tr>" + cells(r).map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>").join("") + "</tbody></table>");
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items = [];
      while (i < lines.length && (/^\s*([-*]|\d+\.)\s+/.test(lines[i]) || (/^\s{2,}\S/.test(lines[i]) && items.length))) {
        if (/^\s*([-*]|\d+\.)\s+/.test(lines[i])) items.push(lines[i].replace(/^\s*([-*]|\d+\.)\s+/, ""));
        else items[items.length - 1] += " " + lines[i].trim();
        i++;
      }
      const tag = ordered ? "ol" : "ul";
      out.push(`<${tag}>` + items.map((it) => `<li>${inline(it)}</li>`).join("") + `</${tag}>`);
      continue;
    }
    if (!line.trim()) { i++; continue; }
    const para = [];
    while (i < lines.length && lines[i].trim() && !/^(#|```|\||\s*([-*]|\d+\.)\s)/.test(lines[i])) para.push(lines[i++]);
    out.push(`<p>${inline(para.join(" "))}</p>`);
  }
  return out.join("\n");
}

// ---------------------------------------------------------------- NASM highlighting
const REG = /^(r(ax|bx|cx|dx|si|di|bp|sp|ip|[89]|1[0-5])[dwb]?|e(ax|bx|cx|dx|si|di|bp|sp|ip)|[abcd][xlh]|si|di|bp|sp|[sd]il|bpl|spl|[cdefgs]s|[xyz]mm\d+|k[0-7]|cr\d|dr\d)$/i;
const DIRECTIVE = /^(section|segment|global|extern|bits|org|default|align|db|dw|dd|dq|dt|do|dy|dz|resb|resw|resd|resq|rest|reso|resy|resz|times|equ|incbin|struc|endstruc|istruc|iend|at|byte|word|dword|qword|tword|oword|yword|zword|rel|abs|strict|%\w+)$/i;

function highlightLine(line) {
  let html = "";
  let i = 0;
  let firstWord = true;
  while (i < line.length) {
    const ch = line[i];
    const rest = line.slice(i);
    if (ch === ";") { html += `<span class="t-c">${esc(rest)}</span>`; break; }
    if (ch === '"' || ch === "'" || ch === "`") {
      let j = i + 1;
      while (j < line.length && line[j] !== ch) j += line[j] === "\\" && ch === "`" ? 2 : 1;
      html += `<span class="t-s">${esc(line.slice(i, j + 1))}</span>`;
      i = j + 1;
      continue;
    }
    const word = rest.match(/^[%.$?@\w]+/);
    if (word) {
      const w = word[0];
      let cls = "";
      const isLabel = line.slice(i + w.length).startsWith(":");
      if (isLabel) cls = "t-l";
      else if (/^(0x[\da-f_]+|0b[01_]+|0o[0-7_]+|[0-9][\da-f_]*[hqob]?|\d[\d_]*)$/i.test(w)) cls = "t-n";
      else if (REG.test(w)) cls = "t-r";
      else if (DIRECTIVE.test(w)) cls = "t-d";
      else if (firstWord) cls = "t-m";
      html += cls ? `<span class="${cls}">${esc(w)}</span>` : esc(w);
      if (!isLabel) firstWord = false;
      i += w.length;
      continue;
    }
    html += esc(ch);
    i++;
  }
  return html;
}

// ---------------------------------------------------------------- editor
const code = $("#code");
const hl = $("#highlight");
const gutter = $("#gutter");

function currentLine() {
  return S.debug && S.debug.line && !S.debug.binary ? S.debug.line : null;
}

function renderEditor() {
  const lines = code.value.split("\n");
  const cur = currentLine();
  hl.innerHTML = lines.map((l, idx) => {
    const n = idx + 1;
    const cls = ["ln", n === cur ? "cur" : "", S.errors.has(n) ? "err" : ""].join(" ");
    return `<span class="${cls}">${highlightLine(l) || " "}</span>`;
  }).join("");
  gutter.innerHTML = lines.map((_, idx) => {
    const n = idx + 1;
    const cls = [S.breakpoints.has(n) ? "bp" : "", n === cur ? "cur" : "", S.errors.has(n) ? "err" : ""].join(" ");
    const title = S.errors.get(n) || "Click to toggle a breakpoint";
    return `<div class="${cls}" data-line="${n}" title="${esc(title)}">${n}</div>`;
  }).join("") + "<div></div>".repeat(3);
  syncScroll();
}

function syncScroll() {
  hl.scrollTop = code.scrollTop;
  hl.scrollLeft = code.scrollLeft;
  gutter.scrollTop = code.scrollTop;
}

function scrollToLine(n) {
  const lh = parseFloat(getComputedStyle(code).lineHeight);
  const top = (n - 1) * lh;
  if (top < code.scrollTop || top > code.scrollTop + code.clientHeight - 2 * lh) {
    code.scrollTop = Math.max(0, top - code.clientHeight / 3);
  }
  syncScroll();
}

code.addEventListener("input", () => { setDirty(true); S.errors.clear(); renderEditor(); });
code.addEventListener("scroll", syncScroll);
code.addEventListener("keydown", (e) => {
  if (e.key === "Tab" && !e.ctrlKey && !e.metaKey) {
    e.preventDefault();
    const { selectionStart: s, selectionEnd: t } = code;
    code.setRangeText("    ", s, t, "end");
    code.dispatchEvent(new Event("input"));
  }
});
gutter.addEventListener("click", (e) => {
  const n = Number(e.target.dataset.line);
  if (!n) return;
  S.breakpoints.has(n) ? S.breakpoints.delete(n) : S.breakpoints.add(n);
  renderEditor();
});

function setDirty(d) {
  S.dirty = d;
  $("#dirty").classList.toggle("hidden", !d);
}

function setReadOnly(ro) {
  code.readOnly = ro;
  $("#editor").classList.toggle("readonly", ro);
}

// ---------------------------------------------------------------- levels & header
const TIERS = { 1: "◆", 2: "◆◆", 3: "◆◆◆", 4: "◆◆◆◆" };

function renderLevels() {
  const nav = $("#levels");
  let html = "";
  let arc = null;
  for (const lv of S.game.levels) {
    if (lv.arc !== arc) { arc = lv.arc; html += `<div class="arc">Arc ${esc(arc)}</div>`; }
    const mark = lv.completed ? '<span class="done">✔</span>' : lv.current ? '<span class="cur">▶</span>' : "";
    const tag = lv.bug ? `<span class="tag bug" title="bug level">bug ${TIERS[lv.bug]}</span>`
      : lv.boss ? '<span class="tag boss">boss</span>' : "";
    const active = S.level && S.level.number === lv.number ? " active" : "";
    html += `<button class="lvl${active}" data-n="${lv.number}" ${lv.unlocked ? "" : "disabled"}>
      <span class="mark">${mark}</span><span class="num">${lv.number}</span>
      <span class="t">${lv.unlocked ? esc(lv.title) : "sealed"}</span>${lv.unlocked ? tag : ""}</button>`;
  }
  nav.innerHTML = html;
  const g = S.game;
  $("#stats").innerHTML = `Cleared <b>${g.cleared}</b> · Heat <b>${g.heat}</b> · Badges <b>${g.badges.length}</b>`;
}

$("#levels").addEventListener("click", (e) => {
  const b = e.target.closest(".lvl");
  if (b && !b.disabled) openLevel(Number(b.dataset.n));
  if (window.innerWidth <= 1000) toggleLevels(false);
});

function toggleLevels(show) {
  S.hideLevels = show === undefined ? !S.hideLevels : !show;
  $(".layout").classList.toggle("no-levels", S.hideLevels);
}
$("#toggle-levels").addEventListener("click", () => toggleLevels());

async function refreshState() {
  S.game = await api("state");
  renderLevels();
}

async function openLevel(n) {
  if (S.dirty && S.level) await save();  // switching levels keeps your work
  stopDebug();
  const lv = await api("open", { level: n });
  S.level = lv;
  S.errors.clear();
  S.breakpoints.clear();
  code.value = lv.text;
  code.scrollTop = 0;
  setDirty(false);
  renderEditor();
  const kind = lv.bug ? ` · bug ${TIERS[lv.bug]}` : lv.boss ? " · boss" : "";
  $("#where").innerHTML = `<b>Level ${lv.number}</b> — ${esc(lv.title)} <span class="muted">· Arc ${esc(lv.arc)}${kind}</span>`;
  $("#file-name").textContent = lv.path;
  document.title = `Level ${lv.number} — ${lv.title} · NASM Adventures`;
  $("#tab-brief").innerHTML = markdown(lv.brief) +
    `<div class="chips">${lv.introduces.map((t) => `<span class="chip" data-doc="${esc(t)}">${esc(t)}</span>`).join("")}</div>`;
  renderHints();
  renderDebugTargets();
  $("#listing-out").textContent = "";
  $("#btab-results").innerHTML = '<p class="muted">Press <b>Test</b> (Ctrl+Enter) to build and run the public tests.</p>';
  showTab("brief");
  renderLevels();
}

// ---------------------------------------------------------------- tabs
function showTab(name) {
  $$(".left .tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $$(".left .pane").forEach((p) => p.classList.toggle("hidden", p.id !== "tab-" + name));
  if (name === "listing") loadListing();
}
$$(".left .tab").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));

function showBottom(name) {
  $$(".bottom .tab").forEach((t) => t.classList.toggle("active", t.dataset.btab === name));
  $$(".bpane").forEach((p) => p.classList.toggle("hidden", p.id !== "btab-" + name));
}
$$(".bottom .tab").forEach((t) => t.addEventListener("click", () => showBottom(t.dataset.btab)));

// ---------------------------------------------------------------- hints & docs & listing
function renderHints() {
  const h = S.level.hints;
  let html = `<p class="muted">Hints get more specific each time. Each one adds heat (1, 2, then 4);
    heat is only a score and never blocks progress.</p>`;
  for (let i = 1; i <= h.count; i++) {
    const text = h.revealed[String(i)];
    if (text) html += `<div class="hint"><b>Hint ${i}</b><pre>${esc(text)}</pre></div>`;
    else {
      const next = i === 1 || h.revealed[String(i - 1)];
      html += `<div class="hint"><b>Hint ${i}</b> <button class="btn small" data-hint="${i}" ${next ? "" : "disabled"}>Reveal</button></div>`;
    }
  }
  $("#tab-hints").innerHTML = html;
}

$("#tab-hints").addEventListener("click", async (e) => {
  const n = e.target.dataset.hint;
  if (!n) return;
  try {
    const r = await api("hint", { level: S.level.number, n: Number(n) });
    S.level.hints.revealed[n] = r.text;
    renderHints();
    if (r.heat_added) toast(`+${r.heat_added} heat`);
    refreshState();
  } catch (err) { toast(err.message); }
});

async function lookup(q) {
  showTab("docs");
  $("#docs-q").value = q;
  const r = await api("docs", { q });
  $("#docs-out").textContent = r.text;
}
$("#docs-form").addEventListener("submit", (e) => { e.preventDefault(); lookup($("#docs-q").value); });
$("#tab-brief").addEventListener("click", (e) => {
  const d = e.target.dataset.doc;
  if (d) lookup(d.split(/[\s,(]/)[0]);
});

async function loadListing() {
  if (!S.level) return;
  const r = await api("listing", { level: S.level.number, text: code.value });
  setDirty(false);
  $("#listing-out").textContent = r.build_error ? "Build failed:\n" + r.build_error :
    (S.level.mode === "fragment" ? "; lines 1-4 and the end are the program the game wraps around your code\n\n" : "") + r.listing;
}
$("#listing-refresh").addEventListener("click", loadListing);

// ---------------------------------------------------------------- save / test / submit
async function save() {
  if (!S.level) return;
  await api("save", { level: S.level.number, text: code.value });
  setDirty(false);
}

function showBuildError(r) {
  S.errors = new Map(r.errors.map((e) => [e.line, `${e.kind}: ${e.message}`]));
  renderEditor();
  const lines = esc(r.build_error).replace(/solution\.asm:(\d+):/g,
    '<span class="errline" data-line="$1">solution.asm:$1:</span>');
  $("#btab-results").innerHTML = `<div class="result-title bad">Build failed</div><pre class="problem" style="margin-left:0">${lines}</pre>`;
  showBottom("results");
}

$("#btab-results").addEventListener("click", (e) => {
  const n = Number(e.target.dataset.line);
  if (n) { scrollToLine(n); code.focus(); }
  if (e.target.dataset.next) openLevel(Number(e.target.dataset.next));
});

async function runTests(submit) {
  if (!S.level) return;
  stopDebug();
  $("#btab-results").innerHTML = `<p class="muted">${submit ? "Submitting" : "Testing"}…</p>`;
  showBottom("results");
  let r;
  try {
    r = await api("test", { level: S.level.number, text: code.value, submit });
  } catch (err) { $("#btab-results").innerHTML = `<p class="bad">${esc(err.message)}</p>`; return; }
  setDirty(false);
  if (r.build_error) return showBuildError(r);
  S.errors.clear();
  renderEditor();
  const mark = (ok) => ok ? '<span class="ok">✔</span>' : '<span class="bad">✘</span>';
  let html = `<div class="result-title">Level ${S.level.number} — ${esc(S.level.title)}</div>`;
  for (const t of r.tests) {
    html += `<div class="row">${mark(t.passed)} ${esc(t.name)}</div>`;
    for (const p of t.problems) html += `<div class="problem">${esc(p)}</div>`;
  }
  if (r.hidden.total) {
    html += `<div class="row">${mark(!r.hidden.first_failure)} hidden tests ${r.hidden.passed}/${r.hidden.total}</div>`;
    if (r.hidden.first_failure) html += `<div class="problem">first failure (${esc(r.hidden.first_failure.name)}): ${esc(r.hidden.first_failure.problem)}</div>`;
  }
  for (const c of r.checks) html += `<div class="row">${mark(c.passed)} ${esc(c.name)} <span class="note">${c.detail ? "(" + esc(c.detail) + ")" : ""}</span></div>`;
  for (const c of r.stretch) html += `<div class="row">${c.passed ? '<span class="ok">✔</span>' : '<span class="note">─</span>'} stretch: ${esc(c.name)} <span class="note">${c.detail ? "(" + esc(c.detail) + ")" : ""}</span></div>`;
  if (submit && r.opened) {
    html += `<div class="banner"><b>Level ${S.level.number} is open.</b> ${r.badges.map((b) => `Badge earned: ${esc(b)}.`).join(" ")}
      ${r.next ? `<button class="btn primary small" data-next="${r.next.number}">Descend to level ${r.next.number}: ${esc(r.next.title)}</button>`
      : "You have cleared every level that exists so far. More are being forged."}</div>`;
    refreshState();
  } else if (submit) {
    html += `<div class="banner fail">The gate holds. Fix the failures above and submit again.</div>`;
  } else if (r.passed) {
    html += `<div class="banner">Public tests pass. <b>Submit</b> runs the hidden tests too.</div>`;
  }
  $("#btab-results").innerHTML = html;
}

$("#btn-save").addEventListener("click", () => save().then(() => toast("Saved")));
$("#btn-test").addEventListener("click", () => runTests(false));
$("#btn-submit").addEventListener("click", () => runTests(true));
$("#btn-reset").addEventListener("click", async () => {
  if (!confirm("Replace your code with the level's starter file? Your current code will be lost.")) return;
  const r = await api("reset", { level: S.level.number });
  code.value = r.text;
  setDirty(false);
  renderEditor();
});

// ---------------------------------------------------------------- debugger
function renderDebugTargets() {
  const sel = $("#dbg-target");
  const opts = S.level.tests.map((t) => `<option value="test:${esc(t)}">your code — test: ${esc(t)}</option>`);
  if (!S.level.tests.length) opts.push('<option value="test:">your code</option>');
  for (const b of S.level.binaries) opts.push(`<option value="bin:${esc(b)}">program: ${esc(b)} (no source)</option>`);
  sel.innerHTML = opts.join("");
}

function setDebugControls(running) {
  $$(".dbg-bar [data-cmd]").forEach((b) => (b.disabled = !running));
  $("#dbg-stop").disabled = !running;
}
setDebugControls(false);

function stopDebug() {
  S.session = null;
  S.debug = null;
  setReadOnly(false);
  setDebugControls(false);
  $("#dbg-status").textContent = "";
  renderEditor();
}

async function startDebug() {
  const [kind, value] = $("#dbg-target").value.split(/:(.*)/s);
  const body = { level: S.level.number, text: code.value };
  if (kind === "bin") body.binary = value; else body.test = value;
  showBottom("debug");
  let r;
  try { r = await api("debug/start", body); } catch (err) { return toast(err.message); }
  setDirty(false);
  if (r.build_error) return showBuildError(r);
  S.session = r.session;
  r.binary = kind === "bin";
  S.memAddr = S.memAddr && r.symbols.includes(S.memAddr) ? S.memAddr : (r.symbols.find((s) => !s.startsWith("_")) || "rsp");
  setReadOnly(!r.binary);
  setDebugControls(true);
  showDebug(r);
}

async function debugCmd(cmd) {
  if (!S.session) return;
  try {
    const r = await api("debug/cmd", { session: S.session, cmd, breakpoints: [...S.breakpoints] });
    r.binary = S.debug && S.debug.binary;
    showDebug(r);
  } catch (err) { toast(err.message); stopDebug(); }
}

function showDebug(v) {
  S.debug = v;
  const status = {
    ready: "paused", running: "paused", done: "reached the end of your code — use back to rewind",
    exited: `program exited with status ${v.exit_code} — use back to rewind`,
    fault: v.fault, limit: "step limit reached",
  }[v.state] || v.state;
  const st = $("#dbg-status");
  st.textContent = `${v.steps} steps · rip ${v.rip}${v.where ? " <" + v.where + ">" : ""}${v.line ? " · line " + v.line : ""} · ${status}` +
    (v.stop === "breakpoint" ? " · breakpoint" : "");
  st.classList.toggle("fault", v.state === "fault");
  $('[data-cmd="back"]').disabled = $('[data-cmd="rcontinue"]').disabled = !v.can_back;
  const fin = ["done", "exited", "fault", "limit"].includes(v.state);
  $$('[data-cmd="step"], [data-cmd="line"], [data-cmd="continue"]').forEach((b) => (b.disabled = fin));

  const regs = v.regs.map((r) => `<div class="reg${r.changed ? " changed" : ""}"><span class="n">${r.name}</span> <span class="v">${r.value}</span></div>`).join("");
  const flags = v.flags.map((f) => `<span class="flag${f.set ? " on" : ""}${f.changed ? " changed" : ""}" title="${f.set ? "set" : "clear"}">${f.name}</span>`).join("");
  const dis = v.disasm.map((d) => `<div class="${d.current ? "cur" : ""}">${d.current ? "→" : " "} ${d.addr}  ${d.bytes.padEnd(24)} ${esc(d.text).padEnd(30)} ${d.line ? "line " + d.line : ""}</div>`).join("");
  const stack = v.stack.map((s, i) => `${i === 0 ? "rsp→" : "    "} ${s.addr}  ${s.value ?? "<unmapped>"}${s.label ? "  <" + esc(s.label) + ">" : ""}`).join("\n");
  const syms = v.symbols.map((s) => `<option value="${esc(s)}">`).join("");
  $("#dbg-body").innerHTML = `
    <div class="box"><h4>Registers</h4><div class="regs">${regs}</div><div class="flags">${flags}</div></div>
    <div class="box"><h4>Disassembly</h4><div class="mono dis">${dis || "<span class='muted'>no code here</span>"}</div></div>
    <div class="box"><h4>Memory</h4>
      <form class="mem-form" id="mem-form"><input id="mem-addr" list="mem-syms" value="${esc(S.memAddr)}" title="label, register, number, or label+offset"><datalist id="mem-syms">${syms}</datalist><button class="btn small">Show</button></form>
      <div id="mem-out" class="mono"></div></div>
    <div class="box"><h4>Stack</h4><div class="mono">${stack}</div></div>
    <div class="box wide"><h4>Output</h4><pre class="out">${v.stdout ? esc(v.stdout) : '<span class="muted">(no stdout yet)</span>'}${v.stderr ? '\n<span class="bad">' + esc(v.stderr) + "</span>" : ""}</pre>
      ${v.syscalls.length ? `<div class="mono muted">${v.syscalls.map(esc).join("\n")}</div>` : ""}</div>`;
  $("#mem-form").addEventListener("submit", (e) => { e.preventDefault(); S.memAddr = $("#mem-addr").value; loadMemory(); });
  loadMemory();
  renderEditor();
  if (v.line && !v.binary) scrollToLine(v.line);
}

async function loadMemory() {
  if (!S.session) return;
  try {
    const r = await api("debug/memory", { session: S.session, addr: S.memAddr, length: 96 });
    $("#mem-out").textContent = r.rows.map((row) => row.hex === null ? `${row.addr}  <unmapped>` :
      `${row.addr}  ${row.hex}  ${row.ascii}${row.label ? "  <" + row.label + ">" : ""}`).join("\n");
  } catch (err) { $("#mem-out").textContent = err.message; }
}

$("#dbg-start").addEventListener("click", startDebug);
$("#dbg-stop").addEventListener("click", stopDebug);
$$(".dbg-bar [data-cmd]").forEach((b) => b.addEventListener("click", () => debugCmd(b.dataset.cmd)));

// ---------------------------------------------------------------- keyboard
document.addEventListener("keydown", (e) => {
  const mod = e.ctrlKey || e.metaKey;
  if (mod && e.key === "s") { e.preventDefault(); save().then(() => toast("Saved")); }
  else if (mod && e.key === "Enter") { e.preventDefault(); runTests(e.shiftKey); }
  else if (S.session && e.key === "F7") { e.preventDefault(); debugCmd(e.shiftKey ? "back" : "step"); }
  else if (S.session && e.key === "F8") { e.preventDefault(); debugCmd("line"); }
  else if (S.session && e.key === "F5") { e.preventDefault(); debugCmd(e.shiftKey ? "rcontinue" : "continue"); }
});
window.addEventListener("beforeunload", (e) => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });

// ---------------------------------------------------------------- start
(async () => {
  try {
    if (window.innerWidth <= 1000) toggleLevels(false);
    await refreshState();
    const start = S.game.levels.find((l) => l.current) || S.game.levels.filter((l) => l.unlocked).pop();
    if (start) await openLevel(start.number);
  } catch (err) {
    document.body.innerHTML = `<p style="padding:20px">Could not reach the game engine: ${esc(err.message)}</p>`;
  }
})();
