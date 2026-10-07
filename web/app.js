"use strict";
/* Sentinel Street dashboard — vanilla JS single-page app. */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const ICONS = {
  home: '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
  video: '<path d="m22 8-6 4 6 4V8Z"/><rect width="14" height="12" x="2" y="6" rx="2"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  pin: '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  bulb: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
  chart: '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
  file: '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/>',
  sliders: '<path d="M21 4h-7M10 4H3M21 12h-9M8 12H3M21 20h-5M12 20H3M14 2v4M8 10v4M16 18v4"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/>',
  car: '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/>',
  user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  play: '<path d="M6 3l14 9-14 9z"/>',
  stop: '<rect width="14" height="14" x="5" y="5" rx="2"/>',
  switch: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  flip: '<path d="M8 3H5a2 2 0 0 0-2 2v14c0 1.1.9 2 2 2h3"/><path d="M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3"/><path d="M12 20v2M12 14v2M12 8v2M12 2v2"/>',
  max: '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>',
  camera: '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2m-7.07-17.07 1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
  send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  locate: '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  cpu: '<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2M15 20v2M2 15h2M2 9h2M20 15h2M20 9h2M9 2v2M9 20v2"/>',
  activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  volume: '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>',
  plug: '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
  eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  mail: '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  radar: '<path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"/><path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"/><circle cx="12" cy="12" r="2"/><path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5"/><path d="M19.1 4.9C23 8.8 23 15.1 19.1 19"/>',
  external: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  image: '<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.09-3.09a2 2 0 0 0-2.82 0L6 21"/>',
  save: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8"/><path d="M7 3v5h8"/>',
};
const ic = (name, cls = "") => `<svg viewBox="0 0 24 24" class="${cls}" aria-hidden="true">${ICONS[name] || ""}</svg>`;

const NAV = [
  { group: "Monitor" },
  { id: "overview", label: "Overview", icon: "home", sub: "Live safety status of this street light" },
  { id: "live", label: "Live monitoring", icon: "video", sub: "Camera feed with real-time AI detection" },
  { id: "incidents", label: "Incident review", icon: "alert", sub: "Recorded events, evidence and alert decisions" },
  { id: "gps", label: "GPS tracking", icon: "pin", sub: "Where this street light is, and where incidents happened" },
  { group: "Response" },
  { id: "contacts", label: "Alert contacts", icon: "users", sub: "Who is notified when risk turns HIGH" },
  { id: "sensors", label: "Sensors & lights", icon: "bulb", sub: "ESP32 street light, PIR motion and LDR light sensor" },
  { group: "Insights" },
  { id: "analytics", label: "Analytics", icon: "chart", sub: "Safety trends over time" },
  { id: "reports", label: "Reports", icon: "file", sub: "Export incident reports as PDF or CSV" },
  { group: "System" },
  { id: "settings", label: "Settings", icon: "sliders", sub: "Detection, risk rules, lighting and clock" },
];

const ALERT_STATUS = {
  none: ["No alert needed", ""], pending: ["Awaiting operator", "amber"], no_contacts: ["No contacts set up", "amber"],
  sending: ["Sending…", "violet"], sent: ["Alert sent", "green"], partial: ["Partly sent", "amber"], failed: ["Alert failed", "red"],
  suppressed: ["Held by cooldown", "amber"],
};
const STATUS_LABEL = { new: "New", reviewed: "Reviewed", false_alarm: "False alarm" };

const S = {
  live: null, settings: null, page: null, wsOk: false, streamKey: 0, seenActivity: 0,
  charts: [], map: null, cleanup: [], lastIncidentId: 0,
};

