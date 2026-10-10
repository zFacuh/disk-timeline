"use strict";

const state = {
  drives: [],
  drive: null,
  daily: [],
  snapshots: [],
  rangeDays: 0,
  newMode: "last",
};

const $ = (sel) => document.querySelector(sel);
const SVG_NS = "http://www.w3.org/2000/svg";
const UNITS = ["B", "KB", "MB", "GB", "TB"];

// ---------- formatting ----------
function humanSize(n, signed = false) {
  if (n === null || n === undefined) return "–";
  let sign = "";
  if (signed) sign = n > 0 ? "+" : n < 0 ? "−" : "±";
  let v = Math.abs(n), i = 0;
  while (v >= 1024 && i < UNITS.length - 1) { v /= 1024; i++; }
  const digits = i === 0 ? 0 : v >= 100 ? 1 : 2;
  return `${sign}${v.toFixed(digits)} ${UNITS[i]}`;
}
const fmtDate = (ts) => new Date(ts * 1000).toLocaleDateString("es", { day: "2-digit", month: "short", year: "numeric" });
const fmtDateTime = (ts) => new Date(ts * 1000).toLocaleString("es", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
const fmtDayShort = (day) => new Date(day + "T12:00:00").toLocaleDateString("es", { day: "numeric", month: "short" });
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function splitPath(p) {
  const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
  return i < 0 ? ["", p] : [p.slice(0, i + 1), p.slice(i + 1)];
}

// ---------- api ----------
async function api(path, opts) {
  const res = await fetch("/api/" + path, opts);
  const data = await res.json();
  if (!res.ok && res.status !== 409) throw new Error(data.error || res.statusText);
  return data;
}
const post = (path, body) => api(path, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-Disk-Timeline": "1" },
  body: JSON.stringify(body),
});

// ---------- svg helpers ----------
function el(name, attrs = {}, parent) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

/** Nice tick values for a byte domain, expressed in a single unit. */
function byteTicks(min, max, count = 5) {
  const top = Math.max(Math.abs(min), Math.abs(max)) || 1;
  let unit = 0;
  while (top / 1024 ** (unit + 1) >= 1 && unit < UNITS.length - 1) unit++;
  const scale = 1024 ** unit;
  const lo = min / scale, hi = max / scale;
  const raw = (hi - lo) / count || 1;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const start = Math.floor(lo / step) * step, end = Math.ceil(hi / step) * step;
  const ticks = [];
  for (let v = start; v <= end + step / 2; v += step) ticks.push(v * scale);
  const decimals = step < 1 ? Math.min(2, -Math.floor(Math.log10(step))) : 0;
  const label = (b) => `${(b / scale).toFixed(decimals)} ${UNITS[unit]}`;
  return { ticks, label, min: start * scale, max: end * scale };
}

function dateTicks(points, width) {
  const maxTicks = Math.max(2, Math.floor(width / 90));
  const step = Math.ceil(points.length / maxTicks);
  return points.filter((_, i) => i % step === 0);
}

const tooltip = $("#tooltip");
function showTip(html, x, y) {
  tooltip.innerHTML = html;
  tooltip.hidden = false;
  const r = tooltip.getBoundingClientRect();
  let left = x + 14, top = y - r.height - 10;
  if (left + r.width > window.innerWidth - 8) left = x - r.width - 14;
  if (top < 8) top = y + 14;
  tooltip.style.left = left + "px";
  tooltip.style.top = top + "px";
}
const hideTip = () => { tooltip.hidden = true; };

function chartFrame(container) {
  container.innerHTML = "";
  const width = container.clientWidth, height = container.clientHeight;
  const m = { top: 12, right: 16, bottom: 26, left: 68 };
  const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, role: "img" }, container);
  return { svg, width, height, m, iw: width - m.left - m.right, ih: height - m.top - m.bottom };
}

function message(container, text) {
  container.innerHTML = `<div class="msg">${esc(text)}</div>`;
}

