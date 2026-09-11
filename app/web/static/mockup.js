"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const DEFAULTS = {
  front: null, back: null,
  scene: "clean", bg: "auto", custom_color: "#f2f3f5", bg_image: "",
  layout: "side",
  size: 60, rotation: 0, perspective: 32, shadow: 55, radius: 30,
  labels: false,
};

const state = {
  cid: localStorage.getItem("bizcard_cid") || "mockup",
  ...DEFAULTS,
};

// ---------------------------------------------------------------- helpers

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

function postJSON(url, body) {
  return api(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function payload(width, height, overrides = {}) {
  return {
    front: state.front, back: state.back,
    scene: state.scene, bg: state.bg,
    custom_color: $("#customColor").value,
    bg_image: state.bg_image,
    layout: state.layout,
    size: state.size, rotation: state.rotation,
    perspective: state.perspective, shadow: state.shadow, radius: state.radius,
    labels: state.labels,
    width, height,
    ...overrides,
  };
}

function sides() {
  return [state.front ? "front" : null, state.back ? "back" : null].filter(Boolean);
}

// ---------------------------------------------------------------- render

let renderTimer = null;
let renderSeq = 0;

function scheduleRender(delay = 140) {
  clearTimeout(renderTimer);
  renderTimer = setTimeout(renderPreview, delay);
}

async function renderPreview() {
  if (!state.front && !state.back) {
    $("#mkImg").removeAttribute("src");
    $("#mkEmpty").classList.remove("hidden");
    $("#mkInfo").textContent = "";
    return;
  }
  const seq = ++renderSeq;
  try {
    const res = await postJSON("/api/mockup/render", payload(1280, 800));
    if (seq !== renderSeq) return; // a newer request superseded this one
    $("#mkImg").src = res.url + "?v=" + Date.now();
    $("#mkEmpty").classList.add("hidden");
    const s = sides();
    $("#mkInfo").textContent = `Showing: ${s.join(" + ")} · live preview = what downloads`;
  } catch (e) {
    if (seq === renderSeq) toast(e.message, true);
  }
}

// ---------------------------------------------------------------- uploads

function setUpSide(side) {
  const dz = $(`.dropzone[data-side="${side}"]`);
  const input = dz.querySelector("input");
  const box = dz.closest(".upbox");
  const row = box.querySelector(".thumbrow");
  const img = row.querySelector("img");
  const st = $("#st" + side[0].toUpperCase() + side.slice(1));

  const apply = (path, url) => {
    state[side] = path;
    img.src = url + "?v=" + Date.now();
    row.classList.remove("hidden");
    dz.classList.add("hidden");
    st.textContent = "loaded";
    st.classList.add("on");
    $("#layoutSec").style.display = state.front && state.back ? "" : "none";
    scheduleRender(60);
  };

  const handle = async (file) => {
    if (!file) return;
    try {
      const fd = new FormData();
      fd.append("cid", state.cid);
      fd.append("file", file);
      const res = await api(`/api/mockup/upload/${side}`, { method: "POST", body: fd });
      apply(res.path, res.url);
    } catch (e) {
      toast(e.message, true);
    }
  };

  dz.addEventListener("click", () => input.click());
  input.addEventListener("change", () => handle(input.files[0]));
  dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
  dz.addEventListener("drop", (e) => {
    e.preventDefault();
    dz.classList.remove("drag");
    handle(e.dataTransfer.files[0]);
  });

  box.querySelector("[data-clear]").addEventListener("click", () => {
    state[side] = null;
    row.classList.add("hidden");
    dz.classList.remove("hidden");
    input.value = "";
    st.textContent = "no file";
    st.classList.remove("on");
    $("#layoutSec").style.display = state.front && state.back ? "" : "none";
    scheduleRender(60);
  });
}

// ---------------------------------------------------------------- controls

function bindControls() {
  $$("#sceneRow .chip-btn").forEach((b) => b.addEventListener("click", () => {
    state.scene = b.dataset.scene;
    $$("#sceneRow .chip-btn").forEach((x) => x.classList.toggle("sel", x === b));
    scheduleRender();
  }));

  $$("input[name=mkbg]").forEach((r) => r.addEventListener("change", () => {
    state.bg = r.value;
    $("#customWrap").classList.toggle("hidden", state.bg !== "custom");
    $("#imageWrap").classList.toggle("hidden", state.bg !== "image");
    scheduleRender();
  }));
  $("#customColor").addEventListener("input", () => {
    if (state.bg === "custom") scheduleRender();
  });
  $("#bgImageSel").addEventListener("change", () => {
    state.bg_image = $("#bgImageSel").value;
    if (state.bg === "image") scheduleRender();
  });

  $$("input[name=mklayout]").forEach((r) => r.addEventListener("change", () => {
    state.layout = r.value;
    scheduleRender();
  }));

  const sliders = [
    ["ctlSize", "size", "valSize", (v) => v],
    ["ctlRot", "rotation", "valRot", (v) => v + "°"],
    ["ctlPersp", "perspective", "valPersp", (v) => v],
    ["ctlShadow", "shadow", "valShadow", (v) => v],
    ["ctlRadius", "radius", "valRadius", (v) => v],
  ];
  for (const [id, key, valId, fmt] of sliders) {
    const el = $("#" + id);
    el.addEventListener("input", () => {
      state[key] = parseInt(el.value, 10);
      $("#" + valId).textContent = fmt(state[key]);
      scheduleRender();
    });
  }

  $("#ctlLabels").addEventListener("change", () => {
    state.labels = $("#ctlLabels").checked;
    scheduleRender();
  });

  $("#btnReset").addEventListener("click", () => {
    Object.assign(state, { scene: DEFAULTS.scene, bg: DEFAULTS.bg, layout: DEFAULTS.layout,
      size: DEFAULTS.size, rotation: DEFAULTS.rotation, perspective: DEFAULTS.perspective,
      shadow: DEFAULTS.shadow, radius: DEFAULTS.radius, labels: DEFAULTS.labels });
    $("#customColor").value = DEFAULTS.custom_color;
    const map = { ctlSize: "size", ctlRot: "rotation", ctlPersp: "perspective",
      ctlShadow: "shadow", ctlRadius: "radius" };
    for (const [id, key] of Object.entries(map)) $("#" + id).value = state[key];
    $("#valSize").textContent = state.size;
    $("#valRot").textContent = state.rotation + "°";
    $("#valPersp").textContent = state.perspective;
    $("#valShadow").textContent = state.shadow;
    $("#valRadius").textContent = state.radius;
    $("#ctlLabels").checked = false;
    $$("#sceneRow .chip-btn").forEach((x) => x.classList.toggle("sel", x.dataset.scene === state.scene));
    $$("input[name=mkbg]").forEach((r) => { r.checked = r.value === state.bg; });
    $$("input[name=mklayout]").forEach((r) => { r.checked = r.value === state.layout; });
    $("#customWrap").classList.add("hidden");
    $("#imageWrap").classList.add("hidden");
    scheduleRender();
  });

  $("#exportSize").addEventListener("change", () => {
    const v = $("#exportSize").value;
    if (v !== "custom") {
      const [w, h] = v.split("x").map(Number);
      $("#expW").value = w;
      $("#expH").value = h;
    }
  });

  $("#openFolder").addEventListener("click", () => api("/api/open-folder", { method: "POST" }));
}

// ---------------------------------------------------------------- export

async function downloadMockup() {
  if (!state.front && !state.back) {
    toast("Upload a front or back image first.", true);
    return;
  }
  const w = Math.max(320, Math.min(3840, parseInt($("#expW").value, 10) || 1920));
  const h = Math.max(240, Math.min(3840, parseInt($("#expH").value, 10) || 1080));
  const name = `bizcardbd-mockup-${sides().join("-")}.png`;
  try {
    const res = await postJSON("/api/mockup/render", payload(w, h));
    const blob = await (await fetch(res.url + "?v=" + Date.now())).blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
    toast(`Saved ${name} (${w} × ${h}) — also in generated/mockups/`);
  } catch (e) {
    toast(e.message, true);
  }
}

// ---------------------------------------------------------------- present

async function openPresent() {
  if (!state.front && !state.back) {
    toast("Upload a front or back image first.", true);
    return;
  }
  try {
    const res = await postJSON("/api/mockup/render",
      payload(Math.min(1920, window.innerWidth * 1.2), 1010, { labels: true, width: Math.round(Math.min(1920, window.innerWidth * 1.2)), height: 1010 }));
    $("#presentImg").src = res.url + "?v=" + Date.now();
    $("#present").classList.remove("hidden");
  } catch (e) {
    toast(e.message, true);
  }
}

function closePresent() {
  $("#present").classList.add("hidden");
  $("#presentImg").removeAttribute("src");
}

// ---------------------------------------------------------------- init

async function init() {
  const q = new URLSearchParams(location.search);
  for (const side of ["front", "back"]) {
    const v = q.get(side);
    if (v) state[side] = v.replace(/^\//, "");
  }

  setUpSide("front");
  setUpSide("back");
  bindControls();

  $("#btnDownload").addEventListener("click", downloadMockup);
  $("#btnPresent").addEventListener("click", openPresent);
  $("#presentClose").addEventListener("click", closePresent);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePresent(); });

  try {
    const bgs = await api("/api/mockup/backgrounds");
    const sel = $("#bgImageSel");
    for (const b of bgs) {
      const o = document.createElement("option");
      o.value = b.path;
      o.textContent = b.name;
      sel.appendChild(o);
    }
  } catch { /* backgrounds folder just missing */ }

  // reflect sides coming from the Card Generator (?front=…&back=…)
  for (const side of ["front", "back"]) {
    if (!state[side]) continue;
    const box = $(`.dropzone[data-side="${side}"]`).closest(".upbox");
    box.querySelector(".thumbrow").classList.remove("hidden");
    box.querySelector(".dropzone").classList.add("hidden");
    box.querySelector(".thumbrow img").src = "/" + state[side].replace(/^\//, "");
    const st = $("#st" + side[0].toUpperCase() + side.slice(1));
    st.textContent = "loaded";
    st.classList.add("on");
  }
  $("#layoutSec").style.display = state.front && state.back ? "" : "none";
  renderPreview();
}

init();