/* ------------------------------------------------------------------ utils */
async function api(path, { method = "GET", body, quiet = false } = {}) {
  let res;
  try {
    res = await fetch(path, {
      method, headers: body !== undefined ? { "Content-Type": "application/json" } : {},
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    if (!quiet) toast("Can't reach the Sentinel server. Is run.py still running?", "error", 5000);
    throw new Error("Server unreachable");
  }
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const detail = data && data.detail;
    const msg = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join(", ") : `Request failed (${res.status})`;
    if (!quiet) toast(msg, "error");
    throw new Error(msg);
  }
  return data;
}

function toast(message, kind = "ok", ms = 3500) {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `${ic(kind === "error" ? "x" : kind === "alert" ? "alert" : "check")}<span>${esc(message)}</span>`;
  $("#toasts").append(el);
  setTimeout(() => el.remove(), ms);
}

const tz = () => (S.settings && S.settings.time_zone) || "Asia/Kolkata";
function fmt(ts, opts) { return new Intl.DateTimeFormat("en-IN", { timeZone: tz(), ...opts }).format(new Date(ts * 1000)); }
const fmtTime = (ts) => fmt(ts, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true });
const fmtDateTime = (ts) => fmt(ts, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: true });
function ago(ts) {
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 60) return `${Math.round(s)}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}
const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const pct = (v) => `${Math.round(v * 100)}%`;
const levelBadge = (level) => `<span class="badge ${level}"><span class="dot"></span>${level}</span>`;

/* Guard for async page loads: returns a check that is false once the user has navigated away or
   started a newer load of the same page, so late responses never draw into the wrong view. */
function loadGuard(page) {
  const token = {}, pageId = S.page;
  page._token = token;
  return () => page._token === token && S.page === pageId;
}

async function busy(button, fn) {
  if (!button) return fn();
  const html = button.innerHTML;
  button.disabled = true;
  try { return await fn(); } finally { button.disabled = false; button.innerHTML = html; }
}

/* ----------------------------------------------------------------- chrome */
function renderNav() {
  $("#nav").innerHTML = NAV.map((item) => item.group
    ? `<div class="nav-label">${item.group}</div>`
    : `<a href="#${item.id}" class="${S.page === item.id ? "active" : ""}" data-nav="${item.id}">${ic(item.icon)}<span>${item.label}</span>${item.id === "incidents" ? '<span class="badge" id="nav-inc" hidden></span>' : ""}</a>`).join("");
}

function updateChrome(d) {
  const pill = $("#risk-pill");
  pill.dataset.level = d.risk.level;
  document.body.classList.toggle("alarm", d.risk.level === "HIGH");
  pill.lastElementChild.textContent = `${d.risk.level} RISK`;
  const sys = $("#sys-status");
  const det = d.detector;
  sys.className = `sys ${S.wsOk && (det.ready || det.loading) ? "ok" : "bad"}`;
  $(".sys-title", sys).textContent = !S.wsOk ? "Disconnected" : det.loading ? "Loading AI model…" : det.ready ? "System ready" : "AI unavailable";
  $(".sys-sub", sys).textContent = det.ready ? `Local AI · ${det.device.toUpperCase()}` : det.error ? det.error.slice(0, 40) : "Local processing";
  const badge = $("#nav-inc");
  if (badge) { badge.hidden = !d.incidents_today; badge.textContent = d.incidents_today; badge.className = "badge violet"; }
}

function tickClock() {
  const now = new Date();
  try {
    $("#clock-time").textContent = new Intl.DateTimeFormat("en-IN", { timeZone: tz(), hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true }).format(now);
    const name = new Intl.DateTimeFormat("en-US", { timeZone: tz(), timeZoneName: "short" }).formatToParts(now).find((p) => p.type === "timeZoneName");
    $("#clock-zone").textContent = `${tz().split("/").pop().replace(/_/g, " ")} · ${name ? name.value : ""}`;
  } catch { /* invalid zone, ignore */ }
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("sentinel-theme", theme); } catch { /* storage unavailable */ }
  route();
}

/* ------------------------------------------------------------- live state */
function connectLive() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onopen = () => {
    S.wsOk = true;
    S.resync = true; // the server may have restarted: its activity ids start again from 1
    if (S.offline) { S.offline = false; toast("Reconnected to Sentinel"); }
  };
  ws.onmessage = (event) => onLive(JSON.parse(event.data));
  ws.onclose = () => {
    const wasOnline = S.wsOk;
    S.wsOk = false;
    showOffline();
    if (wasOnline) { S.offline = true; toast("Lost connection to Sentinel. Reconnecting…", "error", 5000); }
    setTimeout(connectLive, 1500);
  };
}

function showOffline() {
  const pill = $("#risk-pill");
  pill.dataset.level = "OFFLINE";
  pill.lastElementChild.textContent = "OFFLINE";
  document.body.classList.remove("alarm");
  $$(".stage").forEach((stage) => stage.classList.add("stale"));
  const sys = $("#sys-status");
  sys.className = "sys bad";
  $(".sys-title", sys).textContent = "Disconnected";
  $(".sys-sub", sys).textContent = "Reconnecting…";
}

function onLive(d) {
  const prev = S.live;
  S.live = d;
  if (!prev || prev.camera.running !== d.camera.running || S.resync) S.streamKey += 1;
  $$(".stage.stale").forEach((stage) => stage.classList.remove("stale"));
  updateChrome(d);
  const baseline = S.resync;
  if (S.resync) { S.resync = false; S.seenActivity = d.activity.length ? d.activity[0].id : 0; }
  const fresh = d.activity.filter((ev) => ev.id > S.seenActivity).reverse();
  if (prev && !baseline) {
    for (const ev of fresh) {
      if (ev.kind === "incident") toast(ev.text, ev.level === "HIGH" ? "alert" : "ok", ev.level === "HIGH" ? 7000 : 4000);
      if (ev.kind === "alert") {
        const sending = /^Alert for incident/.test(ev.text);
        toast(ev.text, sending ? (ev.text.includes(": sent") ? "ok" : "error") : ev.level === "HIGH" ? "alert" : "ok", 6000);
      }
    }
  }
  if (d.activity.length) S.seenActivity = Math.max(S.seenActivity, d.activity[0].id);
  const page = PAGES[S.page];
  if (page && page.update) page.update(d, prev);
}

/* ---------------------------------------------------------- stage + HUD */
/* The camera panel: live MJPEG stream, or the illustrated street when the camera is off,
   with a heads-up display drawn over it. Used by Overview (immersive) and Live monitoring (fit). */
function stageHTML({ fit = false, tall = false, showcase = false } = {}) {
  // showcase (Overview): example detections only, never the live camera; the camera lives on Live monitoring
  return `
  <section class="stage ${fit ? "fit" : ""} ${tall ? "tall" : ""} ${showcase ? "showcase" : ""}" data-level="LOW">
    <div class="stage-media">${streetScene(`st${Date.now()}`)}<div class="stage-reel" aria-hidden="true"></div><img alt="Live camera feed" hidden></div>
    <button class="reel-caption" hidden></button>
    <div class="hud">
      <span class="corner c-tl"></span><span class="corner c-tr"></span><span class="corner c-bl"></span><span class="corner c-br"></span>
      <div class="hud-tl">
        <div class="label">Risk level · score <span data-hud="score">0</span></div>
        <div class="hud-level" data-hud="level">LOW</div>
        <div class="hud-meter"><i></i><i></i><i></i></div>
        <div class="hud-reason" data-hud="reason"></div>
      </div>
      <div class="hud-tr">
        <span class="hud-tag off" data-hud="live"><span class="dot"></span><span>CAMERA OFF</span></span>
        <span class="hud-tag" data-hud="cam">—</span>
      </div>
      <div class="hud-alert" data-hud="alert" hidden></div>
      <div class="hud-bottom">
        <div class="hud-metric"><div class="label">People</div><div class="v" data-hud="people">—</div></div>
        <div class="hud-metric"><div class="label">Vehicles</div><div class="v" data-hud="vehicles">—</div></div>
        <div class="hud-metric"><div class="label">Light</div><div class="v" data-hud="light">—</div></div>
        <div class="hud-metric"><div class="label">Buzzer</div><div class="v" data-hud="buzzer">—</div></div>
        <div class="hud-metric"><div class="label">Mode</div><div class="v" data-hud="night">—</div></div>
        <div class="hud-controls">
          <button class="btn sm danger solid" data-act="sos-clear" title="Operator has responded" hidden>${ic("check")} Clear SOS</button>
          <button class="btn sm" data-act="cam-stop" title="Stop camera">${ic("stop")} Stop</button>
          <button class="btn sm" data-act="cam-switch" title="Use the next camera">${ic("switch")}</button>
          <button class="btn sm" data-act="cam-mirror" title="Mirror the image">${ic("flip")}</button>
          <a class="btn sm" data-snap href="/api/snapshot" download="snapshot.jpg" title="Save a snapshot">${ic("image")}</a>
          <button class="btn sm" data-act="cam-full" title="Full screen">${ic("max")}</button>
        </div>
      </div>
    </div>
    <div class="stage-cta">
      <button class="btn primary" data-act="cam-start">${ic("play")} Start camera</button>
      <a class="btn primary watch-live" href="#live" hidden>${ic("video")} Watch live camera</a>
      <p class="stage-cta-text">The lamp shows the real street-light brightness. Video is analysed on this computer only.</p>
    </div>
  </section>`;
}

function tween(el, value, format = (v) => String(Math.round(v))) {
  if (!el) return;
  if (typeof value !== "number") { el.textContent = value; el.dataset.v = ""; return; }
  const from = el.dataset.v === "" || el.dataset.v === undefined ? value : +el.dataset.v;
  el.dataset.v = value;
  if (from === value || window.matchMedia("(prefers-reduced-motion: reduce)").matches) { el.textContent = format(value); return; }
  const t0 = performance.now();
  const step = (now) => {
    const k = Math.min(1, (now - t0) / 450);
    el.textContent = format(from + (value - from) * (1 - Math.pow(1 - k, 3)));
    if (k < 1 && el.dataset.v === String(value)) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
const pad2 = (v) => String(Math.round(v)).padStart(2, "0");

function updateStage(root, d) {
  const stage = $(".stage", root);
  if (!stage) return;
  const img = $(".stage-media img", stage);
  const on = d.camera.running;
  const showcase = stage.classList.contains("showcase");
  if (showcase) {
    stage.classList.toggle("camera-on", on);
    $(".watch-live", stage).hidden = !on;
    $('[data-act="cam-start"]', stage).hidden = on;
  }
  if (on && !showcase && img.dataset.key !== String(S.streamKey)) { img.src = `/api/stream?k=${S.streamKey}`; img.dataset.key = String(S.streamKey); }
  if (!on && img.getAttribute("src")) { img.removeAttribute("src"); img.dataset.key = ""; }
  img.hidden = !on || showcase;
  stage.classList.toggle("live", on && !showcase);
  stage.dataset.level = d.risk.level;
  stage.classList.toggle("strobe", !!d.hardware.strobe);
  $$('[data-act="sos-clear"]', stage).forEach((b) => { b.hidden = !(d.sos && d.sos.active); });
  stage.dataset.night = d.night.is_night ? "1" : "0"; // the illustrated street follows real day / night
  setLamp($(".scene", stage), d.hardware.brightness / 100);
  const h = (k) => $(`[data-hud="${k}"]`, stage);
  h("level").textContent = d.risk.level;
  tween(h("score"), d.risk.score);
  h("reason").textContent = d.risk.reasons[0] || "";
  const live = h("live");
  live.classList.toggle("off", !on);
  live.lastElementChild.textContent = on ? "LIVE" : d.detector.loading ? "AI LOADING" : "CAMERA OFF";
  h("cam").textContent = on ? `CAM ${d.camera.index + 1} · ${fmt(d.time, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}` : fmt(d.time, { hour: "2-digit", minute: "2-digit", hour12: false });
  const alert = h("alert");
  alert.hidden = !(d.risk.level === "HIGH" && d.risk.threat);
  if (!alert.hidden) alert.textContent = d.risk.weapon ? `⚠ ${d.risk.threat.toUpperCase()} DETECTED` : `⚠ ${d.risk.threat.split(" — ")[0].toUpperCase()}`;
  tween(h("people"), on ? d.counts.person : "—", pad2);
  tween(h("vehicles"), on ? d.counts.vehicle : "—", pad2);
  tween(h("light"), d.hardware.brightness, (v) => `${Math.round(v)}%`);
  h("buzzer").textContent = d.hardware.buzzer ? "ON" : "OFF";
  h("buzzer").style.color = d.hardware.buzzer ? "var(--high)" : "";
  h("night").textContent = d.night.is_night ? "NIGHT" : "DAY";
  $$('[data-act="cam-start"]', stage).forEach((b) => { b.disabled = on; });
  $$('[data-act="cam-stop"], [data-act="cam-mirror"], [data-act="cam-switch"]', stage).forEach((b) => { b.hidden = !on; });
  const snap = $("[data-snap]", stage);
  if (snap) snap.hidden = !on;
}

const ACTIONS = {
  "cam-start": (btn) => busy(btn, async () => { const r = await api("/api/camera/start", { method: "POST", body: {} }); toast(r.message); }),
  "cam-stop": (btn) => busy(btn, async () => { await api("/api/camera/stop", { method: "POST" }); }),
  "cam-switch": (btn) => busy(btn, async () => { const r = await api("/api/camera/switch", { method: "POST" }); toast(r.message, r.ok ? "ok" : "error"); }),
  "cam-mirror": async () => { const r = await api("/api/camera/mirror", { method: "POST", body: { mirror: !(S.live && S.live.camera.mirror) } }); toast(r.mirror ? "Image mirrored" : "Mirror off"); },
  "voice-test": (btn) => busy(btn, async () => { const r = await api("/api/voice/test", { method: "POST" }); toast(r.message); }),
  "sos-clear": (btn) => busy(btn, async () => { await api("/api/sos/clear", { method: "POST" }); toast("SOS cleared"); }),
  "sos-sim": (btn) => busy(btn, async () => { await api("/api/sos/simulate", { method: "POST" }); }),
  "cam-full": (btn) => { const stage = btn.closest(".stage"); if (stage && stage.requestFullscreen) stage.requestFullscreen(); },
};

/* ------------------------------------------------------------- components */
function stat(id, label, icon, tone) {
  return `<div class="card stat"><div class="stat-top"><span class="stat-label">${label}</span><span class="chip-icon ${tone}">${ic(icon)}</span></div>
    <div class="stat-value" id="${id}">—</div><div class="stat-sub" id="${id}-sub">&nbsp;</div></div>`;
}

function activityHTML(items) {
  if (!items.length) return `<div class="empty"><p>No activity yet.</p></div>`;
  return `<ul class="activity">${items.map((ev) => `<li><span class="ev-dot ${ev.kind === "alert" ? "alert" : ev.level || ""}"></span>
    <span>${esc(ev.text)}</span><time>${fmtTime(ev.ts)}</time></li>`).join("")}</ul>`;
}

function incidentCard(item) {
  const thumb = item.snapshot_url ? `style="background-image:url('${item.snapshot_url}')"` : "";
  const [alertText, alertTone] = ALERT_STATUS[item.alert_status] || ["", ""];
  return `<div class="card inc-card" data-incident="${item.id}" tabindex="0" role="button" aria-label="Open incident ${item.id}: ${esc(item.label)}, ${item.level}">
    <div class="inc-thumb" ${thumb}>${item.snapshot_url ? "" : `<div class="noimg">${ic("image")}</div>`}${levelBadge(item.level)}${item.clip_url ? `<span class="badge clip-badge">${ic("play")} Clip</span>` : ""}</div>
    <div class="inc-body">
      <div class="inc-title">${esc(item.label)}</div>
      <div class="inc-meta"><span>${fmtDateTime(item.ts)}</span>·<span>${STATUS_LABEL[item.status]}</span>
        ${item.level === "HIGH" ? `<span class="badge ${alertTone}">${alertText}</span>` : ""}</div>
    </div></div>`;
}

function emptyState(icon, title, text, extra = "") {
  return `<div class="empty"><div class="chip-icon">${ic(icon)}</div><h3>${title}</h3><p>${text}</p>${extra}</div>`;
}

/* ---------------------------------------------------------------- modal */
function openModal(html) {
  const modal = $("#modal");
  S.modalReturn = document.activeElement;
  modal.innerHTML = `<div class="modal-box" role="dialog" aria-modal="true" tabindex="-1">${html}</div>`;
  modal.hidden = false;
  const first = $("button, textarea, a[href]", modal);
  (first || $(".modal-box", modal)).focus();
}
function closeModal() {
  const modal = $("#modal");
  if (modal.hidden) return;
  modal.hidden = true;
  modal.innerHTML = "";
  if (S.modalReturn && document.contains(S.modalReturn)) S.modalReturn.focus();
  S.modalReturn = null;
}

async function openIncident(id, onChange) {
  const item = await api(`/api/incidents/${id}`).catch(() => null);
  if (!item) return;
  const [alertText, alertTone] = ALERT_STATUS[item.alert_status] || ["", ""];
  const maps = item.lat != null ? `<a href="https://maps.google.com/?q=${item.lat},${item.lng}" target="_blank" rel="noopener">${item.lat.toFixed(5)}, ${item.lng.toFixed(5)} ${ic("external")}</a>` : '<span class="faint">Not set</span>';
  openModal(`
    <div class="modal-grid">
      <div class="evidence">
        ${item.clip_url ? `<video src="${item.clip_url}" controls autoplay muted loop playsinline aria-label="Evidence clip"></video>`
          : item.snapshot_url ? `<img src="${item.snapshot_url}" alt="Evidence snapshot">`
          : `<div class="empty" style="background:var(--feed-bg)">${ic("image")}<p>No snapshot (camera was off)</p></div>`}
        ${item.clip_url && item.snapshot_url ? `<div class="evidence-switch segmented"><button class="on" data-ev="clip">${ic("video")} Clip</button><button data-ev="photo">${ic("image")} Photo</button></div>` : ""}
        ${item.clip_url ? `<a class="btn sm evidence-dl" href="${item.clip_url}" download>${ic("download")} Clip</a>` : ""}
      </div>
      <div class="stack" style="padding:22px;gap:16px">
        <div class="row">${levelBadge(item.level)}<span class="badge">${STATUS_LABEL[item.status]}</span><span class="spacer" style="flex:1"></span>
          <button class="icon-btn" data-close aria-label="Close">${ic("x")}</button></div>
        <div><div style="font-size:22px;font-weight:800;text-transform:capitalize">${esc(item.label)}</div>
          <div class="muted">Incident #${item.id} · ${fmt(item.ts, { dateStyle: "medium", timeStyle: "medium" })}</div></div>
        <dl class="kv">
          <dt>Confidence</dt><dd>${item.confidence != null ? pct(item.confidence) : "—"}</dd>
          <dt>People / vehicles</dt><dd>${item.people} / ${item.vehicles}</dd>
          <dt>Location</dt><dd>${maps}</dd>
          ${item.level === "HIGH" ? `<dt>Alert</dt><dd><span class="badge ${alertTone}">${alertText}</span></dd>` : ""}
        </dl>
        <ul class="reasons" style="margin:0">${item.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
        ${item.level === "HIGH" ? `<button class="btn ${item.alert_status === "sent" ? "" : "danger solid"}" data-m="alert">${ic("send")} ${item.alert_status === "sent" ? "Send alert again" : "Send alert to contacts"}</button>` : ""}
        <div class="field"><label>Review</label>
          <div class="segmented">${Object.entries(STATUS_LABEL).map(([k, v]) => `<button class="${item.status === k ? "on" : ""}" data-status="${k}">${v}</button>`).join("")}</div></div>
        <div class="field"><label for="m-notes">Notes</label><textarea class="input" id="m-notes" maxlength="1000" placeholder="What happened? Who checked it?">${esc(item.notes)}</textarea></div>
        <div class="row"><button class="btn primary" data-m="save">${ic("save")} Save notes</button><span style="flex:1"></span>
          <button class="btn danger" data-m="delete">${ic("trash")} Delete</button></div>
      </div>
    </div>`);
  const box = $("#modal .modal-box");
  box.addEventListener("click", async (event) => {
    const t = event.target.closest("button");
    if (!t) return;
    if (t.hasAttribute("data-close")) return closeModal();
    if (t.dataset.ev) {
      const box = $(".evidence", $("#modal"));
      const media = $("video, img", box);
      const next = t.dataset.ev === "clip"
        ? Object.assign(document.createElement("video"), { src: item.clip_url, controls: true, autoplay: true, muted: true, loop: true, playsInline: true })
        : Object.assign(document.createElement("img"), { src: item.snapshot_url, alt: "Evidence snapshot" });
      media.replaceWith(next);
      $$(".evidence-switch button", box).forEach((b) => b.classList.toggle("on", b === t));
      return;
    }
    if (t.dataset.status) {
      await api(`/api/incidents/${id}`, { method: "PATCH", body: { status: t.dataset.status } });
      toast(`Marked as ${STATUS_LABEL[t.dataset.status].toLowerCase()}`);
      closeModal(); onChange && onChange(); return;
    }
    if (t.dataset.m === "save") {
      await api(`/api/incidents/${id}`, { method: "PATCH", body: { notes: $("#m-notes").value } });
      toast("Notes saved"); onChange && onChange();
    } else if (t.dataset.m === "alert") {
      await busy(t, () => api(`/api/incidents/${id}/alert`, { method: "POST" }));
      toast("Sending alert to contacts…"); closeModal(); onChange && onChange();
    } else if (t.dataset.m === "delete") {
      if (!confirm(`Delete incident #${id} and its snapshot? This cannot be undone.`)) return;
      await api(`/api/incidents/${id}`, { method: "DELETE" });
      toast("Incident deleted"); closeModal(); onChange && onChange();
    }
  });
}

/* ================================================================= PAGES */
const PAGES = {};

/* ------------------------------------------------------------ detection reel */
/* With the camera off, the Overview stage plays recent detection snapshots: slow crossfades with a
   gentle zoom, captioned, click to open the incident. No snapshots yet: the illustrated street shows. */