// ---------- charts ----------
function drawUsedChart(container, points) {
  if (!points.length) return message(container, "Sin datos en este rango.");
  const f = chartFrame(container);
  f.svg.setAttribute("aria-label", "Espacio usado por día");
  const used = points.map((p) => p.used);
  let lo = Math.min(...used), hi = Math.max(...used);
  const pad = Math.max((hi - lo) * 0.15, hi * 0.005);
  const yt = byteTicks(lo - pad, hi + pad);
  const x = (i) => f.m.left + (points.length === 1 ? f.iw / 2 : (i / (points.length - 1)) * f.iw);
  const y = (v) => f.m.top + f.ih - ((v - yt.min) / (yt.max - yt.min)) * f.ih;

  const grid = el("g", { class: "grid" }, f.svg);
  const axis = el("g", { class: "axis" }, f.svg);
  for (const t of yt.ticks) {
    el("line", { x1: f.m.left, x2: f.width - f.m.right, y1: y(t), y2: y(t) }, grid);
    el("text", { x: f.m.left - 8, y: y(t) + 4, "text-anchor": "end" }, axis).textContent = yt.label(t);
  }
  const idx = new Map(points.map((p, i) => [p, i]));
  for (const p of dateTicks(points, f.iw)) {
    el("text", { x: x(idx.get(p)), y: f.height - 6, "text-anchor": "middle" }, axis).textContent = fmtDayShort(p.day);
  }
  el("line", { class: "baseline", x1: f.m.left, x2: f.width - f.m.right, y1: f.m.top + f.ih, y2: f.m.top + f.ih }, f.svg);

  if (points.length > 1) {
    const d = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.used).toFixed(1)}`).join("");
    el("path", { class: "line", d }, f.svg);
  }
  // endpoint marker + label: the one value worth reading without hovering
  const last = points[points.length - 1];
  el("circle", { class: "dot", cx: x(points.length - 1), cy: y(last.used), r: 4 }, f.svg);

  const cross = el("line", { class: "crosshair", y1: f.m.top, y2: f.m.top + f.ih, visibility: "hidden" }, f.svg);
  const focus = el("circle", { class: "dot", r: 5, visibility: "hidden" }, f.svg);
  const hit = el("rect", { x: f.m.left, y: f.m.top, width: f.iw, height: f.ih, fill: "transparent" }, f.svg);
  hit.addEventListener("pointermove", (ev) => {
    const rect = f.svg.getBoundingClientRect();
    const px = ((ev.clientX - rect.left) / rect.width) * f.width;
    const i = points.length === 1 ? 0 : Math.round(((px - f.m.left) / f.iw) * (points.length - 1));
    const p = points[Math.max(0, Math.min(points.length - 1, i))];
    const cx = x(idx.get(p));
    cross.setAttribute("x1", cx); cross.setAttribute("x2", cx); cross.setAttribute("visibility", "visible");
    focus.setAttribute("cx", cx); focus.setAttribute("cy", y(p.used)); focus.setAttribute("visibility", "visible");
    const pct = p.total ? ((100 * p.used) / p.total).toFixed(1) : "–";
    showTip(`<b>${fmtDate(p.taken_at)}</b>
      <div class="row">Usado: ${humanSize(p.used)} (${pct}%)</div>
      <div class="row">Libre: ${humanSize(p.free)}</div>
      ${p.delta !== null ? `<div class="row">Cambio: ${humanSize(p.delta, true)}</div>` : ""}`, ev.clientX, ev.clientY);
  });
  hit.addEventListener("pointerleave", () => {
    cross.setAttribute("visibility", "hidden"); focus.setAttribute("visibility", "hidden"); hideTip();
  });
}

function drawDeltaChart(container, points) {
  const bars = points.filter((p) => p.delta !== null);
  if (!bars.length) return message(container, "Se necesitan capturas de al menos dos días distintos para ver el cambio diario.");
  const f = chartFrame(container);
  f.svg.setAttribute("aria-label", "Cambio diario del espacio usado");
  const vals = bars.map((p) => p.delta);
  const yt = byteTicks(Math.min(0, ...vals), Math.max(0, ...vals));
  const y = (v) => f.m.top + f.ih - ((v - yt.min) / (yt.max - yt.min)) * f.ih;
  const band = f.iw / bars.length;
  const bw = Math.max(2, Math.min(28, band - 2)); // 2px surface gap between bars

  const grid = el("g", { class: "grid" }, f.svg);
  const axis = el("g", { class: "axis" }, f.svg);
  for (const t of yt.ticks) {
    el("line", { x1: f.m.left, x2: f.width - f.m.right, y1: y(t), y2: y(t) }, grid);
    el("text", { x: f.m.left - 8, y: y(t) + 4, "text-anchor": "end" }, axis).textContent = (t > 0 ? "+" : "") + yt.label(t);
  }
  const idx = new Map(bars.map((p, i) => [p, i]));
  for (const p of dateTicks(bars, f.iw)) {
    el("text", { x: f.m.left + band * (idx.get(p) + 0.5), y: f.height - 6, "text-anchor": "middle" }, axis).textContent = fmtDayShort(p.day);
  }

  const g = el("g", {}, f.svg);
  bars.forEach((p, i) => {
    const cx = f.m.left + band * (i + 0.5);
    const y0 = y(0), y1 = y(p.delta);
    const h = Math.max(1, Math.abs(y1 - y0));
    const top = p.delta >= 0 ? y0 - h : y0;
    const r = Math.min(4, bw / 2, h);
    // rounded on the data end only, square at the baseline
    const d = p.delta >= 0
      ? `M${cx - bw / 2},${y0}V${top + r}q0,-${r} ${r},-${r}H${cx + bw / 2 - r}q${r},0 ${r},${r}V${y0}Z`
      : `M${cx - bw / 2},${y0}V${top + h - r}q0,${r} ${r},${r}H${cx + bw / 2 - r}q${r},0 ${r},-${r}V${y0}Z`;
    const bar = el("path", { d, class: `bar ${p.delta >= 0 ? "bar-up" : "bar-down"}` }, g);
    const hit = el("rect", { x: f.m.left + band * i, y: f.m.top, width: band, height: f.ih, fill: "transparent" }, f.svg);
    hit.addEventListener("pointermove", (ev) => {
      g.querySelectorAll(".bar").forEach((b) => b.classList.toggle("dim", b !== bar));
      showTip(`<b>${fmtDate(p.taken_at)}</b>
        <div class="row">${p.delta >= 0 ? "Creció" : "Se liberó"}: ${humanSize(Math.abs(p.delta))}</div>
        <div class="row">Usado: ${humanSize(p.used)}</div>`, ev.clientX, ev.clientY);
    });
    hit.addEventListener("pointerleave", () => {
      g.querySelectorAll(".bar").forEach((b) => b.classList.remove("dim")); hideTip();
    });
  });
  el("line", { class: "baseline", x1: f.m.left, x2: f.width - f.m.right, y1: y(0), y2: y(0) }, f.svg);
}

// ---------- tiles ----------
function renderTiles() {
  const days = state.daily;
  const last = days[days.length - 1];
  const pct = last.total ? (100 * last.used) / last.total : 0;
  const recent = days.slice(-15).map((d) => d.delta).filter((d) => d !== null);
  const avg = recent.length ? recent.reduce((a, b) => a + b, 0) / recent.length : null;
  const daysLeft = avg && avg > 0 ? last.free / avg : null;
  const tile = (label, value, sub = "", extra = "") =>
    `<div class="tile"><div class="label">${label}</div><div class="value">${value}</div><div class="sub">${sub}</div>${extra}</div>`;
  $("#tiles").innerHTML = [
    tile("Usado", humanSize(last.used), `${pct.toFixed(1)}% de ${humanSize(last.total)}`,
      `<div class="meter" role="meter" aria-valuenow="${pct.toFixed(0)}" aria-valuemin="0" aria-valuemax="100"><i style="width:${pct}%"></i></div>`),
    tile("Libre", humanSize(last.free), `última captura ${fmtDateTime(last.taken_at)}`),
    tile("Cambio último día", last.delta === null ? "–" : humanSize(last.delta, true),
      last.delta === null ? "falta una captura de otro día" : "respecto al día anterior"),
    tile("Promedio diario", avg === null ? "–" : humanSize(Math.round(avg), true), `últimos ${recent.length || 0} días con datos`),
    tile("Se llena en", daysLeft === null ? "–" : `${Math.round(daysLeft).toLocaleString("es")} días`,
      daysLeft === null ? "sin crecimiento sostenido" : "al ritmo promedio actual"),
  ].join("");
}

function renderDailyTable() {
  const rows = state.daily.slice().reverse().map((d) => `<tr>
      <td>${fmtDate(d.taken_at)}</td><td class="num">${humanSize(d.used)}</td>
      <td class="num">${humanSize(d.free)}</td>
      <td class="num ${d.delta > 0 ? "up-text" : d.delta < 0 ? "down-text" : ""}">${humanSize(d.delta, true)}</td></tr>`).join("");
  $("#daily-table").innerHTML = `<div class="table-scroll"><table>
    <thead><tr><th>Día</th><th class="num">Usado</th><th class="num">Libre</th><th class="num">Cambio</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

