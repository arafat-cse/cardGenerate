"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const FIELDS = ["company", "name", "title", "tagline", "phone", "email", "website", "address"];
const FONT_KEYS = ["sans", "sansBold", "serif", "serifBold", "serifItal", "mono", "blackletter"];
const SAMPLE_DATA = {
  company: "Northwind Studio", name: "Jubaer Ahmed", title: "Creative Director",
  tagline: "Design · Print · Brand", phone: "+880 1712 345678",
  email: "hello@northwind.co", website: "northwind.co", address: "221 Farmgate, Dhaka 1205",
};

const CANVAS_W_MM = 86, CANVAS_H_MM = 54, PX_PER_MM = 8;
const CANVAS_W = CANVAS_W_MM * PX_PER_MM, CANVAS_H = CANVAS_H_MM * PX_PER_MM;

const state = {
  cid: localStorage.getItem("bizcard_editor_cid") || (() => {
    const id = crypto.randomUUID();
    localStorage.setItem("bizcard_editor_cid", id);
    return id;
  })(),
  tpl: null,
  side: "front",
  sel: null,       // { group: "background"|"elements", index }
  undoStack: [],
  redoStack: [],
  dirty: false,
};

// ---------------------------------------------------------------- helpers (mirrors app.js)

function toast(msg, isErr = false, ms = 4200) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.toggle("err", isErr);
  t.classList.remove("hidden");
  clearTimeout(toast._h);
  toast._h = setTimeout(() => t.classList.add("hidden"), ms);
}

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  let body = null;
  try { body = await res.json(); } catch { /* ignore */ }
  if (!res.ok) throw new Error((body && body.detail) || `Request failed (${res.status})`);
  return body;
}

function busy(on, text = "Working…") {
  $("#busy").classList.toggle("hidden", !on);
  $("#busyText").textContent = text;
}