function startReel(stage, slides) {
  // slides: [{ url, level, html, onClick }]
  if (!stage) return;
  if (S.reelTimer) { clearInterval(S.reelTimer); S.reelTimer = null; }
  const layer = $(".stage-reel", stage), caption = $(".reel-caption", stage);
  stage.classList.toggle("has-reel", slides.length > 0);
  layer.innerHTML = slides.map((slide) => `<div class="reel-slide" style="background-image:url('${slide.url}')"></div>`).join("");
  if (!slides.length) { caption.hidden = true; return; }
  let index = -1;
  const layers = $$(".reel-slide", layer);
  const show = () => {
    index = (index + 1) % slides.length;
    layers.forEach((el, i) => {
      el.classList.toggle("on", i === index);
      if (i === index) { el.style.animation = "none"; void el.offsetWidth; el.style.animation = ""; } // restart the zoom
    });
    const slide = slides[index];
    caption.hidden = false;
    caption.className = `reel-caption ${slide.level || ""} ${slide.onClick ? "" : "static"}`;
    caption.innerHTML = `<span class="dot"></span>${slide.html}<span class="faint"> · ${index + 1}/${slides.length}</span>`;
    caption.onclick = slide.onClick || null;
  };
  show();
  if (slides.length > 1 && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) S.reelTimer = setInterval(show, 4500);
  if (!S.reelCleanup) { S.reelCleanup = true; S.cleanup.push(() => { clearInterval(S.reelTimer); S.reelTimer = null; S.reelCleanup = false; }); }
}

async function showcaseSlides() {
  // example detections from the weapon model's public test set (web/showcase/CREDITS.txt)
  const items = await fetch("/static/showcase/showcase.json").then((r) => r.json()).catch(() => []);
  return items.map((item) => ({
    url: `/static/showcase/${item.file}`, level: "HIGH",
    html: `Example · weapon ${pct(item.confidence)} · ${esc(item.kind)} · ${esc(item.scene)}`,
  }));
}

function incidentSlides(items, onChange) {
  // the operator's own evidence (Live monitoring only); false alarms are not replayed
  return items.filter((i) => i.snapshot_url && i.status !== "false_alarm").slice(0, 8).map((item) => ({
    url: item.snapshot_url, level: item.level,
    html: `#${item.id} · ${item.level} · ${esc(item.label)} · ${fmtTime(item.ts)}`,
    onClick: () => openIncident(item.id, onChange),
  }));
}

/* ---------------------------------------------------------------- overview */
const LADDER = [
  ["LOW", "Street clear · light dimmed at night, off by day"],
  ["MEDIUM", "Someone at night, a crowd, or lingering · light 100%"],
  ["HIGH", "Weapon confirmed · light 100%, buzzer on, alert"],
];

PAGES.overview = {
  render(root) {
    root.innerHTML = `
      ${stageHTML({ showcase: true })}
      <div class="grid g-3">
        <div class="card">
          <div class="card-head"><span class="chip-icon">${ic("shield")}</span><div><h2>Why this level</h2><div class="sub" id="ov-why-sub">Live risk reasoning</div></div></div>
          <div class="card-body stack" style="gap:14px">
            <div class="ladder" id="ov-ladder">${LADDER.map(([l, t]) => `<div class="step ${l}" data-step="${l}"><b>${l}</b><span>${t}</span></div>`).join("")}</div>
            <ul class="reasons" id="ov-reasons"></ul>
          </div>
        </div>
        <div class="card" style="display:flex;flex-direction:column">
          <div class="card-head"><span class="chip-icon cyan">${ic("activity")}</span><div><h2>Activity</h2><div class="sub">Risk changes, incidents and alerts</div></div></div>
          <div id="ov-activity" style="flex:1"></div>
        </div>
        <div class="stack">
          ${stat("ov-today", "Incidents today", "alert", "amber")}
          ${stat("ov-hw", "Street light link", "plug", "cyan")}
          ${stat("ov-energy", "Energy saved today", "bulb", "green")}
        </div>
      </div>
      <div class="card">
        <div class="card-head"><span class="chip-icon amber">${ic("alert")}</span><div><h2>Recent incidents</h2><div class="sub">Snapshots are in Incident review</div></div>
          <span class="spacer"></span><a class="btn sm ghost" href="#incidents">View all ${ic("external")}</a></div>
        <div id="ov-incidents"><div class="empty"><p>Loading…</p></div></div>
      </div>`;
    this.loadIncidents();
    showcaseSlides().then((slides) => { if (S.page === "overview") startReel($(".stage"), slides); });
    root.addEventListener("click", (e) => { const c = e.target.closest("[data-incident]"); if (c) openIncident(+c.dataset.incident, () => this.loadIncidents()); });
  },
  async loadIncidents() {
    const current = loadGuard(this);
    const items = await api("/api/incidents?limit=10", { quiet: true }).catch(() => []);
    const box = $("#ov-incidents");
    if (!box || !current()) return;
    // text only here: camera snapshots (people's faces) stay in Incident review / Live monitoring
    box.innerHTML = items.length ? `<div style="overflow-x:auto"><table class="table"><tbody>${items.map((i) => `
        <tr data-incident="${i.id}" tabindex="0" role="button" style="cursor:pointer" aria-label="Open incident ${i.id}">
          <td class="faint num" style="width:56px">#${i.id}</td><td style="width:110px">${levelBadge(i.level)}</td>
          <td style="text-transform:capitalize" class="strong">${esc(i.label)}</td>
          <td class="muted small">${esc(i.reasons[0] || "")}</td>
          <td class="num muted" style="text-align:right;white-space:nowrap">${fmtDateTime(i.ts)}</td></tr>`).join("")}</tbody></table></div>`
      : emptyState("shield", "No incidents yet", "When the risk rises to MEDIUM or HIGH, the moment is saved with a snapshot in Incident review.");
  },
  update(d) {
    const page = $("#page");
    if (!$("#ov-ladder")) return;
    updateStage(page, d);
    $$("#ov-ladder .step").forEach((el) => el.classList.toggle("on", el.dataset.step === d.risk.level));
    $("#ov-reasons").innerHTML = d.risk.reasons.map((x) => `<li>${esc(x)}</li>`).join("");
    $("#ov-why-sub").textContent = `Decided from ${d.camera.running ? "camera" : "sensors only"} · ${d.night.is_night ? "night" : "day"} by ${d.night.source === "ldr" ? "LDR" : "clock"}`;
    tween($("#ov-today"), d.incidents_today);
    $("#ov-today-sub").textContent = d.alert_mode === "auto" ? "Alerts send automatically" : "Alerts wait for your confirmation";
    const hw = d.hardware;
    $("#ov-hw").textContent = hw.mode === "serial" ? (hw.online ? "ESP32" : "Offline") : "Simulator";
    $("#ov-hw-sub").textContent = hw.mode === "serial" ? `${hw.port} · ${hw.online ? "reporting" : "no data"}` : "Connect the ESP32 in Sensors & lights";
    const en = d.energy_today || {};
    $("#ov-energy").textContent = en.saving_pct == null ? "—" : `${en.saving_pct}%`;
    $("#ov-energy-sub").textContent = en.saving_pct == null ? "Counts from tonight's first dark hour"
      : `${en.saved_kwh} kWh · ${en.currency}${en.saved_cost} · ${en.co2_kg} kg CO₂ vs a normal lamp`;
    const act = $("#ov-activity");
    const top = d.activity.length ? d.activity[0].id : 0;
    if (act.dataset.top !== String(top)) { act.dataset.top = String(top); act.innerHTML = activityHTML(d.activity); }
    const newest = d.activity.find((ev) => ev.incident_id);
    if (newest && newest.id !== this._seen) { const first = this._seen === undefined; this._seen = newest.id; if (!first) this.loadIncidents(); }
  },
};

