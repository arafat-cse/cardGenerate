"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const state = {
  cid: localStorage.getItem("bizcard_cid") || (() => {
    const id = crypto.randomUUID();
    localStorage.setItem("bizcard_cid", id);
    return id;
  })(),
  templateId: localStorage.getItem("bizcard_tpl") || "template-01",
  logo: null,
  photo: null,
  generating: false,
};

const FIELDS = ["company", "name", "title", "tagline", "phone", "email", "website", "address"];
const DEFAULTS = {
  company: "", name: "", title: "", tagline: "",
  phone: "", email: "", website: "", address: "",
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
  if (!res.ok) {
    throw new Error((body && body.detail) || `Request failed (${res.status})`);
  }
  return body;
}

function busy(on, text = "Working…") {
  $("#busy").classList.toggle("hidden", !on);
  $("#busyText").textContent = text;
}

function collectData() {
  const d = { ...DEFAULTS };
  for (const f of FIELDS) {
    const el = $(`[data-f="${f}"]`);
    if (el) d[f] = el.value.trim();
  }
  return d;
}

function payload() {
  return {
    cid: state.cid,
    template_id: state.templateId,
    data: collectData(),
    logo: state.logo,
    photo: state.photo,
    qr: {
      type: $("#qrType").value,
      value: $("#qrValue").value.trim(),
      logo_in_qr: $("#qrLogo").checked,
    },
  };
}