function renderCharts() {
  let pts = state.daily;
  if (state.rangeDays) {
    const cutoff = Date.now() / 1000 - state.rangeDays * 86400;
    pts = pts.filter((p) => p.taken_at >= cutoff);
  }
  drawUsedChart($("#chart-used"), pts);
  drawDeltaChart($("#chart-delta"), pts);
}

// ---------- growth ----------
function snapshotOptions(select, selectedId, includeNone) {
  const opts = state.snapshots.slice().reverse().map((s) =>
    `<option value="${s.id}" ${s.id === selectedId ? "selected" : ""}>${fmtDateTime(s.taken_at)}</option>`);
  if (includeNone) opts.push(`<option value="" ${selectedId == null ? "selected" : ""}>(ninguna)</option>`);
  select.innerHTML = opts.join("");
}

function revealButton(path) {
  return `<button class="reveal" type="button" data-path="${esc(path)}" title="Mostrar en el Explorador">Abrir</button>`;
}

function pathCell(path) {
  const [dir, name] = splitPath(path);
  return `<td class="path"><span class="dir">${esc(dir)}</span>${esc(name)}</td>`;
}

async function loadGrowth() {
  const from = $("#growth-from").value, to = $("#growth-to").value, depth = $("#growth-depth").value;
  const q = new URLSearchParams({ drive: state.drive, limit: 40 });
  if (to) q.set("to", to);
  if (from) q.set("from", from);
  if (depth) q.set("depth", depth);
  const g = await api("growth?" + q);
  const note = $("#growth-note"), box = $("#growth-table");
  if (!g.to) {
    note.textContent = "Hacé un escaneo completo para ver qué carpetas ocupan espacio.";
    box.innerHTML = "";
    return;
  }
  if (!g.from) {
    note.textContent = "Sólo hay una captura completa: se muestran las carpetas más grandes. Con el próximo escaneo verás qué creció.";
    box.innerHTML = `<div class="table-scroll"><table><thead><tr><th>Carpeta</th><th class="num">Tamaño</th><th></th></tr></thead><tbody>
      ${g.folders.map((f) => `<tr>${pathCell(f.path)}<td class="num">${humanSize(f.after)}</td><td>${revealButton(f.path)}</td></tr>`).join("")}
      </tbody></table></div>`;
    return;
  }
  note.textContent = `Comparando ${fmtDateTime(g.from.taken_at)} → ${fmtDateTime(g.to.taken_at)} · disco ${humanSize(g.to.used - g.from.used, true)}`;
  const maxAbs = Math.max(1, ...g.folders.map((f) => Math.abs(f.delta)));
  box.innerHTML = `<div class="table-scroll"><table>
    <thead><tr><th>Carpeta</th><th class="num">Cambio</th><th></th><th class="num">Antes</th><th class="num">Ahora</th><th></th></tr></thead>
    <tbody>${g.folders.map((f) => {
      const w = (Math.abs(f.delta) / maxAbs) * 50;
      const bar = f.delta >= 0
        ? `<i style="left:50%;width:${w}%;background:var(--up)"></i>`
        : `<i style="right:50%;width:${w}%;background:var(--down)"></i>`;
      return `<tr>${pathCell(f.path)}
        <td class="num ${f.delta > 0 ? "up-text" : f.delta < 0 ? "down-text" : ""}">${humanSize(f.delta, true)}</td>
        <td><div class="deltabar"><span class="mid"></span>${bar}</div></td>
        <td class="num">${f.before === null ? "nueva" : humanSize(f.before)}</td>
        <td class="num">${f.after === null ? "borrada" : humanSize(f.after)}</td>
        <td>${revealButton(f.path)}</td></tr>`;
    }).join("")}</tbody></table></div>`;
}