function getJSON(url) { return api(url); }
function putJSON(url, body) {
  return api(url, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}
function postJSON(url, body) {
  return api(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

// ---------------------------------------------------------------- template list

async function loadTemplateList() {
  const list = await api("/api/templates");
  const grid = $("#tplList");
  grid.innerHTML = "";
  for (const t of list) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tpl" + (state.tpl && state.tpl.id === t.id ? " sel" : "");
    btn.innerHTML = `<img loading="lazy" src="${t.preview}" alt="${t.name}">
      <span class="tpl-name">${t.name}${t.is_custom ? ' <span class="tag">custom</span>' : ""}</span>
      <span class="tpl-desc">${t.desc || ""}</span>`;
    btn.addEventListener("click", () => pickTemplate(t));
    grid.appendChild(btn);
  }
}

async function pickTemplate(t) {
  busy(true, "Loading…");
  try {
    if (t.is_custom) {
      const tpl = await getJSON(`/api/templates/${t.id}/config`);
      openTemplate(tpl);
    } else {
      const tpl = await postJSON("/api/templates/custom", { name: `${t.name} copy`, source_id: t.id });
      openTemplate(tpl);
      toast(`Duplicated "${t.name}" as an editable copy`);
      await loadTemplateList();
    }
  } catch (e) {
    toast(e.message, true);
  } finally {
    busy(false);
  }
}

function openTemplate(tpl) {
  state.tpl = tpl;
  state.side = "front";
  state.sel = null;
  state.undoStack = [];
  state.redoStack = [];
  $$(".side-tab").forEach((b) => b.classList.toggle("sel", b.dataset.side === "front"));
  setControlsEnabled(true);
  $("#tplName").value = tpl.name || "";
  $("#statusLine").textContent = `Editing "${tpl.name}" (${tpl.id}) — drag boxes on the canvas, or click one in the Elements list.`;
  renderAll();
  refreshPreview();
}

function setControlsEnabled(on) {
  for (const id of ["addText", "addImage", "addQr", "addRect", "addPalColor",
                     "deleteTplBtn", "applyAdv"]) {
    $("#" + id).disabled = !on;
  }
  $("#tplName").disabled = !on;
  $("#advJson").disabled = !on;
  $$(".side-tab").forEach((b) => { b.disabled = !on; });
}

// ---------------------------------------------------------------- undo/redo

function snapshot() {
  state.undoStack.push(JSON.stringify(state.tpl));
  if (state.undoStack.length > 50) state.undoStack.shift();
  state.redoStack = [];
  updateUndoRedoButtons();
}

function undo() {
  if (!state.undoStack.length) return;
  state.redoStack.push(JSON.stringify(state.tpl));
  state.tpl = JSON.parse(state.undoStack.pop());
  state.sel = null;
  updateUndoRedoButtons();
  renderAll();
  schedulePersist();
}

function redo() {
  if (!state.redoStack.length) return;
  state.undoStack.push(JSON.stringify(state.tpl));
  state.tpl = JSON.parse(state.redoStack.pop());
  state.sel = null;
  updateUndoRedoButtons();
  renderAll();
  schedulePersist();
}

function updateUndoRedoButtons() {
  $("#undoBtn").disabled = state.undoStack.length === 0;
  $("#redoBtn").disabled = state.redoStack.length === 0;
}

// ---------------------------------------------------------------- persistence

let persistTimer = null;
function schedulePersist(delay = 500) {
  if (!state.tpl) return;
  state.dirty = true;
  $("#saveStatus").textContent = "saving…";
  clearTimeout(persistTimer);
  persistTimer = setTimeout(persistNow, delay);
}

async function persistNow() {
  if (!state.tpl) return;
  try {
    await putJSON(`/api/templates/custom/${state.tpl.id}`, state.tpl);
    state.dirty = false;
    $("#saveStatus").textContent = "saved";
    await refreshPreview();
    await loadTemplateList();
  } catch (e) {
    $("#saveStatus").textContent = "error";
    toast(e.message, true);
  }
}

async function refreshPreview() {
  if (!state.tpl) return;
  try {
    const res = await postJSON("/api/templates/preview-side", {
      cid: state.cid, template_id: state.tpl.id, side: state.side, data: SAMPLE_DATA,
    });
    $("#canvasBg").src = res.url;
  } catch (e) {
    toast(e.message, true);
  }
}

// ---------------------------------------------------------------- side helpers

function curSide() { return state.tpl.sides[state.side]; }

function bgShapes() {
  return (curSide().background || [])
    .map((b, i) => ({ b, i }))
    .filter(({ b }) => (b.t === "rect" || b.t === "ellipse") && !(b.w >= 0.95 && b.h >= 0.95));
}

function layerEntries() {
  const out = [];
  for (const { b, i } of bgShapes()) out.push({ group: "background", index: i, obj: b });
  for (let i = 0; i < (curSide().elements || []).length; i++) {
    const el = curSide().elements[i];
    if (el.t === "text" || el.t === "image" || el.t === "qr") out.push({ group: "elements", index: i, obj: el });
  }
  return out;
}

function getSelObj() {
  if (!state.sel) return null;
  const arr = state.sel.group === "background" ? curSide().background : curSide().elements;
  return arr[state.sel.index];
}

function labelFor(entry) {
  const o = entry.obj;
  if (entry.group === "background") return `Shape (${o.t})`;
  if (o.t === "text") return `Text: ${o.lit ? `"${o.lit}"` : Array.isArray(o.field) ? o.field.join("+") : (o.field || "")}`;
  if (o.t === "image") return `Image: ${o.role}`;
  if (o.t === "qr") return "QR code";
  return o.t;
}

// ---------------------------------------------------------------- rendering: overlay + lists

function renderAll() {
  $("#sideLabel").textContent = state.side;
  $("#advSideLabel").textContent = state.side;
  $("#advJson").value = state.tpl ? JSON.stringify(curSide(), null, 2) : "";
  renderElementList();
  renderOverlay();
  renderPropForm();
  renderPalette();
}

function renderElementList() {
  const box = $("#elementList");
  box.innerHTML = "";
  if (!state.tpl) {
    $("#dupElBtn").disabled = true;
    $("#delElBtn").disabled = true;
    return;
  }
  for (const entry of layerEntries()) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "elem-row" + (isSelected(entry) ? " sel" : "");
    row.textContent = labelFor(entry);
    row.addEventListener("click", () => selectEntry(entry));
    box.appendChild(row);
  }
  const hasSel = !!state.sel;
  $("#dupElBtn").disabled = !hasSel;
  $("#delElBtn").disabled = !hasSel;
}

function isSelected(entry) {
  return state.sel && state.sel.group === entry.group && state.sel.index === entry.index;
}

function selectEntry(entry) {
  state.sel = { group: entry.group, index: entry.index };
  renderElementList();
  renderOverlay();
  renderPropForm();
}

function renderOverlay() {
  const layer = $("#overlayLayer");
  layer.innerHTML = "";
  if (!state.tpl) return;
  for (const entry of layerEntries()) {
    const o = entry.obj;
    const box = document.createElement("div");
    box.className = "el-box" + (isSelected(entry) ? " sel" : "") + (entry.group === "background" ? " bg" : "");
    box.style.left = (o.x * CANVAS_W) + "px";
    box.style.top = (o.y * CANVAS_H) + "px";
    box.style.width = (o.w * CANVAS_W) + "px";
    box.style.height = (o.h * CANVAS_H) + "px";
    box.title = labelFor(entry);
    box.addEventListener("pointerdown", (ev) => startDrag(ev, entry, "move"));
    const handle = document.createElement("div");
    handle.className = "resize-handle";
    handle.addEventListener("pointerdown", (ev) => { ev.stopPropagation(); startDrag(ev, entry, "resize"); });
    box.appendChild(handle);
    layer.appendChild(box);
  }
}

// ---------------------------------------------------------------- drag / resize

function startDrag(ev, entry, mode) {
  ev.preventDefault();
  selectEntry(entry);
  const obj = entry.obj;
  const start = { x: obj.x, y: obj.y, w: obj.w, h: obj.h, px: ev.clientX, py: ev.clientY };
  let moved = false;

  function onMove(e) {
    const dx = (e.clientX - start.px) / CANVAS_W;
    const dy = (e.clientY - start.py) / CANVAS_H;
    if (Math.abs(e.clientX - start.px) > 2 || Math.abs(e.clientY - start.py) > 2) moved = true;
    if (mode === "move") {
      obj.x = clamp(start.x + dx, 0, 1 - obj.w);
      obj.y = clamp(start.y + dy, 0, 1 - obj.h);
    } else {
      obj.w = clamp(start.w + dx, 0.02, 1 - obj.x);
      obj.h = clamp(start.h + dy, 0.02, 1 - obj.y);
    }
    renderOverlay();
  }
  function onUp() {
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", onUp);
    if (moved) {
      snapshot();
      schedulePersist();
    }
  }
  document.addEventListener("pointermove", onMove);
  document.addEventListener("pointerup", onUp);
}

function clamp(v, lo, hi) {
  if (hi < lo) hi = lo;
  return Math.min(hi, Math.max(lo, v));
}

// ---------------------------------------------------------------- property form

function field(labelText, inputEl) {
  const lab = document.createElement("label");
  lab.textContent = labelText;
  lab.appendChild(inputEl);
  return lab;
}

function selectEl(options, value) {
  const sel = document.createElement("select");
  for (const [v, text] of options) {
    const opt = document.createElement("option");
    opt.value = v; opt.textContent = text;
    if (v === value) opt.selected = true;
    sel.appendChild(opt);
  }
  return sel;
}

function commitProp() { snapshot(); schedulePersist(); renderElementList(); renderOverlay(); }

function paletteOptions() {
  return Object.keys((state.tpl.palette || {})).map((k) => [k, k]);
}

function renderPropForm() {
  const form = $("#propForm");
  if (!state.tpl) {
    form.innerHTML = "";
    form.classList.add("hidden");
    $("#noSel").classList.remove("hidden");
    return;
  }
  const obj = getSelObj();
  form.innerHTML = "";
  form.classList.toggle("hidden", !obj);
  $("#noSel").classList.toggle("hidden", !!obj);
  if (!obj) return;

  if (obj.t === "text") {
    const isLit = "lit" in obj;
    const kind = selectEl([["field", "Data field"], ["lit", "Custom text"]], isLit ? "lit" : "field");
    kind.addEventListener("change", () => {
      if (kind.value === "lit") { obj.lit = obj.lit ?? "Text"; delete obj.field; }
      else { obj.field = obj.field ?? "name"; delete obj.lit; }
      commitProp(); renderPropForm();
    });
    form.appendChild(field("Source", kind));

    if (isLit) {
      const inp = document.createElement("input");
      inp.value = obj.lit;
      inp.addEventListener("change", () => { obj.lit = inp.value; commitProp(); });
      form.appendChild(field("Text", inp));
    } else {
      const sel = selectEl(FIELDS.map((f) => [f, f]), Array.isArray(obj.field) ? obj.field[0] : obj.field);
      sel.addEventListener("change", () => { obj.field = sel.value; commitProp(); });
      form.appendChild(field("Field", sel));
    }

    const font = selectEl(FONT_KEYS.map((f) => [f, f]), obj.font);
    font.addEventListener("change", () => { obj.font = font.value; commitProp(); });
    form.appendChild(field("Font", font));

    const size = document.createElement("input");
    size.type = "number"; size.step = "0.5"; size.min = "4"; size.max = "60"; size.value = obj.size;
    size.addEventListener("change", () => { obj.size = parseFloat(size.value) || obj.size; commitProp(); });
    form.appendChild(field("Size (pt)", size));

    const color = selectEl(paletteOptions(), obj.color);
    color.addEventListener("change", () => { obj.color = color.value; commitProp(); });
    form.appendChild(field("Color", color));

    const align = selectEl([["left", "left"], ["center", "center"], ["right", "right"]], obj.align || "left");
    align.addEventListener("change", () => { obj.align = align.value; commitProp(); });
    form.appendChild(field("Align", align));

    const track = document.createElement("input");
    track.type = "number"; track.step = "0.02"; track.value = obj.track || 0;
    track.addEventListener("change", () => { obj.track = parseFloat(track.value) || 0; commitProp(); });
    form.appendChild(field("Letter spacing", track));

    const caps = document.createElement("label");
    caps.className = "check";
    const capsInput = document.createElement("input");
    capsInput.type = "checkbox"; capsInput.checked = !!obj.caps;
    capsInput.addEventListener("change", () => { obj.caps = capsInput.checked; commitProp(); });
    caps.appendChild(capsInput);
    caps.append(" ALL CAPS");
    form.appendChild(caps);

  } else if (obj.t === "image") {
    const role = selectEl([["logo", "logo"], ["photo", "photo"]], obj.role);
    role.addEventListener("change", () => { obj.role = role.value; commitProp(); });
    form.appendChild(field("Role", role));

    const fit = selectEl([["contain", "contain"], ["cover", "cover"]], obj.fit || "contain");
    fit.addEventListener("change", () => { obj.fit = fit.value; commitProp(); });
    form.appendChild(field("Fit", fit));

    const circle = document.createElement("label");
    circle.className = "check";
    const circleInput = document.createElement("input");
    circleInput.type = "checkbox"; circleInput.checked = obj.shape === "circle";
    circleInput.addEventListener("change", () => { obj.shape = circleInput.checked ? "circle" : undefined; commitProp(); });
    circle.appendChild(circleInput);
    circle.append(" Circular");
    form.appendChild(circle);

  } else if (obj.t === "qr") {
    const panel = document.createElement("label");
    panel.className = "check";
    const panelInput = document.createElement("input");
    panelInput.type = "checkbox"; panelInput.checked = !!obj.panel;
    panelInput.addEventListener("change", () => { obj.panel = panelInput.checked; commitProp(); renderPropForm(); });
    panel.appendChild(panelInput);
    panel.append(" Panel behind QR");
    form.appendChild(panel);

    if (obj.panel) {
      const pcolor = selectEl(paletteOptions(), obj.panel_color || "bg");
      pcolor.addEventListener("change", () => { obj.panel_color = pcolor.value; commitProp(); });
      form.appendChild(field("Panel color", pcolor));
    }

    const invert = document.createElement("label");
    invert.className = "check";
    const invertInput = document.createElement("input");
    invertInput.type = "checkbox"; invertInput.checked = !!obj.invert;
    invertInput.addEventListener("change", () => { obj.invert = invertInput.checked; commitProp(); });
    invert.appendChild(invertInput);
    invert.append(" Invert (light QR on dark bg)");
    form.appendChild(invert);

  } else if (obj.t === "rect" || obj.t === "ellipse") {
    const fill = selectEl([["", "(none)"], ...paletteOptions()], obj.fill || "");
    fill.addEventListener("change", () => { obj.fill = fill.value || undefined; commitProp(); });
    form.appendChild(field("Fill", fill));

    const stroke = selectEl([["", "(none)"], ...paletteOptions()], obj.stroke || "");
    stroke.addEventListener("change", () => { obj.stroke = stroke.value || undefined; commitProp(); });
    form.appendChild(field("Stroke", stroke));

    const strokeW = document.createElement("input");
    strokeW.type = "number"; strokeW.step = "0.1"; strokeW.value = obj.strokeW || 0;
    strokeW.addEventListener("change", () => { obj.strokeW = parseFloat(strokeW.value) || undefined; commitProp(); });
    form.appendChild(field("Stroke width", strokeW));

    if (obj.t === "rect") {
      const radius = document.createElement("input");
      radius.type = "number"; radius.step = "0.01"; radius.min = "0"; radius.max = "0.5"; radius.value = obj.radius || 0;
      radius.addEventListener("change", () => { obj.radius = parseFloat(radius.value) || 0; commitProp(); });
      form.appendChild(field("Corner radius (0–0.5)", radius));
    } else {
      const circle = document.createElement("label");
      circle.className = "check";
      const circleInput = document.createElement("input");
      circleInput.type = "checkbox"; circleInput.checked = !!obj.circle;
      circleInput.addEventListener("change", () => { obj.circle = circleInput.checked; commitProp(); });
      circle.appendChild(circleInput);
      circle.append(" Force circle");
      form.appendChild(circle);
    }
  }
}

// ---------------------------------------------------------------- palette

function renderPalette() {
  const box = $("#paletteList");
  box.innerHTML = "";
  if (!state.tpl) return;
  for (const [key, hex] of Object.entries(state.tpl.palette || {})) {
    const row = document.createElement("div");
    row.className = "pal-row";
    const swatch = document.createElement("input");
    swatch.type = "color"; swatch.value = /^#[0-9a-f]{6}$/i.test(hex) ? hex : "#000000";
    swatch.addEventListener("change", () => { state.tpl.palette[key] = swatch.value; snapshot(); schedulePersist(); });
    const name = document.createElement("span");
    name.className = "pal-key";
    name.textContent = key;
    const rm = document.createElement("button");
    rm.type = "button"; rm.className = "ghost danger small"; rm.textContent = "×";
    rm.addEventListener("click", () => {
      delete state.tpl.palette[key];
      snapshot(); schedulePersist(); renderPalette();
    });
    row.append(swatch, name, rm);
    box.appendChild(row);
  }
}

$("#addPalColor").addEventListener("click", () => {
  const key = $("#newPalKey").value.trim();
  if (!key) { toast("Enter a palette key name", true); return; }
  if (!state.tpl.palette) state.tpl.palette = {};
  state.tpl.palette[key] = $("#newPalColor").value;
  $("#newPalKey").value = "";
  snapshot(); schedulePersist(); renderPalette();
});

// ---------------------------------------------------------------- add / duplicate / delete elements

function pushElement(el) {
  if (!curSide().elements) curSide().elements = [];
  curSide().elements.push(el);
  const idx = curSide().elements.length - 1;
  snapshot(); schedulePersist();
  renderAll();
  selectEntry({ group: "elements", index: idx, obj: el });
}

$("#addText").addEventListener("click", () => {
  if (!state.tpl) return;
  pushElement({ t: "text", field: "name", x: 0.1, y: 0.1, w: 0.5, h: 0.1, size: 10, font: "sans", color: Object.keys(state.tpl.palette)[0] || "ink", align: "left" });
});
$("#addImage").addEventListener("click", () => {
  if (!state.tpl) return;
  pushElement({ t: "image", role: "logo", x: 0.72, y: 0.08, w: 0.2, h: 0.16, fit: "contain" });
});
$("#addQr").addEventListener("click", () => {
  if (!state.tpl) return;
  pushElement({ t: "qr", x: 0.6, y: 0.6, w: 0.25, h: 0.25 });
});
$("#addRect").addEventListener("click", () => {
  if (!state.tpl) return;
  if (!curSide().background) curSide().background = [];
  const b = { t: "rect", x: 0.3, y: 0.3, w: 0.2, h: 0.1, fill: Object.keys(state.tpl.palette)[0] || "accent" };
  curSide().background.push(b);
  const idx = curSide().background.length - 1;
  snapshot(); schedulePersist();
  renderAll();
  selectEntry({ group: "background", index: idx, obj: b });
});

$("#dupElBtn").addEventListener("click", () => {
  if (!state.sel) return;
  const arr = state.sel.group === "background" ? curSide().background : curSide().elements;
  const copy = JSON.parse(JSON.stringify(arr[state.sel.index]));
  copy.x = clamp((copy.x || 0) + 0.03, 0, 1 - (copy.w || 0));
  copy.y = clamp((copy.y || 0) + 0.03, 0, 1 - (copy.h || 0));
  arr.push(copy);
  const idx = arr.length - 1;
  snapshot(); schedulePersist();
  renderAll();
  selectEntry({ group: state.sel.group, index: idx, obj: copy });
});

$("#delElBtn").addEventListener("click", () => {
  if (!state.sel) return;
  const arr = state.sel.group === "background" ? curSide().background : curSide().elements;
  arr.splice(state.sel.index, 1);
  state.sel = null;
  snapshot(); schedulePersist();
  renderAll();
});

// ---------------------------------------------------------------- top-level controls

$$(".side-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (!state.tpl) return;
    state.side = btn.dataset.side;
    state.sel = null;
    $$(".side-tab").forEach((b) => b.classList.toggle("sel", b === btn));
    renderAll();
    refreshPreview();
  });
});

