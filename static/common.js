// Shared helpers for both portals.
const $ = (sel, root = document) => root.querySelector(sel);

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function ring(value, size = 116) {
  const r = size / 2 - 9, c = 2 * Math.PI * r, v = Math.max(0, Math.min(100, value));
  const color = v >= 70 ? "var(--good)" : v >= 45 ? "var(--warn)" : "var(--bad)";
  return `<svg class="ring" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="${v.toFixed(0)} percent">
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="var(--surface-2)" stroke-width="10"/>
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${color}" stroke-width="10" stroke-linecap="round"
      stroke-dasharray="${(c * v) / 100} ${c}" transform="rotate(-90 ${size / 2} ${size / 2})"/>
    <text x="50%" y="50%" text-anchor="middle" dominant-baseline="central" font-size="${size / 4.4}">${v.toFixed(0)}%</text></svg>`;
}

function chip(text, cls = "", extra = "") {
  return `<span class="chip ${cls}">${esc(text)}${extra ? ` <small>${esc(extra)}</small>` : ""}</span>`;
}

function verdict(score) {
  if (score >= 70) return "Strong match";
  if (score >= 45) return "Moderate match";
  return "Weak match";
}

async function postForm(url, form) {
  const res = await fetch(url, { method: "POST", body: new FormData(form) });
  const data = await res.json().catch(() => ({ error: "Server returned an invalid response." }));
  if (!res.ok || data.error) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

async function loadSample(name) {
  const res = await fetch(`/api/sample/${name}`);
  return (await res.json()).text;
}

function setBusy(on) {
  $("#loading").hidden = !on;
  const btn = $("form button[type=submit]");
  if (btn) btn.disabled = on;
}

function showError(msg) {
  const el = $("#form-error");
  el.textContent = msg || "";
  el.hidden = !msg;
}

fetch("/api/health").then(r => r.json()).then(d => {
  const b = $("#backend-badge");
  if (!b) return;
  if (d.backend === "sbert") { b.textContent = "model: SBERT MiniLM"; b.className = "badge good"; }
  else { b.textContent = "model: TF-IDF fallback"; b.className = "badge warn"; b.title = "sentence-transformers not available — install it for SBERT scoring"; }
}).catch(() => {});