// ---------- new files ----------
async function loadNewFiles() {
  const note = $("#new-note"), box = $("#new-table");
  let files, header;
  if (state.newMode === "all") {
    files = await api(`recent-new?drive=${state.drive}&limit=150`);
    note.textContent = "Archivos grandes detectados en todas las capturas, de la más reciente a la más antigua.";
    header = "Detectado";
    files.forEach((f) => { f.when = f.detected_at; });
  } else {
    const res = await api(`new?drive=${state.drive}&limit=100`);
    if (!res.snapshot) {
      note.textContent = "Hacé un escaneo completo para detectar archivos nuevos.";
      box.innerHTML = "";
      return;
    }
    files = res.files;
    note.textContent = `Archivos creados o modificados entre ${fmtDateTime(res.snapshot.new_since)} y ${fmtDateTime(res.snapshot.taken_at)}.`;
    header = "Fecha";
    files.forEach((f) => { f.when = Math.max(f.created || 0, f.modified || 0); });
  }
  if (!files.length) {
    box.innerHTML = `<p class="muted">Ningún archivo nuevo supera el tamaño mínimo.</p>`;
    return;
  }
  const total = files.reduce((a, f) => a + f.size, 0);
  note.textContent += ` Total listado: ${humanSize(total)}.`;
  box.innerHTML = `<div class="table-scroll"><table>
    <thead><tr><th>Archivo</th><th class="num">Tamaño</th><th class="num">${header}</th><th></th></tr></thead>
    <tbody>${files.map((f) => `<tr>${pathCell(f.path)}<td class="num">${humanSize(f.size)}</td>
      <td class="num">${fmtDateTime(f.when)}</td><td>${revealButton(f.path)}</td></tr>`).join("")}</tbody></table></div>`;
}

