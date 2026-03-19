#!/usr/bin/env python3
"""
Genera un sito HTML statico multi-pagina.

Legge frammenti HTML e dati JSON da data/output/, li assembla con il
template base da scripts/templates/base.html, e genera pagine separate
in data/output/site/.

La pagina workout viene generata interamente da workout_data.json.

Uso:
    python scripts/generate_site.py
    python scripts/generate_site.py --outdir data/output/site
"""

import argparse
import json
import os
import re
import sys
import glob as globmod
from html import escape

sys.path.insert(0, os.path.dirname(__file__))
from volume_calc import EXERCISE_MUSCLES


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_file(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def latest_file(directory: str, prefix: str, ext: str = ".html") -> str | None:
    """Trova il file piu' recente con il prefisso dato, cercando sia nella
    root di output che nelle sottocartelle history/YYYY/."""
    pattern_root = os.path.join(directory, f"{prefix}_*{ext}")
    pattern_history = os.path.join(directory, "history", "**", f"{prefix}_*{ext}")
    files = sorted(globmod.glob(pattern_root) + globmod.glob(pattern_history, recursive=True))
    return files[-1] if files else None


def esc(text) -> str:
    """Escape HTML but keep it readable."""
    return escape(str(text)) if text else "&mdash;"


# ---------------------------------------------------------------------------
# Template
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


def render_page(template: str, title: str, active_id: str, content: str) -> str:
    html = template.replace("{{title}}", title)
    html = html.replace("{{nav}}", build_nav(active_id))
    html = html.replace("{{content}}", content)
    return html


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def _card(label: str, value: str, unit: str, sub: str, extra_cls: str = "") -> str:
    cls = f" {extra_cls}" if extra_cls else ""
    unit_html = f' <span class="unit">{unit}</span>' if unit else ""
    return (
        f'<div class="card{cls}">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}{unit_html}</div>'
        f'<div class="sub">{sub}</div>'
        f'</div>\n'
    )


def build_dashboard(measurements: list[dict]) -> str:
    last = measurements[-1] if measurements else {}
    peso = last.get("peso_kg", "-")
    bf = last.get("body_fat_pct", "-")
    bf_str = f"{bf}%" if bf != "-" else "-"
    squat = last.get("squat_1rm", "-")
    panca = last.get("panca_1rm", "-")
    stacco = last.get("stacco_1rm", "-")
    ffmi_adj = last.get("ffmi_adj", "-")
    tdee = last.get("tdee_kcal", 2871)

    try:
        total = int(squat) + int(panca) + int(stacco)
    except (ValueError, TypeError):
        total = 0

    html = '<h2 class="page-title">Dashboard</h2>\n'
    html += '<div class="cards">\n'
    html += _card("Peso", str(peso), "kg", "Target: 95 kg", "accent")
    html += _card("Body Fat", bf_str, "", "Target: &le;13%")
    html += _card("Totale PL", str(total), "kg", "Target: 600 kg", "green")
    html += _card("FFMI adj", str(ffmi_adj), "", "Limite naturale ~25")
    html += '</div>\n<div class="cards">\n'
    html += _card("Squat", str(squat), "kg", "Target: 200 kg")
    html += _card("Panca", str(panca), "kg", "Target: 150 kg")
    html += _card("Stacco", str(stacco), "kg", "Target: 250 kg")
    html += _card("Calorie target", str(tdee + 300), "kcal", f"TDEE {tdee} + surplus 300")
    html += '</div>\n'

    if measurements:
        # --- Grafico massimali ---
        html += '<h3 style="margin:1.5rem 0 .75rem">Andamento Massimali</h3>\n'
        html += '<div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1rem;">\n'
        html += '  <canvas id="chart-massimali" height="110"></canvas>\n'
        html += '</div>\n'

        # Prepara dati per Chart.js
        labels = []
        squat_data = []
        panca_data = []
        stacco_data = []
        totale_data = []
        for m in measurements:
            data = m.get("data", "")
            eta = m.get("eta", "")
            peso_m = m.get("peso_kg", "")
            if eta and peso_m:
                label = [data, f"{eta}a / {peso_m}kg"]
            else:
                label = [data]
            labels.append(label)
            sq = m.get("squat_1rm") or 0
            pa = m.get("panca_1rm") or 0
            st = m.get("stacco_1rm") or 0
            squat_data.append(sq)
            panca_data.append(pa)
            stacco_data.append(st)
            totale_data.append(sq + pa + st)

        max_single = max(max(squat_data), max(panca_data), max(stacco_data))
        max_totale = max(totale_data)
        y_max = max_single + 100
        y1_max = max_totale + 100

        labels_js = json.dumps(labels)
        squat_js = json.dumps(squat_data)
        panca_js = json.dumps(panca_data)
        stacco_js = json.dumps(stacco_data)
        totale_js = json.dumps(totale_data)

        html += '<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>\n'
        html += f"""<script>
document.addEventListener('DOMContentLoaded', function() {{
    var ctx = document.getElementById('chart-massimali').getContext('2d');
    new Chart(ctx, {{
        type: 'bar',
        data: {{
            labels: {labels_js},
            datasets: [
                {{
                    label: 'Squat',
                    data: {squat_js},
                    backgroundColor: 'rgba(108,140,255,0.7)',
                    borderColor: 'rgba(108,140,255,1)',
                    borderWidth: 1,
                    borderRadius: 4,
                    order: 2
                }},
                {{
                    label: 'Panca',
                    data: {panca_js},
                    backgroundColor: 'rgba(78,205,196,0.7)',
                    borderColor: 'rgba(78,205,196,1)',
                    borderWidth: 1,
                    borderRadius: 4,
                    order: 2
                }},
                {{
                    label: 'Stacco',
                    data: {stacco_js},
                    backgroundColor: 'rgba(255,169,77,0.7)',
                    borderColor: 'rgba(255,169,77,1)',
                    borderWidth: 1,
                    borderRadius: 4,
                    order: 2
                }},
                {{
                    label: 'Totale',
                    data: {totale_js},
                    type: 'line',
                    borderColor: 'rgba(255,217,61,0.8)',
                    backgroundColor: 'rgba(255,217,61,0.1)',
                    borderWidth: 2,
                    pointRadius: 4,
                    pointBackgroundColor: 'rgba(255,217,61,1)',
                    fill: false,
                    yAxisID: 'y1',
                    order: 1
                }}
            ]
        }},
        options: {{
            responsive: true,
            interaction: {{ mode: 'index', intersect: false }},
            plugins: {{
                legend: {{
                    labels: {{ color: '#8b8fa3', font: {{ size: 12 }} }}
                }},
                tooltip: {{
                    callbacks: {{
                        label: function(ctx) {{ return ctx.dataset.label + ': ' + ctx.parsed.y + ' kg'; }}
                    }}
                }}
            }},
            datasets: {{
                bar: {{
                    barPercentage: 0.6,
                    categoryPercentage: 0.5
                }}
            }},
            scales: {{
                x: {{
                    ticks: {{
                        color: '#8b8fa3',
                        font: {{ size: 11 }},
                        maxRotation: 0
                    }},
                    grid: {{ color: 'rgba(45,49,66,0.5)' }}
                }},
                y: {{
                    position: 'left',
                    title: {{ display: true, text: 'Massimale (kg)', color: '#8b8fa3' }},
                    ticks: {{ color: '#8b8fa3' }},
                    grid: {{ color: 'rgba(45,49,66,0.5)' }},
                    beginAtZero: true,
                    max: {y_max}
                }},
                y1: {{
                    position: 'right',
                    title: {{ display: true, text: 'Totale (kg)', color: '#8b8fa3' }},
                    ticks: {{ color: 'rgba(255,217,61,0.8)' }},
                    grid: {{ drawOnChartArea: false }},
                    beginAtZero: true,
                    max: {y1_max}
                }}
            }}
        }}
    }});
}});
</script>
"""

        # --- Tabella storico ---
        cols = [
            ("Data", "data"), ("Peso", "peso_kg"), ("BF%", "body_fat_pct"),
            ("Massa magra", "massa_magra_kg"), ("FFMI adj", "ffmi_adj"),
            ("Squat", "squat_1rm"), ("Panca", "panca_1rm"), ("Stacco", "stacco_1rm"),
            ("Note", "note"),
        ]
        html += '<h3 style="margin:1.5rem 0 .75rem">Storico misurazioni</h3>\n'
        html += '<div class="table-wrap">\n<table><thead><tr>'
        for label, _ in cols:
            html += f'<th>{label}</th>'
        html += '</tr></thead><tbody>\n'
        for row in measurements:
            html += '<tr>'
            for _, key in cols:
                val = row.get(key, "")
                if key == "body_fat_pct" and val:
                    val = f"{val}%"
                html += f'<td>{val}</td>'
            html += '</tr>\n'
        html += '</tbody></table>\n</div>\n'

    return html


# ---------------------------------------------------------------------------
# Workout (generata interamente da workout_data.json)
# ---------------------------------------------------------------------------

def _warmup_html(items: list[str]) -> str:
    html = '<div class="warmup-cooldown">\n'
    html += '<h4>Riscaldamento generale (~10 min)</h4>\n<ol>\n'
    for item in items:
        html += f'  <li>{esc(item)}</li>\n'
    html += '</ol>\n</div>\n'
    return html


def _cooldown_html(items: list[str]) -> str:
    html = '<div class="warmup-cooldown">\n'
    html += '<h4>Defaticamento (~5-10 min)</h4>\n<ol>\n'
    for item in items:
        html += f'  <li>{esc(item)}</li>\n'
    html += '</ol>\n</div>\n'
    return html


def _exercise_table(esercizi: list[dict]) -> str:
    html = '<div class="table-wrap">\n<table>\n<thead><tr>'
    html += '<th>#</th><th>Esercizio</th><th>Serie x Reps</th>'
    html += '<th>Peso / Intensita</th><th>Recupero</th><th>Gruppo</th>'
    html += '</tr></thead>\n<tbody>\n'
    for i, ex in enumerate(esercizi, 1):
        nome = ex["nome"]
        if ex.get("principale"):
            nome = f'<strong>{esc(nome)}</strong>'
        else:
            nome = esc(nome)
        html += f'<tr><td>{i}</td><td>{nome}</td>'
        html += f'<td>{esc(ex.get("reps", ""))}</td>'
        html += f'<td>{esc(ex.get("peso", ""))}</td>'
        html += f'<td>{esc(ex.get("recupero", ""))}</td>'
        html += f'<td>{esc(ex.get("gruppo", ""))}</td></tr>\n'
    html += '</tbody>\n</table>\n</div>\n'
    return html


def _test_day_html(giorno: dict, warmup: str, cooldown: str) -> str:
    """Genera l'HTML per un giorno di test."""
    html = warmup
    info = giorno.get("info_test", {})
    html += f'<h3>{esc(giorno["nome"])}</h3>\n'
    if info:
        html += f'<p><strong>Tipo di test</strong>: {esc(info.get("tipo", ""))}</p>\n'
        html += f'<p><strong>Ordine</strong>: {esc(info.get("ordine", ""))}</p>\n'
        html += f'<p><strong>Formula</strong>: <code>{esc(info.get("formula", ""))}</code></p>\n'
        regole = info.get("regole", [])
        if regole:
            html += '<h4>Regole generali</h4>\n<ul>\n'
            for r in regole:
                html += f'  <li>{esc(r)}</li>\n'
            html += '</ul>\n'
    for proto in giorno.get("protocolli", []):
        html += f'<h4>Protocollo {esc(proto["nome"])} ({esc(proto.get("target", ""))})</h4>\n'
        html += '<div class="table-wrap">\n<table>\n<thead><tr><th>Set</th><th>Peso</th><th>Reps</th><th>Note</th></tr></thead>\n<tbody>\n'
        for s in proto.get("serie", []):
            if s.get("tentativo"):
                html += f'<tr><td><strong>{esc(s["set"])}</strong></td><td><strong>{esc(s["peso"])}</strong></td>'
                html += f'<td><strong>{s["reps"]}</strong></td><td>{esc(s.get("note", ""))}</td></tr>\n'
            else:
                html += f'<tr><td>{esc(s["set"])}</td><td>{esc(s["peso"])}</td>'
                html += f'<td>{s["reps"]}</td><td>{esc(s.get("note", ""))}</td></tr>\n'
        html += '</tbody>\n</table>\n</div>\n'
    html += cooldown
    return html


def build_workout(data: dict) -> str:
    """Genera l'intera pagina workout dal JSON, con tab settimane e sub-tab giorni."""
    settimane = data.get("settimane", [])
    warmup = _warmup_html(data.get("riscaldamento", []))
    cooldown = _cooldown_html(data.get("defaticamento", []))
    meso = data.get("mesociclo", {})

    html = f'<h2 class="page-title">Scheda di Allenamento &mdash; {esc(data.get("data", ""))}</h2>\n'

    # --- Tab settimane (livello 1) ---
    html += '<div class="sub-nav" id="week-nav">\n'
    html += '  <a href="#" class="sub-nav-item active" onclick="showWeek(\'info\', this); return false;">Info</a>\n'
    for sett in settimane:
        sid = sett["id"]
        label = sett["nome"]
        html += f'  <a href="#" class="sub-nav-item" onclick="showWeek(\'{sid}\', this); return false;">{esc(label)}</a>\n'
    html += '</div>\n'

    # === Panel INFO ===
    html += '<div id="week-info" class="week-panel active">\n'
    html += f'<h2>{esc(meso.get("nome", ""))}</h2>\n<ul>\n'
    html += f'  <li><strong>Durata</strong>: {esc(meso.get("durata", ""))}</li>\n'
    html += f'  <li><strong>Metodologia</strong>: {esc(meso.get("metodologia", ""))}</li>\n'
    html += f'  <li><strong>Frequenza</strong>: {esc(meso.get("frequenza", ""))}</li>\n'
    html += f'  <li><strong>Obiettivo</strong>: {esc(meso.get("obiettivo", ""))}</li>\n'
    html += '</ul>\n'
    logica = meso.get("logica", [])
    if logica:
        html += '<h3>Logica del programma</h3>\n<ul>\n'
        for l in logica:
            html += f'  <li>{esc(l)}</li>\n'
        html += '</ul>\n'
    notes = data.get("note", [])
    if notes:
        html += '<h3>Note importanti</h3>\n<ul>\n'
        for n in notes:
            html += f'  <li>{esc(n)}</li>\n'
        html += '</ul>\n'
    html += '</div>\n'

    # === Panels per ogni settimana ===
    for sett in settimane:
        sid = sett["id"]
        giorni = sett.get("giorni", [])
        progressione = sett.get("progressione")

        html += f'<div id="week-{sid}" class="week-panel">\n'
        html += f'<h2>{esc(sett["nome"])}: {esc(sett.get("descrizione", ""))}</h2>\n'

        # Sub-tab giorni (livello 2) — solo se piu' di un giorno
        if len(giorni) > 1:
            html += f'<div class="sub-nav sub-nav-days" id="day-nav-{sid}">\n'
            for i, g in enumerate(giorni):
                active = " active" if i == 0 else ""
                html += f'  <a href="#" class="sub-nav-item{active}" '
                html += f'onclick="showDay(\'{sid}\', \'{g["id"]}\', this); return false;">Giorno {esc(g["id"])}</a>\n'
            html += '</div>\n'

        # Panels per ogni giorno
        for i, giorno in enumerate(giorni):
            gid = giorno["id"]
            active = " active" if i == 0 else ""
            html += f'<div id="day-{sid}-{gid}" class="day-panel{active}">\n'

            # Giorno di test?
            if giorno.get("protocolli"):
                html += _test_day_html(giorno, warmup, cooldown)
            else:
                # Giorno normale: riscaldamento + esercizi + defaticamento
                html += warmup
                html += f'<h3>{esc(giorno["nome"])}</h3>\n'
                html += _exercise_table(giorno.get("esercizi", []))
                html += cooldown

            # Navigazione prev/next
            if len(giorni) > 1:
                html += '<div class="day-nav">\n'
                if i > 0:
                    prev = giorni[i - 1]
                    html += f'  <a href="#" onclick="showDay(\'{sid}\', \'{prev["id"]}\', '
                    html += f'document.querySelector(\'#day-nav-{sid} [onclick*={prev["id"]}]\')); return false;">'
                    html += f'&larr; Giorno {esc(prev["id"])}</a>\n'
                else:
                    html += '  <span></span>\n'
                if i < len(giorni) - 1:
                    nxt = giorni[i + 1]
                    html += f'  <a href="#" onclick="showDay(\'{sid}\', \'{nxt["id"]}\', '
                    html += f'document.querySelector(\'#day-nav-{sid} [onclick*={nxt["id"]}]\')); return false;">'
                    html += f'Giorno {esc(nxt["id"])} &rarr;</a>\n'
                else:
                    html += '  <span></span>\n'
                html += '</div>\n'

            html += '</div>\n'  # day-panel

        # Tabella progressione (se presente)
        if progressione:
            tab = progressione.get("tabella", [])
            if tab:
                html += '<hr>\n<h3>Progressione settimanale (top set)</h3>\n'
                # Colonne dinamiche dalla prima riga
                cols = [k for k in tab[0].keys() if k != "esercizio"]
                html += '<div class="table-wrap">\n<table>\n<thead><tr><th>Esercizio</th>'
                for c in cols:
                    html += f'<th>{esc(c)}</th>'
                html += '</tr></thead>\n<tbody>\n'
                for row in tab:
                    html += f'<tr><td>{esc(row["esercizio"])}</td>'
                    for c in cols:
                        html += f'<td>{esc(row.get(c, ""))}</td>'
                    html += '</tr>\n'
                html += '</tbody>\n</table>\n</div>\n'
                nota = progressione.get("nota", "")
                if nota:
                    html += f'<blockquote><p>{esc(nota)}</p></blockquote>\n'

        html += '</div>\n'  # week-panel

    # JavaScript per la navigazione
    html += """
<script>
function showWeek(id, link) {
    document.querySelectorAll('.week-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('#week-nav .sub-nav-item').forEach(a => a.classList.remove('active'));
    var el = document.getElementById('week-' + id);
    if (el) el.classList.add('active');
    if (link) link.classList.add('active');
}

function showDay(weekId, dayId, link) {
    var parent = document.getElementById('week-' + weekId);
    if (!parent) return;
    parent.querySelectorAll('.day-panel').forEach(p => p.classList.remove('active'));
    var navContainer = document.getElementById('day-nav-' + weekId);
    if (navContainer) navContainer.querySelectorAll('.sub-nav-item').forEach(a => a.classList.remove('active'));
    var dayEl = document.getElementById('day-' + weekId + '-' + dayId);
    if (dayEl) dayEl.classList.add('active');
    if (link) link.classList.add('active');
}
</script>
"""
    return html


# ---------------------------------------------------------------------------
# Volume
# ---------------------------------------------------------------------------

def match_exercise(name: str) -> dict | None:
    name_lower = name.lower().strip()
    if name_lower in EXERCISE_MUSCLES:
        return EXERCISE_MUSCLES[name_lower]
    for key, muscles in EXERCISE_MUSCLES.items():
        if key in name_lower or name_lower in key:
            return muscles
    return None


def build_volume(workout_data: dict) -> str:
    volume: dict[str, dict] = {}
    unmatched = []

    # Usa solo la prima settimana (struttura principale) per il conteggio volume
    settimane = workout_data.get("settimane", [])
    main_week = settimane[0] if settimane else {}

    for giorno in main_week.get("giorni", []):
        day_label = f"Giorno {giorno['id']}"
        for ex in giorno.get("esercizi", []):
            muscles = match_exercise(ex["nome"])
            if muscles is None:
                unmatched.append(ex["nome"])
                continue
            sets = ex["serie"]
            for role, weight in [("principale", 1.0), ("secondario", 0.5), ("terziario", 0.3)]:
                for muscle in muscles.get(role, []):
                    if muscle not in volume:
                        volume[muscle] = {"serie_pesate": 0, "dettaglio": []}
                    volume[muscle]["serie_pesate"] += round(sets * weight, 1)
                    volume[muscle]["dettaglio"].append({
                        "esercizio": ex["nome"],
                        "giorno": day_label,
                        "serie": sets,
                        "ruolo": role,
                        "peso": weight,
                        "contributo": round(sets * weight, 1),
                    })

    for m in volume:
        volume[m]["serie_pesate"] = round(volume[m]["serie_pesate"], 1)

    sorted_muscles = sorted(volume.items(), key=lambda x: x[1]["serie_pesate"], reverse=True)
    max_val = sorted_muscles[0][1]["serie_pesate"] if sorted_muscles else 1

    html = '<h2 class="page-title">Volume per Distretto Muscolare</h2>\n'
    html += '<h3>Serie pesate per distretto muscolare</h3>\n'
    html += '<p class="subtitle">Principale = 1.0 | Secondario = 0.5 | Terziario = 0.3</p>\n'
    html += '<div class="bar-chart">\n'
    for muscle, data in sorted_muscles:
        pct = (data["serie_pesate"] / max_val) * 100
        html += (
            f'<div class="bar-row">'
            f'<span class="bar-label">{muscle}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.0f}%"></div></div>'
            f'<span class="bar-value">{data["serie_pesate"]}</span>'
            f'</div>\n'
        )
    html += '</div>\n'

    html += '<h3>Dettaglio per distretto</h3>\n'
    for muscle, data in sorted_muscles:
        html += '<details class="muscle-detail">\n'
        html += f'<summary>{muscle.capitalize()} &mdash; {data["serie_pesate"]} serie pesate</summary>\n'
        html += '<div class="table-wrap">\n<table class="detail-table"><thead><tr><th>Ruolo</th><th>Esercizio</th><th>Giorno</th><th>Serie</th><th>Peso</th><th>Contributo</th></tr></thead><tbody>\n'
        for d in data["dettaglio"]:
            tag = {"principale": "P", "secondario": "S", "terziario": "T"}[d["ruolo"]]
            tag_cls = {"P": "tag-primary", "S": "tag-secondary", "T": "tag-tertiary"}[tag]
            html += (
                f'<tr><td><span class="tag {tag_cls}">{tag}</span></td>'
                f'<td>{d["esercizio"]}</td><td>{d["giorno"]}</td>'
                f'<td>{d["serie"]}</td><td>{d["peso"]}</td><td>{d["contributo"]}</td></tr>\n'
            )
        html += '</tbody></table>\n</div>\n</details>\n'

    if unmatched:
        html += '<p class="subtitle" style="margin-top:1rem">Esercizi non mappati: ' + ', '.join(set(unmatched)) + '</p>\n'

    return html


# ---------------------------------------------------------------------------
# Tabbed content (generic: diet, feedback, plan)
# ---------------------------------------------------------------------------

def _wrap_fragment_tables(html: str) -> str:
    """Wrap <table>...</table> in fragment HTML with scrollable containers."""
    return re.sub(
        r"(<table\b.*?</table>)",
        r'<div class="table-wrap">\1</div>',
        html,
        flags=re.DOTALL,
    )


def build_tabbed_content(html_fragment: str, page_id: str, max_tabs: int = 0) -> str:
    """Split an HTML fragment by <h3> headings into a tabbed layout.

    The first <h2> (if any) becomes the page title shown above the tabs.
    Any content before the first <h3> is shown above the tabs as intro.
    Each <h3> section becomes a tab.

    If max_tabs > 0 and there are more sections than max_tabs, excess
    sections are merged into the last tab.
    """
    remaining = _wrap_fragment_tables(html_fragment.strip())

    # Extract page title (<h2>)
    title_html = ""
    h2_match = re.search(r"<h2[^>]*>(.*?)</h2>", remaining, re.DOTALL)
    if h2_match:
        title_html = f'<h2 class="page-title">{h2_match.group(1)}</h2>\n'
        remaining = remaining[: h2_match.start()] + remaining[h2_match.end() :]

    # Split on <h3> boundaries
    parts = re.split(r"(?=<h3[^>]*>)", remaining.strip())
    parts = [p.strip() for p in parts if p.strip()]

    # Separate intro (no <h3>) from tabbed sections
    intro_html = ""
    sections: list[tuple[str, str]] = []  # (label, content)
    for part in parts:
        h3_match = re.match(r"<h3[^>]*>(.*?)</h3>", part, re.DOTALL)
        if h3_match:
            # Strip HTML tags and common entities for the tab label
            label = re.sub(r"<[^>]+>", "", h3_match.group(1)).strip()
            label = (
                label.replace("&mdash;", "\u2014")
                .replace("&egrave;", "\u00e8")
                .replace("&agrave;", "\u00e0")
                .replace("&ograve;", "\u00f2")
                .replace("&ugrave;", "\u00f9")
                .replace("&rsquo;", "\u2019")
                .replace("&le;", "\u2264")
            )
            sections.append((label, part))
        else:
            intro_html += part

    # Not enough sections for tabs -> return as-is
    if len(sections) <= 1:
        return f'{title_html}<div class="md-content">{_wrap_fragment_tables(html_fragment)}</div>'

    # Merge excess sections into the last tab if max_tabs is set
    if max_tabs > 0 and len(sections) > max_tabs:
        merged: list[tuple[str, str]] = list(sections[: max_tabs - 1])
        # Combine remaining sections: use first remaining label, concatenate all content
        last_label = sections[max_tabs - 1][0]
        last_content = ""
        for _, content in sections[max_tabs - 1 :]:
            # Downgrade <h3> to <h4> inside merged content so they show as sub-headings
            content = re.sub(r"<h3([^>]*)>", r"<h4\1>", content)
            content = content.replace("</h3>", "</h4>")
            last_content += content + "\n"
        merged.append((last_label, last_content))
        sections = merged

    html = title_html
    if intro_html:
        html += f'<div class="md-content">{intro_html}</div>\n'

    # Tab bar
    html += f'<div class="sub-nav" id="{page_id}-nav">\n'
    for i, (label, _) in enumerate(sections):
        active = " active" if i == 0 else ""
        html += (
            f'  <a href="#" class="sub-nav-item{active}" '
            f"onclick=\"showTab('{page_id}', '{page_id}-{i}', this); return false;\">"
            f"{label}</a>\n"
        )
    html += "</div>\n"

    # Panels
    for i, (_, content) in enumerate(sections):
        active = " active" if i == 0 else ""
        html += f'<div id="{page_id}-{i}" class="{page_id}-panel tab-panel{active}">\n'
        html += f'<div class="md-content">{content}</div>\n'
        html += "</div>\n"

    # JS (generic, safe to include multiple times since function name is the same)
    html += """
<script>
function showTab(pageId, tabId, link) {
    document.querySelectorAll('.' + pageId + '-panel').forEach(function(p) { p.classList.remove('active'); });
    document.querySelectorAll('#' + pageId + '-nav .sub-nav-item').forEach(function(a) { a.classList.remove('active'); });
    var el = document.getElementById(tabId);
    if (el) el.classList.add('active');
    if (link) link.classList.add('active');
}
</script>
"""
    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Genera sito HTML statico multi-pagina")
    parser.add_argument("--outdir", default="data/output/site", help="Directory di output")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_out = os.path.join(base_dir, "data", "output")
    outdir = os.path.join(base_dir, args.outdir)
    template = read_file(os.path.join(base_dir, "scripts", "templates", "base.html"))

    # Dati strutturati
    measurements_path = os.path.join(data_out, "measurements.json")
    measurements = read_json(measurements_path) if os.path.exists(measurements_path) else []

    workout_data_path = latest_file(data_out, "workout_data", ext=".json")
    workout_data = read_json(workout_data_path) if workout_data_path else None

    # Contenuti HTML statici
    diet_html_path = latest_file(data_out, "diet")
    feedback_html_path = latest_file(data_out, "feedback")
    plan_html_path = os.path.join(data_out, "plan.html")

    # Assembla le pagine
    page_content = {
        "dashboard": build_dashboard(measurements),
        "workout": build_workout(workout_data) if workout_data else "<p>Nessun dato workout trovato.</p>",
        "volume": build_volume(workout_data) if workout_data else "<p>Nessun dato workout trovato.</p>",
        "diet": build_tabbed_content(read_file(diet_html_path), "diet") if diet_html_path else "<p>Nessuna dieta trovata.</p>",
        "plan": build_tabbed_content(read_file(plan_html_path), "plan") if os.path.exists(plan_html_path) else "<p>Nessun piano trovato.</p>",
        "feedback": build_tabbed_content(read_file(feedback_html_path), "feedback", max_tabs=4) if feedback_html_path else "<p>Nessun feedback trovato.</p>",
    }

    # Genera file HTML
    for page in PAGES:
        html = render_page(template, page["label"], page["id"], page_content[page["id"]])
        out_path = os.path.join(outdir, f'{page["id"]}.html')
        write_file(out_path, html)
        print(f"  {page['id']}.html")

    # index.html -> redirect
    write_file(
        os.path.join(outdir, "index.html"),
        '<meta http-equiv="refresh" content="0;url=dashboard.html">'
    )

    print(f"\nSito generato in: {outdir}")


if __name__ == "__main__":
    main()
