"""it-snapshot Inventory Server — FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .db import init_db
from .routers import devices, ingest


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="it-snapshot Inventory Server",
    description=(
        "Central inventory server that receives endpoint snapshots from "
        "it-snapshot agents and exposes them through a query API.\n\n"
        "**Authentication**: every request must include the `X-API-Key` header "
        "matching the `IT_SNAPSHOT_API_KEY` environment variable set on the server."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(ingest.router)
app.include_router(devices.router)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"], summary="Health check")
async def health() -> dict:
    return {"status": "ok"}


# ── Admin UI ──────────────────────────────────────────────────────────────────

_ADMIN_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>it-snapshot &mdash; Inventory Admin</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, -apple-system, sans-serif; background: #f4f6f9; color: #1a1a2e; }
  header { background: #16213e; color: #e2e8f0; padding: 1rem 2rem;
           display: flex; align-items: center; gap: 1rem; }
  header h1 { font-size: 1.25rem; font-weight: 600; }
  header span { font-size: 0.8rem; opacity: 0.6; }
  .toolbar { padding: 1rem 2rem; display: flex; gap: 0.75rem; align-items: center;
             background: #fff; border-bottom: 1px solid #e2e8f0; flex-wrap: wrap; }
  .toolbar label { font-size: 0.85rem; font-weight: 500; }
  .toolbar input { border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.4rem 0.75rem;
                   font-size: 0.85rem; width: 280px; font-family: monospace; }
  .toolbar button { background: #2563eb; color: #fff; border: none; border-radius: 6px;
                    padding: 0.45rem 1rem; font-size: 0.85rem; cursor: pointer; }
  .toolbar button:hover { background: #1d4ed8; }
  #status { font-size: 0.8rem; color: #64748b; }
  main { padding: 1.5rem 2rem; }
  .stats { display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
  .stat-card { background: #fff; border-radius: 10px; padding: 1rem 1.5rem;
               border: 1px solid #e2e8f0; min-width: 130px; }
  .stat-card .label { font-size: 0.72rem; color: #64748b; text-transform: uppercase;
                      letter-spacing: 0.05em; }
  .stat-card .value { font-size: 1.75rem; font-weight: 700; color: #16213e; }
  table { width: 100%; border-collapse: collapse; background: #fff;
          border-radius: 10px; overflow: hidden; border: 1px solid #e2e8f0; }
  th { background: #f8fafc; text-align: left; padding: 0.65rem 1rem;
       font-size: 0.78rem; color: #475569; text-transform: uppercase;
       letter-spacing: 0.05em; border-bottom: 1px solid #e2e8f0; }
  td { padding: 0.65rem 1rem; font-size: 0.88rem; border-bottom: 1px solid #f1f5f9; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #f8fafc; }
  .risk { display: inline-block; padding: 0.2rem 0.55rem; border-radius: 999px;
          font-size: 0.72rem; font-weight: 600; text-transform: uppercase; }
  .risk-low      { background: #d1fae5; color: #065f46; }
  .risk-medium   { background: #fef3c7; color: #92400e; }
  .risk-high     { background: #fee2e2; color: #991b1b; }
  .risk-critical { background: #7f1d1d; color: #fef2f2; }
  .btn-sm { background: none; border: 1px solid #cbd5e1; border-radius: 5px;
            padding: 0.2rem 0.6rem; font-size: 0.78rem; cursor: pointer; color: #2563eb; }
  .btn-sm:hover { background: #eff6ff; }
  /* Modal */
  .modal-bg { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.45);
              z-index: 100; align-items: flex-start; justify-content: center;
              padding: 4rem 1rem; overflow-y: auto; }
  .modal-bg.open { display: flex; }
  .modal { background: #fff; border-radius: 12px; width: 100%; max-width: 860px;
           padding: 1.5rem; position: relative; }
  .modal h2 { font-size: 1rem; font-weight: 600; margin-bottom: 1rem; color: #16213e; }
  .modal-close { position: absolute; top: 1rem; right: 1rem; background: none; border: none;
                 font-size: 1.25rem; cursor: pointer; color: #64748b; }
  pre { background: #0f172a; color: #e2e8f0; border-radius: 8px; padding: 1rem;
        font-size: 0.75rem; overflow: auto; max-height: 60vh; white-space: pre; }
  .empty { text-align: center; padding: 3rem; color: #94a3b8; font-size: 0.9rem; }
  #error-msg { color: #dc2626; font-size: 0.85rem; display: none; }
</style>
</head>
<body>

<header>
  <h1>it-snapshot &mdash; Inventory Admin</h1>
  <span>Central device inventory</span>
</header>

<div class="toolbar">
  <label for="apikey">API Key</label>
  <input id="apikey" type="password" placeholder="X-API-Key value" autocomplete="off" />
  <button onclick="loadDevices()">Refresh</button>
  <span id="status"></span>
  <span id="error-msg"></span>
</div>

<main>
  <div class="stats" id="stats"></div>
  <div id="table-wrap"></div>
</main>

<!-- Report modal -->
<div class="modal-bg" id="modal">
  <div class="modal">
    <button class="modal-close" onclick="closeModal()">&times;</button>
    <h2 id="modal-title">Latest report</h2>
    <pre id="modal-body"></pre>
  </div>
</div>

<script>
const $ = id => document.getElementById(id);

function getKey() {
  const k = $("apikey").value.trim();
  if (!k) { sessionStorage.removeItem("itkey"); return ""; }
  sessionStorage.setItem("itkey", k);
  return k;
}

// Restore key from session
if (sessionStorage.getItem("itkey")) $("apikey").value = sessionStorage.getItem("itkey");

function riskClass(score) {
  if (score >= 61) return "risk-critical";
  if (score >= 31) return "risk-high";
  if (score >= 11) return "risk-medium";
  return "risk-low";
}
function riskLabel(score) {
  if (score >= 61) return "critical";
  if (score >= 31) return "high";
  if (score >= 11) return "medium";
  return "low";
}

async function apiFetch(path) {
  const key = getKey();
  if (!key) { showError("Enter an API key first."); return null; }
  const res = await fetch(path, { headers: { "X-API-Key": key } });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    showError(`${res.status}: ${body.detail || res.statusText}`);
    return null;
  }
  clearError();
  return res.json();
}

function showError(msg) { $("error-msg").textContent = msg; $("error-msg").style.display = ""; }
function clearError()   { $("error-msg").style.display = "none"; }
function setStatus(msg) { $("status").textContent = msg; }

async function loadDevices() {
  setStatus("Loading…");
  const devices = await apiFetch("/devices");
  if (!devices) { setStatus(""); return; }

  // Stats
  const total    = devices.length;
  const critical = devices.filter(d => d.risk_score >= 61).length;
  const high     = devices.filter(d => d.risk_score >= 31 && d.risk_score < 61).length;
  $("stats").innerHTML = `
    <div class="stat-card"><div class="label">Devices</div><div class="value">${total}</div></div>
    <div class="stat-card"><div class="label">Critical risk</div><div class="value" style="color:#991b1b">${critical}</div></div>
    <div class="stat-card"><div class="label">High risk</div><div class="value" style="color:#b45309">${high}</div></div>
  `;

  if (!devices.length) {
    $("table-wrap").innerHTML = '<div class="empty">No devices have reported yet.</div>';
    setStatus(""); return;
  }

  $("table-wrap").innerHTML = `
  <table>
    <thead><tr>
      <th>ID</th><th>Hostname</th><th>Domain</th>
      <th>OS</th><th>Last Seen (UTC)</th><th>Risk</th><th></th>
    </tr></thead>
    <tbody>
    ${devices.map(d => `
      <tr>
        <td>${d.id}</td>
        <td><strong>${esc(d.hostname)}</strong></td>
        <td>${esc(d.domain) || '<span style="color:#94a3b8">—</span>'}</td>
        <td>${esc(d.os_name || '')} ${esc(d.os_version || '')}</td>
        <td>${esc(d.last_seen.replace("T", " ").replace("Z", "").slice(0,19))}</td>
        <td><span class="risk ${riskClass(d.risk_score)}">${riskLabel(d.risk_score)} (${d.risk_score})</span></td>
        <td><button class="btn-sm" onclick="showLatest(${d.id}, '${esc(d.hostname)}')">Latest report</button></td>
      </tr>`).join("")}
    </tbody>
  </table>`;
  setStatus(`Loaded ${total} device${total === 1 ? "" : "s"} · ` + new Date().toLocaleTimeString());
}

async function showLatest(deviceId, hostname) {
  $("modal-title").textContent = `Latest report — ${hostname}`;
  $("modal-body").textContent = "Loading…";
  $("modal").classList.add("open");
  const data = await apiFetch(`/devices/${deviceId}/latest`);
  if (data) {
    $("modal-body").textContent = JSON.stringify(data.raw, null, 2);
  } else {
    $("modal-body").textContent = "(failed to load)";
  }
}

function closeModal() { $("modal").classList.remove("open"); }
$("modal").addEventListener("click", e => { if (e.target === $("modal")) closeModal(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Auto-load if key is already set
if ($("apikey").value) loadDevices();
</script>
</body>
</html>
"""


@app.get(
    "/admin",
    response_class=HTMLResponse,
    include_in_schema=False,
    summary="Admin UI",
)
async def admin_ui() -> HTMLResponse:
    """Simple browser-based admin page.

    Enter your API key in the toolbar to load device data.
    The key is kept in ``sessionStorage`` for the duration of the browser tab.
    """
    return HTMLResponse(_ADMIN_HTML)
