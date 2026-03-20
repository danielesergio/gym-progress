#!/usr/bin/env python3
"""
Genera i JSON ottimizzati per il sito web a partire dai dati degli agenti.

Legge i file di output (YAML/JSON/MD/HTML) da data/output/ e scrive
JSON normalizzati in docs/data/:

  docs/data/measurements.json  — storico misurazioni
  docs/data/workout.json       — scheda corrente
  docs/data/volume.json        — volume per distretto (pre-calcolato)
  docs/data/diet.json          — dieta corrente
  docs/data/plan.json          — piano a lungo termine
  docs/data/feedback.json      — feedback coach + atleta { "coach_html": "...", "atleta_html": "..." }

Uso:
    python scripts/generate_data.py
    python scripts/generate_data.py --outdir docs/data
"""

import argparse
import glob as globmod
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from volume_calc import EXERCISE_MUSCLES

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_OUT = os.path.join(BASE_DIR, "data", "output")


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_yaml(path: str):
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        try:
            return read_json(path)
        except Exception:
            return None
    except Exception:
        return None


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  -> {os.path.relpath(path, BASE_DIR)}")


def latest_file(prefix: str, exts: list) -> str | None:
    """Trova il file piu' recente con il prefisso dato tra piu' estensioni."""
    all_files = []
    for ext in exts:
        pattern_root = os.path.join(DATA_OUT, f"{prefix}_[0-9]*{ext}")
        pattern_hist = os.path.join(DATA_OUT, "history", "**", f"{prefix}_[0-9]*{ext}")
        all_files.extend(globmod.glob(pattern_root) + globmod.glob(pattern_hist, recursive=True))
    return sorted(all_files)[-1] if all_files else None


# ---------------------------------------------------------------------------
# Markdown -> HTML (inline)
# ---------------------------------------------------------------------------

