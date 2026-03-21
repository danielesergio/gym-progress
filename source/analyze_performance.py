#!/usr/bin/env python3
"""
Invoca gym-performance-analyst con analisi guidata.

Modalita':
  completa       Analizza tutti i periodi e tutte le schede disponibili.
  funziona       Focalizzata sui periodi con i migliori risultati per lift.
  non_funziona   Focalizzata sui periodi con i peggiori risultati o stallo.

In base alla modalita' e ai dati di measurements.json, lo script seleziona
quali periodi e file l'agente deve leggere, riducendo il rumore.

Uso:
    python source/analyze_performance.py
    python source/analyze_performance.py --mode funziona
    python source/analyze_performance.py --mode non_funziona --lift squat
    python source/analyze_performance.py --mode completa --output report_custom.yaml
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR     = PROJECT_ROOT / "data"
OUTPUT_DIR   = DATA_DIR / "output"
HISTORY_DIR  = OUTPUT_DIR / "history"

LIFTS = ["squat", "panca", "stacco"]
LIFT_KEYS = {"squat": "squat_1rm", "panca": "panca_1rm", "stacco": "stacco_1rm"}


# ---------------------------------------------------------------------------
# Parsing measurements
# ---------------------------------------------------------------------------

def load_measurements() -> list:
    path = OUTPUT_DIR / "measurements.json"
    if not path.exists():
        print(f"[ERROR] measurements.json non trovato in {OUTPUT_DIR}")
        sys.exit(1)
    data = json.loads(path.read_text(encoding="utf-8"))
    if len(data) < 2:
        print("[ERROR] measurements.json ha meno di 2 entry — analisi impossibile")
        sys.exit(1)
    return data


def compute_periods(measurements: list) -> list:
    """
    Calcola i delta tra entry consecutive.
    Ritorna lista di dict con dati del periodo.
    """
    periods = []
    for i in range(1, len(measurements)):
        prev = measurements[i - 1]
        curr = measurements[i]

        try:
            d0 = datetime.strptime(prev["data"], "%Y-%m-%d").date()
            d1 = datetime.strptime(curr["data"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue

        days = (d1 - d0).days
        if days <= 0:
            continue
        years = days / 365.25

        period = {
            "idx":         i,
            "data_inizio": str(d0),
            "data_fine":   str(d1),
            "giorni":      days,
            "id_scheda":   prev.get("id"),          # la scheda da valutare e' quella di prev
            "efficacia":   prev.get("efficacia_workout"),
            "note":        prev.get("note", ""),
            "delta":       {},
            "delta_anno":  {},
        }

        for lift, key in LIFT_KEYS.items():
            c, p = curr.get(key), prev.get(key)
            if c is not None and p is not None:
                d = round(c - p, 1)
                period["delta"][lift]      = d
                period["delta_anno"][lift] = round(d / years, 1)
            else:
                period["delta"][lift]      = None
                period["delta_anno"][lift] = None

        periods.append(period)

    return periods


# ---------------------------------------------------------------------------
# Selezione periodi per modalita'
# ---------------------------------------------------------------------------

def _delta_anno_score(period: dict, lifts: list) -> float:
    """Score medio normalizzato per i lift richiesti (ignora None)."""
    vals = [period["delta_anno"][l] for l in lifts if period["delta_anno"].get(l) is not None]
    return sum(vals) / len(vals) if vals else 0.0


def select_periods(periods: list, mode: str, lifts: list) -> tuple:
    """
    Ritorna (periodi_selezionati, descrizione_selezione).
    """
    if mode == "completa":
        return periods, "tutti i periodi disponibili"

    scored = [(p, _delta_anno_score(p, lifts)) for p in periods]
    scored.sort(key=lambda x: x[1], reverse=(mode == "funziona"))

    # Prende il terzo migliore/peggiore, minimo 1
    n = max(1, len(periods) // 3)
    selected = [p for p, _ in scored[:n]]

    if mode == "funziona":
        desc = f"top {n} periodo/i per progressione su {', '.join(lifts)}"
    else:
        desc = f"bottom {n} periodo/i per progressione su {', '.join(lifts)}"

    return selected, desc


# ---------------------------------------------------------------------------
# Ricerca file schede e feedback
# ---------------------------------------------------------------------------

def _find_file(name: str) -> Path | None:
    """Cerca un file in output/ e in tutti gli history/<anno>/."""
    for candidate in [OUTPUT_DIR / name] + sorted(HISTORY_DIR.glob(f"*/{name}")):
        if candidate.exists():
            return candidate
    return None


def resolve_files(periods: list) -> dict:
    """
    Per ogni periodo selezionato, trova i file esistenti.
    Ritorna dict: id_scheda -> {workout, feedback_atleta, feedback_coach}
    """
    resolved = {}
    for p in periods:
        sid = p.get("id_scheda")
        if not sid:
            resolved[p["data_fine"]] = {"workout": None, "feedback_atleta": None, "feedback_coach": None}
            continue

        resolved[sid] = {
            "workout":          _find_file(f"workout_data_{sid}.yaml"),
            "feedback_atleta":  _find_file(f"feedback_atleta_{sid}.md"),
            "feedback_coach":   _find_file(f"feedback_coach_{sid}.md"),
        }
    return resolved


# ---------------------------------------------------------------------------
# Costruzione prompt
# ---------------------------------------------------------------------------

def _period_summary(period: dict) -> str:
    lines = [
        f"  Periodo: {period['data_inizio']} -> {period['data_fine']} ({period['giorni']} giorni)",
        f"  ID scheda: {period.get('id_scheda') or 'N/A'}",
        f"  Efficacia dichiarata: {period['efficacia'] if period['efficacia'] is not None else 'non registrata'}",
    ]
    for lift in LIFTS:
        d  = period["delta"].get(lift)
        da = period["delta_anno"].get(lift)
        if d is not None:
            sign = "+" if d >= 0 else ""
            lines.append(f"  - {lift.capitalize()}: {sign}{d} kg ({sign}{da} kg/anno)")
        else:
            lines.append(f"  - {lift.capitalize()}: dato mancante")
    if period.get("note"):
        lines.append(f"  Note: {period['note']}")
    return "\n".join(lines)


def _files_section(resolved: dict) -> str:
    lines = ["File da leggere per ogni periodo (percorsi relativi dalla root del progetto):"]
    for sid, files in resolved.items():
        lines.append(f"\n  ID / chiave: {sid}")
        for label, path in files.items():
            if path:
                lines.append(f"    - {label}: {path.relative_to(PROJECT_ROOT)}")
            else:
                lines.append(f"    - {label}: (non trovato)")
    return "\n".join(lines)


def build_prompt(
    mode: str,
    lifts: list,
    periods: list,
    selection_desc: str,
    resolved: dict,
    output_file: str,
) -> str:

    focus_map = {
        "completa":      "Analisi completa: individua pattern trasversali — cosa distingue i periodi migliori da quelli peggiori per ciascun lift.",
        "funziona":      "Analisi focalizzata su COSA HA FUNZIONATO: identifica le caratteristiche comuni (frequenza, volume, intensita', tecniche, stato soggettivo) dei periodi con la migliore progressione. Formula ipotesi falsificabili su cosa replicare.",
        "non_funziona":  "Analisi focalizzata su COSA NON HA FUNZIONATO: identifica le caratteristiche comuni dei periodi con peggior progressione o regressione. Distingui cause metodologiche (scheda sbagliata) da cause esterne (infortuni, stress, aderenza bassa). Formula ipotesi su cosa evitare.",
    }

    lifts_str = ", ".join(l.capitalize() for l in lifts)
    periods_text = "\n\n".join(_period_summary(p) for p in periods)

    return f"""Sei l'analista delle performance atletiche del progetto fitness.

