#!/usr/bin/env python3
"""
Genera il sito HTML statico (shell con JS rendering).

Le pagine HTML caricano i dati da docs/data/*.json via fetch() e li
renderizzano client-side. I dati vengono aggiornati separatamente da
generate_data.py, che deve essere eseguito ad ogni iterazione.

Questo script deve essere eseguito solo quando:
  - Il sito non esiste ancora (prima generazione)
  - La struttura HTML/CSS/JS cambia (raro)

Uso:
    python scripts/generate_site.py
    python scripts/generate_site.py --outdir docs
    python scripts/generate_site.py --force   # rigenera anche se gia' esiste
"""

import argparse
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write_file(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# CSS (shared)
# ---------------------------------------------------------------------------

CSS = """
:root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #232734;
    --border: #2d3142;
    --text: #e4e6ed;
    --text-muted: #8b8fa3;
    --accent: #6c8cff;
    --accent2: #4ecdc4;
    --green: #4ecdc4;
    --yellow: #ffd93d;
    --red: #ff6b6b;
    --orange: #ffa94d;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
}
nav {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 0 2rem;
    position: sticky;
    top: 0;
    z-index: 100;
    display: flex;
    align-items: center;
    gap: 2rem;
}
nav .logo {
    font-weight: 700; font-size: 1.25rem; color: var(--accent);
    padding: 1rem 0; white-space: nowrap; text-decoration: none;
}
nav .nav-links { display: flex; gap: 0; overflow-x: auto; }
nav a.nav-item {
    color: var(--text-muted); text-decoration: none;
    padding: 1rem 1.25rem; font-size: 0.9rem; font-weight: 500;
    border-bottom: 2px solid transparent; transition: all 0.2s; white-space: nowrap;
}
nav a.nav-item:hover { color: var(--text); }
nav a.nav-item.active { color: var(--accent); border-bottom-color: var(--accent); }
.content { padding: 2rem; max-width: 1400px; margin: 0 auto; width: 100%; }
.cards {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem; margin-bottom: 2rem;
}
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; }
.card .label { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem; }
.card .value { font-size: 2rem; font-weight: 700; color: var(--text); }
.card .value .unit { font-size: 0.9rem; color: var(--text-muted); font-weight: 400; }
.card .sub { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem; }
.card.accent { border-color: var(--accent); }
.card.green { border-color: var(--green); }
.table-wrap { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 1rem 0; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; min-width: 480px; }
th { background: var(--surface2); color: var(--text-muted); text-align: left; padding: 0.75rem 1rem; font-weight: 600; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.03em; border-bottom: 1px solid var(--border); }
td { padding: 0.6rem 1rem; border-bottom: 1px solid var(--border); }
tr:hover { background: var(--surface); }
tr.total-row { font-weight: 700; background: var(--surface2); }
.sub-nav { display: flex; gap: 0; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow-x: auto; margin-bottom: 1.5rem; }
.sub-nav-item { color: var(--text-muted); text-decoration: none; padding: 0.75rem 1.25rem; font-size: 0.85rem; font-weight: 500; white-space: nowrap; border-bottom: 2px solid transparent; transition: all 0.2s; cursor: pointer; }
.sub-nav-item:hover { color: var(--text); background: var(--surface2); }
.sub-nav-item.active { color: var(--accent); background: var(--surface2); border-bottom-color: var(--accent); }
.panel { display: none; }
.panel.active { display: block; }
.sub-nav-days { margin-top: -0.5rem; margin-bottom: 1.5rem; background: var(--surface2); border-color: var(--border); }
.sub-nav-days .sub-nav-item.active { background: var(--surface); }
.warmup-cooldown { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem 1.25rem; margin: 1rem 0; }
.warmup-cooldown h4 { font-size: 0.85rem; color: var(--accent2); text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 0.5rem; }
.warmup-cooldown ol { margin: 0 0 0 1.25rem; color: var(--text-muted); font-size: 0.9rem; }
.warmup-cooldown li { margin: 0.2rem 0; }
.day-nav { display: flex; justify-content: space-between; margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--border); }
.day-nav a { color: var(--accent); text-decoration: none; font-weight: 500; font-size: 0.9rem; padding: 0.5rem 1rem; border-radius: 6px; transition: background 0.2s; cursor: pointer; }
.day-nav a:hover { background: var(--surface2); }
.bar-chart { margin: 1.5rem 0; }
.bar-row { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; }
.bar-label { width: 160px; font-size: 0.85rem; text-align: right; color: var(--text-muted); flex-shrink: 0; }
.bar-track { flex: 1; height: 24px; background: var(--surface2); border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent2)); border-radius: 4px; transition: width 0.5s ease; }
.bar-value { width: 45px; font-size: 0.85rem; font-weight: 600; color: var(--text); }
.tag { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
.tag-primary { background: rgba(108,140,255,0.2); color: var(--accent); }
.tag-secondary { background: rgba(78,205,196,0.2); color: var(--green); }
.tag-tertiary { background: rgba(255,217,61,0.15); color: var(--yellow); }
details.muscle-detail { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 0.5rem; }
details.muscle-detail summary { padding: 0.75rem 1rem; cursor: pointer; font-weight: 600; font-size: 0.95rem; }
details.muscle-detail summary:hover { color: var(--accent); }
details.muscle-detail .detail-table { margin: 0; }
details.muscle-detail .detail-table td, details.muscle-detail .detail-table th { padding: 0.5rem 0.75rem; font-size: 0.85rem; }
.md-content h1 { font-size: 1.6rem; margin: 1.5rem 0 0.75rem; color: var(--accent); }
.md-content h2 { font-size: 1.3rem; margin: 1.5rem 0 0.75rem; color: var(--text); border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
.md-content h3 { font-size: 1.1rem; margin: 1.25rem 0 0.5rem; color: var(--text); }
.md-content h4 { font-size: 1rem; margin: 1rem 0 0.5rem; color: var(--accent2); }
.md-content p { margin: 0.5rem 0; color: var(--text-muted); }
.md-content ul { margin: 0.5rem 0 0.5rem 1.5rem; }
.md-content li { margin: 0.25rem 0; color: var(--text-muted); }
.md-content strong { color: var(--text); }
.md-content code { background: var(--surface2); padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.85em; color: var(--accent2); }
.md-content hr { border: none; border-top: 1px solid var(--border); margin: 1.5rem 0; }
.md-content .table-wrap { margin: 1rem 0; }
.md-content table { background: var(--surface); border-radius: 8px; overflow: hidden; }
.subtitle { color: var(--text-muted); font-size: 0.9rem; margin-bottom: 1rem; }
h2.page-title { font-size: 1.5rem; margin-bottom: 1.5rem; color: var(--text); }
.loading { color: var(--text-muted); padding: 2rem 0; }
@media (min-width: 1400px) { .content { max-width: 1600px; } .cards { grid-template-columns: repeat(4, 1fr); } }
@media (max-width: 768px) {
    nav { padding: 0 1rem; flex-direction: column; gap: 0; }
    nav .logo { padding: 0.75rem 0 0; }
    nav .nav-links { width: 100%; }
    nav a.nav-item { padding: 0.75rem 0.75rem; font-size: 0.8rem; }
    .content { padding: 1rem; }
    .cards { grid-template-columns: repeat(2, 1fr); }
    .card .value { font-size: 1.5rem; }
    .bar-label { width: 110px; font-size: 0.78rem; }
    table { font-size: 0.8rem; }
    td, th { padding: 0.4rem 0.5rem; }
}
@media (max-width: 480px) {
    nav { padding: 0 0.5rem; }
    nav a.nav-item { padding: 0.6rem 0.5rem; font-size: 0.75rem; }
    .content { padding: 0.75rem; }
    .cards { grid-template-columns: 1fr 1fr; gap: 0.5rem; }
    .card { padding: 1rem; }
    .card .value { font-size: 1.25rem; }
    h2.page-title { font-size: 1.2rem; margin-bottom: 1rem; }
    .bar-label { width: 80px; font-size: 0.7rem; }
    .sub-nav-item { padding: 0.6rem 0.75rem; font-size: 0.78rem; }
}
"""


# ---------------------------------------------------------------------------
# Base HTML wrapper
# ---------------------------------------------------------------------------

PAGES = [
    {"id": "dashboard", "label": "Dashboard"},
    {"id": "workout",   "label": "Scheda"},
    {"id": "volume",    "label": "Volume"},
    {"id": "diet",      "label": "Dieta"},
    {"id": "plan",      "label": "Piano"},
    {"id": "feedback",  "label": "Feedback"},
]


def build_nav(active_id: str) -> str:
    items = []
    for p in PAGES:
        cls = "nav-item active" if p["id"] == active_id else "nav-item"
        items.append(f'<a href="{p["id"]}.html" class="{cls}">{p["label"]}</a>')
    return "\n        ".join(items)


def page_html(title: str, active_id: str, body_script: str) -> str:
    nav = build_nav(active_id)
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — GYM</title>
<style>{CSS}</style>
</head>
<body>
<nav>
    <a href="dashboard.html" class="logo">GYM</a>
    <div class="nav-links">
        {nav}
    </div>
</nav>
<div class="content" id="main-content">
    <p class="loading">Caricamento...</p>
</div>
{body_script}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Shared JS utilities (injected in every page)
# ---------------------------------------------------------------------------

SHARED_JS = """
<script>
function esc(s) {
    if (s == null) return '&mdash;';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function card(label, value, unit, sub, extraCls) {
    var cls = 'card' + (extraCls ? ' ' + extraCls : '');
    var unitHtml = unit ? ' <span class="unit">' + esc(unit) + '</span>' : '';
    return '<div class="' + cls + '">'
        + '<div class="label">' + esc(label) + '</div>'
        + '<div class="value">' + esc(value) + unitHtml + '</div>'
        + '<div class="sub">' + sub + '</div>'
        + '</div>';
}
function showTab(navId, panelClass, tabId) {
    document.querySelectorAll('.' + panelClass).forEach(function(p) { p.classList.remove('active'); });
    document.querySelectorAll('#' + navId + ' .sub-nav-item').forEach(function(a) { a.classList.remove('active'); });
    var el = document.getElementById(tabId);
    if (el) el.classList.add('active');
}
function activateNavItem(navId, idx) {
    var items = document.querySelectorAll('#' + navId + ' .sub-nav-item');
    if (items[idx]) items[idx].classList.add('active');
}
</script>
"""


# ---------------------------------------------------------------------------
# Dashboard page
# ---------------------------------------------------------------------------

DASHBOARD_JS = SHARED_JS + """
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script>
Promise.all([
    fetch('data/measurements.json').then(function(r){ return r.json(); }),
    fetch('data/plan.json').then(function(r){ return r.json(); })
]).then(function(results){ renderDashboard(results[0], results[1]); })
    .catch(function(){ document.getElementById('main-content').innerHTML = '<p>Dati non disponibili.</p>'; });

function renderDashboard(measurements, planData) {
    var root = document.getElementById('main-content');
    if (!measurements || !measurements.length) {
        root.innerHTML = '<p>Nessun dato disponibile.</p>'; return;
    }
    var last = measurements[measurements.length - 1];
    var peso = last.peso_kg || '-';
    var bf = last.body_fat_pct ? last.body_fat_pct + '%' : '-';
    var sq = last.squat_1rm || 0;
    var pa = last.panca_1rm || 0;
    var st = last.stacco_1rm || 0;
    var total = (sq && pa && st) ? sq + pa + st : 0;
    var ffmi = last.ffmi_adj || '-';
    var tdee = last.tdee_kcal || 2871;

    var targets = {};
    if (planData && planData.target && planData.target.length > 0) {
        var target12 = planData.target[planData.target.length - 1];
        var corpTarget = planData.target_corporeo || { peso_kg: 95, bf_pct_max: 13 };
        targets = {
            peso: corpTarget.peso_kg || 95,
            bf: corpTarget.bf_pct_max || 13,
            squat: target12.squat || 200,
            panca: target12.panca || 150,
            stacco: target12.stacco || 250,
            totale: (target12.squat || 200) + (target12.panca || 150) + (target12.stacco || 250)
        };
    } else {
        targets = { peso: 95, bf: 13, squat: 200, panca: 150, stacco: 250, totale: 600 };
    }

    function progressBar(current, target) {
        var pct = Math.min(100, Math.max(0, (current / target * 100).toFixed(0)));
        return '<div style="background:var(--surface2);border-radius:4px;height:4px;margin-top:6px"><div style="background:var(--accent);height:100%;border-radius:4px;width:' + pct + '%"></div></div><div style="font-size:0.75rem;color:var(--text-muted);margin-top:3px">' + pct + '% del target</div>';
    }

    function progressBarBF(currentBF, targetBF, measurements) {
        // Per BF% la logica e' inversa: partiamo da alto e scendersi verso il target.
        // Caso generale: troviamo il BF massimo storico, da cui parti.
        if (!currentBF || !measurements || measurements.length === 0) return '';
        var maxBF = Math.max.apply(null, measurements.map(function(m) { return m.body_fat_pct || 0; }));
        if (maxBF < targetBF) maxBF = targetBF + 5; // fallback se tutte le misurazioni sono gia' sotto target
        // Calcolo: (max - current) / (max - target) * 100
        var pct = maxBF <= targetBF ? 100 : Math.min(100, Math.max(0, ((maxBF - currentBF) / (maxBF - targetBF) * 100).toFixed(0)));
        return '<div style="background:var(--surface2);border-radius:4px;height:4px;margin-top:6px"><div style="background:var(--accent);height:100%;border-radius:4px;width:' + pct + '%"></div></div><div style="font-size:0.75rem;color:var(--text-muted);margin-top:3px">' + pct + '% del target</div>';
    }

    var html = '<h2 class="page-title">Dashboard</h2>';
    html += '<div class="cards">';
    html += card('Peso', peso, 'kg', 'Target: ' + targets.peso + ' kg' + progressBar(last.peso_kg || 0, targets.peso), 'accent');
    html += card('Body Fat', bf, '', 'Target: &le;' + targets.bf + '%' + (last.body_fat_pct ? progressBarBF(last.body_fat_pct, targets.bf, measurements) : ''));
    html += card('Totale PL', total || '-', 'kg', 'Target: ' + targets.totale + ' kg' + progressBar(total || 0, targets.totale), 'green');
    html += card('FFMI adj', ffmi, '', 'Limite naturale ~25');
    html += '</div><div class="cards">';
    html += card('Squat', sq || '-', 'kg', 'Target: ' + targets.squat + ' kg' + progressBar(sq || 0, targets.squat));
    html += card('Panca', pa || '-', 'kg', 'Target: ' + targets.panca + ' kg' + progressBar(pa || 0, targets.panca));
    html += card('Stacco', st || '-', 'kg', 'Target: ' + targets.stacco + ' kg' + progressBar(st || 0, targets.stacco));
    html += card('Calorie target', tdee + 300, 'kcal', 'TDEE ' + tdee + ' + surplus 300');
    html += '</div>';

    // Chart
    html += '<h3 style="margin:1.5rem 0 .75rem">Andamento Massimali</h3>';
    html += '<div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1rem;">';
    html += '<canvas id="chart-massimali" height="110"></canvas></div>';

    // History table with delta info
    html += '<h3 style="margin:1.5rem 0 .75rem">Storico misurazioni</h3>';
    html += '<div class="table-wrap"><table><thead><tr>';
    ['Data','Peso','Δ Peso','BF%','Δ BF','Trend','Massa magra','FFMI adj','Squat','Panca','Stacco','Note'].forEach(function(h){
        html += '<th>' + h + '</th>';
    });
    html += '</tr></thead><tbody>';
    measurements.forEach(function(m) {
        var trendIcon = m.bf_trend === 'migliorante' ? '📈' : m.bf_trend === 'peggiorante' ? '📉' : '➡️';
        html += '<tr>'
            + '<td>' + esc(m.data) + '</td>'
            + '<td>' + esc(m.peso_kg) + '</td>'
            + '<td>' + (m.delta_peso_kg ? (m.delta_peso_kg > 0 ? '+' : '') + m.delta_peso_kg : '&mdash;') + '</td>'
            + '<td>' + (m.body_fat_pct ? m.body_fat_pct + '%' : '&mdash;') + '</td>'
            + '<td>' + (m.delta_bf_pct !== undefined && m.delta_bf_pct !== 0 ? (m.delta_bf_pct > 0 ? '+' : '') + m.delta_bf_pct + '%' : '&mdash;') + '</td>'
            + '<td>' + trendIcon + '</td>'
            + '<td>' + esc(m.massa_magra_kg) + '</td>'
            + '<td>' + esc(m.ffmi_adj) + '</td>'
            + '<td>' + esc(m.squat_1rm) + '</td>'
            + '<td>' + esc(m.panca_1rm) + '</td>'
            + '<td>' + esc(m.stacco_1rm) + '</td>'
            + '<td>' + esc(m.note) + '</td>'
            + '</tr>';
    });
    html += '</tbody></table></div>';
    root.innerHTML = html;

    // Init chart
    var labels = measurements.map(function(m) {
        var l = [m.data || ''];
        if (m.eta && m.peso_kg) l.push(m.eta + 'a / ' + m.peso_kg + 'kg');
        return l;
    });
    var sqData = measurements.map(function(m){ return m.squat_1rm || 0; });
    var paData = measurements.map(function(m){ return m.panca_1rm || 0; });
    var stData = measurements.map(function(m){ return m.stacco_1rm || 0; });
    var totData = measurements.map(function(m){ return (m.squat_1rm||0)+(m.panca_1rm||0)+(m.stacco_1rm||0); });
    var yMax = Math.max.apply(null, sqData.concat(paData, stData)) + 100;
    var y1Max = Math.max.apply(null, totData) + 100;

    new Chart(document.getElementById('chart-massimali').getContext('2d'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                { label: 'Squat', data: sqData, backgroundColor: 'rgba(108,140,255,0.7)', borderColor: 'rgba(108,140,255,1)', borderWidth: 1, borderRadius: 4, order: 2 },
                { label: 'Panca', data: paData, backgroundColor: 'rgba(78,205,196,0.7)', borderColor: 'rgba(78,205,196,1)', borderWidth: 1, borderRadius: 4, order: 2 },
                { label: 'Stacco', data: stData, backgroundColor: 'rgba(255,169,77,0.7)', borderColor: 'rgba(255,169,77,1)', borderWidth: 1, borderRadius: 4, order: 2 },
                { label: 'Totale', data: totData, type: 'line', borderColor: 'rgba(255,217,61,0.8)', backgroundColor: 'rgba(255,217,61,0.1)', borderWidth: 2, pointRadius: 4, fill: false, yAxisID: 'y1', order: 1 }
            ]
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { labels: { color: '#8b8fa3', font: { size: 12 } } },
                tooltip: { callbacks: { label: function(c){ return c.dataset.label + ': ' + c.parsed.y + ' kg'; } } }
            },
            datasets: { bar: { barPercentage: 0.6, categoryPercentage: 0.5 } },
            scales: {
                x: { ticks: { color: '#8b8fa3', font: { size: 11 }, maxRotation: 0 }, grid: { color: 'rgba(45,49,66,0.5)' } },
                y: { position: 'left', title: { display: true, text: 'Massimale (kg)', color: '#8b8fa3' }, ticks: { color: '#8b8fa3' }, grid: { color: 'rgba(45,49,66,0.5)' }, beginAtZero: true, max: yMax },
                y1: { position: 'right', title: { display: true, text: 'Totale (kg)', color: '#8b8fa3' }, ticks: { color: 'rgba(255,217,61,0.8)' }, grid: { drawOnChartArea: false }, beginAtZero: true, max: y1Max }
            }
        }
    });
}
</script>
"""


# ---------------------------------------------------------------------------
# Workout page
# ---------------------------------------------------------------------------

WORKOUT_JS = SHARED_JS + """
<script>
fetch('data/workout.json').then(function(r){ return r.json(); }).then(renderWorkout)
    .catch(function(){ document.getElementById('main-content').innerHTML = '<p>Dati non disponibili.</p>'; });

function renderWorkout(data) {
    var root = document.getElementById('main-content');
    var settimane = data.settimane || [];
    var meta = data.meta || {};
    var warmupItems = data.riscaldamento || [];
    var cooldownItems = data.defaticamento || [];

    function warmupHtml(items) {
        if (!items || !items.length) return '';
        return '<div class="warmup-cooldown"><h4>Riscaldamento generale (~10 min)</h4><ol>'
            + items.map(function(i){ return '<li>' + esc(i) + '</li>'; }).join('')
            + '</ol></div>';
    }
    function cooldownHtml(items) {
        if (!items || !items.length) return '';
        return '<div class="warmup-cooldown"><h4>Defaticamento (~5-10 min)</h4><ol>'
            + items.map(function(i){ return '<li>' + esc(i) + '</li>'; }).join('')
            + '</ol></div>';
    }
    function exerciseTable(esercizi) {
        var h = '<div class="table-wrap"><table><thead><tr><th>#</th><th>Esercizio</th><th>Serie x Reps</th><th>Peso / Intensita</th><th>Recupero</th><th>Gruppo</th></tr></thead><tbody>';
        esercizi.forEach(function(ex, i) {
            var nome = ex.principale ? '<strong>' + esc(ex.nome) + '</strong>' : esc(ex.nome);
            h += '<tr><td>' + (i+1) + '</td><td>' + nome + '</td>'
                + '<td>' + esc(ex.reps) + '</td><td>' + esc(ex.peso) + '</td>'
                + '<td>' + esc(ex.recupero) + '</td><td>' + esc(ex.gruppo) + '</td></tr>';
        });
        return h + '</tbody></table></div>';
    }
    function testDayHtml(giorno, wu, cd) {
        var h = wu;
        var isRPEVerifica = giorno.tipo && giorno.tipo.toLowerCase().indexOf('verifica') !== -1;
        if (isRPEVerifica) {
            h += '<div style="background:rgba(255,217,61,0.15); border:2px solid var(--yellow); border-radius:8px; padding:0.75rem 1rem; margin-bottom:1rem;"><strong style="color:var(--yellow)">SESSIONE VERIFICA RPE</strong><p style="margin:0.5rem 0 0;color:var(--text-muted);font-size:0.9rem">Usare i carichi della Settimana 1. Non incrementare i pesi in questa sessione.</p></div>';
        }
        h += '<h3>' + esc(giorno.giorno) + ': ' + esc(giorno.tipo) + '</h3>';
        if (giorno.note_sessione) h += '<p><em>' + esc(giorno.note_sessione) + '</em></p>';
        (giorno.protocolli || []).forEach(function(proto) {
            h += '<h4>Protocollo ' + esc(proto.nome) + ' (' + esc(proto.target) + ')</h4>';
            h += '<div class="table-wrap"><table><thead><tr><th>Set</th><th>Peso</th><th>Reps</th><th>Note</th></tr></thead><tbody>';
            (proto.serie || []).forEach(function(s) {
                if (s.tentativo) {
                    h += '<tr><td><strong>' + esc(s.set) + '</strong></td><td><strong>' + esc(s.peso) + '</strong></td>'
                        + '<td><strong>' + esc(s.reps) + '</strong></td><td>' + esc(s.note) + '</td></tr>';
                } else {
                    h += '<tr><td>' + esc(s.set) + '</td><td>' + esc(s.peso) + '</td>'
                        + '<td>' + esc(s.reps) + '</td><td>' + esc(s.note) + '</td></tr>';
                }
            });
            h += '</tbody></table></div>';
        });
        return h + cd;
    }

    var html = '<h2 class="page-title">Scheda di Allenamento &mdash; ' + esc(meta.periodo) + '</h2>';

    // Week tabs
    html += '<div class="sub-nav" id="week-nav">';
    html += '<a class="sub-nav-item active" onclick="switchWeek(\'info\', this)">Info</a>';
    settimane.forEach(function(s) {
        html += '<a class="sub-nav-item" onclick="switchWeek(\'sett' + s.numero + '\', this)">Settimana ' + s.numero + '</a>';
    });
    html += '</div>';

    // Info panel
    html += '<div id="panel-info" class="panel active">';
    html += '<h2>' + esc(meta.tipo_fase) + '</h2><ul>';
    html += '<li><strong>Periodo</strong>: ' + esc(meta.periodo) + '</li>';
    html += '<li><strong>Durata</strong>: ' + esc(meta.durata_settimane) + ' settimane</li>';
    html += '<li><strong>Frequenza</strong>: ' + esc(meta.frequenza_settimanale) + ' sessioni/settimana</li>';
    html += '<li><strong>Obiettivo</strong>: ' + esc(meta.obiettivo) + '</li>';
    html += '</ul>';
    if (data.note_generali && data.note_generali.length) {
        html += '<h3>Note generali</h3><ul>';
        data.note_generali.forEach(function(n){ html += '<li>' + esc(n) + '</li>'; });
        html += '</ul>';
    }
    html += '</div>';

    // Week panels
    settimane.forEach(function(sett) {
        var sid = 'sett' + sett.numero;
        var giorni = sett.giorni || [];
        html += '<div id="panel-' + sid + '" class="panel">';
        html += '<h2>Settimana ' + sett.numero + '</h2>';
        html += '<p><strong>Intensita target</strong>: ' + esc(sett.intensita_target) + '</p>';
        if (sett.note_settimana) html += '<p>' + esc(sett.note_settimana) + '</p>';

        if (giorni.length > 1) {
            html += '<div class="sub-nav sub-nav-days" id="day-nav-' + sid + '">';
            giorni.forEach(function(g, i) {
                var ac = i === 0 ? ' active' : '';
                html += '<a class="sub-nav-item' + ac + '" onclick="switchDay(\'' + sid + '\', ' + i + ', this)">' + esc(g.giorno) + '</a>';
            });
            html += '</div>';
        }

        giorni.forEach(function(giorno, i) {
            var ac = i === 0 ? ' active' : '';
            html += '<div id="day-' + sid + '-' + i + '" class="panel' + ac + '">';
            var wu = giorno.riscaldamento ? warmupHtml(giorno.riscaldamento) : warmupHtml(warmupItems);
            var cd = giorno.defaticamento ? cooldownHtml(giorno.defaticamento) : cooldownHtml(cooldownItems);
            if (giorno.protocolli && giorno.protocolli.length) {
                html += testDayHtml(giorno, wu, cd);
            } else {
                html += wu;
                var isRPEVerifica = giorno.tipo && giorno.tipo.toLowerCase().indexOf('verifica') !== -1;
                if (isRPEVerifica) {
                    html += '<div style="background:rgba(255,217,61,0.15); border:2px solid var(--yellow); border-radius:8px; padding:0.75rem 1rem; margin-bottom:1rem;"><strong style="color:var(--yellow)">SESSIONE VERIFICA RPE</strong><p style="margin:0.5rem 0 0;color:var(--text-muted);font-size:0.9rem">Usare i carichi della Settimana 1. Non incrementare i pesi in questa sessione.</p></div>';
                }
                html += '<h3>' + esc(giorno.giorno) + ': ' + esc(giorno.tipo) + '</h3>';
                if (giorno.note_sessione) html += '<p><em>' + esc(giorno.note_sessione) + '</em></p>';
                html += exerciseTable(giorno.esercizi || []);
                html += cd;
            }
            if (giorni.length > 1) {
                html += '<div class="day-nav">';
                if (i > 0) html += '<a onclick="switchDay(\'' + sid + '\', ' + (i-1) + ', null)">&larr; ' + esc(giorni[i-1].giorno) + '</a>';
                else html += '<span></span>';
                if (i < giorni.length - 1) html += '<a onclick="switchDay(\'' + sid + '\', ' + (i+1) + ', null)">' + esc(giorni[i+1].giorno) + ' &rarr;</a>';
                else html += '<span></span>';
                html += '</div>';
            }
            html += '</div>';
        });
        html += '</div>';
    });

    root.innerHTML = html;
}

function switchWeek(id, link) {
    document.querySelectorAll('[id^="panel-"]').forEach(function(p){ p.classList.remove('active'); });
    document.querySelectorAll('#week-nav .sub-nav-item').forEach(function(a){ a.classList.remove('active'); });
    var el = document.getElementById('panel-' + id);
    if (el) el.classList.add('active');
    if (link) link.classList.add('active');
}
function switchDay(sid, idx, link) {
    var prefix = 'day-' + sid + '-';
    document.querySelectorAll('[id^="' + prefix + '"]').forEach(function(p){ p.classList.remove('active'); });
    var nav = document.getElementById('day-nav-' + sid);
    if (nav) nav.querySelectorAll('.sub-nav-item').forEach(function(a){ a.classList.remove('active'); });
    var el = document.getElementById(prefix + idx);
    if (el) el.classList.add('active');
    if (link) { link.classList.add('active'); return; }
    if (nav) { var items = nav.querySelectorAll('.sub-nav-item'); if (items[idx]) items[idx].classList.add('active'); }
}
</script>
"""


# ---------------------------------------------------------------------------
# Volume page
# ---------------------------------------------------------------------------

VOLUME_JS = SHARED_JS + """
<script>
fetch('data/volume.json').then(function(r){ return r.json(); }).then(renderVolume)
    .catch(function(){ document.getElementById('main-content').innerHTML = '<p>Dati non disponibili.</p>'; });

function renderVolume(volumeData) {
    var root = document.getElementById('main-content');
    // Handle both old (array) and new (object with volumi/meta) structures
    var volumi = volumeData.volumi || volumeData;
    var meta = volumeData.meta || {};
    var items = (Array.isArray(volumi) ? volumi : []).filter(function(d){ return !d._unmatched; });
    var unmatched = (volumi.find ? volumi.find(function(d){ return d._unmatched; }) : null) || {};
    unmatched = unmatched._unmatched || [];
    var maxVal = items.length ? items[0].serie_pesate : 1;

    var html = '<h2 class="page-title">Volume per Distretto Muscolare</h2>';

    // Meta summary if available
    if (meta.total_serie_pesate !== undefined) {
        html += '<div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1.5rem;margin-bottom:1.5rem;">';
        html += '<h3 style="margin-bottom:1rem">Riepilogo equilibrio</h3>';
        html += '<div class="cards">';
        html += '<div class="card"><div class="label">Total Serie</div><div class="value">' + meta.total_serie_pesate + '</div></div>';
        html += '<div class="card"><div class="label">Push Serie</div><div class="value">' + meta.push_serie + '</div></div>';
        html += '<div class="card"><div class="label">Pull Serie</div><div class="value">' + meta.pull_serie + '</div></div>';
        html += '<div class="card"><div class="label">Ratio P/P</div><div class="value">' + meta.pull_push_ratio + '</div></div>';
        html += '</div>';
        html += '<p class="subtitle">Equilibrio: <strong>' + meta.balance_rating + '</strong></p>';
        html += '</div>';
    }

    html += '<h3>Serie pesate per distretto muscolare</h3>';
    html += '<p class="subtitle">Principale = 1.0 | Secondario = 0.5 | Terziario = 0.3</p>';
    html += '<div class="bar-chart">';
    items.forEach(function(m) {
        var pct = (m.serie_pesate / maxVal * 100).toFixed(0);
        html += '<div class="bar-row">'
            + '<span class="bar-label">' + esc(m.muscolo) + '</span>'
            + '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%"></div></div>'
            + '<span class="bar-value">' + m.serie_pesate + '</span>'
            + '</div>';
    });
    html += '</div>';
    html += '<h3>Dettaglio per distretto</h3>';
    items.forEach(function(m) {
        html += '<details class="muscle-detail"><summary>' + esc(m.muscolo) + ' &mdash; ' + m.serie_pesate + ' serie pesate</summary>';
        html += '<div class="table-wrap"><table class="detail-table"><thead><tr><th>Ruolo</th><th>Esercizio</th><th>Giorno</th><th>Serie</th><th>Peso</th><th>Contributo</th></tr></thead><tbody>';
        (m.dettaglio || []).forEach(function(d) {
            var tagMap = { principale: 'P', secondario: 'S', terziario: 'T' };
            var clsMap = { P: 'tag-primary', S: 'tag-secondary', T: 'tag-tertiary' };
            var tag = tagMap[d.ruolo] || d.ruolo;
            html += '<tr><td><span class="tag ' + clsMap[tag] + '">' + tag + '</span></td>'
                + '<td>' + esc(d.esercizio) + '</td><td>' + esc(d.giorno) + '</td>'
                + '<td>' + esc(d.serie) + '</td><td>' + esc(d.peso) + '</td><td>' + esc(d.contributo) + '</td></tr>';
        });
        html += '</tbody></table></div></details>';
    });
    if (unmatched.length) {
        html += '<p class="subtitle" style="margin-top:1rem">Esercizi non mappati: ' + unmatched.join(', ') + '</p>';
    }
    root.innerHTML = html;
}
</script>
"""


# ---------------------------------------------------------------------------
# Diet page
# ---------------------------------------------------------------------------

DIET_JS = SHARED_JS + """
<script>
fetch('data/diet.json').then(function(r){ return r.json(); }).then(renderDiet)
    .catch(function(){ document.getElementById('main-content').innerHTML = '<p>Dati non disponibili.</p>'; });

function renderDiet(data) {
    var root = document.getElementById('main-content');
    // Legacy HTML fallback
    if (data.html) {
        root.innerHTML = '<div class="md-content">' + data.html + '</div>';
        return;
    }
    var meta = data.meta || {};
    var giorni = data.giorni || [];
    var integratori = data.integratori || [];

    var html = '<h2 class="page-title">Dieta Settimanale</h2>';
    html += '<div class="cards">';
    if (meta.kcal_allenamento) html += card('Kcal Allenamento', meta.kcal_allenamento, 'kcal', 'P:' + meta.proteine_g + 'g C:' + (meta.carboidrati_g_allenamento || meta.carboidrati_g || 0) + 'g G:' + meta.grassi_g + 'g');
    if (meta.kcal_riposo) html += card('Kcal Riposo', meta.kcal_riposo, 'kcal', 'P:' + meta.proteine_g + 'g C:' + (meta.carboidrati_g_riposo || meta.carboidrati_g || 0) + 'g G:' + meta.grassi_g + 'g');
    if (meta.fase) html += card('Fase', meta.fase, '', (meta.note_strategia || '').substring(0, 60));
    html += '</div>';
    if (meta.note_strategia) html += '<p><em>' + esc(meta.note_strategia) + '</em></p>';

    // Tabs for giorni
    var tabIds = giorni.map(function(_, i){ return 'diet-' + i; });
    html += '<div class="sub-nav" id="diet-nav">';
    giorni.forEach(function(g, i) {
        html += '<a class="sub-nav-item' + (i===0?' active':'') + '" onclick="dietTab(' + i + ', this)">' + esc(g.nome) + '</a>';
    });
    if (integratori.length) html += '<a class="sub-nav-item" onclick="dietTab(' + giorni.length + ', this)">Integratori</a>';
    html += '</div>';

    giorni.forEach(function(giorno, i) {
        html += '<div id="diet-panel-' + i + '" class="panel' + (i===0?' active':'') + '">';
        html += '<p><strong>Tipo</strong>: ' + esc(giorno.tipo) + ' &mdash; <strong>Calorie</strong>: ' + esc(giorno.kcal) + ' kcal';
        var macros = giorno.macros || {};
        if (macros.proteine) html += ' &mdash; P: ' + macros.proteine + 'g C: ' + macros.carboidrati + 'g G: ' + macros.grassi + 'g';
        html += '</p>';
        (giorno.pasti || []).forEach(function(pasto) {
            var orario = pasto.orario ? ' (' + pasto.orario + ')' : '';
            html += '<h4>' + esc(pasto.nome) + orario + '</h4>';
            if (pasto.alimenti && pasto.alimenti.length) {
                html += '<div class="table-wrap"><table><thead><tr><th>Alimento</th><th>Grammi</th><th>Kcal</th><th>P (g)</th><th>C (g)</th><th>G (g)</th></tr></thead><tbody>';
                pasto.alimenti.forEach(function(a) {
                    html += '<tr><td>' + esc(a.nome) + '</td><td>' + esc(a.grammi) + '</td><td>' + esc(a.kcal) + '</td><td>' + esc(a.proteine) + '</td><td>' + esc(a.carbo) + '</td><td>' + esc(a.grassi) + '</td></tr>';
                });
                var tot = pasto.totale || {};
                if (tot.kcal) html += '<tr class="total-row"><td><strong>Totale</strong></td><td></td><td><strong>' + tot.kcal + '</strong></td><td><strong>' + tot.proteine + '</strong></td><td><strong>' + tot.carbo + '</strong></td><td><strong>' + tot.grassi + '</strong></td></tr>';
                html += '</tbody></table></div>';
            }
        });
        html += '</div>';
    });

    if (integratori.length) {
        html += '<div id="diet-panel-' + giorni.length + '" class="panel">';
        html += '<div class="table-wrap"><table><thead><tr><th>Integratore</th><th>Dose</th><th>Timing</th><th>Note</th></tr></thead><tbody>';
        integratori.forEach(function(ig) {
            html += '<tr><td>' + esc(ig.nome) + '</td><td>' + esc(ig.dose) + '</td><td>' + esc(ig.timing) + '</td><td>' + esc(ig.note) + '</td></tr>';
        });
        html += '</tbody></table></div></div>';
    }

    root.innerHTML = html;
}

function dietTab(idx, link) {
    document.querySelectorAll('[id^="diet-panel-"]').forEach(function(p){ p.classList.remove('active'); });
    document.querySelectorAll('#diet-nav .sub-nav-item').forEach(function(a){ a.classList.remove('active'); });
    var el = document.getElementById('diet-panel-' + idx);
    if (el) el.classList.add('active');
    if (link) link.classList.add('active');
}
</script>
"""


# ---------------------------------------------------------------------------
# Plan page
# ---------------------------------------------------------------------------

PLAN_JS = SHARED_JS + """
<script>
fetch('data/plan.json').then(function(r){ return r.json(); }).then(renderPlan)
    .catch(function(){ document.getElementById('main-content').innerHTML = '<p>Dati non disponibili.</p>'; });

function renderPlan(data) {
    var root = document.getElementById('main-content');
    if (data.html) {
        root.innerHTML = '<div class="md-content">' + data.html + '</div>';
        return;
    }
    var meta = data.meta || {};
    var situazione = data.situazione || {};
    var massimali = data.massimali_attuali || {};
    var targets = data.target || [];
    var fasi = data.fasi || [];
    var strategia = data.strategia_nutrizionale || {};
    var rischi = data.rischi || [];

    var tabs = [
        { id: 'panoramica', label: 'Panoramica' },
        { id: 'target', label: 'Target Massimali' },
        { id: 'fasi', label: 'Fasi' },
        { id: 'strategia', label: 'Strategia' },
        { id: 'rischi', label: 'Rischi' }
    ];

    var html = '<h2 class="page-title">Piano a Lungo Termine</h2>';
    html += '<div class="sub-nav" id="plan-nav">';
    tabs.forEach(function(t, i) {
        html += '<a class="sub-nav-item' + (i===0?' active':'') + '" onclick="planTab(\'' + t.id + '\', this)">' + t.label + '</a>';
    });
    html += '</div>';

    // Panoramica
    html += '<div id="plan-panoramica" class="panel active">';
    if (meta.atleta) html += '<p><strong>Atleta</strong>: ' + esc(meta.atleta) + ' &mdash; <strong>Aggiornato</strong>: ' + esc(meta.data_aggiornamento) + '</p>';
    if (situazione.infortunio) html += '<p><strong>Infortunio</strong>: ' + esc(situazione.infortunio) + '</p>';
    if (situazione.note) html += '<p>' + esc(situazione.note) + '</p>';
    if (massimali.squat || massimali.panca || massimali.stacco) {
        html += '<div class="cards">';
        html += card('Squat', massimali.squat || '-', 'kg', 'Massimale attuale');
        html += card('Panca', massimali.panca || '-', 'kg', 'Massimale attuale');
        html += card('Stacco', massimali.stacco || '-', 'kg', 'Massimale attuale');
        html += '</div>';
    }
    html += '</div>';

    // Target
    html += '<div id="plan-target" class="panel">';
    if (targets.length) {
        html += '<div class="table-wrap"><table><thead><tr><th>Orizzonte</th><th>Data</th><th>Squat</th><th>Panca</th><th>Stacco</th><th>Note</th></tr></thead><tbody>';
        targets.forEach(function(t) {
            html += '<tr><td>' + esc(t.orizzonte) + '</td><td>' + esc(t.data) + '</td><td>' + esc(t.squat) + '</td><td>' + esc(t.panca) + '</td><td>' + esc(t.stacco) + '</td><td>' + esc(t.note) + '</td></tr>';
        });
        html += '</tbody></table></div>';
    } else { html += '<p>Nessun target definito.</p>'; }
    html += '</div>';

    // Fasi
    html += '<div id="plan-fasi" class="panel">';
    fasi.forEach(function(fase) {
        html += '<h4>Fase ' + esc(fase.numero) + ': ' + esc(fase.nome) + '</h4><ul>';
        if (fase.durata_settimane) html += '<li><strong>Durata</strong>: ' + fase.durata_settimane + ' settimane</li>';
        if (fase.obiettivo) html += '<li><strong>Obiettivo</strong>: ' + esc(fase.obiettivo) + '</li>';
        if (fase.metodologia) html += '<li><strong>Metodologia</strong>: ' + esc(fase.metodologia) + '</li>';
        if (fase.note) html += '<li><strong>Note</strong>: ' + esc(fase.note) + '</li>';
        html += '</ul>';
    });
    html += '</div>';

    // Strategia
    html += '<div id="plan-strategia" class="panel"><ul>';
    Object.entries(strategia).forEach(function(e) {
        html += '<li><strong>' + esc(e[0].replace(/_/g,' ')) + '</strong>: ' + esc(e[1]) + '</li>';
    });
    html += '</ul></div>';

    // Rischi
    html += '<div id="plan-rischi" class="panel">';
    if (rischi.length) {
        html += '<div class="table-wrap"><table><thead><tr><th>Area</th><th>Livello</th><th>Azione</th></tr></thead><tbody>';
        rischi.forEach(function(r) {
            var clsMap = { alto: 'tag-primary', medio: 'tag-secondary', basso: 'tag-tertiary' };
            html += '<tr><td>' + esc(r.area) + '</td><td><span class="tag ' + (clsMap[r.livello]||'') + '">' + esc(r.livello) + '</span></td><td>' + esc(r.azione) + '</td></tr>';
        });
        html += '</tbody></table></div>';
    } else { html += '<p>Nessun rischio identificato.</p>'; }
    html += '</div>';

    root.innerHTML = html;
}

function planTab(id, link) {
    document.querySelectorAll('[id^="plan-"]').forEach(function(p){ if(p.classList.contains('panel')) p.classList.remove('active'); });
    document.querySelectorAll('#plan-nav .sub-nav-item').forEach(function(a){ a.classList.remove('active'); });
    var el = document.getElementById('plan-' + id);
    if (el) el.classList.add('active');
    if (link) link.classList.add('active');
}
</script>
"""


# ---------------------------------------------------------------------------
# Feedback page
# ---------------------------------------------------------------------------

FEEDBACK_JS = SHARED_JS + """
<script>
fetch('data/feedback.json').then(function(r){ return r.json(); }).then(renderFeedback)
    .catch(function(){ document.getElementById('main-content').innerHTML = '<p>Dati non disponibili.</p>'; });

function renderFeedback(data) {
    var root = document.getElementById('main-content');
    var html = data.html || '<p>Nessun feedback disponibile.</p>';
    root.innerHTML = '<div class="md-content">' + html + '</div>';
}
</script>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Genera HTML shell per il sito GYM")
    parser.add_argument("--outdir", default="docs", help="Directory di output (default: docs)")
    parser.add_argument("--force", action="store_true", help="Rigenera anche se i file esistono gia'")
    args = parser.parse_args()

    outdir = os.path.join(BASE_DIR, args.outdir)

    # Check se il sito esiste gia'
    dashboard_path = os.path.join(outdir, "dashboard.html")
    if os.path.exists(dashboard_path) and not args.force:
        print(f"Sito gia' presente in {args.outdir}/. Usa --force per rigenerare.")
        print("Per aggiornare i dati esegui: python scripts/generate_data.py")
        sys.exit(0)

    pages = [
        ("dashboard", "Dashboard", DASHBOARD_JS),
        ("workout",   "Scheda",    WORKOUT_JS),
        ("volume",    "Volume",    VOLUME_JS),
        ("diet",      "Dieta",     DIET_JS),
        ("plan",      "Piano",     PLAN_JS),
        ("feedback",  "Feedback",  FEEDBACK_JS),
    ]

    for page_id, title, script in pages:
        html = page_html(title, page_id, script)
        out_path = os.path.join(outdir, f"{page_id}.html")
        write_file(out_path, html)
        print(f"  {page_id}.html")

    # index redirect
    write_file(
        os.path.join(outdir, "index.html"),
        '<meta http-equiv="refresh" content="0;url=dashboard.html">'
    )
    print("  index.html")

    # Genera anche i dati
    print("\nGenerazione dati...")
    generate_data = os.path.join(BASE_DIR, "scripts", "generate_data.py")
    data_dir = os.path.join(args.outdir, "data")
    result = subprocess.run(
        [sys.executable, generate_data, "--outdir", data_dir],
        cwd=BASE_DIR
    )
    if result.returncode != 0:
        print("Errore nella generazione dei dati.")
        sys.exit(result.returncode)

    print(f"\nSito generato in: {args.outdir}/")


if __name__ == "__main__":
    main()
