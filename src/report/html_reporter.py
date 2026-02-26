"""Generate a self-contained HTML report (no CDN dependencies)."""

from __future__ import annotations

import html
import json
from pathlib import Path
import sys


# ── helpers ──────────────────────────────────────────────────────────────────

def _esc(v) -> str:
    return html.escape(str(v) if v is not None else "")


def _badge(severity: str) -> str:
    colors = {
        "critical": ("#7f1d1d", "#fca5a5"),
        "high":     ("#7c2d12", "#fdba74"),
        "medium":   ("#713f12", "#fde68a"),
        "low":      ("#14532d", "#86efac"),
    }
    bg, fg = colors.get(severity.lower(), ("#374151", "#d1d5db"))
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;'
        f'border-radius:9999px;font-size:0.75rem;font-weight:700;'
        f'text-transform:uppercase">{_esc(severity)}</span>'
    )


def _risk_badge(level: str, score: int) -> str:
    colors = {
        "critical": ("#7f1d1d", "#fca5a5"),
        "high":     ("#7c2d12", "#fdba74"),
        "medium":   ("#713f12", "#fde68a"),
        "low":      ("#14532d", "#86efac"),
    }
    bg, fg = colors.get(level.lower(), ("#374151", "#d1d5db"))
    return (
        f'<span style="background:{bg};color:{fg};padding:4px 14px;'
        f'border-radius:9999px;font-size:1rem;font-weight:700;'
        f'text-transform:uppercase">{_esc(level)} ({score}/100)</span>'
    )


def _kv_table(rows: list[tuple]) -> str:
    lines = ['<table class="kv">']
    for k, v in rows:
        lines.append(
            f"<tr><th>{_esc(k)}</th>"
            f"<td>{_esc(v) if v is not None else '<em>N/A</em>'}</td></tr>"
        )
    lines.append("</table>")
    return "\n".join(lines)


def _section(title: str, content: str, sid: str = "") -> str:
    sid = sid or title.lower().replace(" ", "-")
    return f"""
<details class="section" open>
  <summary class="section-title" id="{_esc(sid)}">{_esc(title)}</summary>
  <div class="section-body">
{content}
  </div>
</details>
"""


def _progress_bar(pct: float | None) -> str:
    if pct is None:
        return "<em>N/A</em>"
    pct = float(pct)
    color = "#ef4444" if pct > 95 else "#f97316" if pct > 90 else "#22c55e"
    return (
        f'<div style="background:#374151;border-radius:4px;height:14px;width:200px;display:inline-block;vertical-align:middle">'
        f'<div style="background:{color};width:{min(pct,100):.1f}%;height:100%;border-radius:4px"></div></div>'
        f' <span style="font-size:.85rem">{pct:.1f}%</span>'
    )


# ── section renderers ─────────────────────────────────────────────────────────

def _render_findings(findings: list) -> str:
    if not findings:
        return "<p style='color:#86efac'>No findings detected.</p>"
    rows = ["<table>",
            "<thead><tr><th>ID</th><th>Severity</th><th>Title</th><th>Detail</th></tr></thead>",
            "<tbody>"]
    for f in findings:
        rows.append(
            f"<tr>"
            f"<td><code>{_esc(f.get('id',''))}</code></td>"
            f"<td>{_badge(f.get('severity',''))}</td>"
            f"<td>{_esc(f.get('title',''))}</td>"
            f"<td>{_esc(f.get('detail',''))}</td>"
            f"</tr>"
        )
    rows += ["</tbody></table>"]
    return "\n".join(rows)


def _render_device_identity(di: dict) -> str:
    rows = [
        ("Hostname",        di.get("hostname")),
        ("FQDN",            di.get("fqdn")),
        ("Domain",          di.get("domain")),
        ("Workgroup",       di.get("workgroup")),
        ("Machine ID",      di.get("os_machine_id")),
        ("Azure AD Device", di.get("azure_ad_device_id")),
        ("Primary MACs",    ", ".join(di.get("primary_macs") or [])),
    ]
    return _kv_table(rows)