$("#undoBtn").addEventListener("click", undo);
$("#redoBtn").addEventListener("click", redo);

$("#tplName").addEventListener("change", () => {
  if (!state.tpl) return;
  state.tpl.name = $("#tplName").value;
  snapshot(); schedulePersist();
});

$("#applyAdv").addEventListener("click", () => {
  if (!state.tpl) return;
  try {
    const parsed = JSON.parse($("#advJson").value);
    state.tpl.sides[state.side] = parsed;
    state.sel = null;
    snapshot(); schedulePersist();
    renderAll();
    toast("Applied");
  } catch (e) {
    toast("Invalid JSON: " + e.message, true);
  }
});

$("#newBlank").addEventListener("click", async () => {
  busy(true, "Creating…");
  try {
    const tpl = await postJSON("/api/templates/custom", { name: $("#newName").value.trim() || "Untitled" });
    openTemplate(tpl);
    await loadTemplateList();
    toast("Blank template created");
  } catch (e) {
    toast(e.message, true);
  } finally {
    busy(false);
  }
});

$("#deleteTplBtn").addEventListener("click", async () => {
  if (!state.tpl) return;
  if (!confirm(`Delete "${state.tpl.name}"? This cannot be undone.`)) return;
  busy(true, "Deleting…");
  try {
    await api(`/api/templates/custom/${state.tpl.id}`, { method: "DELETE" });
    state.tpl = null;
    state.sel = null;
    $("#canvasBg").src = "";
    $("#overlayLayer").innerHTML = "";
    $("#tplName").value = "";
    setControlsEnabled(false);
    $("#saveStatus").textContent = "no template loaded";
    $("#statusLine").textContent = "No template loaded — create a blank one or pick a template on the left.";
    renderElementList(); renderPropForm(); renderPalette();
    $("#advJson").value = "";
    await loadTemplateList();
    toast("Template deleted");
  } catch (e) {
    toast(e.message, true);
  } finally {
    busy(false);
  }
});

// ---------------------------------------------------------------- init

$("#canvas").style.width = CANVAS_W + "px";
$("#canvas").style.height = CANVAS_H + "px";
loadTemplateList().catch((e) => toast(e.message, true));