## Modalita' di analisi: {mode.upper()}

Lift da analizzare: {lifts_str}
Periodi selezionati ({selection_desc}):

{periods_text}

---

## Focus dell'analisi

{focus_map[mode]}

---

## {_files_section(resolved)}

Leggi SOLO i file elencati sopra (quelli contrassegnati come "non trovato" saltali).
Non leggere altri file oltre a quelli indicati, salvo `data/output/measurements.json` che puoi sempre consultare.

---

## Output

Scrivi il report in `data/output/{output_file}` seguendo la struttura YAML definita nel tuo ruolo.

Nel campo `meta.note_analisi` specifica:
- La modalita' usata ({mode})
- I periodi inclusi e il criterio di selezione
- I lift analizzati ({lifts_str})
- Eventuali limitazioni (schede mancanti, infortuni come variabili confondenti, ecc.)

Confidenza onesta: con pochi campioni scrivi "bassa" — non estrapolare oltre i dati."""


# ---------------------------------------------------------------------------
# Invocazione agente
# ---------------------------------------------------------------------------

def run_analyst(prompt: str, timeout: int = 900) -> None:
    cmd = [
        "claude", "--print",
        "--dangerously-skip-permissions",
        "--output-format", "text",
        "--agent", "gym-performance-analyst",
    ]
    print("\n[ACTION] gym-performance-analyst avviato...\n")
    try:
        result = subprocess.run(
            cmd, input=prompt, capture_output=False, text=True,
            encoding="utf-8", errors="replace",
            cwd=PROJECT_ROOT, timeout=timeout,
        )
        if result.returncode != 0:
            print(f"[ERROR] agente terminato con rc={result.returncode}")
    except subprocess.TimeoutExpired:
        print(f"[ERROR] Timeout ({timeout}s)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["completa", "funziona", "non_funziona"],
        default=None,
        help="Modalita' di analisi (default: selezione interattiva)",
    )
    parser.add_argument(
        "--lift", "-l",
        choices=LIFTS + ["tutti"],
        default="tutti",
        help="Lift da analizzare (default: tutti)",
    )
    parser.add_argument(
        "--output", "-o",
        default="performance_analysis.yaml",
        help="Nome file output in data/output/ (default: performance_analysis.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra il prompt senza invocare l'agente",
    )
    parser.add_argument(
        "--log-context",
        action="store_true",
        help="Logga file e info calcolate passati nel prompt dell'agente",
    )
    args = parser.parse_args()

    def log_context(agent: str, files: list, calcs: list = None) -> None:
        if not args.log_context:
            return
        LABEL = {
            "incorporato":  "Incorporato  ",
            "obbligatorio": "Da leggere   ",
            "discrezione":  "A discrezione",
        }
        print(f"\n  [CONTEXT] {agent}")
        for path_raw, modalita in files:
            p = path_raw if isinstance(path_raw, Path) else Path(path_raw)
            abs_p = p if p.is_absolute() else PROJECT_ROOT / p
            stato = f"{abs_p.stat().st_size:>7} B" if abs_p.exists() else "  MANCANTE"
            rel = abs_p.relative_to(PROJECT_ROOT) if abs_p.is_relative_to(PROJECT_ROOT) else abs_p
            print(f"    [{LABEL.get(modalita, modalita)}] {rel}  ({stato})")
        for desc in (calcs or []):
            print(f"    [Info calcolata ] {desc}")

    # Selezione interattiva se non passata da CLI
    mode = args.mode
    if not mode:
        print("\nModalita' di analisi:")
        print("  1. completa      — tutti i periodi, pattern trasversali")
        print("  2. funziona      — top periodi per progressione")
        print("  3. non_funziona  — bottom periodi, cosa evitare")
        choice = input("\nScelta [1/2/3]: ").strip()
        mode = {"1": "completa", "2": "funziona", "3": "non_funziona"}.get(choice, "completa")
        print(f"Modalita' selezionata: {mode}\n")

    lifts = LIFTS if args.lift == "tutti" else [args.lift]

    # Carica e calcola
    measurements = load_measurements()
    periods      = compute_periods(measurements)

    print(f"[INFO] {len(measurements)} misurazioni, {len(periods)} periodi calcolati")
    print(f"[INFO] Lift: {', '.join(lifts)} | Modalita': {mode}")

    # Selezione periodi
    selected, selection_desc = select_periods(periods, mode, lifts)
    print(f"[INFO] Periodi selezionati: {len(selected)} ({selection_desc})")

    # Risolvi file
    resolved = resolve_files(selected)
    found    = sum(1 for files in resolved.values() for p in files.values() if p)
    print(f"[INFO] File trovati: {found} / {len(resolved) * 3} possibili")

    # Stampa riepilogo periodi
    print("\nPeriodi inclusi nell'analisi:")
    for p in selected:
        scores = {l: p["delta_anno"].get(l) for l in lifts}
        score_str = ", ".join(
            f"{l}: {('+' if v >= 0 else '')}{v} kg/a" if v is not None else f"{l}: N/A"
            for l, v in scores.items()
        )
        eff = p["efficacia"]
        eff_str = f" | efficacia={eff}" if eff is not None else ""
        print(f"  {p['data_inizio']} -> {p['data_fine']}  [{score_str}]{eff_str}")

    # Costruisci prompt
    prompt = build_prompt(mode, lifts, selected, selection_desc, resolved, args.output)

    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN — prompt che verrebbe inviato all'agente:")
        print("=" * 60)
        print(prompt)
        return

    confirm = input("\nProcedere con l'analisi? [s/N]: ").strip().lower()
    if confirm != "s":
        print("Annullato.")
        return

    # Costruisci lista file per log_context
    period_files = []
    period_files.append((OUTPUT_DIR / "measurements.json", "obbligatorio"))
    for sid, files in resolved.items():
        for label, path in files.items():
            if path:
                period_files.append((path, "obbligatorio"))
    log_context("gym-performance-analyst", period_files, [
        f"Modalita': {mode} | Lift: {', '.join(lifts)}",
        f"Periodi selezionati: {len(selected)} ({selection_desc})",
        "Delta massimali e delta/anno per periodo (calcolati da Python)",
    ])

    run_analyst(prompt)

    output_path = OUTPUT_DIR / args.output
    if output_path.exists():
        print(f"\n[OK] Report scritto: {output_path}")
    else:
        print(f"\n[WARN] {args.output} non trovato in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