def _render_hardware(hw: dict) -> str:
    out = []
    cpu = hw.get("cpu") or {}
    ram = hw.get("ram") or {}
    mobo = hw.get("motherboard") or {}
    bios = hw.get("bios") or {}
    gpu_list = hw.get("gpu") or []

    out.append("<h3>CPU</h3>")
    out.append(_kv_table([
        ("Physical Cores",        cpu.get("physical_cores")),
        ("Logical Cores",         cpu.get("logical_cores")),
        ("Max Frequency (MHz)",   cpu.get("max_frequency_mhz")),
        ("Current Freq (MHz)",    cpu.get("current_frequency_mhz")),
        ("Usage %",               cpu.get("usage_percent")),
    ]))

    out.append("<h3>RAM</h3>")
    out.append(_kv_table([
        ("Total (GB)",     ram.get("total_gb")),
        ("Used (GB)",      ram.get("used_gb")),
        ("Available (GB)", ram.get("available_gb")),
        ("Used %",         ram.get("percent_used")),
    ]))

    if gpu_list:
        out.append("<h3>GPU</h3><table><thead><tr><th>Name</th><th>Driver</th><th>VRAM (MB)</th></tr></thead><tbody>")
        for g in gpu_list:
            out.append(
                f"<tr><td>{_esc(g.get('name'))}</td>"
                f"<td>{_esc(g.get('driver_version'))}</td>"
                f"<td>{_esc(g.get('vram_mb'))}</td></tr>"
            )
        out.append("</tbody></table>")

    out.append("<h3>Motherboard</h3>")
    out.append(_kv_table([
        ("Manufacturer", mobo.get("manufacturer")),
        ("Product",      mobo.get("product")),
        ("Serial",       mobo.get("serial")),
    ]))

    out.append("<h3>BIOS</h3>")
    out.append(_kv_table([
        ("Manufacturer",  bios.get("manufacturer")),
        ("Version",       bios.get("version")),
        ("Release Date",  bios.get("release_date")),
    ]))

    return "\n".join(out)


def _render_storage(storage: list) -> str:
    if not storage:
        return "<em>No storage data.</em>"
    rows = [
        "<table>",
        "<thead><tr><th>Device</th><th>Mount</th><th>FS</th>"
        "<th>Total (GB)</th><th>Used (GB)</th><th>Free (GB)</th>"
        "<th>Usage</th><th>Status</th></tr></thead>",
        "<tbody>",
    ]
    for d in storage:
        rows.append(
            f"<tr>"
            f"<td>{_esc(d.get('device'))}</td>"
            f"<td>{_esc(d.get('mountpoint'))}</td>"
            f"<td>{_esc(d.get('fstype'))}</td>"
            f"<td>{_esc(d.get('total_gb'))}</td>"
            f"<td>{_esc(d.get('used_gb'))}</td>"
            f"<td>{_esc(d.get('free_gb'))}</td>"
            f"<td>{_progress_bar(d.get('percent_used'))}</td>"
            f"<td>{_esc(d.get('status',''))}</td>"
            f"</tr>"
        )
    rows += ["</tbody></table>"]
    return "\n".join(rows)


