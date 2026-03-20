#!/usr/bin/env python3
"""
Orchestratore Python per la nuova iterazione mensile del programma fitness.

Filosofia:
  - Tutta la logica (loop, calcoli, parsing, archivazione) e' in Python puro.
  - Gli LLM vengono invocati solo quando servono: generazione piano, scheda, dieta,
    feedback coach, revisioni PT senior.
  - I report di review sono JSON con schema fisso -Python decide approve/reject.
  - I calcoli (body fat, BMR, TDEE, 1RM, rate progressione) sono Python puro
    usando le funzioni di scripts/body_calc.py.
  - L'archiviazione (copia, spostamento file) e' Python puro via shutil.
  - Gli agenti LLM vengono invocati tramite CLI: claude --print --agent <nome>

Flusso:
  1. [Python] Legge tutti i file in data/
  2. [Python] Calcola rate progressione storica e body composition
  3. [Python] Aggiorna measurements.json con nuova entry
  4. [LLM] gym-personal-trainer genera plan.yaml
  5. [Loop] gym-pt-senior-reviewer valuta piano (max N iter)
  6. [LLM] gym-personal-trainer genera feedback_coach_(data).md
  7. [LLM x2 parallelo] gym-dietologo + gym-personal-trainer -> diet + workout
  8. [Loop] gym-pt-senior-reviewer valuta scheda (max N iter)
  9. [Python] Archivia file, crea nuovo feedback_atleta.md vuoto

Uso:
    python source/new_iteration.py
    python source/new_iteration.py --max-iter 3
    python source/new_iteration.py --dry-run   # solo parsing e calcoli, nessun LLM
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR  = PROJECT_ROOT / "scripts"
DATA_DIR     = PROJECT_ROOT / "data"
OUTPUT_DIR   = DATA_DIR / "output"
HISTORY_DIR  = OUTPUT_DIR / "history"
REVIEW_PT_DIR = OUTPUT_DIR / "review" / "pt"

DATE_STR      = datetime.now().strftime("%Y-%m-%d")
TODAY         = datetime.now().date()
ITERATION_ID  = uuid.uuid4().hex[:8]   # es. "a3f27c1b" — cross-reference measurements <-> file

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_LABELS = {
    "INFO":   "INFO  ",
    "ACTION": "ACTION",
    "OK":     "OK    ",
    "WARN":   "WARN  ",
    "ERROR":  "ERROR ",
    "SKIP":   "SKIP  ",
}


def log(level: str, msg: str) -> None:
    print(f"[{_LABELS.get(level, level)}] {msg}", flush=True)


def separator(title: str = "") -> None:
    line = "=" * 60
    if title:
        print(f"\n{line}\n  {title}\n{line}")
    else:
        print(line)


# ---------------------------------------------------------------------------
# Body calc -importa da scripts/body_calc.py
# ---------------------------------------------------------------------------

sys.path.insert(0, str(SCRIPTS_DIR))
try:
    from body_calc import body_fat_navy, bmr_mifflin, ffmi_adjusted, stima_1rm_epley
    _BODY_CALC_OK = True
except ImportError:
    _BODY_CALC_OK = False
    log("WARN", "body_calc.py non trovato -calcoli body composition disabilitati")



# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def read_text(path: Path, default: str = "") -> str:
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8")
    return default


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log("WARN", f"JSON non valido in {path.name}: {e}")
        return default


def _read_path_or_dir(p: Path) -> str:
    """Legge un file o tutti i file in una directory."""
    if not p.exists():
        return ""
    if p.is_file():
        return read_text(p)
    parts = []
    for f in sorted(p.iterdir()):
        if f.is_file():
            parts.append(f"### {f.name}\n{read_text(f)}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Feedback parsing (Python puro, nessun LLM)
# ---------------------------------------------------------------------------

def _parse_number(text: str, label: str) -> Optional[float]:
    """Estrae un valore numerico da '**Label**: 87.2' o 'label: 87.2'."""
    patterns = [
        rf"\*\*{re.escape(label)}\*\*\s*[:\(]?\s*(\d+[.,]?\d*)",
        rf"\b{re.escape(label.lower())}\b\s*[:\(]?\s*(\d+[.,]?\d*)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", "."))
            except ValueError:
                pass
    return None


def _parse_lift(text: str, lift: str) -> Optional[tuple]:
    """Estrae (peso_kg, reps) da '**Squat**: 120 kg x 5' o '120x5'."""
    pat = rf"\*\*{re.escape(lift)}\*\*\s*[:\(]?\s*(\d+\.?\d*)\s*(?:kg)?\s*[xX×]\s*(\d+)"
    m = re.search(pat, text, re.IGNORECASE)
    if m:
        return float(m.group(1)), int(m.group(2))
    return None


def parse_feedback(feedback_text: str) -> dict:
    """
    Estrae i dati numerici da feedback_atleta.md.
    I campi mancanti o template non compilati restano None.
    """
    t = feedback_text
    return {
        "peso_kg":       _parse_number(t, "Peso (kg)") or _parse_number(t, "Peso"),
        "vita_cm":       _parse_number(t, "Vita ombelico (cm)") or _parse_number(t, "Vita"),
        "fianchi_cm":    _parse_number(t, "Fianchi (cm)") or _parse_number(t, "Fianchi"),
        "petto_cm":      _parse_number(t, "Petto (cm)") or _parse_number(t, "Petto"),
        "braccio_dx_cm": _parse_number(t, "Braccio dx (cm)") or _parse_number(t, "Braccio"),
        "coscia_dx_cm":  _parse_number(t, "Coscia dx (cm)") or _parse_number(t, "Coscia"),
        "collo_cm":      _parse_number(t, "Collo (cm)") or _parse_number(t, "collo"),
        "squat_test":    _parse_lift(t, "Squat"),
        "panca_test":    _parse_lift(t, "Panca"),
        "stacco_test":   _parse_lift(t, "Stacco"),
    }


def parse_athlete_profile(athlete_text: str) -> dict:
    """Estrae altezza, sesso, eta' dall'athlete.md."""
    t = athlete_text
    profile: dict = {}

    m = re.search(r"Altezza.*?(\d{3})", t)
    if m:
        profile["altezza_cm"] = float(m.group(1))

    m = re.search(r"Sesso[^:]*:\s*([MFmf])", t)
    if m:
        profile["sesso"] = m.group(1).upper()

    m = re.search(r"Data di na[^:]*:\s*(\d{4}-\d{2}-\d{2})", t)
    if m:
        try:
            dob = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            profile["eta"] = (TODAY - dob).days // 365
        except ValueError:
            pass

    return profile


# ---------------------------------------------------------------------------
# Calcolo rate di progressione (Python puro)
# ---------------------------------------------------------------------------

def calc_progression_rates(measurements: list) -> dict:
    """
    Calcola rate di progressione annuale (kg/anno) per squat, panca, stacco.
    Considera solo entry con massimali validi.
    """
    lifts = {
        "squat":  "squat_1rm",
        "panca":  "panca_1rm",
        "stacco": "stacco_1rm",
    }
    rates: dict = {k: [] for k in lifts}

    valid = [m for m in measurements if all(m.get(v) for v in lifts.values())]

    for i in range(1, len(valid)):
        prev, curr = valid[i - 1], valid[i]
        try:
            d_prev = datetime.strptime(prev["data"], "%Y-%m-%d").date()
            d_curr = datetime.strptime(curr["data"], "%Y-%m-%d").date()
            days = (d_curr - d_prev).days
            if days <= 0:
                continue
            years = days / 365.25
            for label, key in lifts.items():
                delta = curr[key] - prev[key]
                rates[label].append(round(delta / years, 1))
        except (ValueError, KeyError):
            continue

    result = {}
    for label, vals in rates.items():
        if vals:
            result[label] = {
                "media": round(sum(vals) / len(vals), 1),
                "min":   min(vals),
                "max":   max(vals),
                "n":     len(vals),
            }
        else:
            result[label] = {"media": 0.0, "min": 0.0, "max": 0.0, "n": 0}

    return result


def apply_corrections(rates: dict, measurements: list, feedback_text: str) -> dict:
    """Applica fattori correttivi conservativi ai rate (infortunio, eta', stallo)."""
    latest = measurements[-1] if measurements else {}
    eta = latest.get("eta", 30)

    has_injury = bool(re.search(
        r"infortun|dolor|lesion|TOS|tendin|stiram|contrat",
        feedback_text, re.IGNORECASE
    ))
    age_penalty = eta > 35

    corrected = {}
    for lift, data in rates.items():
        media = data["media"]
        factor = 1.0
        if media <= 0:
            factor *= 0.5      # stallo: -50%
        elif has_injury:
            factor *= 0.7      # infortunio: -30%
        if age_penalty:
            factor *= 0.9      # eta' >35: -10%

        corrected[lift] = {
            **data,
            "media_corretta": round(media * factor, 1),
            "fattori": {
                "infortunio":  has_injury,
                "eta_over_35": age_penalty,
                "stallo":      media <= 0,
            },
        }
    return corrected


# ---------------------------------------------------------------------------
# Aggiornamento measurements.json (Python puro)
# ---------------------------------------------------------------------------

def build_new_measurement(
    feedback: dict,
    profile: dict,
    measurements: list,
) -> Optional[dict]:
    """
    Costruisce la nuova entry di measurements.json.
    Ritorna None se il peso non e' disponibile nel feedback.
    """
    peso = feedback.get("peso_kg")
    if not peso:
        log("WARN", "Peso non trovato nel feedback -misurazioni non aggiornate")
        return None

    altezza = profile.get("altezza_cm", 188.0)
    sesso   = profile.get("sesso", "M")
    eta     = profile.get("eta", 38)
    vita    = feedback.get("vita_cm")
    collo   = feedback.get("collo_cm")
    fianchi = feedback.get("fianchi_cm")

    entry: dict = {
        "id":            ITERATION_ID,
        "data":          DATE_STR,
        "eta":           eta,
        "peso_kg":       peso,
        "vita_cm":       vita,
        "fianchi_cm":    fianchi,
        "petto_cm":      feedback.get("petto_cm"),
        "collo_cm":      collo,
        "braccio_dx_cm": feedback.get("braccio_dx_cm"),
        "coscia_dx_cm":  feedback.get("coscia_dx_cm"),
    }

    # Body composition
    if _BODY_CALC_OK and vita and collo and altezza:
        try:
            bf          = body_fat_navy(sesso, vita, collo, altezza, fianchi or 0)
            massa_magra = round(peso * (1 - bf / 100), 1)
            entry["body_fat_pct"]  = bf
            entry["massa_magra_kg"] = massa_magra
            entry["ffmi_adj"]       = ffmi_adjusted(massa_magra, altezza)
            entry["bmr_kcal"]       = int(bmr_mifflin(peso, altezza, eta, sesso))
            entry["tdee_kcal"]      = int(entry["bmr_kcal"] * 1.55)
        except Exception as e:
            log("WARN", f"Calcolo body composition fallito: {e}")
            _fill_body_nulls(entry)
    else:
        _fill_body_nulls(entry)

    # 1RM da test (Epley)
    lifts_map = [
        ("Squat",  "squat_1rm",  "squat_test"),
        ("Panca",  "panca_1rm",  "panca_test"),
        ("Stacco", "stacco_1rm", "stacco_test"),
    ]
    last = measurements[-1] if measurements else {}
    tipo = "R"
    for _, key, fb_key in lifts_map:
        test = feedback.get(fb_key)
        if test:
            p, r = test
            if _BODY_CALC_OK:
                entry[key] = stima_1rm_epley(p, r)
            else:
                entry[key] = round(p * (1 + r / 30), 1)
            tipo = "S"
        else:
            entry[key] = last.get(key)

    entry["massimali_tipo"]   = tipo
    entry["efficacia_workout"] = None   # calcolata dal coach con contesto completo
    entry["note"]              = ""

    return entry


def _fill_body_nulls(entry: dict) -> None:
    for k in ("body_fat_pct", "massa_magra_kg", "ffmi_adj", "bmr_kcal", "tdee_kcal"):
        entry[k] = None


# ---------------------------------------------------------------------------
# LLM invocation via claude CLI
# ---------------------------------------------------------------------------

def run_agent(agent_type: Optional[str], prompt: str, timeout: int = 720) -> str:
    """Invoca claude CLI in modalita' non-interattiva."""
    cmd = [
        "claude", "--print",
        "--dangerously-skip-permissions",
        "--output-format", "text",
    ]
    if agent_type:
        cmd += ["--agent", agent_type]
    cmd.append(prompt)

    log("ACTION", f"LLM: {agent_type or 'default'}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            cwd=PROJECT_ROOT, timeout=timeout,
        )
        if result.returncode != 0:
            log("ERROR", f"Agente {agent_type} rc={result.returncode}: {result.stderr[:300]}")
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        log("ERROR", f"Timeout ({timeout}s) per agente {agent_type}")
        return ""


def run_agents_parallel(tasks: list) -> dict:
    """Lancia piu' agenti in parallelo. tasks = [(agent_type, prompt), ...]"""
    results: dict = {}
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {executor.submit(run_agent, ag, pr): ag for ag, pr in tasks}
        for future in as_completed(futures):
            ag = futures[future]
            try:
                results[ag or "default"] = future.result()
            except Exception as e:
                log("ERROR", f"Agente {ag} eccezione: {e}")
                results[ag or "default"] = ""
    return results


# ---------------------------------------------------------------------------
# Review JSON parsing
# ---------------------------------------------------------------------------

def parse_review(path: Path) -> tuple:
    """
    Legge un review JSON. Ritorna (approvato: bool, valutazione: int, problemi: list).
    Approvato = valutazione >= 8 AND nessun problema critico, oppure esito == APPROVATA.
    """
    if not path.exists():
        log("WARN", f"Review non trovato: {path.name} -considerato BOCCIATO")
        return False, 0, ["(file non trovato)"]
    try:
        data        = json.loads(path.read_text(encoding="utf-8"))
        meta        = data.get("meta", {}) or {}
        valutazione = int(meta.get("valutazione", 0))
        esito       = str(meta.get("esito", "")).upper()
        problemi    = data.get("problemi_critici", []) or []
        if not isinstance(problemi, list):
            problemi = [problemi]
        approvato = (valutazione >= 8 and len(problemi) == 0) or esito == "APPROVATA"
        return approvato, valutazione, problemi
    except json.JSONDecodeError as e:
        log("ERROR", f"JSON non valido in {path.name}: {e}")
        return False, 0, [f"JSON invalido: {e}"]
    except Exception as e:
        log("ERROR", f"Errore parsing review {path.name}: {e}")
        return False, 0, [str(e)]


# ---------------------------------------------------------------------------
# Archiving (Python puro, nessun LLM)
# ---------------------------------------------------------------------------

def archive_feedback() -> None:
    """Copia data/feedback_atleta.md -> data/output/feedback_atleta_(date).md."""
    src  = DATA_DIR / "feedback_atleta.md"
    dest = OUTPUT_DIR / f"feedback_atleta_{ITERATION_ID}.md"
    if src.exists():
        shutil.copy2(src, dest)
        log("OK", f"Archiviato: {dest.name}")
    else:
        log("WARN", "feedback_atleta.md non trovato -nessuna copia archiviata")


def archive_old_output_files() -> None:
    """
    Sposta i file di ITERAZIONI PRECEDENTI da data/output/ a data/output/history/YYYY/.
    I file correnti hanno suffisso _{ITERATION_ID} e restano in root.
    I file permanenti (measurements.json, plan.yaml) restano sempre in root.
    Per determinare l'anno di archivio si usa la data di modifica del file.
    """
    ALWAYS_KEEP = {"measurements.json", "plan.yaml"}
    # pattern: suffisso _<8 hex> prima dell'estensione
    suffix_re = re.compile(r"_([0-9a-f]{8})\.[^.]+$")

    for f in list(OUTPUT_DIR.iterdir()):
        if not f.is_file():
            continue
        if f.name in ALWAYS_KEEP:
            continue
        m = suffix_re.search(f.name)
        if not m:
            continue
        suffix = m.group(1)
        if suffix == ITERATION_ID:
            continue  # file dell'iterazione corrente -rimane

        # Anno da data di modifica del file
        year = str(datetime.fromtimestamp(f.stat().st_mtime).year)
        dest_dir = HISTORY_DIR / year
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f.name

        if not dest.exists():
            shutil.move(str(f), str(dest))
            log("OK", f"-> history/{year}/{f.name}")
        else:
            log("WARN", f"Gia' in history/{year}/{f.name} -non spostato")


def create_empty_feedback(next_label: str = "") -> None:
    """Sovrascrive data/feedback_atleta.md con il template vuoto."""
    header = f"# Feedback Atleta -{next_label}" if next_label else "# Feedback Atleta"
    template = f"""{header}
## Come ti sei sentito questo mese?
- **Energia generale**: (1-10)
- **Qualita' del sonno**: (1-10)
- **Stress**: (basso / medio / alto)

## Allenamento
- **Hai seguito la scheda?**: (si' / parzialmente / no)
- **Esercizi troppo pesanti / leggeri**:
- **Esercizi che hai trovato difficili o problematici**:
- **Note sull'allenamento**:

## Dieta
- **Hai seguito la dieta?**: (si' / parzialmente / no)
- **Difficolta' riscontrate**:
- **Note sulla dieta**:

## Progressi Percepiti
- **Ti senti piu' forte?**: (si' / no / uguale)
- **Cambiamenti fisici notati**:

## Massimali / Test del mese
Inserisci il peso e le ripetizioni fatte (es. 100 kg x 5). La conversione a 1RM viene calcolata automaticamente.
- **Squat**: kg x rep
- **Panca**: kg x rep
- **Stacco**: kg x rep

## Composizione Corporea
- **Peso (kg)**:
- **Misure** (opzionale):
    - Vita ombelico (cm):
    - Fianchi (cm):
    - Petto (cm):
    - Braccio dx (cm):
    - Coscia dx (cm):
    - Collo (cm):

## Altro
- **Infortuni o dolori**:
- **Commenti liberi**:
"""
    dest = DATA_DIR / "feedback_atleta.md"
    dest.write_text(template, encoding="utf-8")
    log("OK", f"Nuovo feedback_atleta.md creato ({next_label or 'prossima iterazione'})")


# ---------------------------------------------------------------------------
# Prompt builders -i dati vengono embeddati direttamente
# ---------------------------------------------------------------------------

def _rates_text(rates: dict) -> str:
    lines = ["RATE DI PROGRESSIONE STORICA (kg/anno, corretti):"]
    for lift, d in rates.items():
        flags = []
        if d["fattori"]["infortunio"]:  flags.append("infortunio -30%")
        if d["fattori"]["eta_over_35"]: flags.append("eta' -10%")
        if d["fattori"]["stallo"]:      flags.append("stallo -50%")
        flags_str = f"  [{', '.join(flags)}]" if flags else ""
        lines.append(
            f"  - {lift.capitalize()}: storico {d['media']} kg/anno "
            f"-> corretta {d['media_corretta']} kg/anno "
            f"(range {d['min']}..{d['max']}){flags_str}"
        )
    return "\n".join(lines)


def _last_n_measurements(measurements: list, n: int = 5) -> str:
    return json.dumps(measurements[-n:] if len(measurements) > n else measurements,
                      indent=2, ensure_ascii=False)


def _latest_file(pattern: str) -> str:
    files = sorted(OUTPUT_DIR.glob(pattern), reverse=True)
    return read_text(files[0]) if files else ""


def _schema_pt() -> str:
    """Ritorna lo schema JSON del review PT da includere nei prompt."""
    schema_path = PROJECT_ROOT / "source" / "schemas" / "review_pt.schema.json"
    return read_text(schema_path, default="(schema non trovato)")


def _performance_analysis_text() -> str:
    """Legge il report dell'analista performance se disponibile."""
    path = OUTPUT_DIR / "performance_analysis.yaml"
    text = read_text(path)
    if text:
        return f"## Analisi performance empirica (gym-performance-analyst)\n```yaml\n{text}\n```"
    return "## Analisi performance empirica\n(non disponibile - prima iterazione o analisi saltata)"



def build_plan_prompt(ctx: dict) -> str:
    return f"""Sei il personal trainer certificato del progetto fitness.
Genera il piano a lungo termine `data/output/plan.yaml` con la struttura standard.

## Profilo atleta
{ctx['athlete_text']}

## Obiettivi
{ctx['goals_text']}

## Preferenze
{ctx['preferences_text']}

## Feedback atleta corrente (PUNTO DI PARTENZA)
{ctx['feedback_text']}

## Piano precedente (se esiste)
{ctx['plan_text'] if ctx['plan_text'] else '(nessun piano precedente)'}

## Misurazioni storiche -ultime 5
```json
{_last_n_measurements(ctx['measurements'], 5)}
```

## {_rates_text(ctx['rates'])}

{_performance_analysis_text()}

## Istruzioni
- I target a 3/6/12 mesi DEVONO usare i rate corretti sopra -mai proiettare di piu'
- La somma settimane di tutte le fasi DEVE essere esattamente 52
- Infortuni e richieste dell'atleta hanno precedenza assoluta
- Considera le metodologie empiricamente efficaci dal report performance (se disponibile)
- Scrivi SOLO il file plan.yaml, nessun testo aggiuntivo"""


def build_plan_review_prompt(ctx: dict) -> str:
    plan_text = read_text(OUTPUT_DIR / "plan.yaml")
    return f"""Sei il personal trainer senior (revisore).
Valuta il piano a lungo termine appena generato in `data/output/plan.yaml`.

## Piano da revisionare
```yaml
{plan_text}
```

## Profilo atleta
{ctx['athlete_text']}

## Feedback corrente
{ctx['feedback_text']}

## {_rates_text(ctx['rates'])}

## Misurazioni storiche -ultime 5
```json
{_last_n_measurements(ctx['measurements'], 5)}
```

## Istruzioni
Scrivi il report in `data/output/review/pt/review_plan_{DATE_STR}.json` come JSON valido.

Schema richiesto:
```json
{_schema_pt()}
```

Regole:
- Valutazione >= 8 e problemi_critici vuoto -> esito APPROVATA, altrimenti BOCCIATA
- Correggi direttamente in plan.yaml gli errori di calcolo numerici (poi mettili in correzioni_applicate)
- Nessun testo fuori dal file JSON"""


def build_plan_regen_prompt(ctx: dict) -> str:
    return f"""Sei il personal trainer certificato. Il piano e' stato bocciato.
Leggi `data/output/review/pt/review_plan_{DATE_STR}.json` e correggi `data/output/plan.yaml`
applicando TUTTI i problemi_critici e i suggerimenti indicati.

## {_rates_text(ctx['rates'])}

## Dati disponibili per la rigenerazione
- Profilo: data/athlete.md
- Feedback archiviato: data/output/feedback_atleta_{ITERATION_ID}.md
- Misurazioni: data/output/measurements.json
- Obiettivi: data/goals | data/preferences

Leggi autonomamente la review e genera la versione corretta di plan.yaml."""


def _calc_efficacia_context(measurements: list, feedback_text: str) -> str:
    """
    Calcola i delta tra la nuova entry (oggi, risultati del mese) e quella precedente (inizio mese).
    La nuova entry e' measurements[-1], quella da valutare (penultima) e' measurements[-2].
    """
    if len(measurements) < 2:
        return "(storico insufficiente per calcolare delta)"

    prev = measurements[-2]   # inizio del periodo: da qui e' partita la scheda del mese scorso
    curr = measurements[-1]   # oggi: i risultati prodotti da quella scheda

    lines = ["DELTA RISPETTO AL MESE SCORSO (misura attuale - misura precedente):"]

    for label, key in [("Squat 1RM", "squat_1rm"), ("Panca 1RM", "panca_1rm"), ("Stacco 1RM", "stacco_1rm")]:
        c, p = curr.get(key), prev.get(key)
        if c is not None and p is not None:
            delta = round(c - p, 1)
            sign = "+" if delta >= 0 else ""
            lines.append(f"  - {label}: {p} -> {c} kg ({sign}{delta})")
        else:
            lines.append(f"  - {label}: dato mancante")

    for label, key in [("Peso", "peso_kg"), ("Body Fat %", "body_fat_pct"), ("Massa magra", "massa_magra_kg")]:
        c, p = curr.get(key), prev.get(key)
        if c is not None and p is not None:
            delta = round(c - p, 1)
            sign = "+" if delta >= 0 else ""
            lines.append(f"  - {label}: {p} -> {c} ({sign}{delta})")

    # Aderenza e stato soggettivo dal feedback
    patterns = [
        ("Aderenza scheda",   r"Hai seguito la scheda\?[^\n]*:\s*([^\n]+)"),
        ("Energia generale",  r"Energia generale[^\n]*:\s*([^\n]+)"),
        ("Qualita' sonno",    r"Qualita'?\s+del\s+sonno[^\n]*:\s*([^\n]+)"),
        ("Stress",            r"Stress[^\n]*:\s*([^\n]+)"),
    ]
    for label, pattern in patterns:
        m = re.search(pattern, feedback_text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if val and val not in ("(1-10)", "(basso / medio / alto)", "(si' / parzialmente / no)"):
                lines.append(f"  - {label}: {val}")

    return "\n".join(lines)


def build_feedback_coach_prompt(ctx: dict) -> str:
    # La nuova entry e' gia' in ctx["measurements"][-1] (aggiunta in fase 3a).
    # La penultima ([-2]) e' la scheda da valutare.
    efficacia_ctx = _calc_efficacia_context(ctx["measurements"], ctx["feedback_text"])

    return f"""Sei il coach del progetto fitness.
Genera il file `data/output/feedback_coach_{ITERATION_ID}.md`.

Il documento deve contenere le seguenti sezioni nell'ordine:

## Valutazione scheda precedente

La scheda del mese scorso ha prodotto questi risultati oggettivi:

{efficacia_ctx}

Analizza i risultati e assegna un voto `efficacia_workout` (intero 1-10) usando questa scala:
- 9-10: progressione eccellente su tutti i lift, composizione migliorata, aderenza alta, energia/sonno buoni
- 7-8:  progressione buona su almeno 2 lift, situazione stabile, stato soggettivo nella norma
- 5-6:  progressione minima o solo su 1 lift, aderenza parziale o stress/sonno negativi
- 3-4:  regressione o stallo, problemi di aderenza, energia bassa o stress alto
- 1-2:  regressione significativa, infortuni, aderenza molto bassa

Fattori contestuali:
- Infortunio in corso: non penalizzare i lift coinvolti, valuta solo quelli non interessati
- Stress alto o sonno scarso: attenua il giudizio (recupero compromesso indipendentemente dalla scheda)
- Aderenza parziale o assente: i risultati non riflettono la scheda, segnalalo

**IMPORTANTE**: il documento deve contenere esattamente questa riga (con il valore scelto):
`EFFICACIA_WORKOUT: <valore>`

Esempio: `EFFICACIA_WORKOUT: 7`

## Progressi del mese
Commento ai delta numerici sopra, punti di forza e aree di miglioramento.

## Risposta a infortuni e richieste
Rispondi a quanto segnalato dall'atleta nella sezione "Altro" del feedback.

## Indicazioni per il mese successivo
Consigli pratici su allenamento, recupero e nutrizione.

---

## Feedback atleta (input del mese)
{ctx['feedback_text']}

## Piano approvato (fase attuale)
{read_text(OUTPUT_DIR / 'plan.yaml')}

## {_rates_text(ctx['rates'])}

## Ultime 3 misurazioni
```json
{_last_n_measurements(ctx['measurements'], 3)}
```

Formato Markdown, tono professionale ma diretto."""


def write_efficacia_to_measurements(measurements: list) -> None:
    """
    Legge EFFICACIA_WORKOUT dal feedback_coach appena generato e lo scrive
    nella penultima entry di measurements.json (la scheda che viene valutata).
    """
    feedback_coach_path = OUTPUT_DIR / f"feedback_coach_{ITERATION_ID}.md"
    if not feedback_coach_path.exists():
        log("WARN", "feedback_coach non trovato — efficacia_workout non aggiornata")
        return

    text = feedback_coach_path.read_text(encoding="utf-8")
    m = re.search(r"EFFICACIA_WORKOUT:\s*(\d+)", text)
    if not m:
        log("WARN", "EFFICACIA_WORKOUT non trovata nel feedback_coach — misurazioni non aggiornate")
        return

    valore = int(m.group(1))
    if not (1 <= valore <= 10):
        log("WARN", f"EFFICACIA_WORKOUT={valore} fuori range 1-10 — ignorato")
        return

    if len(measurements) < 2:
        log("WARN", "Meno di 2 entry in measurements — nessuna penultima da aggiornare")
        return

    # La penultima entry e' la scheda da valutare
    target_data = measurements[-2].get("data", "?")
    measurements[-2]["efficacia_workout"] = valore

    measurements_path = OUTPUT_DIR / "measurements.json"
    measurements_path.write_text(
        json.dumps(measurements, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    log("OK", f"efficacia_workout={valore} scritto in entry {target_data}")


def build_diet_prompt(ctx: dict) -> str:
    last_diet = _latest_file("diet_*.yaml")
    return f"""Sei il dietologo del progetto fitness.
Genera la dieta settimanale `data/output/diet_{ITERATION_ID}.yaml`.

## Profilo atleta
{ctx['athlete_text']}

## Obiettivi e preferenze alimentari
{ctx['goals_text']}
{ctx['preferences_text']}

## Feedback atleta (aderenza dieta, difficolta')
{ctx['feedback_text']}

## Piano approvato (fase e fabbisogno)
{read_text(OUTPUT_DIR / 'plan.yaml')}

## Ultime 2 misurazioni (BMR/TDEE)
```json
{_last_n_measurements(ctx['measurements'], 2)}
```

## Dieta precedente (riferimento)
{last_diet if last_diet else '(nessuna dieta precedente)'}

## Istruzioni
- Adatta apporto calorico alla fase del piano (recupero / forza / ipertrofia / cut)
- Rispetta preferenze e difficolta' riportate
- Struttura: meta, giorni (7), integratori"""


def build_workout_prompt(ctx: dict) -> str:
    # Ultime 2 schede per contesto storico
    workout_files = sorted(OUTPUT_DIR.glob("workout_data_*.yaml"), reverse=True)[:2]
    workouts_text = "\n\n".join(
        f"### {f.name}\n{read_text(f)}" for f in workout_files
    ) or "(nessuna scheda precedente)"

    last_coach = _latest_file("feedback_coach_*.md")

    return f"""Sei il personal trainer certificato. Genera la scheda `data/output/workout_data_{ITERATION_ID}.yaml`.

## Profilo atleta
{ctx['athlete_text']}

## Obiettivi e preferenze
{ctx['goals_text']}
{ctx['preferences_text']}

## Feedback atleta corrente (PUNTO DI PARTENZA -infortuni hanno precedenza assoluta)
{ctx['feedback_text']}

## Feedback coach del mese
{last_coach if last_coach else '(nessuno)'}

## Piano annuale approvato
{read_text(OUTPUT_DIR / 'plan.yaml')}

## {_rates_text(ctx['rates'])}

## Ultime 3 misurazioni (massimali reali)
```json
{_last_n_measurements(ctx['measurements'], 3)}
```

## Schede precedenti
{workouts_text}

{_performance_analysis_text()}

## Istruzioni
- Infortuni -> escludi TUTTI gli esercizi che coinvolgono le aree interessate
- Test Day OBBLIGATORIO: ultimo giorno dell'ultima settimana con protocolli Squat/Panca/Stacco
- Aggiorna EXERCISE_MUSCLES in scripts/volume_calc.py per ogni nuovo esercizio
- Carichi basati sui massimali reali in measurements.json
- Privilegia le metodologie empiricamente efficaci dal report performance (se disponibile)"""


def build_workout_review_prompt(ctx: dict) -> str:
    workout_text = read_text(OUTPUT_DIR / f"workout_data_{ITERATION_ID}.yaml")

    return f"""Sei il personal trainer senior (revisore).
Valuta la scheda di allenamento appena generata.

## Scheda da revisionare
```yaml
{workout_text}
```

## Piano annuale approvato
{read_text(OUTPUT_DIR / 'plan.yaml')}

## Profilo e feedback atleta
{ctx['athlete_text']}
{ctx['feedback_text']}

## {_rates_text(ctx['rates'])}

## Ultime 3 misurazioni
```json
{_last_n_measurements(ctx['measurements'], 3)}
```

{_performance_analysis_text()}

## Istruzioni
Scrivi il report in `data/output/review/pt/review_workout_{DATE_STR}.json` come JSON valido.

Schema richiesto:
```json
{_schema_pt()}
```

Regole:
- Valutazione >= 8 e problemi_critici vuoto -> esito APPROVATA, altrimenti BOCCIATA
- Correggi direttamente nella scheda gli errori di calcolo numerici (poi mettili in correzioni_applicate)
- Verifica che la scheda privilegia le metodologie con efficacia storica alta (dal report performance)
- Nessun testo fuori dal file JSON"""


def build_workout_regen_prompt(ctx: dict) -> str:
    return f"""Sei il personal trainer certificato. La scheda e' stata bocciata.
Leggi `data/output/review/pt/review_workout_{DATE_STR}.json` e correggi `data/output/workout_data_{ITERATION_ID}.yaml`
applicando TUTTI i problemi_critici e i suggerimenti indicati.

## {_rates_text(ctx['rates'])}

## Dati disponibili
- Profilo: data/athlete.md
- Feedback archiviato: data/output/feedback_atleta_{ITERATION_ID}.md
- Piano: data/output/plan.yaml
- Misurazioni: data/output/measurements.json

Leggi autonomamente la review. Mantieni il Test Day nell'ultima settimana."""


# ---------------------------------------------------------------------------
# Caricamento dati (Python puro)
# ---------------------------------------------------------------------------

def load_all_data() -> dict:
    """Legge tutti i file di input necessari all'iterazione."""
    log("INFO", "Caricamento file dati...")

    athlete_text    = read_text(DATA_DIR / "athlete.md")
    feedback_text   = read_text(DATA_DIR / "feedback_atleta.md")
    goals_text      = _read_path_or_dir(DATA_DIR / "goals")
    preferences_text = _read_path_or_dir(DATA_DIR / "preferences")
    measurements_path = OUTPUT_DIR / "measurements.json"
    if not measurements_path.exists():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        previous_path = DATA_DIR / "previous_data.json"
        if previous_path.exists():
            seed = read_json(previous_path, default=[])
            measurements_path.write_text(
                json.dumps(seed, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            log("OK", f"measurements.json creato da previous_data.json ({len(seed)} entry)")
        else:
            measurements_path.write_text("[]", encoding="utf-8")
            log("OK", "measurements.json creato (lista vuota - previous_data.json non trovato)")
    measurements    = read_json(measurements_path, default=[])
    plan_text       = read_text(OUTPUT_DIR / "plan.yaml") or read_text(OUTPUT_DIR / "plan.html")

    log("INFO", f"  {len(measurements)} misurazioni storiche")
    log("INFO", f"  feedback_atleta.md: {len(feedback_text)} caratteri")

    return {
        "athlete_text":     athlete_text,
        "feedback_text":    feedback_text,
        "goals_text":       goals_text,
        "preferences_text": preferences_text,
        "measurements":     measurements,
        "plan_text":        plan_text,
        "rates":            {},   # compilato in fase 2
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-iter",    type=int,  default=3,     help="Iterazioni max loop revisione (default: 3)")
    parser.add_argument("--dry-run",     action="store_true",       help="Solo fase 1-2-3a (calcoli, nessun LLM)")
    args = parser.parse_args()

    MAX_ITER = args.max_iter
    plan_approved    = False
    workout_approved = False

    # ──────────────────────────────────────────────────────────────────
    # FASE 1 -Lettura dati
    # ──────────────────────────────────────────────────────────────────
    separator("FASE 1 -Lettura dati")
    ctx = load_all_data()

    # ──────────────────────────────────────────────────────────────────
    # FASE 2 -Calcoli
    # ──────────────────────────────────────────────────────────────────
    separator("FASE 2 -Calcoli progressione e composizione corporea")

    athlete_profile = parse_athlete_profile(ctx["athlete_text"])
    feedback        = parse_feedback(ctx["feedback_text"])

    log("INFO", f"Profilo: altezza={athlete_profile.get('altezza_cm')} cm, "
        f"sesso={athlete_profile.get('sesso')}, eta={athlete_profile.get('eta')} anni")
    log("INFO", f"Feedback: peso={feedback.get('peso_kg')} kg | "
        f"squat={feedback.get('squat_test')}, panca={feedback.get('panca_test')}, "
        f"stacco={feedback.get('stacco_test')}")

    rates_raw = calc_progression_rates(ctx["measurements"])
    rates     = apply_corrections(rates_raw, ctx["measurements"], ctx["feedback_text"])
    ctx["rates"] = rates

    print()
    print("RATE DI PROGRESSIONE STORICA:")
    for lift, d in rates.items():
        print(f"  - {lift.capitalize()}: storico {d['media']} kg/anno "
              f"-> corretta {d['media_corretta']} kg/anno "
              f"(range {d['min']}..{d['max']}, n={d['n']})")

    # ──────────────────────────────────────────────────────────────────
    # FASE 3a -Aggiorna measurements.json
    # ──────────────────────────────────────────────────────────────────
    separator("FASE 3a -Aggiornamento measurements.json")

    new_m = build_new_measurement(feedback, athlete_profile, ctx["measurements"])
    if new_m:
        if any(m.get("data") == DATE_STR for m in ctx["measurements"]):
            log("WARN", f"Entry {DATE_STR} gia' presente -non duplicata")
        else:
            ctx["measurements"].append(new_m)
            (OUTPUT_DIR / "measurements.json").write_text(
                json.dumps(ctx["measurements"], indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            log("OK", f"measurements.json aggiornato: BF%={new_m.get('body_fat_pct')}, "
                f"MM={new_m.get('massa_magra_kg')} kg, FFMI={new_m.get('ffmi_adj')}")
    else:
        log("SKIP", "measurements.json non aggiornato (dati insufficienti nel feedback)")

    if args.dry_run:
        log("INFO", "Dry-run: terminato. Nessun LLM invocato.")
        return

    # ──────────────────────────────────────────────────────────────────
    # FASE 3b -Piano a lungo termine
    # ──────────────────────────────────────────────────────────────────
    separator("FASE 3b -Generazione piano a lungo termine")
    REVIEW_PT_DIR.mkdir(parents=True, exist_ok=True)
    plan_review_path = REVIEW_PT_DIR / f"review_plan_{DATE_STR}.json"

    log("ACTION", "gym-personal-trainer -> plan.yaml")
    run_agent("gym-personal-trainer", build_plan_prompt(ctx))

    # Loop revisione piano
    for i in range(1, MAX_ITER + 1):
        separator(f"FASE 3b-loop -Revisione piano ({i}/{MAX_ITER})")
        log("ACTION", "gym-pt-senior-reviewer -> review_plan")
        run_agent("gym-pt-senior-reviewer", build_plan_review_prompt(ctx))

        approved, score, problems = parse_review(plan_review_path)
        log("INFO", f"Piano: valutazione={score}/10, approvato={approved}, "
            f"problemi_critici={len(problems)}")

        if approved:
            log("OK", f"Piano APPROVATO ({score}/10)")
            plan_approved = True
            break

        if i < MAX_ITER:
            log("WARN", f"Piano BOCCIATO -rigenerazione (iter {i + 1}/{MAX_ITER})")
            run_agent("gym-personal-trainer", build_plan_regen_prompt(ctx))

    if not plan_approved:
        log("WARN", f"Piano non approvato dopo {MAX_ITER} iterazioni -procedo con ultima versione")

    # ──────────────────────────────────────────────────────────────────
    # FASE 3c -Feedback coach
    # ──────────────────────────────────────────────────────────────────
    separator("FASE 3c -Generazione feedback coach")
    log("ACTION", f"gym-personal-trainer -> feedback_coach_{ITERATION_ID}.md")
    run_agent("gym-personal-trainer", build_feedback_coach_prompt(ctx))
    write_efficacia_to_measurements(ctx["measurements"])

    # ──────────────────────────────────────────────────────────────────
    # FASE 3d+3e -Dieta + Scheda in parallelo
    # ──────────────────────────────────────────────────────────────────
    separator("FASE 3d+3e -Dieta e scheda allenamento (parallelo)")
    log("ACTION", "gym-dietologo || gym-personal-trainer -> diet + workout_data")
    run_agents_parallel([
        ("gym-dietologo",        build_diet_prompt(ctx)),
        ("gym-personal-trainer", build_workout_prompt(ctx)),
    ])

    # ──────────────────────────────────────────────────────────────────
    # FASE 3f -Loop revisione scheda
    # ──────────────────────────────────────────────────────────────────
    workout_review_path = REVIEW_PT_DIR / f"review_workout_{DATE_STR}.json"

    for i in range(1, MAX_ITER + 1):
        separator(f"FASE 3f -Revisione scheda ({i}/{MAX_ITER})")
        log("ACTION", "gym-pt-senior-reviewer -> review_workout")
        run_agent("gym-pt-senior-reviewer", build_workout_review_prompt(ctx))

        approved, score, problems = parse_review(workout_review_path)
        log("INFO", f"Scheda: valutazione={score}/10, approvata={approved}, "
            f"problemi_critici={len(problems)}")

        if approved:
            log("OK", f"Scheda APPROVATA ({score}/10)")
            workout_approved = True
            break

        if i < MAX_ITER:
            log("WARN", f"Scheda BOCCIATA -rigenerazione (iter {i + 1}/{MAX_ITER})")
            run_agent("gym-personal-trainer", build_workout_regen_prompt(ctx))

    if not workout_approved:
        log("WARN", f"Scheda non approvata dopo {MAX_ITER} iterazioni -procedo con ultima versione")

    # ──────────────────────────────────────────────────────────────────
    # FASE 4 -Archiviazione
    # ──────────────────────────────────────────────────────────────────
    separator("FASE 4 -Archiviazione")

    # 4a. Copia feedback_atleta.md -> output/feedback_atleta_(date).md
    archive_feedback()

    # 4b. Sposta file vecchi -> history/YYYY/
    archive_old_output_files()

    # 4c. Crea nuovo feedback_atleta.md vuoto per la prossima iterazione
    m_today = TODAY.month
    y_today = TODAY.year
    if m_today == 12:
        next_m, next_y = 1, y_today + 1
    else:
        next_m, next_y = m_today + 1, y_today
    months_it = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
                 "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    next_label = f"{months_it[next_m - 1]} {next_y}"
    create_empty_feedback(next_label)

    # ──────────────────────────────────────────────────────────────────
    # Sommario finale
    # ──────────────────────────────────────────────────────────────────
    separator("SOMMARIO FINALE")
    print(f"DATA         : {DATE_STR}")
    print(f"ITERATION_ID : {ITERATION_ID}")
    print(f"PIANO        : {'APPROVATO' if plan_approved else 'NON APPROVATO (ultima versione)'}")
    print(f"SCHEDA       : {'APPROVATA' if workout_approved else 'NON APPROVATA (ultima versione)'}")
    print()
    print("FILE OUTPUT (data/output/):")
    for name in [
        "measurements.json",
        "performance_analysis.yaml",
        "plan.yaml",
        f"feedback_coach_{ITERATION_ID}.md",
        f"diet_{ITERATION_ID}.yaml",
        f"workout_data_{ITERATION_ID}.yaml",
        f"feedback_atleta_{ITERATION_ID}.md",
    ]:
        status = "OK" if (OUTPUT_DIR / name).exists() else "MANCANTE"
        print(f"  [{status}] {name}")

    print()
    print("REVIEW:")
    print(f"  {REVIEW_PT_DIR / f'review_plan_{DATE_STR}.json'}")
    print(f"  {REVIEW_PT_DIR / f'review_workout_{DATE_STR}.json'}")

    if not (plan_approved and workout_approved):
        sys.exit(1)


if __name__ == "__main__":
    main()