/* ------------------------------------------------------------ live monitor */
PAGES.live = {
  render(root) {
    const s = S.settings;
    root.innerHTML = `
      <div class="grid g-main">
        ${stageHTML({ fit: true, tall: true })}
        <div class="stack">
          <div class="card">
            <div class="card-head"><span class="chip-icon">${ic("cpu")}</span><div><h2>AI detector</h2><div class="sub" id="lv-models">—</div></div></div>
            <div class="card-body stack" style="gap:14px">
              <div class="row" style="justify-content:space-between"><span class="label">Camera health</span><span class="badge" id="lv-health">—</span></div>
              <div class="grid g-3" style="gap:10px">
                <div><div class="label">Camera FPS</div><div class="strong num" id="lv-fps">—</div></div>
                <div><div class="label">Inference</div><div class="strong num" id="lv-ms">—</div></div>
                <div><div class="label">Runs on</div><div class="strong" id="lv-dev">—</div></div>
              </div>
              <div class="field"><label for="lv-conf">People & vehicle confidence</label>
                <div class="range-row"><input type="range" id="lv-conf" min="0.05" max="0.95" step="0.05" value="${s.confidence}" data-live="confidence"><output>${pct(s.confidence)}</output></div></div>
              <div class="field"><label for="lv-wconf">Weapon confidence</label>
                <div class="range-row"><input type="range" id="lv-wconf" min="0.05" max="0.95" step="0.05" value="${s.weapon_confidence}" data-live="weapon_confidence"><output>${pct(s.weapon_confidence)}</output></div>
                <div class="hint">Higher = fewer false alarms, but may miss real weapons.</div></div>
              <div class="field"><label for="lv-cconf">Crime confidence</label>
                <div class="range-row"><input type="range" id="lv-cconf" min="0.05" max="0.95" step="0.05" value="${s.crime_confidence}" data-live="crime_confidence"><output>${pct(s.crime_confidence)}</output></div>
                <div class="hint">Violence, fight, robbery. Higher = fewer false alarms.</div></div>
            </div>
          </div>
          <div class="card">
            <div class="card-head"><span class="chip-icon cyan">${ic("eye")}</span><div><h2>In view now</h2><div class="sub" id="lv-count">—</div></div></div>
            <div class="card-body"><ul class="det-list" id="lv-dets"></ul></div>
          </div>
          <div class="card">
            <div class="card-head"><span class="chip-icon amber">${ic("pin")}</span><div><h2>Zones & tripwires</h2><div class="sub" id="zn-sub">Draw on the live camera</div></div></div>
            <div class="card-body stack" style="gap:12px">
              <div class="row wrap">
                <button class="btn sm" data-zone-draw="area">${ic("plus")} Draw area</button>
                <button class="btn sm" data-zone-draw="line">${ic("plus")} Draw tripwire</button>
              </div>
              <div id="zn-draft" hidden></div>
              <ul class="det-list" id="zn-list"></ul>
            </div>
          </div>
        </div>
      </div>`;
    const loadReel = () => api("/api/incidents?limit=20", { quiet: true }).then((items) => {
      if (S.page === "live") startReel($(".stage", root), incidentSlides(items, loadReel));
    }).catch(() => {});
    loadReel();
    this.zones = (S.settings.zones || []).map((z) => ({ ...z }));
    this.renderZones();
    root.addEventListener("click", (e) => this.onZoneClick(e));
    root.addEventListener("change", (e) => {
      if (e.target.dataset.zoneToggle) {
        const zone = this.zones.find((z) => z.id === e.target.dataset.zoneToggle);
        zone.enabled = e.target.checked;
        this.saveZones(zone.enabled ? `${zone.name} on` : `${zone.name} paused`);
      }
    });
    S.cleanup.push(() => this.stopDrawing());
    $$("[data-live]", root).forEach((input) => {
      input.addEventListener("input", () => { input.nextElementSibling.textContent = pct(+input.value); });
      input.addEventListener("change", async () => {
        S.settings = await api("/api/settings", { method: "PUT", body: { [input.dataset.live]: +input.value } });
        toast("Detection threshold updated");
      });
    });
  },
  /* ---------------------------------------------------------- zones */
  zoneSummary(z) {
    if (z.type === "line") return `Tripwire · ${{ any: "either way", a_to_b: "with the arrow", b_to_a: "against the arrow" }[z.direction]}`;
    return z.rule === "loiter" ? `Area · lingering over ${z.seconds} s` : "Area · no entry";
  },
  renderZones() {
    const list = $("#zn-list");
    if (!list) return;
    $("#zn-sub").textContent = this.zones.length ? `${this.zones.length} zone${this.zones.length === 1 ? "" : "s"} · drawn on the video` : "Draw on the live camera";
    list.innerHTML = this.zones.length ? this.zones.map((z) => `
      <li>
        <label class="toggle" title="On / off"><input type="checkbox" data-zone-toggle="${z.id}" ${z.enabled !== false ? "checked" : ""}><span></span></label>
        <div style="flex:1;min-width:0"><div class="strong">${esc(z.name)}</div>
          <div class="small muted">${this.zoneSummary(z)} · ${z.schedule === "night" ? "night only" : "always"}</div></div>
        ${levelBadge(z.level)}
        <button class="icon-btn" style="width:30px;height:30px" data-zone-delete="${z.id}" aria-label="Delete ${esc(z.name)}">${ic("trash")}</button>
      </li>`).join("")
      : `<li class="muted">No zones yet. Draw an area (e.g. an ATM, a closed park) or a tripwire (e.g. a gate).</li>`;
  },
  async saveZones(message) {
    const saved = await api("/api/zones", { method: "PUT", body: this.zones });
    this.zones = saved.map((z) => ({ ...z }));
    S.settings.zones = saved;
    this.renderZones();
    if (message) toast(message);
  },
  async onZoneClick(e) {
    const draw = e.target.closest("[data-zone-draw]");
    if (draw) return this.startDrawing(draw.dataset.zoneDraw);
    const del = e.target.closest("[data-zone-delete]");
    if (del) {
      const zone = this.zones.find((z) => z.id === del.dataset.zoneDelete);
      if (!confirm(`Delete zone "${zone.name}"?`)) return;
      this.zones = this.zones.filter((z) => z !== zone);
      return this.saveZones("Zone deleted");
    }
    const act = e.target.closest("[data-zone-act]");
    if (act && act.dataset.zoneAct === "finish") return this.finishDrawing();
    if (act && act.dataset.zoneAct === "cancel") return this.stopDrawing();
    if (act && act.dataset.zoneAct === "save") return this.saveDraft();
  },
  // where the camera picture actually is inside the stage (object-fit: contain letterboxes it)
  imageRect() {
    const img = $(".stage-media img");
    if (!img || img.hidden || !img.naturalWidth) return null;
    const box = img.getBoundingClientRect();
    const scale = Math.min(box.width / img.naturalWidth, box.height / img.naturalHeight);
    const w = img.naturalWidth * scale, h = img.naturalHeight * scale;
    return { left: box.left + (box.width - w) / 2, top: box.top + (box.height - h) / 2, width: w, height: h };
  },
  startDrawing(type) {
    if (!S.live || !S.live.camera.running || !this.imageRect()) {
      toast("Start the camera first, so you can draw on the real view", "error");
      return;
    }
    this.stopDrawing();
    const stage = $(".stage");
    stage.classList.add("drawing");
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.classList.add("zone-draw");
    svg.setAttribute("viewBox", "0 0 1000 1000");
    svg.setAttribute("preserveAspectRatio", "none");
    stage.append(svg);
    this.draft = { type, points: [], svg };
    this.placeOverlay();
    svg.addEventListener("click", (e) => {
      const r = svg.getBoundingClientRect();
      const x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), y = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height));
      this.draft.points.push([+x.toFixed(4), +y.toFixed(4)]);
      if (type === "line" && this.draft.points.length === 2) this.finishDrawing();
      else this.drawDraft();
    });
    this.resizeHandler = () => this.placeOverlay();
    window.addEventListener("resize", this.resizeHandler);
    $("#zn-draft").hidden = false;
    $("#zn-draft").innerHTML = `<div class="callout"><span>${ic("info")}</span><div class="small">${type === "area"
      ? "Click the corners of the area on the camera image. Mark where people's <b>feet</b> would be. Then press Finish."
      : "Click two points on the camera image to draw the tripwire."}</div></div>
      <div class="row" style="margin-top:8px">${type === "area" ? `<button class="btn sm primary" data-zone-act="finish">${ic("check")} Finish</button>` : ""}
      <button class="btn sm" data-zone-act="cancel">Cancel</button></div>`;
    this.drawDraft();
  },
  placeOverlay() {
    const rect = this.imageRect(), stage = $(".stage");
    if (!rect || !this.draft || !stage) return;
    const s = stage.getBoundingClientRect();
    Object.assign(this.draft.svg.style, { left: `${rect.left - s.left}px`, top: `${rect.top - s.top}px`, width: `${rect.width}px`, height: `${rect.height}px` });
  },
  drawDraft() {
    const { svg, points, type } = this.draft;
    const p = points.map(([x, y]) => `${x * 1000},${y * 1000}`).join(" ");
    svg.innerHTML = `${points.length > 1 ? (type === "area"
        ? `<polygon points="${p}" class="zd-shape"/>` : `<polyline points="${p}" class="zd-line"/>`) : ""}
      ${points.map(([x, y]) => `<circle cx="${x * 1000}" cy="${y * 1000}" r="9" class="zd-dot"/>`).join("")}`;
  },
  finishDrawing() {
    const d = this.draft;
    if (!d) return;
    if (d.type === "area" && d.points.length < 3) return toast("An area needs at least 3 corners", "error");
    const points = d.points;
    const type = d.type;
    this.stopDrawing();
    this.pending = { type, points };
    $("#zn-draft").hidden = false;
    $("#zn-draft").innerHTML = `<form class="stack" style="gap:10px" onsubmit="return false">
      <div class="field"><label for="zd-name">Name</label><input class="input" id="zd-name" maxlength="40" value="${type === "area" ? "Area" : "Tripwire"} ${this.zones.length + 1}"></div>
      ${type === "area" ? `
        <div class="field"><label for="zd-rule">Rule</label><select class="input" id="zd-rule"><option value="no_entry">No entry: alarm when anyone steps inside</option><option value="loiter">Lingering: alarm when someone stays too long</option></select></div>
        <div class="field" id="zd-sec-field" hidden><label for="zd-sec">Lingering after (seconds)</label><input class="input" id="zd-sec" type="number" min="3" max="3600" value="30"></div>`
      : `<div class="field"><label for="zd-dir">Direction</label><select class="input" id="zd-dir"><option value="any">Either way</option><option value="a_to_b">Only with the arrow</option><option value="b_to_a">Only against the arrow</option></select>
          <div class="hint">The arrow is drawn on the video after saving.</div></div>`}
      <div class="grid g-2" style="gap:10px">
        <div class="field"><label for="zd-level">Level</label><select class="input" id="zd-level"><option value="MEDIUM">MEDIUM (light 100%)</option><option value="HIGH">HIGH (buzzer, alert)</option></select></div>
        <div class="field"><label for="zd-sched">Active</label><select class="input" id="zd-sched"><option value="always">Always</option><option value="night">Night only</option></select></div>
      </div>
      <div class="row"><button class="btn sm primary" data-zone-act="save">${ic("save")} Save zone</button><button class="btn sm" data-zone-act="cancel">Cancel</button></div>
    </form>`;
    const rule = $("#zd-rule");
    if (rule) rule.addEventListener("change", () => { $("#zd-sec-field").hidden = rule.value !== "loiter"; });
  },
  async saveDraft() {
    const p = this.pending;
    if (!p) return;
    const zone = { type: p.type, points: p.points, name: $("#zd-name").value, level: $("#zd-level").value, schedule: $("#zd-sched").value, enabled: true };
    if (p.type === "area") Object.assign(zone, { rule: $("#zd-rule").value, seconds: +($("#zd-sec") ? $("#zd-sec").value : 30) });
    else zone.direction = $("#zd-dir").value;
    this.zones.push(zone);
    try { await this.saveZones(`Zone "${zone.name}" saved`); } catch { this.zones.pop(); return; }
    this.pending = null;
    $("#zn-draft").hidden = true;
  },
  stopDrawing() {
    if (this.draft) { this.draft.svg.remove(); this.draft = null; }
    if (this.resizeHandler) { window.removeEventListener("resize", this.resizeHandler); this.resizeHandler = null; }
    const stage = $(".stage");
    if (stage) stage.classList.remove("drawing");
    this.pending = null;
    const box = $("#zn-draft");
    if (box) { box.hidden = true; box.innerHTML = ""; }
  },
  update(d) {
    updateStage($("#page"), d);
    const det = d.detector;
    $("#lv-models").textContent = det.ready ? `${det.models.join(" + ")} · tracking ${det.tracking ? "on" : "off"}` : det.loading ? "Loading model…" : det.error || "Not available";
    $("#lv-fps").textContent = d.camera.running ? d.camera.fps.toFixed(1) : "—";
    const health = d.camera.health || "off";
    const healthEl = $("#lv-health");
    healthEl.className = `badge ${health === "ok" ? "green" : health === "covered" ? "red" : health === "off" ? "" : "amber"}`;
    healthEl.textContent = { ok: "OK", off: "Camera off", covered: "Covered / blinded", blurred: "Blurred", moved: "View moved" }[health] || health;
    $("#lv-ms").textContent = d.camera.running && det.ready ? `${det.inference_ms} ms` : "—";
    $("#lv-dev").textContent = det.device ? det.device.toUpperCase() : "—";
    $("#lv-count").textContent = d.camera.running ? `${d.counts.person} people · ${d.counts.vehicle} vehicles · ${d.counts.weapon} weapons` : "Camera off";
    const colors = { person: "var(--data)", vehicle: "var(--low)", weapon: "var(--high)", event: "var(--medium)", calm: "var(--low)" };
    const events = (d.events || []).map((e) => `<li style="border:1px solid ${e.severity === "HIGH" ? "var(--high)" : "var(--medium)"}">
      <span class="det-swatch" style="background:${e.severity === "HIGH" ? "var(--high)" : "var(--medium)"}"></span>
      <span class="strong">${esc(e.label)}</span><span class="conf">${e.severity}</span></li>`).join("");
    $("#lv-dets").innerHTML = events + (d.detections.length
      ? d.detections.slice().sort((a, b) => (b.category === "weapon") - (a.category === "weapon") || b.confidence - a.confidence)
        .map((x) => `<li><span class="det-swatch" style="background:${colors[x.category]}"></span><span style="text-transform:capitalize">${esc(x.label)}${x.track_id != null ? ` <span class="faint">#${x.track_id}</span>` : ""}</span>
          <span class="faint small" title="Model that found it">${esc(x.source || "yolo · tracked")}</span>
          <span class="conf">${pct(x.confidence)}</span></li>`).join("")
      : `<li class="muted">${d.camera.running ? "Nothing detected" : "Start the camera to see detections"}</li>`);
  },
};

/* --------------------------------------------------------------- incidents */
PAGES.incidents = {
  filter: { level: "", status: "" },
  render(root) {
    const f = this.filter;
    root.innerHTML = `
      <div class="toolbar">
        <div class="segmented" id="inc-level">${[["", "All"], ["HIGH", "High"], ["MEDIUM", "Medium"]].map(([v, l]) => `<button data-v="${v}" class="${f.level === v ? "on" : ""}">${l}</button>`).join("")}</div>
        <select class="input" id="inc-status" style="width:auto">${[["", "Any status"], ["new", "New"], ["reviewed", "Reviewed"], ["false_alarm", "False alarm"]].map(([v, l]) => `<option value="${v}" ${f.status === v ? "selected" : ""}>${l}</option>`).join("")}</select>
        <span class="spacer"></span><span class="muted" id="inc-count"></span>
        <button class="btn" id="inc-refresh">${ic("switch")} Refresh</button>
      </div>
      <div id="inc-list"></div>`;
    $("#inc-level").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; f.level = b.dataset.v; $$("#inc-level button").forEach((x) => x.classList.toggle("on", x === b)); this.load(); });
    $("#inc-status").addEventListener("change", (e) => { f.status = e.target.value; this.load(); });
    $("#inc-refresh").addEventListener("click", () => this.load());
    $("#inc-list").addEventListener("click", (e) => { const c = e.target.closest("[data-incident]"); if (c) openIncident(+c.dataset.incident, () => this.load()); });
    this.load();
  },
  async load() {
    const current = loadGuard(this);
    const items = await api(`/api/incidents?level=${this.filter.level}&status=${this.filter.status}&limit=300`);
    const list = $("#inc-list");
    if (!list || !current()) return;
    $("#inc-count").textContent = `${items.length} incident${items.length === 1 ? "" : "s"}`;
    list.innerHTML = items.length ? `<div class="inc-grid">${items.map(incidentCard).join("")}</div>`
      : `<div class="card">${emptyState("shield", "No incidents match", "Incidents are saved automatically when risk rises to MEDIUM or HIGH. Each one keeps a snapshot, the reasons, and the alert decision.")}</div>`;
  },
  update(d) {
    const ev = d.activity.find((x) => x.incident_id);
    if (ev && ev.id !== this._seen) { const first = this._seen === undefined; this._seen = ev.id; if (!first) this.load(); }
  },
};

/* --------------------------------------------------------------------- GPS */
PAGES.gps = {
  render(root) {
    const loc = S.settings.light_location;
    root.innerHTML = `
      <div class="grid g-main">
        <div class="card" id="gps-card">
          <div class="card-head"><span class="chip-icon">${ic("pin")}</span><div><h2>Map</h2><div class="sub" id="gps-hint">Street light and incident locations</div></div>
            <span class="spacer"></span>
            <button class="btn sm" id="gps-pick">${ic("locate")} Pick on map</button>
            <button class="btn sm primary" id="gps-here">${ic("locate")} Use my location</button></div>
          <div class="map" id="map"></div>
        </div>
        <div class="stack">
          <div class="card">
            <div class="card-head"><span class="chip-icon cyan">${ic("bulb")}</span><div><h2>Street light position</h2><div class="sub" id="gps-updated">—</div></div></div>
            <div class="card-body stack" style="gap:14px">
              <dl class="kv" id="gps-kv"></dl>
              <div class="divider"></div>
              <div class="field"><label for="gps-label">Name</label><input class="input" id="gps-label" maxlength="80" placeholder="e.g. MG Road, pole 14" value="${esc(loc.label || "")}"></div>
              <div class="grid g-2" style="gap:12px">
                <div class="field"><label for="gps-lat">Latitude</label><input class="input num" id="gps-lat" type="number" step="0.000001" value="${loc.lat ?? ""}"></div>
                <div class="field"><label for="gps-lng">Longitude</label><input class="input num" id="gps-lng" type="number" step="0.000001" value="${loc.lng ?? ""}"></div>
              </div>
              <button class="btn primary" id="gps-save">${ic("save")} Save position</button>
            </div>
          </div>
          <div class="card card-pad stack" style="gap:12px">
            <div class="row"><span class="chip-icon green">${ic("radar")}</span><div style="flex:1"><div class="strong">Live tracking</div><div class="small muted">Keep updating while this page is open (for a mobile unit)</div></div>
              <label class="toggle"><input type="checkbox" id="gps-track"><span></span></label></div>
            <div class="small muted" id="gps-track-status">Off</div>
          </div>
          <div class="callout"><span>${ic("info")}</span><div class="small">Uses this device's location service: real GPS on phones, Wi-Fi positioning on laptops (usually 20–100 m). The browser will ask for permission. Incidents are tagged with the position saved at the time.</div></div>
        </div>
      </div>`;
    this.picking = false;
    this.renderInfo(loc);
    $("#gps-here").addEventListener("click", (e) => this.locate(e.currentTarget));
    $("#gps-pick").addEventListener("click", () => {
      this.picking = !this.picking;
      $("#gps-card").classList.toggle("map-pick", this.picking);
      $("#gps-pick").classList.toggle("primary", this.picking);
      $("#gps-hint").textContent = this.picking ? "Click on the map to place the street light, then Save" : "Street light and incident locations";
    });
    $("#gps-save").addEventListener("click", () => {
      const lat = parseFloat($("#gps-lat").value), lng = parseFloat($("#gps-lng").value);
      if (Number.isNaN(lat) || Number.isNaN(lng)) return toast("Enter latitude and longitude, or pick on the map", "error");
      this.save({ lat, lng, accuracy: null, source: this.picking ? "map" : "manual" });
    });
    $("#gps-track").addEventListener("change", (e) => this.track(e.target.checked));
    S.cleanup.push(() => this.track(false));
    if (typeof L === "undefined") {
      $("#map").innerHTML = `<div class="empty">${ic("pin")}<h3>Map unavailable offline</h3><p>The map tiles need internet. You can still type the coordinates and save them.</p></div>`;
      $("#gps-pick").disabled = true;
    } else {
      this.initMap(loc);
    }
  },
  initMap(loc) {
    const map = L.map("map", { zoomControl: true, attributionControl: true });
    S.map = map;
    // Standard OSM tiles (free, no key). Night theme darkens them with a CSS filter on the tile pane.
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    if (loc.lat != null) map.setView([loc.lat, loc.lng], 17); else map.setView([20.59, 78.96], 5);
    map.on("click", (e) => {
      if (!this.picking) return;
      $("#gps-lat").value = e.latlng.lat.toFixed(6);
      $("#gps-lng").value = e.latlng.lng.toFixed(6);
      this.placeMarker(e.latlng.lat, e.latlng.lng, null);
    });
    if (loc.lat != null) this.placeMarker(loc.lat, loc.lng, loc.accuracy);
    this.loadIncidents();
    setTimeout(() => map.invalidateSize(), 50);
  },
  placeMarker(lat, lng, accuracy) {
    const map = S.map;
    if (!map) return;
    if (this.marker) this.marker.remove();
    if (this.circle) { this.circle.remove(); this.circle = null; }
    const icon = L.divIcon({ className: "", html: `<div class="light-marker">${ic("bulb")}</div>`, iconSize: [34, 34], iconAnchor: [17, 17] });
    this.marker = L.marker([lat, lng], { icon }).addTo(map).bindPopup("Street light");
    if (accuracy) this.circle = L.circle([lat, lng], { radius: accuracy, color: cssVar("--accent"), weight: 1, fillOpacity: 0.08 }).addTo(map);
  },
  async loadIncidents() {
    const current = loadGuard(this);
    const map = S.map;
    const items = (await api("/api/incidents?limit=500", { quiet: true }).catch(() => [])).filter((i) => i.lat != null);
    if (!S.map || S.map !== map || !current()) return;
    const colors = { HIGH: cssVar("--high"), MEDIUM: cssVar("--medium"), LOW: cssVar("--low") };
    items.forEach((i, n) => {
      const jitter = (n % 7) * 0.00001; // spread incidents recorded at the same pole
      L.circleMarker([i.lat + jitter, i.lng + jitter], { radius: 7, color: "#fff", weight: 2, fillColor: colors[i.level], fillOpacity: 0.95 })
        .addTo(S.map).bindPopup(`<b style="text-transform:capitalize">${esc(i.label)}</b><br>${i.level} · ${fmtDateTime(i.ts)}<br><a href="#incidents">Open incidents</a>`);
    });
    this.incidentCount = items.length;
    this.renderInfo(S.settings.light_location);
  },
  renderInfo(loc) {
    const kv = $("#gps-kv");
    if (!kv) return;
    const set = loc.lat != null;
    kv.innerHTML = `
      <dt>Coordinates</dt><dd class="num">${set ? `${loc.lat.toFixed(6)}, ${loc.lng.toFixed(6)}` : '<span class="faint">Not set</span>'}</dd>
      <dt>Accuracy</dt><dd>${loc.accuracy ? `± ${Math.round(loc.accuracy)} m` : "—"}</dd>
      <dt>Source</dt><dd>${{ "device-gps": "Device location", map: "Picked on map", manual: "Entered by hand", tracking: "Live tracking" }[loc.source] || "—"}</dd>
      <dt>Incidents on map</dt><dd>${this.incidentCount ?? "—"}</dd>
      ${set ? `<dt>Open in</dt><dd><a href="https://maps.google.com/?q=${loc.lat},${loc.lng}" target="_blank" rel="noopener">Google Maps ${ic("external")}</a></dd>` : ""}`;
    $("#gps-updated").textContent = loc.updated ? `Updated ${ago(loc.updated)}` : "Not set yet";
  },
  async save(body, quiet = false) {
    // if the user already left this page (slow GPS fix), keep the saved name instead of wiping it
    body.label = $("#gps-label") ? $("#gps-label").value : (S.settings.light_location.label || "");
    const loc = await api("/api/location", { method: "PUT", body });
    S.settings.light_location = loc;
    if (!$("#gps-lat")) return loc;
    $("#gps-lat").value = loc.lat; $("#gps-lng").value = loc.lng;
    this.placeMarker(loc.lat, loc.lng, loc.accuracy);
    this.renderInfo(loc);
    if (!quiet) { toast("Street light position saved"); S.map && S.map.setView([loc.lat, loc.lng], Math.max(S.map.getZoom(), 16)); }
    return loc;
  },
  locate(btn) {
    if (!navigator.geolocation) return toast("This browser has no location service", "error");
    btn.disabled = true;
    navigator.geolocation.getCurrentPosition(
      async (pos) => { btn.disabled = false; await this.save({ lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: pos.coords.accuracy, source: "device-gps" }); },
      (err) => { btn.disabled = false; toast(err.code === 1 ? "Location permission denied. Allow it in the browser's site settings." : `Location unavailable: ${err.message}`, "error", 6000); },
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 });
  },
  track(on) {
    if (this.watch != null) { navigator.geolocation.clearWatch(this.watch); this.watch = null; }
    const status = $("#gps-track-status");
    if (!on) { if (status) status.textContent = "Off"; return; }
    if (!navigator.geolocation) { toast("No location service", "error"); return; }
    let last = null;
    status.textContent = "Waiting for first fix…";
    this.watch = navigator.geolocation.watchPosition(async (pos) => {
      const { latitude: lat, longitude: lng, accuracy } = pos.coords;
      const moved = !last || S.map.distance([last.lat, last.lng], [lat, lng]) > 10 || Date.now() - last.t > 60000;
      if (status) status.textContent = `Last fix ${new Date().toLocaleTimeString()} · ± ${Math.round(accuracy)} m`;
      if (moved) { last = { lat, lng, t: Date.now() }; await this.save({ lat, lng, accuracy, source: "tracking" }, true); }
    }, (err) => { if (status) status.textContent = `Error: ${err.message}`; }, { enableHighAccuracy: true, maximumAge: 5000 });
  },
};

/* ---------------------------------------------------------------- contacts */
PAGES.contacts = {
  render(root) {
    root.innerHTML = `<div class="stack" id="ct-root"><div class="empty"><p>Loading…</p></div></div>`;
    this.load();
    root.addEventListener("click", (e) => this.onClick(e));
    root.addEventListener("change", (e) => this.onChange(e));
  },
  async load() {
    const current = loadGuard(this);
    const data = await api("/api/contacts");
    const rootEl = $("#ct-root");
    if (!rootEl || !current()) return;
    this.data = data;
    const ch = data.channels;
    const channelCard = (key, icon, title) => `
      <div class="card card-pad stack" style="gap:12px">
        <div class="row"><span class="chip-icon ${ch[key].configured ? "green" : "amber"}">${ic(icon)}</span>
          <div style="flex:1"><div class="strong">${title}</div><div class="small muted">${ch[key].configured ? (ch[key].sender ? `Sending from ${esc(ch[key].sender)}` : "Bot token found") : "Not configured"}</div></div>
          <span class="badge ${ch[key].configured ? "green" : "amber"}">${ch[key].configured ? "Ready" : "Setup needed"}</span></div>
        ${ch[key].configured ? "" : `<div class="small muted">${esc(ch[key].setup)}</div>`}
      </div>`;
    rootEl.innerHTML = `
      <div class="card card-pad">
        <div class="row wrap" style="gap:16px">
          <span class="chip-icon red">${ic("bell")}</span>
          <div style="flex:1;min-width:240px"><div class="strong">When risk turns HIGH</div>
            <div class="small muted" id="ct-mode-text">${data.alert_mode === "auto"
              ? "Alerts are sent to all enabled contacts automatically, with the snapshot attached (rate-limited by the cooldown in Settings)."
              : "The incident is saved and you confirm before anyone is messaged. Safer: AI can mistake a phone or tool for a weapon."}</div></div>
          <div class="segmented" id="ct-mode"><button data-mode="manual" class="${data.alert_mode === "manual" ? "on" : ""}">Operator confirms</button><button data-mode="auto" class="${data.alert_mode === "auto" ? "on" : ""}">Automatic</button></div>
        </div>
      </div>
      <div class="grid g-2">${channelCard("email", "mail", "Email")}${channelCard("telegram", "send", "Telegram")}</div>
      <div class="card">
        <div class="card-head"><span class="chip-icon">${ic("users")}</span><div><h2>Contacts</h2><div class="sub">${data.contacts.length} contact${data.contacts.length === 1 ? "" : "s"}</div></div></div>
        ${data.contacts.length ? `<div style="overflow-x:auto"><table class="table"><thead><tr><th>Name</th><th>Channel</th><th>Address</th><th>Enabled</th><th></th></tr></thead><tbody>
          ${data.contacts.map((c) => `<tr>
            <td class="strong">${esc(c.name)}</td>
            <td><span class="badge ${c.channel === "email" ? "violet" : "green"}">${ic(c.channel === "email" ? "mail" : "send")} ${c.channel}</span></td>
            <td class="mono">${esc(c.address)}</td>
            <td><label class="toggle"><input type="checkbox" data-enable="${c.id}" ${c.enabled ? "checked" : ""}><span></span></label></td>
            <td style="text-align:right;white-space:nowrap"><button class="btn sm" data-test="${c.id}">${ic("send")} Test</button>
              <button class="btn sm ghost danger" data-del="${c.id}" title="Remove">${ic("trash")}</button></td></tr>`).join("")}
        </tbody></table></div>` : emptyState("users", "No contacts yet", "Add the people who should be told when a weapon is detected.")}
        <div class="card-body" style="border-top:1px solid var(--border)">
          <form class="form-grid" id="ct-form" autocomplete="off">
            <div class="field"><label for="ct-name">Name</label><input class="input" id="ct-name" maxlength="60" required placeholder="e.g. Police control room"></div>
            <div class="field"><label for="ct-channel">Channel</label><select class="input" id="ct-channel"><option value="email">Email</option><option value="telegram">Telegram</option></select></div>
            <div class="field"><label for="ct-address" id="ct-address-label">Email address</label><input class="input" id="ct-address" maxlength="120" required placeholder="name@example.com"></div>
            <div class="field" style="justify-content:flex-end"><button class="btn primary" type="submit">${ic("plus")} Add contact</button></div>
          </form>
        </div>
      </div>
      <div class="card">
        <div class="card-head"><span class="chip-icon cyan">${ic("activity")}</span><div><h2>Delivery log</h2><div class="sub">Last 20 attempts</div></div></div>
        ${data.log.length ? `<div style="overflow-x:auto"><table class="table"><thead><tr><th>Time</th><th>Contact</th><th>Channel</th><th>Result</th></tr></thead><tbody>
          ${data.log.map((a) => `<tr><td class="num">${fmtDateTime(a.ts)}</td><td>${esc(a.contact_name || "Removed contact")}</td><td>${a.channel}</td>
            <td>${a.ok ? '<span class="badge green">Delivered</span>' : `<span class="badge red">Failed</span> <span class="small muted">${esc(a.error)}</span>`}${a.incident_id ? ` <span class="small faint">#${a.incident_id}</span>` : ' <span class="small faint">test</span>'}</td></tr>`).join("")}
        </tbody></table></div>` : `<div class="empty"><p>No alerts sent yet.</p></div>`}
      </div>`;
    $("#ct-channel").addEventListener("change", (e) => {
      const tg = e.target.value === "telegram";
      $("#ct-address-label").textContent = tg ? "Telegram chat ID" : "Email address";
      $("#ct-address").placeholder = tg ? "e.g. 123456789 (from @userinfobot)" : "name@example.com";
    });
    $("#ct-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const button = $("#ct-form button[type=submit]");
      if (button.disabled) return;
      await busy(button, () => api("/api/contacts", { method: "POST", body: { name: $("#ct-name").value, channel: $("#ct-channel").value, address: $("#ct-address").value } }));
      toast("Contact added"); this.load();
    });
  },
  async onClick(e) {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.mode) {
      S.settings = await api("/api/settings", { method: "PUT", body: { alert_mode: b.dataset.mode } });
      toast(b.dataset.mode === "auto" ? "Alerts will send automatically" : "Alerts now need your confirmation"); this.load();
    } else if (b.dataset.test) {
      await busy(b, async () => { const r = await api(`/api/contacts/${b.dataset.test}/test`, { method: "POST" }).catch(() => null); if (r) toast(r.message); });
      this.load();
    } else if (b.dataset.del) {
      const c = this.data.contacts.find((x) => x.id === +b.dataset.del);
      if (!confirm(`Remove ${c ? c.name : "this contact"}?`)) return;
      await api(`/api/contacts/${b.dataset.del}`, { method: "DELETE" }); toast("Contact removed"); this.load();
    }
  },
  async onChange(e) {
    if (e.target.dataset.enable) {
      await api(`/api/contacts/${e.target.dataset.enable}`, { method: "PATCH", body: { enabled: e.target.checked } });
      toast(e.target.checked ? "Contact enabled" : "Contact paused");
    }
  },
};

/* ----------------------------------------------------------------- sensors */
PAGES.sensors = {
  render(root) {
    root.innerHTML = `
      <div class="grid g-main">
        <div class="stack">
          <div class="card">
            <div class="card-head"><span class="chip-icon">${ic("plug")}</span><div><h2>ESP32 connection</h2><div class="sub" id="hw-sub">—</div></div>
              <span class="spacer"></span><span class="badge" id="hw-badge">—</span></div>
            <div class="card-body stack" style="gap:14px">
              <div class="row wrap">
                <select class="input" id="hw-port" style="flex:1;min-width:220px"></select>
                <button class="btn" id="hw-refresh" title="Rescan USB ports">${ic("switch")}</button>
                <button class="btn primary" id="hw-connect">${ic("plug")} Connect</button>
              </div>
              <dl class="kv" id="hw-kv"></dl>
            </div>
          </div>
          <div class="card">
            <div class="card-head"><span class="chip-icon amber">${ic("sliders")}</span><div><h2>Manual test</h2><div class="sub">Overrides the AI response for a few seconds</div></div></div>
            <div class="card-body stack" style="gap:14px">
              <div class="field"><label>Brightness</label><div class="range-row"><input type="range" min="0" max="100" step="5" value="100" id="t-bright"><output id="t-bright-out">100%</output></div></div>
              <div class="row wrap">
                <label class="row" style="gap:10px"><span class="toggle"><input type="checkbox" id="t-buzz"><span></span></span> Buzzer</label>
                <span class="spacer" style="flex:1"></span>
                <select class="input" id="t-secs" style="width:auto"><option value="3">3 s</option><option value="5" selected>5 s</option><option value="10">10 s</option></select>
                <button class="btn primary" id="t-run">${ic("play")} Run test</button>
              </div>
              <div class="row wrap" style="border-top:1px solid var(--border);padding-top:14px">
                <span class="chip-icon red">${ic("bell")}</span>
                <div style="flex:1;min-width:180px"><div class="strong">SOS button</div><div class="small muted" id="sos-status">Not pressed</div></div>
                <button class="btn sm danger solid" data-act="sos-sim">${ic("alert")} Simulate SOS press</button>
                <button class="btn sm" data-act="sos-clear" id="sos-clear-btn" hidden>${ic("check")} Clear SOS</button>
              </div>
              <div class="row wrap">
                <button class="btn sm" data-quick="0,0">Light off</button>
                <button class="btn sm" data-quick="20,0">Dim 20%</button>
                <button class="btn sm" data-quick="100,0">Full brightness</button>
                <button class="btn sm danger" data-quick="100,1">Beep buzzer</button>
              </div>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-head"><span class="chip-icon cyan">${ic("bulb")}</span><div><h2>Street light</h2><div class="sub" id="lamp-sub">—</div></div></div>
          <div class="card-body stack" style="gap:16px">
            <div class="lamp-stage">${streetScene("lampsc")}
              <div class="readout"><div class="label" style="color:rgba(242,239,233,.7)">Brightness</div><div class="v" id="lamp-val">0%</div></div>
              <span class="badge buzz" id="lamp-buzzer">Buzzer off</span></div>
            <dl class="kv" id="lamp-kv"></dl>
            <div><div class="row" style="justify-content:space-between"><span class="label">LDR light level</span><span class="small muted num" id="ldr-val">—</span></div>
              <div class="meter" style="margin-top:8px"><i id="ldr-bar" style="width:0"></i><span class="mark" id="ldr-mark"></span></div>
              <div class="small faint" style="margin-top:6px">Line = dark threshold (Settings). Below it counts as night.</div></div>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-head"><span class="chip-icon">${ic("cpu")}</span><div><h2>Wiring & firmware</h2><div class="sub">firmware/esp32_street_light/esp32_street_light.ino</div></div></div>
        <div style="overflow-x:auto"><table class="table"><thead><tr><th>Part</th><th>ESP32 pin</th><th>Notes</th></tr></thead><tbody>
          <tr><td class="strong">Street light LED</td><td class="mono">GPIO 25</td><td class="muted">Through a transistor/MOSFET for anything brighter than a single LED. PWM dimming.</td></tr>
          <tr><td class="strong">Piezo buzzer</td><td class="mono">GPIO 26</td><td class="muted">Active buzzer, or passive driven with a tone.</td></tr>
          <tr><td class="strong">PIR motion sensor</td><td class="mono">GPIO 27</td><td class="muted">HC-SR501 OUT pin. Power from 5 V, output is 3.3 V safe.</td></tr>
          <tr><td class="strong">SOS push button</td><td class="mono">GPIO 14</td><td class="muted">Button to GND (internal pull-up). Works even if the PC is off: the lamp strobes and the buzzer sounds for 60 s.</td></tr>
          <tr><td class="strong">LDR</td><td class="mono">GPIO 34</td><td class="muted">Voltage divider with a 10 kΩ resistor to 3.3 V. Brighter = higher value.</td></tr>
        </tbody></table></div>
        <div class="card-body small muted" style="border-top:1px solid var(--border)">
          Flash the sketch with Arduino IDE (board: <code>ESP32 Dev Module</code>), plug the ESP32 in by USB, then pick its port above.
          If the dashboard stops talking to it for 5 s, the ESP32 runs on its own: PIR + LDR switch the light by themselves.
        </div>
      </div>`;
    $("#t-bright").addEventListener("input", (e) => { $("#t-bright-out").textContent = `${e.target.value}%`; });
    $("#t-run").addEventListener("click", () => this.test(+$("#t-bright").value, $("#t-buzz").checked, +$("#t-secs").value));
    $$("[data-quick]", root).forEach((b) => b.addEventListener("click", () => { const [v, z] = b.dataset.quick.split(","); this.test(+v, z === "1", z === "1" ? 1.5 : 5); }));
    $("#hw-refresh").addEventListener("click", () => this.loadPorts(true));
    $("#hw-connect").addEventListener("click", (e) => busy(e.currentTarget, async () => {
      const r = await api("/api/hardware/connect", { method: "POST", body: { port: $("#hw-port").value } });
      S.settings.serial_port = $("#hw-port").value;
      toast(r.message);
    }));
    this.loadPorts(false);
  },
  async loadPorts(announce) {
    const ports = await api("/api/hardware/ports", { quiet: true }).catch(() => []);
    const sel = $("#hw-port");
    if (!sel) return;
    const current = S.settings.serial_port || "";
    sel.innerHTML = `<option value="">Simulator (no hardware)</option>` + ports.map((p) => `<option value="${esc(p.device)}">${esc(p.device)} — ${esc(p.description)}${p.likely_esp32 ? " ★" : ""}</option>`).join("");
    if (current && !ports.some((p) => p.device === current)) sel.insertAdjacentHTML("beforeend", `<option value="${esc(current)}">${esc(current)} (not found)</option>`);
    sel.value = current;
    if (announce) toast(ports.length ? `${ports.length} serial port${ports.length === 1 ? "" : "s"} found` : "No USB serial ports found. Is the ESP32 plugged in?", ports.length ? "ok" : "error");
  },
  async test(brightness, buzzer, seconds) {
    const r = await api("/api/hardware/test", { method: "POST", body: { brightness, buzzer, seconds } });
    toast(r.message);
  },
  update(d) {
    const hw = d.hardware;
    if (!$("#hw-kv")) return;
    const serial = hw.mode === "serial";
    $("#hw-sub").textContent = serial ? `USB serial · ${hw.port}` : "Simulator: outputs follow the AI, sensors are simulated";
    const badge = $("#hw-badge");
    badge.className = `badge ${serial ? (hw.online ? "green" : "red") : "violet"}`;
    badge.innerHTML = `<span class="dot"></span>${serial ? (hw.online ? "Online" : "No data") : "Simulator"}`;
    $("#hw-kv").innerHTML = `
      <dt>Mode</dt><dd>${serial ? "ESP32 over USB" : "Simulator"}</dd>
      <dt>Firmware</dt><dd>${esc(hw.firmware) || "—"}</dd>
      <dt>Last report</dt><dd>${hw.last_seen ? ago(hw.last_seen) : "never"}</dd>
      ${hw.error ? `<dt>Error</dt><dd style="color:var(--high)">${esc(hw.error)}</dd>` : ""}`;
    setLamp($("#lampsc"), hw.brightness / 100);
    $(".lamp-stage").classList.toggle("strobe", !!hw.strobe);
    const sosActive = d.sos && d.sos.active;
    $("#sos-status").textContent = sosActive ? `ACTIVE: HIGH risk held until ${fmtTime(d.sos.until)} or cleared` : "Not pressed";
    $("#sos-status").style.color = sosActive ? "var(--high)" : "";
    $("#sos-clear-btn").hidden = !sosActive;
    tween($("#lamp-val"), hw.brightness, (v) => `${Math.round(v)}%`);
    const buzz = $("#lamp-buzzer");
    buzz.className = `badge buzz ${hw.buzzer ? "red" : ""}`;
    buzz.textContent = hw.buzzer ? "Buzzer ON" : "Buzzer off";
    $("#lamp-sub").textContent = hw.override ? "Manual test running" : `Following AI risk: ${d.risk.level}`;
    $("#lamp-kv").innerHTML = `
      <dt>Brightness</dt><dd>${hw.brightness}%</dd>
      <dt>Buzzer</dt><dd>${hw.buzzer ? '<span class="badge red">ON</span>' : "Off"}</dd>
      <dt>Strobe</dt><dd>${hw.strobe ? '<span class="badge red">Flashing</span>' : "Off"}</dd>
      <dt>PIR motion</dt><dd>${hw.pir ? '<span class="badge amber">Motion</span>' : "Still"}</dd>
      <dt>Day / night</dt><dd>${d.night.is_night ? "Night" : "Day"} <span class="faint small">(${d.night.source === "ldr" ? "LDR" : "clock"})</span></dd>`;
    const ldr = hw.ldr;
    $("#ldr-val").textContent = ldr == null ? "—" : `${ldr} / 4095`;
    $("#ldr-bar").style.width = ldr == null ? "0" : `${(ldr / 4095) * 100}%`;
    $("#ldr-mark").style.left = `${(S.settings.ldr_dark_threshold / 4095) * 100}%`;
  },
};

/* --------------------------------------------------------------- analytics */
PAGES.analytics = {
  days: 7,
  render(root) {
    root.innerHTML = `
      <div class="toolbar"><div class="segmented" id="an-days">${[7, 30, 90].map((d) => `<button data-d="${d}" class="${this.days === d ? "on" : ""}">${d} days</button>`).join("")}</div></div>
      <div class="grid g-4">${stat("an-total", "Incidents", "alert", "amber")}${stat("an-high", "High risk", "shield", "red")}${stat("an-fa", "False alarm rate", "check", "green")}${stat("an-peak", "Busiest hour", "clock", "cyan")}</div>
      <div class="grid g-2">
        <div class="card"><div class="card-head"><h3>Incidents per day</h3></div><div class="card-body"><div class="chart-box"><canvas id="c-day"></canvas></div></div></div>
        <div class="card"><div class="card-head"><h3>By hour of day</h3></div><div class="card-body"><div class="chart-box"><canvas id="c-hour"></canvas></div></div></div>
      </div>
      <div class="card">
        <div class="card-head"><span class="chip-icon green">${ic("bulb")}</span><div><h2>Energy</h2><div class="sub" id="an-energy-sub">Smart dimming vs a normal lamp at full power all night</div></div></div>
        <div class="card-body">
          <div class="grid g-4" style="gap:12px;margin-bottom:16px">
            <div><div class="label">Saved</div><div class="stat-value" id="en-kwh">—</div></div>
            <div><div class="label">Money saved</div><div class="stat-value" id="en-cost">—</div></div>
            <div><div class="label">CO₂ avoided</div><div class="stat-value" id="en-co2">—</div></div>
            <div><div class="label">Saving</div><div class="stat-value" id="en-pct">—</div></div>
          </div>
          <div class="chart-box sm"><canvas id="c-energy"></canvas></div>
        </div>
      </div>
      <div class="card">
        <div class="card-head"><span class="chip-icon amber">${ic("pin")}</span><div><h2>Where people go</h2><div class="sub">Feet positions counted on the camera view · faces blurred in the background</div></div></div>
        <div class="card-body"><div class="heat-box"><canvas id="c-heat"></canvas><div class="heat-empty muted" id="heat-empty" hidden>No people counted yet in this period</div></div></div>
      </div>
      <div class="grid g-2">
        <div class="card"><div class="card-head"><h3>What was detected</h3></div><div class="card-body"><div class="chart-box sm"><canvas id="c-label"></canvas></div></div></div>
        <div class="card"><div class="card-head"><h3>Street activity · last 24 h</h3><span class="spacer"></span><span class="sub">Average per 30 min while camera is on</span></div><div class="card-body"><div class="chart-box sm"><canvas id="c-line"></canvas></div></div></div>
      </div>`;
    $("#an-days").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; this.days = +b.dataset.d; route(); });
    this.load();
  },
  async load() {
    const current = loadGuard(this);
    const a = await api(`/api/analytics?days=${this.days}`);
    if (!$("#c-day") || !current()) return;
    S.charts.forEach((chart) => chart.destroy());
    S.charts = [];
    const k = a.kpis;
    $("#an-total").textContent = k.total; $("#an-total-sub").textContent = `${k.medium} medium · last ${this.days} days`;
    $("#an-high").textContent = k.high; $("#an-high-sub").textContent = `${k.alerts_sent} alert message${k.alerts_sent === 1 ? "" : "s"} delivered`;
    $("#an-fa").textContent = k.false_alarm_rate == null ? "—" : pct(k.false_alarm_rate); $("#an-fa-sub").textContent = "Of incidents you reviewed";
    $("#an-peak").textContent = k.peak_hour == null ? "—" : `${String(k.peak_hour).padStart(2, "0")}:00`; $("#an-peak-sub").textContent = "Most incidents start";

    const text = cssVar("--muted"), grid = cssVar("--border");
    Chart.defaults.color = text; Chart.defaults.font.family = "Inter, system-ui, sans-serif"; Chart.defaults.borderColor = grid;
    const high = cssVar("--high"), med = cssVar("--medium"), acc = cssVar("--accent"), acc2 = cssVar("--data"), low = cssVar("--low");
    const base = { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { boxWidth: 10, boxHeight: 10, useBorderRadius: true, borderRadius: 3 } } } };
    const axes = { x: { grid: { display: false } }, y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: grid } } };
    const labels = a.days.map((d) => new Date(`${d}T12:00:00`).toLocaleDateString("en-IN", { day: "2-digit", month: "short" }));
    S.charts.push(new Chart($("#c-day"), { type: "bar", data: { labels, datasets: [
      { label: "High", data: a.per_day.HIGH, backgroundColor: high, borderRadius: 4, stack: "s" },
      { label: "Medium", data: a.per_day.MEDIUM, backgroundColor: med, borderRadius: 4, stack: "s" }] },
    options: { ...base, scales: { x: { ...axes.x, stacked: true }, y: { ...axes.y, stacked: true } } } }));
    S.charts.push(new Chart($("#c-hour"), { type: "bar", data: { labels: [...Array(24).keys()].map((h) => String(h).padStart(2, "0")), datasets: [
      { label: "Incidents", data: a.by_hour, backgroundColor: acc, borderRadius: 4 }] }, options: { ...base, plugins: { legend: { display: false } }, scales: axes } }));
    const palette = [high, med, acc, acc2, low, "#B39DDB", "#8D8478", "#5B6B73"];
    S.charts.push(new Chart($("#c-label"), { type: "doughnut", data: { labels: a.by_label.length ? a.by_label.map((x) => x[0]) : ["No incidents"],
      datasets: [{ data: a.by_label.length ? a.by_label.map((x) => x[1]) : [1], backgroundColor: a.by_label.length ? palette : [cssVar("--surface-3")], borderWidth: 0 }] },
    options: { ...base, cutout: "68%", plugins: { legend: { position: "right", labels: { boxWidth: 10, boxHeight: 10 } } } } }));
    this.drawHeat(current);
    const en = a.energy;
    $("#en-kwh").textContent = `${en.saved_kwh} kWh`;
    $("#en-cost").textContent = `${en.currency}${en.saved_cost}`;
    $("#en-co2").textContent = `${en.co2_kg} kg`;
    $("#en-pct").textContent = en.saving_pct == null ? "—" : `${en.saving_pct}%`;
    $("#an-energy-sub").textContent = `Smart dimming vs a normal ${en.lamp_watts} W lamp at full power all night`;
    S.charts.push(new Chart($("#c-energy"), { type: "bar", data: { labels, datasets: [
      { label: "Normal lamp (kWh)", data: en.baseline_kwh, backgroundColor: cssVar("--faint"), borderRadius: 4 },
      { label: "Sentinel lamp (kWh)", data: en.lamp_kwh, backgroundColor: low, borderRadius: 4 }] },
    options: { ...base, scales: { x: axes.x, y: { ...axes.y, ticks: {} } } } }));
    const tl = a.timeline;
    S.charts.push(new Chart($("#c-line"), { type: "line", data: { labels: tl.map((p) => fmt(p.ts, { hour: "2-digit", minute: "2-digit", hour12: false })), datasets: [
      { label: "People", data: tl.map((p) => p.people), borderColor: acc2, backgroundColor: acc2 + "22", fill: true, tension: 0.35, pointRadius: 0 },
      { label: "Vehicles", data: tl.map((p) => p.vehicles), borderColor: low, tension: 0.35, pointRadius: 0 }] },
    options: { ...base, scales: { x: axes.x, y: { ...axes.y, ticks: {} } } } }));
  },
};

PAGES.analytics.drawHeat = async function drawHeat(current) {
  const heat = await api(`/api/heatmap?days=${this.days}`, { quiet: true }).catch(() => null);
  const canvas = $("#c-heat");
  if (!heat || !canvas || !current()) return;
  const width = canvas.parentElement.clientWidth, height = Math.round(width * 9 / 16);
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio; canvas.height = height * ratio;
  canvas.style.width = `${width}px`; canvas.style.height = `${height}px`;
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  ctx.fillStyle = cssVar("--feed-bg");
  ctx.fillRect(0, 0, width, height);
  if (heat.background) {
    const img = await new Promise((resolve) => { const i = new Image(); i.onload = () => resolve(i); i.onerror = () => resolve(null); i.src = heat.background; });
    if (img && current()) { ctx.globalAlpha = 0.55; ctx.drawImage(img, 0, 0, width, height); ctx.globalAlpha = 1; }
  }
  $("#heat-empty").hidden = heat.peak > 0;
  if (!heat.peak) return;
  // one pixel per grid cell, then scaled up with smoothing for a soft heat look
  const grid = document.createElement("canvas");
  grid.width = heat.width; grid.height = heat.height;
  const g = grid.getContext("2d"), cells = g.createImageData(heat.width, heat.height);
  heat.cells.forEach((count, i) => {
    const v = Math.sqrt(count / heat.peak); // sqrt so quieter paths still show
    cells.data[i * 4] = 245 + 10 * v;            // amber -> red
    cells.data[i * 4 + 1] = 165 - 96 * v;
    cells.data[i * 4 + 2] = 36 + 33 * v;
    cells.data[i * 4 + 3] = count ? Math.round(60 + 170 * v) : 0;
  });
  g.putImageData(cells, 0, 0);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.filter = "blur(6px)";
  ctx.drawImage(grid, 0, 0, width, height);
  ctx.filter = "none";
};

/* ----------------------------------------------------------------- reports */
PAGES.reports = {
  render(root) {
    const today = new Date();
    const iso = (d) => new Intl.DateTimeFormat("en-CA", { timeZone: tz() }).format(d);
    const weekAgo = new Date(today.getTime() - 6 * 86400000);
    root.innerHTML = `
      <div class="card">
        <div class="card-head"><span class="chip-icon">${ic("file")}</span><div><h2>Generate report</h2><div class="sub">Incident log, summary and evidence snapshots</div></div></div>
        <div class="card-body stack" style="gap:16px">
          <div class="row wrap" style="gap:12px;align-items:flex-end">
            <div class="field"><label for="rp-start">From</label><input class="input" type="date" id="rp-start" value="${iso(weekAgo)}"></div>
            <div class="field"><label for="rp-end">To</label><input class="input" type="date" id="rp-end" value="${iso(today)}"></div>
            <div class="segmented" id="rp-quick"><button data-q="0">Today</button><button data-q="6" class="on">7 days</button><button data-q="29">30 days</button></div>
            <span style="flex:1"></span>
            <a class="btn" id="rp-csv">${ic("download")} CSV</a>
            <a class="btn primary" id="rp-pdf">${ic("download")} PDF report</a>
          </div>
        </div>
      </div>
      <div class="grid g-4">${stat("rp-total", "Incidents in range", "alert", "amber")}${stat("rp-high", "High risk", "shield", "red")}${stat("rp-fa", "False alarms", "check", "green")}${stat("rp-ev", "With snapshots", "image", "cyan")}</div>
      <div class="card"><div class="card-head"><h3>Preview</h3><span class="spacer"></span><span class="sub" id="rp-sub"></span></div><div id="rp-table"></div></div>`;
    const sync = () => this.preview();
    $("#rp-start").addEventListener("change", sync);
    $("#rp-end").addEventListener("change", sync);
    $("#rp-quick").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      $$("#rp-quick button").forEach((x) => x.classList.toggle("on", x === b));
      $("#rp-start").value = iso(new Date(Date.now() - +b.dataset.q * 86400000)); $("#rp-end").value = iso(new Date());
      sync();
    });
    sync();
  },
  async preview() {
    const start = $("#rp-start").value, end = $("#rp-end").value;
    const qs = `start=${start}&end=${end}`;
    $("#rp-pdf").href = `/api/reports/pdf?${qs}`;
    $("#rp-csv").href = `/api/reports/csv?${qs}`;
    // fetch a day either side (browser and dashboard time zones may differ), then keep dashboard-local days
    const startTs = Date.parse(`${start}T00:00:00Z`) / 1000 - 86400, endTs = Date.parse(`${end}T23:59:59Z`) / 1000 + 86400;
    const current = loadGuard(this);
    const items = (await api(`/api/incidents?start=${startTs}&end=${endTs}&limit=5000`))
      .filter((i) => { const day = new Intl.DateTimeFormat("en-CA", { timeZone: tz() }).format(new Date(i.ts * 1000)); return day >= start && day <= end; });
    if (!$("#rp-table") || !current()) return;
    $("#rp-total").textContent = items.length;
    $("#rp-high").textContent = items.filter((i) => i.level === "HIGH").length;
    $("#rp-fa").textContent = items.filter((i) => i.status === "false_alarm").length;
    $("#rp-ev").textContent = items.filter((i) => i.snapshot).length;
    $("#rp-sub").textContent = `${items.length} row${items.length === 1 ? "" : "s"}`;
    $("#rp-table").innerHTML = items.length ? `<div style="overflow-x:auto"><table class="table"><thead><tr><th>#</th><th>Time</th><th>Level</th><th>Detection</th><th>Confidence</th><th>Status</th></tr></thead><tbody>
      ${items.slice(0, 100).map((i) => `<tr><td class="faint">${i.id}</td><td class="num">${fmtDateTime(i.ts)}</td><td>${levelBadge(i.level)}</td>
        <td style="text-transform:capitalize">${esc(i.label)}</td><td class="num">${i.confidence != null ? pct(i.confidence) : "—"}</td><td>${STATUS_LABEL[i.status]}</td></tr>`).join("")}
      </tbody></table></div>` : emptyState("file", "Nothing in this range", "The report will still generate, showing zero incidents.");
  },
};

/* ---------------------------------------------------------------- settings */
const QUICK_ZONES = [["India", "Asia/Kolkata"], ["Dubai", "Asia/Dubai"], ["London", "Europe/London"], ["New York", "America/New_York"],
  ["Los Angeles", "America/Los_Angeles"], ["Singapore", "Asia/Singapore"], ["Tokyo", "Asia/Tokyo"], ["Sydney", "Australia/Sydney"]];

PAGES.settings = {
  render(root) {
    const s = S.settings;
    const num = (key, label, hint, attrs = "") => `<div class="field"><label for="s-${key}">${label}</label><input class="input num" type="number" id="s-${key}" data-key="${key}" value="${s[key]}" ${attrs}>${hint ? `<div class="hint">${hint}</div>` : ""}</div>`;
    const range = (key, label, min, max, step, asPct, hint) => `<div class="field"><label for="s-${key}">${label}</label><div class="range-row"><input type="range" id="s-${key}" data-key="${key}" min="${min}" max="${max}" step="${step}" value="${s[key]}" data-pct="${asPct ? 1 : 0}"><output>${asPct ? pct(s[key]) : `${s[key]}%`}</output></div>${hint ? `<div class="hint">${hint}</div>` : ""}</div>`;
    const select = (key, label, options, hint) => `<div class="field"><label for="s-${key}">${label}</label><select class="input" id="s-${key}" data-key="${key}">${options.map(([v, l]) => `<option value="${v}" ${s[key] === v ? "selected" : ""}>${l}</option>`).join("")}</select>${hint ? `<div class="hint">${hint}</div>` : ""}</div>`;
    const zones = (Intl.supportedValuesOf ? Intl.supportedValuesOf("timeZone") : QUICK_ZONES.map((z) => z[1]));
    if (!zones.includes(s.time_zone)) zones.unshift(s.time_zone);
    const section = (icon, tone, title, sub, body) => `<div class="card"><div class="card-head"><span class="chip-icon ${tone}">${ic(icon)}</span><div><h2>${title}</h2><div class="sub">${sub}</div></div></div><div class="card-body">${body}</div></div>`;
    root.innerHTML = `
      ${section("clock", "cyan", "Clock & region", "Used for the clock, night hours, incident times and reports", `
        <div class="zone-grid" id="zone-grid">${QUICK_ZONES.map(([n, z]) => `<button class="zone ${s.time_zone === z ? "on" : ""}" data-zone="${z}"><div class="small muted">${n}</div><div class="t" data-zone-time="${z}">--:--</div></button>`).join("")}</div>
        <div class="field" style="margin-top:16px;max-width:360px"><label for="s-time_zone">Time zone</label><select class="input" id="s-time_zone" data-key="time_zone">${zones.map((z) => `<option ${z === s.time_zone ? "selected" : ""}>${z}</option>`).join("")}</select></div>`)}
      ${section("cpu", "", "Detection", "Which AI model runs, and how sure it must be before it counts something", `<div class="form-grid">
        <div class="field"><label for="s-model">People &amp; vehicle model</label><select class="input" id="s-model" data-key="model"><option value="${esc(s.model)}">${esc(s.model)}</option></select>
          <div class="hint" id="s-model-hint">Bigger models spot small objects like knives better but run slower.</div></div>
        ${range("confidence", "People & vehicle confidence", 0.05, 0.95, 0.05, true)}
        ${range("weapon_confidence", "Weapon confidence", 0.05, 0.95, 0.05, true, "Higher = fewer false alarms")}
        ${range("crime_confidence", "Crime confidence", 0.05, 0.95, 0.05, true, "Violence, fight, robbery. Higher = fewer false alarms")}
        ${num("detect_interval_ms", "Detection interval (ms)", "Lower = faster reaction, more CPU", 'min="50" max="2000" step="50"')}
        ${num("camera_index", "Camera number", "0 = built-in, 1+ = USB webcams", 'min="0" max="9"')}
        <div class="field"><label for="s-mirror">Mirror image</label><label class="toggle"><input type="checkbox" id="s-mirror" data-key="mirror" ${s.mirror ? "checked" : ""}><span></span></label></div>
        <div class="field"><label for="s-tamper_detection">Camera tamper detection</label><label class="toggle"><input type="checkbox" id="s-tamper_detection" data-key="tamper_detection" ${s.tamper_detection ? "checked" : ""}><span></span></label>
          <div class="hint">Alarm if the camera is covered, blurred or turned away</div></div>
        <div class="field"><label for="s-behaviour_analysis">Crime behaviour analysis</label><label class="toggle"><input type="checkbox" id="s-behaviour_analysis" data-key="behaviour_analysis" ${s.behaviour_analysis ? "checked" : ""}><span></span></label>
          <div class="hint">Body-pose cues: possible fight, person down, hands raised near someone, people running</div></div></div>`)}
      ${section("shield", "amber", "Risk rules", "When LOW turns into MEDIUM (HIGH is always a confirmed weapon)", `<div class="form-grid">
        ${num("crowd_threshold", "Crowd size", "People in view that count as a crowd", 'min="2" max="100"')}
        ${num("loiter_seconds", "Lingering after (seconds)", "Someone staying this long at night", 'min="5" max="3600"')}
        <div class="field"><label for="s-night_start">Night starts</label><input class="input" type="time" id="s-night_start" data-key="night_start" value="${s.night_start}"></div>
        <div class="field"><label for="s-night_end">Night ends</label><input class="input" type="time" id="s-night_end" data-key="night_end" value="${s.night_end}"></div>
        ${select("day_night_source", "Decide day/night from", [["auto", "LDR if connected, else clock"], ["clock", "Clock only"], ["ldr", "LDR sensor only"]])}
        ${num("ldr_dark_threshold", "LDR dark threshold", "0–4095; below this is night", 'min="0" max="4095"')}</div>`)}
      ${section("bulb", "green", "Lighting", "What the street light does at each risk level", `<div class="form-grid">${range("low_brightness", "Night brightness when quiet", 0, 100, 5, false, "MEDIUM and HIGH always use 100%")}
        <div class="field"><label for="s-strobe_on_high">Strobe the lamp on HIGH</label><label class="toggle"><input type="checkbox" id="s-strobe_on_high" data-key="strobe_on_high" ${s.strobe_on_high ? "checked" : ""}><span></span></label>
          <div class="hint">Flashing deters and draws attention</div></div>
        ${num("sos_hold_s", "SOS keeps HIGH for (s)", "Unless an operator clears it", 'min="10" max="600"')}
        ${select("voice_warnings", "Voice warning from the speaker", [["off", "Off"], ["high", "On HIGH"], ["medium", "On MEDIUM and HIGH"]], "Repeats every 30 s while risk stays raised")}
        <div class="field"><label for="s-voice_high">HIGH message</label><input class="input" id="s-voice_high" data-key="voice_high" maxlength="200" value="${esc(s.voice_high)}"></div>
        <div class="field"><label for="s-voice_medium">MEDIUM message</label><input class="input" id="s-voice_medium" data-key="voice_medium" maxlength="200" value="${esc(s.voice_medium)}"></div>
        <div class="field"><label for="s-voice_sos">SOS message</label><input class="input" id="s-voice_sos" data-key="voice_sos" maxlength="200" value="${esc(s.voice_sos)}"></div>
        <div class="field" style="justify-content:flex-end"><button class="btn" type="button" data-act="voice-test">${ic("volume")} Test voice</button></div>
        ${num("lamp_watts", "Lamp power (W)", "At 100 % brightness, for the energy report", 'min="1" max="2000"')}
        ${num("tariff_per_kwh", "Electricity price per kWh", "", 'min="0" max="1000" step="0.1"')}
        <div class="field"><label for="s-currency">Currency symbol</label><input class="input" id="s-currency" data-key="currency" maxlength="4" value="${esc(s.currency)}"></div>
        ${num("co2_kg_per_kwh", "Grid CO₂ (kg per kWh)", "India ≈ 0.71", 'min="0" max="3" step="0.01"')}</div>`)}
      ${section("bell", "red", "Alerts & evidence", "Messaging and how long records are kept", `<div class="form-grid">
        ${select("blur_faces", "Blur faces (privacy)", [["off", "Off"], ["live", "On the operator's screen only (evidence keeps faces)"], ["everywhere", "Everywhere, including snapshots and clips"]], "Pixelates faces of everyone in view")}
        ${select("alert_mode", "When risk is HIGH", [["manual", "Operator confirms before sending"], ["auto", "Send automatically"]])}
        ${num("alert_cooldown_s", "Auto-alert cooldown (s)", "Minimum gap between automatic alerts", 'min="0" max="3600"')}
        ${num("escalate_after_min", "Escalate after (min)", "Unconfirmed HIGH alerts are sent automatically; 0 = never", 'min="0" max="240"')}
        ${num("incident_cooldown_s", "Incident cooldown (s)", "Same-level incidents closer than this are merged", 'min="5" max="3600"')}
        ${num("evidence_retention_days", "Keep evidence for (days)", "Older incidents, snapshots and clips are deleted", 'min="1" max="365"')}
        <div class="field"><label for="s-record_clips">Record video clips</label><label class="toggle"><input type="checkbox" id="s-record_clips" data-key="record_clips" ${s.record_clips ? "checked" : ""}><span></span></label>
          <div class="hint">About 10 s around each incident: 5 s before, 5 s after</div></div></div>`)}
      <div class="card card-pad row" style="position:sticky;bottom:16px;z-index:5">
        <span class="muted" id="s-dirty">All changes saved</span><span style="flex:1"></span>
        <button class="btn" id="s-reset">Reset</button><button class="btn primary" id="s-save" disabled>${ic("save")} Save settings</button>
      </div>`;
    const markDirty = () => { $("#s-save").disabled = false; $("#s-dirty").textContent = "Unsaved changes"; };
    root.addEventListener("input", (e) => {
      const el = e.target;
      if (!el.dataset.key) return;
      if (el.type === "range") el.nextElementSibling.textContent = el.dataset.pct === "1" ? pct(+el.value) : `${el.value}%`;
      markDirty();
    });
    root.addEventListener("change", (e) => { if (e.target.dataset.key) markDirty(); });
    $("#zone-grid").addEventListener("click", (e) => {
      const b = e.target.closest("[data-zone]"); if (!b) return;
      $("#s-time_zone").value = b.dataset.zone;
      $$("#zone-grid .zone").forEach((x) => x.classList.toggle("on", x === b));
      markDirty();
    });
    $("#s-reset").addEventListener("click", () => route());
    $("#s-save").addEventListener("click", (e) => busy(e.currentTarget, async () => {
      const values = {};
      $$("[data-key]", root).forEach((el) => {
        values[el.dataset.key] = el.type === "checkbox" ? el.checked : (el.type === "number" || el.type === "range") ? +el.value : el.value;
      });
      S.settings = await api("/api/settings", { method: "PUT", body: values });
      toast("Settings saved");
      $("#s-dirty").textContent = "All changes saved";
      tickClock();
    }).then(() => { if ($("#s-save")) $("#s-save").disabled = true; }));
    api("/api/models", { quiet: true }).then(({ models, always_on: alwaysOn }) => {
      const sel = $("#s-model");
      if (!sel) return;
      sel.innerHTML = models.map((m) => `<option value="${m.id}" ${m.id === s.model ? "selected" : ""}>${esc(m.label)}</option>`).join("");
      if (alwaysOn.length) $("#s-model-hint").textContent = `People & vehicles. Always running with it: ${alwaysOn.join(", ")}`;
    }).catch(() => {});
    const tickZones = () => $$("[data-zone-time]").forEach((el) => {
      el.textContent = new Intl.DateTimeFormat("en-IN", { timeZone: el.dataset.zoneTime, hour: "2-digit", minute: "2-digit", hour12: true }).format(new Date());
    });
    tickZones();
    const timer = setInterval(tickZones, 15000);
    S.cleanup.push(() => clearInterval(timer));
  },
};

/* ------------------------------------------------------------------ router */
function teardown() {
  S.cleanup.forEach((fn) => fn());
  S.cleanup = [];
  S.charts.forEach((c) => c.destroy());
  S.charts = [];
  if (S.map) { S.map.remove(); S.map = null; }
  closeModal();
}

function route() {
  const id = location.hash.slice(1);
  const page = PAGES[id] ? id : "overview";
  teardown();
  S.page = page;
  const meta = NAV.find((n) => n.id === page);
  $("#page-title").textContent = meta.label;
  $("#page-sub").textContent = meta.sub;
  document.title = `${meta.label} · Sentinel Street`;
  renderNav();
  const root = $("#page");
  const fresh = root.cloneNode(false); // drop listeners from the previous page
  root.replaceWith(fresh);
  PAGES[page].render(fresh);
  if (S.live && PAGES[page].update) PAGES[page].update(S.live);
  $("#sidebar").classList.remove("open");
  $("#scrim").classList.remove("show");
  window.scrollTo(0, 0);
}

document.addEventListener("click", (e) => {
  const act = e.target.closest("[data-act]");
  if (act && ACTIONS[act.dataset.act]) { e.preventDefault(); ACTIONS[act.dataset.act](act); return; }
  const theme = e.target.closest("[data-theme-set]");
  if (theme) setTheme(theme.dataset.themeSet);
});
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
  const card = e.target.closest && e.target.closest("[data-incident]");
  if (card && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); card.click(); }
  if (e.key === "Tab" && !$("#modal").hidden) { // keep focus inside the open dialog
    const items = $$("#modal button, #modal textarea, #modal a[href], #modal input").filter((el) => !el.disabled);
    if (!items.length) return;
    const [first, last] = [items[0], items[items.length - 1]];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
});
$("#menu-btn").addEventListener("click", () => { $("#sidebar").classList.add("open"); $("#scrim").classList.add("show"); });
$("#scrim").addEventListener("click", () => { $("#sidebar").classList.remove("open"); $("#scrim").classList.remove("show"); });
window.addEventListener("hashchange", route);

(async function boot() {
  S.settings = await api("/api/settings");
  route();
  tickClock();
  setInterval(tickClock, 1000);
  connectLive();
})();