def _render_network(net: dict) -> str:
    out = []
    ifaces = net.get("interfaces") or []
    if ifaces:
        out.append(
            "<table><thead><tr>"
            "<th>Interface</th><th>MAC</th><th>IPs</th><th>IPv6</th>"
            "<th>Up</th><th>Speed (Mbps)</th>"
            "</tr></thead><tbody>"
        )
        for iface in ifaces:
            up_icon = "Yes" if iface.get("is_up") else "No"
            out.append(
                f"<tr>"
                f"<td>{_esc(iface.get('name'))}</td>"
                f"<td><code>{_esc(iface.get('mac_address'))}</code></td>"
                f"<td>{_esc(', '.join(iface.get('ip_addresses') or []))}</td>"
                f"<td>{_esc(', '.join((iface.get('ipv6_addresses') or [])[:2]))}</td>"
                f"<td>{up_icon}</td>"
                f"<td>{_esc(iface.get('speed_mbps'))}</td>"
                f"</tr>"
            )
        out.append("</tbody></table>")

    dns = net.get("dns_servers") or []
    gw = net.get("default_gateway")
    out.append(_kv_table([
        ("DNS Servers",      ", ".join(dns) if dns else None),
        ("Default Gateway",  gw),
    ]))
    return "\n".join(out)


def _render_software(sw: dict) -> str:
    items = sw.get("installed") or []
    count = sw.get("count", len(items))
    if not items:
        return "<em>No software data.</em>"

    out = [
        f"<p><strong>{count} installed package(s)</strong></p>",
        '<input type="text" id="sw-search" placeholder="Filter software..." '
        'style="padding:6px 10px;border-radius:4px;border:1px solid #4b5563;'
        'background:#1f2937;color:#f3f4f6;width:300px;margin-bottom:8px" '
        'oninput="filterSoftware(this.value)">',
        '<table id="sw-table">',
        "<thead><tr><th>Name</th><th>Version</th><th>Publisher</th><th>Installed</th></tr></thead>",
        "<tbody>",
    ]
    for item in items:
        out.append(
            f'<tr class="sw-row">'
            f"<td>{_esc(item.get('name'))}</td>"
            f"<td>{_esc(item.get('version'))}</td>"
            f"<td>{_esc(item.get('publisher'))}</td>"
            f"<td>{_esc(item.get('install_date'))}</td>"
            f"</tr>"
        )
    out += ["</tbody></table>"]
    return "\n".join(out)


def _render_security(sec: dict) -> str:
    out = []

    av_list = sec.get("antivirus") or []
    out.append("<h3>Antivirus</h3>")
    if av_list:
        out.append(
            "<table><thead><tr><th>Name</th><th>Enabled</th>"
            "<th>Up to Date</th><th>Product State</th></tr></thead><tbody>"
        )
        for av in av_list:
            enabled_str = "Yes" if av.get("enabled") else "No"
            utd_str = "Yes" if av.get("up_to_date") else "No"
            out.append(
                f"<tr>"
                f"<td>{_esc(av.get('name'))}</td>"
                f"<td>{enabled_str}</td>"
                f"<td>{utd_str}</td>"
                f"<td>{_esc(av.get('product_state'))}</td>"
                f"</tr>"
            )
        out.append("</tbody></table>")
    else:
        out.append('<p style="color:#fca5a5">No antivirus products detected.</p>')

    fw = sec.get("firewall") or {}
    out.append("<h3>Firewall</h3>")
    out.append(_kv_table([
        ("Domain Profile",  "Enabled" if fw.get("domain_enabled") else ("Disabled" if fw.get("domain_enabled") is False else "Unknown")),
        ("Private Profile", "Enabled" if fw.get("private_enabled") else ("Disabled" if fw.get("private_enabled") is False else "Unknown")),
        ("Public Profile",  "Enabled" if fw.get("public_enabled") else ("Disabled" if fw.get("public_enabled") is False else "Unknown")),
    ]))

    enc = sec.get("encryption") or {}
    out.append("<h3>Encryption</h3>")
    bl = enc.get("bitlocker_volumes") or []
    fv = enc.get("filevault_enabled")
    if bl:
        out.append(
            "<table><thead><tr><th>Volume</th><th>Volume Status</th>"
            "<th>Protection Status</th></tr></thead><tbody>"
        )
        for v in bl:
            ps = v.get("protection_status")
            ps_str = "On" if ps == 1 else ("Off" if ps == 0 else str(ps))
            out.append(
                f"<tr>"
                f"<td>{_esc(v.get('mount_point'))}</td>"
                f"<td>{_esc(v.get('volume_status'))}</td>"
                f"<td>{ps_str}</td>"
                f"</tr>"
            )
        out.append("</tbody></table>")
    elif fv is not None:
        out.append(_kv_table([("FileVault", "Enabled" if fv else "Disabled")]))
    else:
        out.append("<em>No encryption data available.</em>")

    defender = sec.get("windows_defender") or {}
    if defender:
        out.append("<h3>Windows Defender</h3>")
        out.append(_kv_table([
            ("Service Enabled",          defender.get("enabled")),
            ("Real-Time Protection",     defender.get("real_time_protection")),
            ("Signatures Last Updated",  defender.get("signatures_last_updated")),
        ]))

    out.append("<h3>Other</h3>")
    out.append(_kv_table([
        ("UAC Enabled",         sec.get("uac_enabled")),
        ("Secure Boot",         sec.get("secure_boot_enabled")),
        ("Gatekeeper (macOS)",  sec.get("gatekeeper_enabled")),
        ("SIP (macOS)",         sec.get("sip_enabled")),
    ]))

    return "\n".join(out)


