"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const state = {
  cid: sessionStorage.getItem("bizcard_prep_cid") || (() => {
    const id = crypto.randomUUID();
    sessionStorage.setItem("bizcard_prep_cid", id);
    return id;
  })(),
  hasImage: false,
  info: null,
  flips: { h: false, v: false },
  zoomPct: null,          // null = Fit
  lastSvg: null,
};

// ---------------------------------------------------------------- helpers

function toast(msg, isErr = false, ms = 5000) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.toggle("err", isErr);
  t.classList.remove("hidden");
  clearTimeout(toast._h);
  toast._h = setTimeout(() => t.classList.add("hidden"), ms);
}

function busy(on, text = "Working…") {
  $("#busy").classList.toggle("hidden", !on);
  $("#busyText").textContent = text;
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

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Could not load " + url));
    img.src = url;
  });
}

function saveBlob(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

function toPx(v, unit, dpi) {
  if (v === null || v === "" || isNaN(v) || v <= 0) return null;
  v = parseFloat(v);
  if (unit === "px") return Math.round(v);
  if (unit === "mm") return Math.round(v / 25.4 * dpi);
  if (unit === "cm") return Math.round(v / 10 / 25.4 * dpi);
  if (unit === "in") return Math.round(v * dpi);
  return null;
}

// ---------------------------------------------------------------- payload

function opts() {
  const dpi = Math.max(36, Math.min(1200, parseInt($("#szDpi").value, 10) || 300));
  return {
    cid: state.cid,
    bg_mode: document.querySelector('input[name="ppbg"]:checked').value,
    enhance: parseInt(document.querySelector('input[name="ppenh"]:checked').value, 10),
    rotate: parseFloat($("#rotSlider").value) || 0,
    flip_h: state.flips.h,
    flip_v: state.flips.v,
    trim: $("#trimChk").checked,
    width: $("#szW").value ? parseFloat($("#szW").value) : null,
    height: $("#szH").value ? parseFloat($("#szH").value) : null,
    unit: $("#szUnit").value,
    dpi,
    keep_aspect: $("#szAspect").checked,
  };
}

// ---------------------------------------------------------------- process

let procTimer = null;
let procSeq = 0;

function scheduleProcess(ms = 380) {
  if (!state.hasImage) return;
  clearTimeout(procTimer);
  procTimer = setTimeout(() => process().catch((e) => toast(e.message, true)), ms);
}

async function process({ useBusy = false, busyText = "Processing…" } = {}) {
  if (!state.hasImage) return;
  const seq = ++procSeq;
  if (useBusy) busy(true, busyText);
  try {
    const res = await postJSON("/api/prep/process", opts());
    if (seq !== procSeq) return;           // a newer request superseded this one
    state.info = res;
    $("#procImg").src = res.processed_url;
    $("#procEmpty").classList.add("hidden");
    $("#procMeta").textContent =
      `${res.width} × ${res.height} px · ${res.transparency_pct}% transparent`;
    $("#pngName").textContent = res.png_name;
    renderQuality(res);
    updatePxReadout();
    for (const id of ["btnDlPng", "btnDlSvg", "btnDlAll", "btnUseGen", "btnUseMock"]) {
      $("#" + id).disabled = false;
    }
  } finally {
    if (useBusy) busy(false);
  }
}

function renderQuality(res) {
  const box = $("#qualityBox");
  box.classList.remove("hidden");
  const v = res.verdict || { level: "ok", message: "" };
  const chip = $("#verdictChip");
  const labels = { good: "Good", fair: "Fair", low: "Low", verylow: "Very low", ok: "—" };
  chip.textContent = labels[v.level] || v.level;
  chip.className = "pp-chip " + v.level;
  $("#verdictMsg").textContent = v.message || "";
  const warns = res.warnings || [];
  const ul = $("#warnList");
  ul.classList.toggle("hidden", !warns.length);
  ul.innerHTML = "";
  for (const w of warns) {
    const li = document.createElement("li");
    li.textContent = w;
    ul.appendChild(li);
  }
}

function updatePxReadout() {
  const o = opts();
  const tw = toPx(o.width, o.unit, o.dpi);
  const th = toPx(o.height, o.unit, o.dpi);
  const base = state.info;
  let out;
  if (tw && th) {
    out = o.keep_aspect
      ? `Output: fits inside ${tw} × ${th} px (aspect kept)`
      : `Output: exactly ${tw} × ${th} px`;
  } else if (tw || th) {
    out = `Output: ${tw || "?"} px wide × auto height`;
  } else {
    out = base
      ? `Output: ${base.width} × ${base.height} px (unchanged size)`
      : "Output size: —";
  }
  $("#pxReadout").textContent = `${out} · DPI ${o.dpi}`;
}

// ----------------------------------------------------------------- upload

async function upload(file) {
  if (!file) return;
  if (!/\.(jpe?g|png|webp)$/i.test(file.name)) {
    toast("Only JPG, JPEG, PNG and WEBP files are supported.", true);
    return;
  }
  busy(true, "Uploading…");
  try {
    const fd = new FormData();
    fd.append("cid", state.cid);
    fd.append("file", file);
    const res = await api("/api/prep/upload", { method: "POST", body: fd });
    state.hasImage = true;
    state.info = null;
    $("#ppDrop").classList.add("hidden");
    $("#ppPanes").classList.remove("hidden");
    $("#origImg").src = res.original_url;
    $("#origMeta").textContent = `${res.width} × ${res.height} px · ${res.type} · ${res.file_kb} KB`;
    $("#cmpImg").src = res.original_url;
    $("#procImg").removeAttribute("src");
    $("#procMeta").textContent = "…";
    $("#procEmpty").classList.remove("hidden");
    // per-image transforms reset; size/quality settings persist for batch work
    $("#rotSlider").value = 0;
    $("#rotVal").textContent = "0°";
    state.flips.h = state.flips.v = false;
    $("#btnFlipH").classList.remove("sel");
    $("#btnFlipV").classList.remove("sel");
    // fresh session: clear any previous result
    const auto = document.querySelector('input[name="ppbg"]:checked').value === "auto";
    await process({
      useBusy: true,
      busyText: auto
        ? "Removing background — first run downloads an AI model (~170 MB), please wait…"
        : "Preparing…",
    });
  } catch (e) {
    toast(e.message, true, 8000);
  } finally {
    busy(false);
  }
}

// ------------------------------------------------------------------- zoom

function applyZoom() {
  const imgs = [$("#origImg"), $("#procImg"), $("#cmpImg")];
  for (const img of imgs) {
    if (state.zoomPct === null) {          // Fit
      img.style.width = "auto";
      img.style.maxWidth = "100%";
      img.style.maxHeight = "100%";
    } else if (state.zoomPct === "actual") {
      img.style.maxWidth = "none";
      img.style.maxHeight = "none";
      img.style.width = img.naturalWidth + "px";
    } else {
      img.style.maxWidth = "none";
      img.style.maxHeight = "none";
      img.style.width = state.zoomPct + "%";
    }
  }
  $("#zoomVal").textContent =
    state.zoomPct === null ? "Fit" : state.zoomPct === "actual" ? "100%" : Math.round(state.zoomPct) + "%";
}

function zoomIn() {
  state.zoomPct = state.zoomPct === null || state.zoomPct === "actual" ? 125 : Math.min(500, state.zoomPct * 1.3);
  applyZoom();
}
function zoomOut() {
  if (state.zoomPct === null || state.zoomPct === "actual") return;
  state.zoomPct = Math.max(20, state.zoomPct / 1.3);
  applyZoom();
}

// ---------------------------------------------------------------- compare

function applyCompare() {
  const on = $("#cmpToggle").checked && state.hasImage;
  $("#cmpBase").classList.toggle("hidden", !on);
  $("#cmpSlider").classList.toggle("hidden", !on);
  if (on) applyCompareValue();
}

function applyCompareValue() {
  const v = parseInt($("#cmpSlider").value, 10);
  // the ORIGINAL sits on top and is clipped to the left `v`% — the right side
  // reveals the processed result beneath it
  $("#cmpBase").style.clipPath = `inset(0 ${100 - v}% 0 0)`;
  $("#cmpBase").style.webkitClipPath = `inset(0 ${100 - v}% 0 0)`;
}

// ---------------------------------------------------------- refine editor

const R = {
  open: false, tool: "erase", size: 24,
  undo: [], redo: [],
  drawing: false, last: null,
  proc: null, orig: null,
};

function openRefine() {
  if (!state.info) return;
  busy(true, "Loading refine editor…");
  Promise.all([
    loadImage(state.info.processed_url),
    loadImage($("#origImg").src),
  ]).then(([proc, orig]) => {
    R.proc = proc; R.orig = orig;
    const cap = 1400;
    const s = Math.min(1, cap / Math.max(proc.width, proc.height));
    const cv = $("#refineCanvas");
    cv.width = Math.max(1, Math.round(proc.width * s));
    cv.height = Math.max(1, Math.round(proc.height * s));
    const ctx = cv.getContext("2d");
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.drawImage(proc, 0, 0, cv.width, cv.height);
    R.undo = [ctx.getImageData(0, 0, cv.width, cv.height)];
    R.redo = [];
    R.open = true;
    $("#refineModal").classList.remove("hidden");
  }).catch((e) => toast(e.message, true)).finally(() => busy(false));
}

function closeRefine() {
  R.open = false;
  $("#refineModal").classList.add("hidden");
}

function refinePos(e) {
  const cv = $("#refineCanvas");
  const rect = cv.getBoundingClientRect();
  const sx = cv.width / rect.width;
  return {
    x: (e.clientX - rect.left) * sx,
    y: (e.clientY - rect.top) * sx,
    scale: sx,
  };
}

function pushUndo() {
  const cv = $("#refineCanvas");
  const ctx = cv.getContext("2d");
  R.undo.push(ctx.getImageData(0, 0, cv.width, cv.height));
  if (R.undo.length > 14) R.undo.shift();
  R.redo = [];
}

function refineStroke(e) {
  const cv = $("#refineCanvas");
  const ctx = cv.getContext("2d");
  const { x, y, scale } = refinePos(e);
  const r = Math.max(2, R.size * scale / 2);

  if (R.tool === "erase") {
    ctx.globalCompositeOperation = "destination-out";
    ctx.strokeStyle = "rgba(0,0,0,1)";
    ctx.fillStyle = "rgba(0,0,0,1)";
    ctx.lineWidth = r * 2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    if (R.last) {
      ctx.beginPath();
      ctx.moveTo(R.last.x, R.last.y);
      ctx.lineTo(x, y);
      ctx.stroke();
    } else {
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalCompositeOperation = "source-over";
  } else {
    // restore: re-paint the ORIGINAL image through a circular punch
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.clip();
    ctx.drawImage(R.orig, 0, 0, cv.width, cv.height);
    ctx.restore();
  }
  R.last = { x, y };
}

// --------------------------------------------------------------- download

async function downloadPng() {
  if (!state.info) return;
  busy(true, "Preparing PNG…");
  try {
    const res = await fetch(state.info.processed_url);
    const blob = await res.blob();
    saveBlob(blob, state.info.png_name || "prepared.png");
    toast("PNG saved — check your browser downloads.");
  } catch (e) {
    toast(e.message, true);
  } finally {
    busy(false);
  }
}

async function downloadSvg({ quiet = false } = {}) {
  if (!state.info) return;
  busy(true, "Building SVG…");
  try {
    const res = await postJSON("/api/prep/svg", {
      cid: state.cid,
      mode: $("#svgMode").value,
      detail: parseInt($("#svgDetail").value, 10) || 6,
      colors: parseInt($("#svgColors").value, 10) || 6,
      smoothing: $("#svgSmooth").value === "1",
    });
    state.lastSvg = res;
    const blob = new Blob([res.svg], { type: "image/svg+xml" });
    saveBlob(blob, res.name);
    if (!quiet) {
      if (res.kind === "vector") {
        toast(`SVG saved — ${res.label}.`);
      } else {
        toast(`SVG saved — ${res.label}. It is NOT a true vector file; the PNG is embedded inside the SVG.`, false, 9000);
      }
    }
    return res;
  } catch (e) {
    toast(e.message, true, 8000);
  } finally {
    busy(false);
  }
}

async function downloadAll() {
  await downloadPng();
  await downloadSvg();
}

// --------------------------------------------------------- use / mockup

function useModal(open) {
  $("#useModal").classList.toggle("hidden", !open);
}

async function useInGenerator(kind) {
  busy(true, "Sending to Card Generator…");
  try {
    const res = await postJSON("/api/prep/use", { cid: state.cid, kind });
    sessionStorage.setItem("bizcard_handoff", JSON.stringify(res));
    window.location.href = "/";
  } catch (e) {
    busy(false);
    toast(e.message, true);
  }
}

// --------------------------------------------------------------- presets

const PRESETS = {
  cardlogo: { bg: "auto", enh: "1", unit: "mm", dpi: 300, w: "30", h: "30", aspect: true, trim: true },
  cardphoto: { bg: "auto", enh: "1", unit: "mm", dpi: 300, w: "35", h: "45", aspect: true, trim: false },
  social: { bg: "auto", enh: "2", unit: "px", dpi: 96, w: "1000", h: "1000", aspect: true, trim: false },
};

function applyPreset(name) {
  $$("#presetRow .chip-btn").forEach((b) => b.classList.toggle("sel", b.dataset.preset === name));
  const p = PRESETS[name];
  if (!p) return;                          // custom = user's own values
  document.querySelector(`input[name="ppbg"][value="${p.bg}"]`).checked = true;
  document.querySelector(`input[name="ppenh"][value="${p.enh}"]`).checked = true;
  $("#szUnit").value = p.unit;
  $("#szDpi").value = p.dpi;
  $("#szW").value = p.w;
  $("#szH").value = p.h;
  $("#szAspect").checked = p.aspect;
  $("#trimChk").checked = p.trim;
  scheduleProcess();
}

// ------------------------------------------------------------------- init

function bindDropzone() {
  const dz = $("#ppDrop");
  const input = $("#ppFile");
  dz.addEventListener("click", () => input.click());
  input.addEventListener("change", () => upload(input.files[0]));
  dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
  dz.addEventListener("drop", (e) => {
    e.preventDefault();
    dz.classList.remove("drag");
    upload(e.dataTransfer.files[0]);
  });
}

function init() {
  bindDropzone();

  $("#btnRemove").addEventListener("click", () => {
    const auto = document.querySelector('input[name="ppbg"]:checked').value === "auto";
    process({
      useBusy: true,
      busyText: auto
        ? "Removing background — first run downloads an AI model (~170 MB), please wait…"
        : "Preparing…",
    }).catch((e) => toast(e.message, true));
  });

  for (const name of ["ppbg", "ppenh"]) {
    $$(`input[name="${name}"]`).forEach((r) => r.addEventListener("change", () => {
      $$("#presetRow .chip-btn").forEach((b) => b.classList.remove("sel"));
      $$('#presetRow [data-preset="custom"]').forEach((b) => b.classList.add("sel"));
      process({
        useBusy: name === "ppbg" && r.value === "auto",
        busyText: "Removing background — first run downloads an AI model (~170 MB), please wait…",
      }).catch((e) => toast(e.message, true));
    }));
  }

  for (const id of ["szW", "szH", "szUnit", "szDpi"]) {
    $("#" + id).addEventListener("input", () => {
      updatePxReadout();
      scheduleProcess();
    });
  }
  $("#szAspect").addEventListener("change", () => scheduleProcess());

  $("#rotSlider").addEventListener("input", () => {
    $("#rotVal").textContent = $("#rotSlider").value + "°";
  });
  $("#rotSlider").addEventListener("change", () => scheduleProcess(80));

  $("#btnFlipH").addEventListener("click", () => {
    state.flips.h = !state.flips.h;
    $("#btnFlipH").classList.toggle("sel", state.flips.h);
    scheduleProcess(10);
  });
  $("#btnFlipV").addEventListener("click", () => {
    state.flips.v = !state.flips.v;
    $("#btnFlipV").classList.toggle("sel", state.flips.v);
    scheduleProcess(10);
  });
  $("#btnTrim").addEventListener("click", () => {
    $("#trimChk").checked = true;
    scheduleProcess(10);
  });
  $("#btnTrimOff").addEventListener("click", () => {
    $("#trimChk").checked = false;
    scheduleProcess(10);
  });
  $("#trimChk").addEventListener("change", () => scheduleProcess());

  $$("#presetRow .chip-btn").forEach((b) =>
    b.addEventListener("click", () => applyPreset(b.dataset.preset)));

  // zoom + compare
  $("#zoomIn").addEventListener("click", zoomIn);
  $("#zoomOut").addEventListener("click", zoomOut);
  $("#zoomFit").addEventListener("click", () => { state.zoomPct = null; applyZoom(); });
  $("#zoomActual").addEventListener("click", () => { state.zoomPct = "actual"; applyZoom(); });
  $("#cmpToggle").addEventListener("change", applyCompare);
  $("#cmpSlider").addEventListener("input", applyCompareValue);

  // refine
  $("#btnRefine").addEventListener("click", openRefine);
  $("#refineClose").addEventListener("click", closeRefine);
  $$("#refineModal [data-tool]").forEach((b) => b.addEventListener("click", () => {
    R.tool = b.dataset.tool;
    $$("#refineModal [data-tool]").forEach((x) => x.classList.toggle("sel", x === b));
  }));
  $("#brushSize").addEventListener("input", () => {
    R.size = parseInt($("#brushSize").value, 10);
    $("#brushVal").textContent = R.size;
  });
  const cv = $("#refineCanvas");
  cv.addEventListener("pointerdown", (e) => {
    if (!R.open) return;
    e.preventDefault();
    cv.setPointerCapture(e.pointerId);
    pushUndo();
    R.drawing = true;
    R.last = null;
    refineStroke(e);
  });
  cv.addEventListener("pointermove", (e) => {
    if (R.open && R.drawing) refineStroke(e);
  });
  const stopDraw = () => { R.drawing = false; R.last = null; };
  cv.addEventListener("pointerup", stopDraw);
  cv.addEventListener("pointercancel", stopDraw);
  $("#refineUndo").addEventListener("click", () => {
    if (R.undo.length < 2) return;
    const ctx = cv.getContext("2d");
    R.redo.push(R.undo.pop());
    ctx.putImageData(R.undo[R.undo.length - 1], 0, 0);
  });
  $("#refineRedo").addEventListener("click", () => {
    if (!R.redo.length) return;
    const ctx = cv.getContext("2d");
    const img = R.redo.pop();
    R.undo.push(img);
    ctx.putImageData(img, 0, 0);
  });
  $("#refineReset").addEventListener("click", () => {
    const ctx = cv.getContext("2d");
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.drawImage(R.proc, 0, 0, cv.width, cv.height);
    R.undo = [ctx.getImageData(0, 0, cv.width, cv.height)];
    R.redo = [];
  });
  $("#refineApply").addEventListener("click", async () => {
    busy(true, "Applying refinements…");
    try {
      const data = cv.toDataURL("image/png");
      const fd = new FormData();
      fd.append("cid", state.cid);
      fd.append("image", data);
      const res = await api("/api/prep/refine", { method: "POST", body: fd });
      state.info = { ...state.info, ...res };
      $("#procImg").src = res.processed_url;
      $("#procMeta").textContent = `${res.width} × ${res.height} px · ${res.transparency_pct}% transparent`;
      $("#pngName").textContent = res.png_name;
      closeRefine();
      toast("Refinements applied.");
    } catch (e) {
      toast(e.message, true);
    } finally {
      busy(false);
    }
  });

  // svg controls
  $("#svgMode").addEventListener("change", () => {
    const vectorize = $("#svgMode").value === "vectorize";
    $("#svgSettings").classList.toggle("hidden", !vectorize);
    $("#svgHint").textContent = vectorize
      ? "Vectorize traces the image into real SVG paths locally (vtracer). Best for flat logos — photos become large files."
      : "PNG is the main output — it keeps full transparency. SVG is honest: real vectors only when traced; otherwise it is clearly labeled as a raster wrapper, never a renamed PNG.";
  });

  $("#btnDlPng").addEventListener("click", downloadPng);
  $("#btnDlSvg").addEventListener("click", () => downloadSvg());
  $("#btnDlAll").addEventListener("click", downloadAll);

  // use
  $("#btnUseGen").addEventListener("click", () => useModal(true));
  $("#useClose").addEventListener("click", () => useModal(false));
  $("#useAsLogo").addEventListener("click", () => useInGenerator("logo"));
  $("#useAsPhoto").addEventListener("click", () => useInGenerator("photo"));
  $("#btnUseMock").addEventListener("click", () => {
    if (!state.info) return;
    window.location.href = "/mockup.html?front=" + encodeURIComponent(state.info.processed_url);
  });

  updatePxReadout();
}

init();