def _md_inline(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    return text


def md_to_html(text: str) -> str:
    lines = text.split("\n")
    html_parts = []
    i = 0
    in_ul = False
    in_ol = False
    paragraph_lines: list[str] = []

    def flush_paragraph():
        nonlocal paragraph_lines
        if paragraph_lines:
            para = " ".join(paragraph_lines).strip()
            if para:
                html_parts.append(f"<p>{_md_inline(para)}</p>")
            paragraph_lines = []

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            html_parts.append("</ul>")
            in_ul = False
        if in_ol:
            html_parts.append("</ol>")
            in_ol = False

    while i < len(lines):
        line = lines[i]
        h4 = re.match(r"^#{4}\s+(.*)", line)
        h3 = re.match(r"^#{3}\s+(.*)", line)
        h2 = re.match(r"^#{2}\s+(.*)", line)
        h1 = re.match(r"^#\s+(.*)", line)

        if h4:
            flush_paragraph(); close_lists()
            html_parts.append(f"<h4>{_md_inline(h4.group(1))}</h4>")
        elif h3:
            flush_paragraph(); close_lists()
            html_parts.append(f"<h3>{_md_inline(h3.group(1))}</h3>")
        elif h2:
            flush_paragraph(); close_lists()
            html_parts.append(f"<h2>{_md_inline(h2.group(1))}</h2>")
        elif h1:
            flush_paragraph(); close_lists()
            html_parts.append(f"<h1>{_md_inline(h1.group(1))}</h1>")
        elif re.match(r"^---+\s*$", line):
            flush_paragraph(); close_lists()
            html_parts.append("<hr>")
        elif re.match(r"^(\s*[-*])\s+(.*)", line):
            m = re.match(r"^(\s*[-*])\s+(.*)", line)
            flush_paragraph()
            if in_ol:
                html_parts.append("</ol>"); in_ol = False
            if not in_ul:
                html_parts.append("<ul>"); in_ul = True
            html_parts.append(f"<li>{_md_inline(m.group(2))}</li>")
        elif re.match(r"^\d+\.\s+(.*)", line):
            m = re.match(r"^\d+\.\s+(.*)", line)
            flush_paragraph()
            if in_ul:
                html_parts.append("</ul>"); in_ul = False
            if not in_ol:
                html_parts.append("<ol>"); in_ol = True
            html_parts.append(f"<li>{_md_inline(m.group(1))}</li>")
        elif line.strip() == "":
            flush_paragraph(); close_lists()
        else:
            paragraph_lines.append(line)
        i += 1

    flush_paragraph(); close_lists()
    return "\n".join(html_parts)


# ---------------------------------------------------------------------------
# Feedback parsers (structured extraction)
# ---------------------------------------------------------------------------

def _parse_md_sections(text: str) -> dict:
    """Split markdown text into {section_name: [lines]} by ## headings."""
    sections: dict = {}
    current = None
    for line in text.split("\n"):
        m = re.match(r"^##\s+(.+)", line)
        if m:
            current = m.group(1).strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def parse_atleta_md(text: str) -> dict:
    """Parse athlete self-assessment into a structured dict."""
    sections = _parse_md_sections(text)
    # key-value: - **Key**: value  (parenthetical unit inside ** is kept as part of key)
    kv_re = re.compile(r"^\s*-\s+\*\*([^*]+)\*\*\s*(?:\([^)]*\))?\s*:?\s*(.*)")
    # sub-item (indented):   - Label (unit): value   or   - text
    sub_re = re.compile(r"^\s{2,}-\s+(.+)")

    data: dict = {}

    for sec_name, lines in sections.items():
        sec_lower = sec_name.lower()
        kv: dict = {}
        sub_items: dict = {}
        last_key = None

        for line in lines:
            m = kv_re.match(line)
            if m:
                key = m.group(1).strip()
                val = m.group(2).strip()
                kv[key] = val
                last_key = key
                sub_items[key] = []
                continue
            if last_key is not None:
                m2 = sub_re.match(line)
                if m2:
                    raw = m2.group(1).strip()
                    # try "Label (unit): value" or "Label: value"
                    km = re.match(r"^(.+?)\s*(?:\([^)]*\))?\s*:\s*(.*)", raw)
                    if km:
                        sub_items[last_key].append({"k": km.group(1).strip(), "v": km.group(2).strip()})
                    else:
                        sub_items[last_key].append({"k": None, "v": raw})

        # Build sec_data merging subs
        sec_data: dict = {}
        for k, v in kv.items():
            subs = sub_items.get(k, [])
            if subs:
                if all(s["k"] for s in subs):
                    sec_data[k] = {s["k"]: s["v"] for s in subs}
                else:
                    sec_data[k] = [s["v"] for s in subs if s["v"]]
            else:
                sec_data[k] = v

        if "sentito" in sec_lower:
            data["sensazioni"] = sec_data
        elif "allenamento" in sec_lower:
            data["allenamento"] = sec_data
        elif "dieta" in sec_lower:
            data["dieta"] = sec_data
        elif "progress" in sec_lower:
            data["progressi"] = sec_data
        elif "massimal" in sec_lower:
            lifts = []
            for lift_name, raw in sec_data.items():
                if isinstance(raw, str):
                    lm = re.match(r"(\d+(?:\.\d+)?)\s*kg\s*[xX×]\s*(\d+)", raw)
                    if lm:
                        peso = float(lm.group(1))
                        reps = int(lm.group(2))
                        orm = round(peso * (1 + reps / 30))
                        lifts.append({"lift": lift_name, "peso": peso, "reps": reps, "orm_stimato": orm, "raw": raw})
                    elif raw:
                        lifts.append({"lift": lift_name, "peso": None, "reps": None, "orm_stimato": None, "raw": raw})
            data["massimali"] = lifts
        elif "compos" in sec_lower or "corporea" in sec_lower:
            corpo: dict = {}
            for k, v in sec_data.items():
                if isinstance(v, dict):
                    misure: dict = {}
                    for mk, mv in v.items():
                        try:
                            misure[mk] = float(mv)
                        except (ValueError, TypeError):
                            misure[mk] = mv
                    corpo["misure"] = misure
                else:
                    try:
                        corpo[k] = float(v) if v else None
                    except (ValueError, TypeError):
                        corpo[k] = v
            data["corpo"] = corpo
        elif "altro" in sec_lower:
            data["altro"] = sec_data

    return data


def parse_coach_md(text: str) -> list:
    """Split coach feedback into [{title, html}] sections by ## headings."""
    sections = []
    current_title = None
    current_lines: list = []

    for line in text.split("\n"):
        m = re.match(r"^##\s+(.+)", line)
        if m:
            if current_title is not None:
                content = "\n".join(current_lines).strip()
                if content:
                    sections.append({"title": current_title, "html": md_to_html(content)})
            current_title = m.group(1).strip()
            current_lines = []
        elif current_title is not None:
            current_lines.append(line)

    if current_title is not None:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append({"title": current_title, "html": md_to_html(content)})

    return sections


# ---------------------------------------------------------------------------
# Volume calculation
# ---------------------------------------------------------------------------

def match_exercise(name: str) -> dict | None:
    name_lower = name.lower().strip()
    if name_lower in EXERCISE_MUSCLES:
        return EXERCISE_MUSCLES[name_lower]
    for key, muscles in EXERCISE_MUSCLES.items():
        if key in name_lower or name_lower in key:
            return muscles
    return None


def compute_volume(workout_data: dict) -> list:
    """Restituisce lista ordinata di {muscolo, serie_pesate, dettaglio[]}."""
    volume: dict = {}
    settimane = workout_data.get("settimane", [])
    main_week = settimane[0] if settimane else {}
    unmatched = []

    for i, giorno in enumerate(main_week.get("giorni", [])):
        day_label = giorno.get("giorno", f"Giorno {i+1}")
        for ex in giorno.get("esercizi", []):
            muscles = match_exercise(ex["nome"])
            if muscles is None:
                unmatched.append(ex["nome"])
                continue
            sets = ex["serie"]
            for role, weight in [("principale", 1.0), ("secondario", 0.5), ("terziario", 0.3)]:
                for muscle in muscles.get(role, []):
                    if muscle not in volume:
                        volume[muscle] = {"serie_pesate": 0.0, "dettaglio": []}
                    volume[muscle]["serie_pesate"] += round(sets * weight, 1)
                    volume[muscle]["dettaglio"].append({
                        "esercizio": ex["nome"],
                        "giorno": day_label,
                        "serie": sets,
                        "ruolo": role,
                        "peso": weight,
                        "contributo": round(sets * weight, 1),
                    })

    result = []
    for muscle, data in sorted(volume.items(), key=lambda x: x[1]["serie_pesate"], reverse=True):
        result.append({
            "muscolo": muscle,
            "serie_pesate": round(data["serie_pesate"], 1),
            "dettaglio": data["dettaglio"],
        })

    if unmatched:
        result.append({"_unmatched": list(set(unmatched))})

    return result


# ---------------------------------------------------------------------------
# Data enrichment functions for UI optimization
# ---------------------------------------------------------------------------

def enrich_measurements(measurements: list) -> list:
    """Aggiungi metadati derivati per il rendering (variazione %, tendenza, badge, tipo massimali)."""
    if not measurements:
        return measurements

    enriched = []
    for i, m in enumerate(measurements):
        m_copy = dict(m)
        # Calcola variazione dalla misurazione precedente
        if i > 0:
            prev = measurements[i - 1]
            m_copy["delta_peso_kg"] = round(m["peso_kg"] - prev["peso_kg"], 1)
            m_copy["delta_bf_pct"] = round(m["body_fat_pct"] - prev["body_fat_pct"], 1)
            m_copy["delta_mm_kg"] = round(m["massa_magra_kg"] - prev["massa_magra_kg"], 1)
            # Tendenza (migliorante/peggiorante/stabile)
            bf_delta = m_copy["delta_bf_pct"]
            if bf_delta < -0.5:
                m_copy["bf_trend"] = "migliorante"  # BF diminuisce = bene
            elif bf_delta > 0.5:
                m_copy["bf_trend"] = "peggiorante"
            else:
                m_copy["bf_trend"] = "stabile"
        else:
            m_copy["delta_peso_kg"] = 0
            m_copy["delta_bf_pct"] = 0
            m_copy["delta_mm_kg"] = 0
            m_copy["bf_trend"] = "baseline"

        # Aggiungi tipo massimale (R=Reale, S=Stimato) se non presente
        # Assume che se il campo massimali_tipo non esiste, tutti sono "R" (reali)
        if "squat_1rm_tipo" not in m_copy:
            m_copy["squat_1rm_tipo"] = m_copy.get("squat_1rm_tipo", "R")
        if "panca_1rm_tipo" not in m_copy:
            m_copy["panca_1rm_tipo"] = m_copy.get("panca_1rm_tipo", "R")
        if "stacco_1rm_tipo" not in m_copy:
            m_copy["stacco_1rm_tipo"] = m_copy.get("stacco_1rm_tipo", "R")

        enriched.append(m_copy)
    return enriched


def enrich_volume(volume: list) -> list:
    """Aggiungi indice di equilibrio push/pull e rating complessivo."""
    if not volume:
        return volume

    total_serie = sum(v.get("serie_pesate", 0) for v in volume if "muscolo" in v)

    # Muscoli push vs pull
    push_muscles = {"deltoidi", "petto", "tricipiti"}
    pull_muscles = {"dorsali", "bicipiti", "trapezi", "deltoidi posteriori", "romboidi"}

    push_serie = 0
    pull_serie = 0
    for v in volume:
        muscolo = v.get("muscolo", "").lower()
        serie = v.get("serie_pesate", 0)
        if any(pm in muscolo for pm in push_muscles):
            push_serie += serie
        if any(pm in muscolo for pm in pull_muscles):
            pull_serie += serie

    # Calcola rapporto
    ratio = round(pull_serie / max(push_serie, 0.1), 2) if push_serie > 0 else 0

    # Rating equilibrio (ideale pull/push ~1.0-1.5)
    if 0.8 <= ratio <= 1.5:
        balance_rating = "equilibrato"
    elif ratio < 0.8:
        balance_rating = "insufficiente_pull"
    else:
        balance_rating = "eccessivo_pull"

    return {
        "volumi": volume,
        "meta": {
            "total_serie_pesate": round(total_serie, 1),
            "push_serie": round(push_serie, 1),
            "pull_serie": round(pull_serie, 1),
            "pull_push_ratio": ratio,
            "balance_rating": balance_rating
        }
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Genera JSON per il sito")
    parser.add_argument("--outdir", default="docs/data", help="Directory di output")
    args = parser.parse_args()

    out = os.path.join(BASE_DIR, args.outdir)
    print(f"Generazione dati -> {args.outdir}/")

    # --- measurements ---
    meas_path = os.path.join(DATA_OUT, "measurements.json")
    measurements = read_json(meas_path) if os.path.exists(meas_path) else []
    measurements = enrich_measurements(measurements)
    write_json(os.path.join(out, "measurements.json"), measurements)

    # --- workout ---
    workout_path = latest_file("workout_data", [".yaml"]) or latest_file("workout_data", [".json"])
    workout_data = None
    if workout_path:
        workout_data = (read_yaml(workout_path) if workout_path.endswith(".yaml")
                        else read_json(workout_path))
    if workout_data:
        write_json(os.path.join(out, "workout.json"), workout_data)
        volume_raw = compute_volume(workout_data)
        volume_enriched = enrich_volume(volume_raw)
        write_json(os.path.join(out, "volume.json"), volume_enriched)
    else:
        print("  ! workout_data non trovato")

    # --- diet ---
    diet_yaml = latest_file("diet", [".yaml"])
    diet_html = latest_file("diet", [".html"])
    if diet_yaml:
        write_json(os.path.join(out, "diet.json"), read_yaml(diet_yaml))
    elif diet_html:
        write_json(os.path.join(out, "diet.json"), {"html": read_text(diet_html)})
    else:
        print("  ! dieta non trovata")

    # --- plan ---
    plan_yaml = os.path.join(DATA_OUT, "plan.yaml")
    plan_html = os.path.join(DATA_OUT, "plan.html")
    if os.path.exists(plan_yaml):
        write_json(os.path.join(out, "plan.json"), read_yaml(plan_yaml))
    elif os.path.exists(plan_html):
        write_json(os.path.join(out, "plan.json"), {"html": read_text(plan_html)})
    else:
        print("  ! piano non trovato")

    # --- feedback ---
    fb_coach_md = latest_file("feedback_coach", [".md"])
    fb_atleta_md = latest_file("feedback_atleta", [".md"])
    fb_html = latest_file("feedback", [".html"])
    if fb_coach_md or fb_atleta_md:
        coach_text = read_text(fb_coach_md) if fb_coach_md else None
        atleta_text = read_text(fb_atleta_md) if fb_atleta_md else None
        write_json(os.path.join(out, "feedback.json"), {
            "coach_sections": parse_coach_md(coach_text) if coach_text else [],
            "coach_html": md_to_html(coach_text) if coach_text else None,
            "atleta": parse_atleta_md(atleta_text) if atleta_text else {},
            "atleta_html": md_to_html(atleta_text) if atleta_text else None,
        })
    elif fb_html:
        write_json(os.path.join(out, "feedback.json"), {
            "coach_sections": [], "coach_html": read_text(fb_html),
            "atleta": {}, "atleta_html": None,
        })
    else:
        print("  ! feedback non trovato")

    print(f"\nDati generati in: {args.outdir}/")


if __name__ == "__main__":
    main()