def _render_logs(logs: dict) -> str:
    out = []
    for key, label in [
        ("recent_errors",   "Recent Errors"),
        ("recent_warnings", "Recent Warnings"),
        ("failed_logins",   "Failed Login Attempts"),
    ]:
        entries = logs.get(key) or []
        out.append(f"<h3>{label} ({len(entries)})</h3>")
        if not entries:
            out.append("<p><em>None.</em></p>")
            continue
        out.append(
            "<table><thead><tr><th>Time</th><th>Event ID</th>"
            "<th>Source</th><th>Message</th></tr></thead><tbody>"
        )
        for e in entries:
            out.append(
                f"<tr>"
                f"<td style='white-space:nowrap'>{_esc(e.get('time'))}</td>"
                f"<td>{_esc(e.get('event_id'))}</td>"
                f"<td>{_esc(e.get('source'))}</td>"
                f"<td style='max-width:500px;word-break:break-word'>{_esc(e.get('message'))}</td>"
                f"</tr>"
            )
        out.append("</tbody></table>")
    return "\n".join(out)


def _render_errors(errors: list) -> str:
    if not errors:
        return "<p><em>No collection errors.</em></p>"
    items = "".join(f"<li><code>{_esc(e)}</code></li>" for e in errors)
    return f'<ul style="color:#fca5a5">{items}</ul>'


# ── main builder ──────────────────────────────────────────────────────────────

def write_html(report: dict, output_path: Path) -> None:
    """Render a self-contained HTML report and write to output_path."""
    r = report

    hostname = (r.get("device_identity") or {}).get("hostname") or (r.get("os") or {}).get("hostname", "Unknown")
    os_info = r.get("os") or {}
    os_name = (os_info.get("os") or {}).get("name", "")
    os_release = (os_info.get("os") or {}).get("release", "")
    os_label = f"{os_name} {os_release}".strip() or "Unknown OS"
    collected_at = r.get("collected_at", r.get("snapshot", {}).get("generated_at_utc", ""))
    risk = r.get("risk_score") or {}
    findings = r.get("findings") or []
    errors = r.get("errors") or []
    storage = r.get("storage") or []
    sw_count = (r.get("software") or {}).get("count", 0)
    uptime_hr = ((r.get("reboot") or {}).get("uptime") or {}).get("human_readable", "N/A")

    CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #111827; color: #f3f4f6; font-size: 14px; line-height: 1.5; }