// ---------- drive selection ----------
async function selectDrive(drive) {
  state.drive = drive;
  document.querySelectorAll("#drive-tabs button").forEach((b) => b.setAttribute("aria-selected", b.dataset.drive === drive));
  try { localStorage.setItem("dt-drive", drive); } catch (_) { /* storage unavailable */ }
  const [daily, snaps] = await Promise.all([api(`daily?drive=${drive}`), api(`snapshots?drive=${drive}`)]);
  state.daily = daily;
  state.snapshots = snaps;
  renderTiles();
  renderCharts();
  renderDailyTable();
  const lastId = snaps.length ? snaps[snaps.length - 1].id : null;
  const prevId = snaps.length > 1 ? snaps[snaps.length - 2].id : null;
  snapshotOptions($("#growth-to"), lastId, false);
  snapshotOptions($("#growth-from"), prevId, true);
  await Promise.all([loadGrowth(), loadNewFiles()]);
}

async function loadDrives() {
  state.drives = await api("drives");
  const has = state.drives.length > 0;
  $("#empty").hidden = has;
  $("#dashboard").hidden = !has;
  if (!has) return;
  $("#drive-tabs").innerHTML = state.drives.map((d) =>
    `<button role="tab" data-drive="${d.drive}" aria-selected="false">${esc(d.root)}</button>`).join("");
  let saved = null;
  try { saved = localStorage.getItem("dt-drive"); } catch (_) { /* storage unavailable */ }
  const keep = [state.drive, saved].find((d) => d && state.drives.some((x) => x.drive === d));
  await selectDrive(keep || state.drives[0].drive);
}

// ---------- snapshot jobs ----------
let polling = null;
async function startJob(full) {
  const body = { full, drives: full && state.drive ? [state.drive] : [] };
  const res = await post("snapshot", body);
  if (!res.started) { $("#job-status").textContent = "Ya hay una captura en curso…"; }
  pollJob();
}

function pollJob() {
  clearTimeout(polling);
  polling = setTimeout(async () => {
    const job = await api("job");
    const busy = !!job.running;
    $("#btn-quick").disabled = busy;
    $("#btn-full").disabled = busy;
    if (busy) {
      $("#job-status").textContent = job.full
        ? `Escaneando ${job.current}: … ${job.files.toLocaleString("es")} archivos`
        : "Registrando uso…";
      pollJob();
    } else if (job.finished) {
      $("#job-status").textContent = job.error ? `Error: ${job.error}` : `Captura lista (${fmtDateTime(job.finished)})`;
      await loadDrives();
    }
  }, 800);
}

// ---------- wiring ----------
$("#drive-tabs").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-drive]");
  if (b) selectDrive(b.dataset.drive);
});
$("#range").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-days]");
  if (!b) return;
  state.rangeDays = Number(b.dataset.days);
  document.querySelectorAll("#range button").forEach((x) => x.classList.toggle("on", x === b));
  renderCharts();
});
$("#new-mode").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-mode]");
  if (!b) return;
  state.newMode = b.dataset.mode;
  document.querySelectorAll("#new-mode button").forEach((x) => x.classList.toggle("on", x === b));
  loadNewFiles();
});
["#growth-from", "#growth-to", "#growth-depth"].forEach((s) => $(s).addEventListener("change", loadGrowth));
document.addEventListener("click", async (e) => {
  const b = e.target.closest("button.reveal");
  if (!b) return;
  try { await post("reveal", { path: b.dataset.path }); }
  catch (_) { b.textContent = "No existe"; b.disabled = true; }
});
$("#btn-quick").addEventListener("click", () => startJob(false));
$("#btn-full").addEventListener("click", () => startJob(true));

let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { if (state.daily.length) renderCharts(); }, 150);
});

loadDrives().then(() => api("job")).then((job) => { if (job.running) pollJob(); })
  .catch((err) => { $("#job-status").textContent = "Error: " + err.message; });