function postJSON(url, body) {
  return api(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------- preview

let previewTimer = null;
function schedulePreview(delay = 500) {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(updatePreview, delay);
}

async function updatePreview() {
  try {
    const res = await postJSON("/api/preview", payload());
    $("#preview").src = res.url;
    $("#previewInfo").textContent =
      "Front (top) and back (bottom) · 3.5 × 2 in + bleed · this preview is exactly what gets printed";
  } catch (e) {
    toast(e.message, true);
  }
}

// ---------------------------------------------------------------- templates

async function loadTemplates() {
  const list = await api("/api/templates");
  const grid = $("#templates");
  grid.innerHTML = "";
  for (const t of list) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tpl" + (t.id === state.templateId ? " sel" : "");
    btn.dataset.id = t.id;
    btn.innerHTML = `<img loading="lazy" src="${t.preview}" alt="${t.name}">
      <span class="tpl-name">${t.name}</span><span class="tpl-desc">${t.desc || ""}</span>`;
    btn.addEventListener("click", () => {
      state.templateId = t.id;
      localStorage.setItem("bizcard_tpl", t.id);
      $$(".tpl").forEach((b) => b.classList.toggle("sel", b.dataset.id === t.id));
      updatePreview();
    });
    grid.appendChild(btn);
  }
}

// ---------------------------------------------------------------- uploads

function setUpUpload(kind) {
  const dz = $(`.dropzone[data-kind="${kind}"]`);
  const input = dz.querySelector("input");
  const box = dz.closest(".upbox");
  const row = box.querySelector(".thumbrow");
  const img = row.querySelector("img");

  const handle = async (file) => {
    if (!file) return;
    busy(true, "Uploading…");
    try {
      const fd = new FormData();
      fd.append("cid", state.cid);
      fd.append("file", file);
      const res = await api(`/api/upload/${kind}`, { method: "POST", body: fd });
      state[kind === "logos" ? "logo" : "photo"] = res.path;
      img.src = res.url + "?v=" + Date.now();
      row.classList.remove("hidden");
      dz.classList.add("hidden");
      updatePreview();
    } catch (e) {
      toast(e.message, true);
    } finally {
      busy(false);
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

  box.querySelector("[data-bg]").addEventListener("click", async () => {
    const path = state[kind === "logos" ? "logo" : "photo"];
    if (!path) return;
    busy(true, "Removing background — first run downloads an AI model (~170 MB), please wait…");
    try {
      const fd = new FormData();
      fd.append("cid", state.cid);
      fd.append("kind", kind);
      fd.append("path", path);
      const res = await api("/api/bg-remove", { method: "POST", body: fd });
      state[kind === "logos" ? "logo" : "photo"] = res.path;
      img.src = res.url + "?v=" + Date.now();
      updatePreview();
      toast("Background removed.");
    } catch (e) {
      toast(e.message, true, 8000);
    } finally {
      busy(false);
    }
  });

  box.querySelector("[data-clear]").addEventListener("click", () => {
    state[kind === "logos" ? "logo" : "photo"] = null;
    row.classList.add("hidden");
    dz.classList.remove("hidden");
    input.value = "";
    updatePreview();
  });
}

// ---------------------------------------------------------------- outputs

async function refreshOutputs() {
  const rows = await api(`/api/outputs?cid=${encodeURIComponent(state.cid)}`);
  const box = $("#outputs");
  box.innerHTML = "";
  if (!rows.length) return;
  const h = document.createElement("div");
  h.className = "muted";
  h.textContent = "Your generated files (in the generated/ folder):";
  box.appendChild(h);
  for (const r of rows) {
    const row = document.createElement("div");
    row.className = "out-row";
    const kindLabel = { png: "PNG 300 DPI", pdf: "PDF print", ai: "Illustrator .ai" }[r.kind] || r.kind;
    row.innerHTML = `<span class="tag">${kindLabel}</span><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.name}</span>
      <a href="${r.url}" download>Download</a>`;
    box.appendChild(row);
  }
}

// ---------------------------------------------------------------- actions

async function generate() {
  busy(true, "Rendering 600 DPI artwork…");
  try {
    const res = await postJSON("/api/generate", payload());
    for (const o of res.outputs) {
      toast(`Created: ${res.outputs.map((o) => o.name).join(", ")}`, false, 6000);
    }
    await refreshOutputs();
  } catch (e) {
    toast(e.message, true);
  } finally {
    busy(false);
  }
}

async function sendToIllustrator() {
  busy(true, "Building Illustrator job…");
  try {
    const res = await postJSON("/api/illustrator", payload());
    busy(true, "Waiting for Adobe Illustrator to build the .ai file… (check the Illustrator window)");
    const started = Date.now();
    while (Date.now() - started < 180000) {
      await new Promise((r) => setTimeout(r, 2000));
      const st = await api(`/api/illustrator/status/${encodeURIComponent(res.job)}`);
      if (st.status === "done") {
        busy(false);
        toast("Illustrator file created: card.ai — it is also open in Illustrator.");
        await refreshOutputs();
        return;
      }
      if (st.status === "error") {
        busy(false);
        toast("Illustrator error: " + st.message, true, 10000);
        return;
      }
    }
    busy(false);
    toast("Timed out waiting for Illustrator. If it is still open, the .ai may appear in generated/ai later.", true, 10000);
  } catch (e) {
    busy(false);
    toast(e.message, true, 10000);
  }
}

// ---------------------------------------------------------------- init

function restoreForm() {
  const saved = JSON.parse(localStorage.getItem("bizcard_data") || "{}");
  for (const f of FIELDS) {
    const el = $(`[data-f="${f}"]`);
    if (el && saved[f]) el.value = saved[f];
  }
  for (const el of $$("[data-f]")) {
    el.addEventListener("input", () => {
      const d = collectData();
      localStorage.setItem("bizcard_data", JSON.stringify(d));
      schedulePreview();
    });
  }
}

async function init() {
  restoreForm();
  setUpUpload("logos");
  setUpUpload("photos");

  $("#qrType").addEventListener("change", () => {
    const t = $("#qrType").value;
    $("#qrValueWrap").classList.toggle("hidden", t === "none" || t === "vcard");
    schedulePreview(200);
  });
  $("#qrValue").addEventListener("input", () => schedulePreview());
  $("#qrLogo").addEventListener("change", () => schedulePreview(200));

  $("#btnPreview").addEventListener("click", updatePreview);
  $("#btnGenerate").addEventListener("click", generate);
  $("#btnAI").addEventListener("click", sendToIllustrator);
  $("#openFolder").addEventListener("click", () => api("/api/open-folder", { method: "POST" }));

  try {
    const h = await api("/api/health");
    const chip = $("#aiStatus");
    if (h.illustrator) {
      chip.textContent = "Illustrator detected";
      chip.classList.add("ok");
    } else {
      chip.textContent = "Illustrator not found";
      chip.title = "Create illustrator_path.txt next to start.bat with the full path to Illustrator.exe";
    }
    if (h.blackletter_font) {
      $("#fontNote").textContent = "Name font: " + h.blackletter_font;
    }
  } catch { /* server just started */ }

  await loadTemplates();
  await updatePreview();
  refreshOutputs().catch(() => {});
}

init();