a { color: #60a5fa; }
h3 { margin: 16px 0 8px; color: #93c5fd; font-size: 1rem; }
table { width: 100%; border-collapse: collapse; margin-bottom: 12px; }
th, td { padding: 6px 10px; border: 1px solid #374151; text-align: left; vertical-align: top; }
th { background: #1f2937; color: #9ca3af; font-weight: 600; font-size: .8rem; text-transform: uppercase; }
tr:nth-child(even) { background: #1a2332; }
code { background: #1f2937; padding: 1px 5px; border-radius: 3px; font-size: .9em; }
.header { background: linear-gradient(135deg,#1e3a5f,#0f2027);
          padding: 20px 24px; display: flex; align-items: center;
          justify-content: space-between; flex-wrap: wrap; gap: 12px;
          border-bottom: 2px solid #2563eb; }
.header h1 { font-size: 1.4rem; color: #93c5fd; }
.header .meta { font-size: .85rem; color: #9ca3af; }
.cards { display: flex; flex-wrap: wrap; gap: 12px; padding: 16px 24px; }
.card { background: #1f2937; border: 1px solid #374151; border-radius: 8px;
        padding: 14px 18px; min-width: 160px; flex: 1; }
.card .label { font-size: .75rem; color: #9ca3af; text-transform: uppercase; margin-bottom: 4px; }
.card .value { font-size: 1.4rem; font-weight: 700; color: #f3f4f6; }
.section { background: #1f2937; border: 1px solid #374151; border-radius: 8px;
           margin: 0 24px 16px; }
.section-title { cursor: pointer; padding: 12px 16px; font-size: 1rem;
                 font-weight: 600; color: #e5e7eb; list-style: none;
                 display: flex; align-items: center; gap: 8px; }
.section-title::before { content: '▶'; font-size: .7rem; color: #6b7280;
                          transition: transform .2s; }
details[open] .section-title::before { transform: rotate(90deg); }
.section-body { padding: 0 16px 16px; }
table.kv th { width: 200px; }
em { color: #6b7280; }
input[type=text]:focus { outline: 2px solid #3b82f6; }
"""

    JS = """
function filterSoftware(q) {
  q = q.toLowerCase();
  document.querySelectorAll('.sw-row').forEach(function(row) {
    row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
}
"""

    body_parts = []

    # Header
    body_parts.append(
        f'<div class="header">'
        f'<div><h1>IT Snapshot: {_esc(hostname)}</h1>'
        f'<div class="meta">{_esc(os_label)} &nbsp;|&nbsp; {_esc(collected_at)}</div></div>'
        f'<div>{_risk_badge(risk.get("level","low"), risk.get("score",0))}</div>'
        f'</div>'
    )

    # Summary cards
    body_parts.append('<div class="cards">')
    for label, value in [
        ("Uptime",      uptime_hr),
        ("Volumes",     len(storage)),
        ("Software",    sw_count),
        ("Findings",    len(findings)),
        ("Errors",      len(errors)),
    ]:
        body_parts.append(
            f'<div class="card"><div class="label">{label}</div>'
            f'<div class="value">{_esc(value)}</div></div>'
        )
    body_parts.append('</div>')

    # Sections
    body_parts.append(_section("Findings", _render_findings(findings)))
    body_parts.append(_section("Device Identity", _render_device_identity(r.get("device_identity") or {})))
    body_parts.append(_section("Hardware", _render_hardware(r.get("hardware") or {})))
    body_parts.append(_section("Storage", _render_storage(storage)))
    body_parts.append(_section("Network", _render_network(r.get("network") or {})))
    body_parts.append(_section("Software", _render_software(r.get("software") or {})))
    body_parts.append(_section("Security", _render_security(r.get("security") or {})))
    body_parts.append(_section("Logs", _render_logs(r.get("logs") or {})))
    body_parts.append(_section("Collection Errors", _render_errors(errors)))

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IT Snapshot - {_esc(hostname)}</title>
<style>{CSS}</style>
</head>
<body>
{"".join(body_parts)}
<script>{JS}</script>
</body>
</html>"""

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(page, encoding="utf-8")
    except OSError as exc:
        print(f"[error] Could not write HTML to '{output_path}': {exc}", file=sys.stderr)
        sys.exit(1)
