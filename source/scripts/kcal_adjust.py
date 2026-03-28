"""
kcal_adjust.py — Adattamento automatico delle calorie giornaliere.

Legge measurements.json (e opzionalmente measurements-temp.json) e calcola
l'aggiustamento calorico raccomandato in base a progressi reali e fase.
Incorpora feedback_atleta.yaml per calcolare l'attendibilita' delle variazioni.
Tiene conto del dispendio calorico da altre attivita' (corsa, ciclismo, ecc.).

Uso:
    python source/scripts/kcal_adjust.py --fase cut --kcal-attuali 2400
    python source/scripts/kcal_adjust.py --fase bulk --kcal-attuali 3100
    python source/scripts/kcal_adjust.py --fase cut --kcal-attuali 2400 --kcal-extra-settimana 1200
    python source/scripts/kcal_adjust.py --fase cut --kcal-attuali 2400 --temp data/measurements-temp.json
"""

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).parent.parent
MEASUREMENTS_PATH = ROOT / "data" / "output" / "measurements.json"
TEMP_PATH         = ROOT / "data" / "measurements-temp.json"
FEEDBACK_PATH     = ROOT / "data" / "feedback_atleta.yaml"

MAX_DELTA  = 200
STEP       = 150
STEP_SMALL = 75


# ---------------------------------------------------------------------------
# Helpers — I/O
# ---------------------------------------------------------------------------

def load_json(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_feedback(path: Path) -> dict:
    if not path.exists():
        return {}
    if yaml is None:
        # fallback minimale senza pyyaml
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
# Helpers — metriche
# ---------------------------------------------------------------------------

def days_between(a: dict, b: dict) -> float:
    return (parse_date(b["data"]) - parse_date(a["data"])).days


def weight_loss_pct_per_week(prev: dict, curr: dict) -> float | None:
    days = days_between(prev, curr)
    if days <= 0:
        return None
    delta_kg = prev["peso_kg"] - curr["peso_kg"]
    return (delta_kg / prev["peso_kg"]) * 100 / (days / 7)


def weight_gain_pct_per_week(prev: dict, curr: dict) -> float | None:
    days = days_between(prev, curr)
    if days <= 0:
        return None
    delta_kg = curr["peso_kg"] - prev["peso_kg"]
    return (delta_kg / prev["peso_kg"]) * 100 / (days / 7)


def lean_mass_loss_ratio(prev: dict, curr: dict) -> float | None:
    mm_prev = prev.get("massa_magra_kg")
    mm_curr = curr.get("massa_magra_kg")
    if mm_prev is None or mm_curr is None:
        return None
    total_loss = prev["peso_kg"] - curr["peso_kg"]
    if total_loss <= 0:
        return None
    return (mm_prev - mm_curr) / total_loss


def strength_change_pct_per_week(prev: dict, curr: dict) -> float | None:
    fields = ["squat_1rm", "panca_1rm", "stacco_1rm"]
    prev_vals = [prev.get(f) for f in fields]
    curr_vals = [curr.get(f) for f in fields]
    if any(v is None for v in prev_vals + curr_vals):
        return None
    prev_tot = sum(prev_vals)
    curr_tot = sum(curr_vals)
    days = days_between(prev, curr)
    if days <= 0 or prev_tot == 0:
        return None
    return ((curr_tot - prev_tot) / prev_tot) * 100 / (days / 7)


def waist_change(prev: dict, curr: dict) -> float | None:
    v_prev = prev.get("vita_cm")
    v_curr = curr.get("vita_cm")
    if v_prev is None or v_curr is None:
        return None
    return v_curr - v_prev


def bf_targets(bf: float) -> dict:
    if bf < 12:
        return {"cut_min": 0.3, "cut_max": 0.5, "bulk_min": 0.1,  "bulk_max": 0.25}
    elif bf <= 18:
        return {"cut_min": 0.5, "cut_max": 0.7, "bulk_min": 0.25, "bulk_max": 0.5}
    else:
        return {"cut_min": 0.7, "cut_max": 1.0, "bulk_min": None, "bulk_max": None}


# ---------------------------------------------------------------------------
# Attendibilita'
# ---------------------------------------------------------------------------

def calc_attendibilita(feedback: dict, kcal_attuali: int) -> tuple[float, list[str]]:
    """
    Calcola un coefficiente di attendibilita' [0.0 - 1.0] basandosi su:
    - dieta.seguita          (si / parzialmente / no)
    - dieta.kcal_media_stimata  (scarto rispetto al target)

    Ritorna (coefficiente, [note_attendibilita]).
    """
    notes = []
    dieta = feedback.get("dieta", {}) or {}

    seguita_raw = (dieta.get("seguita") or "").strip().lower()
    kcal_stimata = dieta.get("kcal_media_stimata")

    # Base da aderenza dichiarata
    if seguita_raw == "si":
        base = 1.0
        notes.append("Dieta dichiarata seguita: attendibilita' base 100%")
    elif seguita_raw == "parzialmente":
        base = 0.5
        notes.append("Dieta dichiarata seguita parzialmente: attendibilita' base 50%")
    elif seguita_raw == "no":
        base = 0.0
        notes.append("Dieta dichiarata NON seguita: attendibilita' 0% — le variazioni di peso non riflettono la dieta")
        return 0.0, notes
    else:
        base = 0.7  # dato mancante, assumiamo aderenza parziale
        notes.append("Aderenza dieta non dichiarata: attendibilita' base 70% (default)")

    # Correzione da scarto kcal_media_stimata
    if kcal_stimata and kcal_attuali:
        try:
            kcal_stimata = float(kcal_stimata)
            scarto = abs(kcal_stimata - kcal_attuali)
            scarto_pct = scarto / kcal_attuali

            if scarto_pct <= 0.05:
                corr = 0.0
                notes.append(f"Kcal stimata {kcal_stimata:.0f} vs target {kcal_attuali} (scarto {scarto:.0f} kcal, {scarto_pct*100:.1f}%): coerente, nessuna correzione")
            elif scarto_pct <= 0.10:
                corr = -0.1
                notes.append(f"Kcal stimata {kcal_stimata:.0f} vs target {kcal_attuali} (scarto {scarto:.0f} kcal, {scarto_pct*100:.1f}%): scarto lieve, -10% attendibilita'")
            elif scarto_pct <= 0.20:
                corr = -0.25
                notes.append(f"Kcal stimata {kcal_stimata:.0f} vs target {kcal_attuali} (scarto {scarto:.0f} kcal, {scarto_pct*100:.1f}%): scarto moderato, -25% attendibilita'")
            else:
                corr = -0.40
                notes.append(f"Kcal stimata {kcal_stimata:.0f} vs target {kcal_attuali} (scarto {scarto:.0f} kcal, {scarto_pct*100:.1f}%): scarto elevato, -40% attendibilita'")

            base = max(0.0, base + corr)
        except (ValueError, TypeError):
            notes.append("kcal_media_stimata non parsabile, ignorata")

    return round(base, 2), notes


def apply_attendibilita(delta: int, attendibilita: float) -> int:
    """
    Scala il delta in base all'attendibilita'.
    Sotto 0.3 il delta e' azzerato (segnale troppo rumoroso).
    Tra 0.3 e 0.7 il delta e' dimezzato.
    Sopra 0.7 il delta e' pieno.
    """
    if attendibilita < 0.3:
        return 0
    elif attendibilita < 0.7:
        return round(delta * 0.5)
    else:
        return delta


# ---------------------------------------------------------------------------
# Logica cut / bulk / mantenimento
# ---------------------------------------------------------------------------

def analyze_mantenimento(prev: dict, curr: dict) -> tuple[int, list[str]]:
    reasons = []

    loss_pct     = weight_loss_pct_per_week(prev, curr)
    gain_pct     = weight_gain_pct_per_week(prev, curr)
    mm_ratio     = lean_mass_loss_ratio(prev, curr)
    strength_chg = strength_change_pct_per_week(prev, curr)
    waist_chg    = waist_change(prev, curr)

    # M1-M3 — perdita peso / catabolismo: TDEE sottostimato
    muscle_alarm = False
    if loss_pct is not None and loss_pct > 0.5:
        reasons.append(f"M1: perdita peso {loss_pct:.2f}%/sett > 0.5% in normocalorica (TDEE sottostimato)")
        muscle_alarm = True
    if mm_ratio is not None and mm_ratio > 0.25:
        reasons.append(f"M2: massa magra persa = {mm_ratio*100:.0f}% della perdita totale (soglia 25%) — catabolismo")
        muscle_alarm = True
    if strength_chg is not None and strength_chg < -5.0:
        reasons.append(f"M3: forza -{abs(strength_chg):.1f}%/sett (soglia -5%) — segnale catabolico")
        muscle_alarm = True
    if muscle_alarm:
        return +STEP, reasons

    # M4 — guadagno eccessivo: TDEE sovrastimato
    if gain_pct is not None and gain_pct > 0.5:
        if waist_chg is not None and waist_chg > 0.5:
            reasons.append(f"M4: guadagno {gain_pct:.2f}%/sett > 0.5% e vita +{waist_chg:.1f} cm (TDEE sovrastimato)")
            return -STEP_SMALL, reasons

    if not reasons:
        reasons.append(
            f"Mantenimento nella norma: variazione peso {loss_pct:.2f}%/sett" if loss_pct is not None
            else "Dati insufficienti per analisi"
        )
    return 0, reasons


def analyze_cut(prev: dict, curr: dict, targets: dict) -> tuple[int, list[str]]:
    reasons = []
    delta = 0

    loss_pct    = weight_loss_pct_per_week(prev, curr)
    mm_ratio    = lean_mass_loss_ratio(prev, curr)
    strength_chg = strength_change_pct_per_week(prev, curr)
    waist_chg   = waist_change(prev, curr)

    # P1 — protezione massa muscolare
    muscle_alarm = False
    if loss_pct is not None and loss_pct > 1.0:
        reasons.append(f"P1: perdita peso {loss_pct:.2f}%/sett > 1% BW")
        muscle_alarm = True
    if mm_ratio is not None and mm_ratio > 0.25:
        reasons.append(f"P1: massa magra persa = {mm_ratio*100:.0f}% della perdita totale (soglia 25%)")
        muscle_alarm = True
    if strength_chg is not None and strength_chg < -5.0:
        reasons.append(f"P1: forza -{abs(strength_chg):.1f}%/sett (soglia -5%)")
        muscle_alarm = True
    if muscle_alarm:
        return +STEP, reasons

    # P2 — cut inefficace
    if loss_pct is not None and loss_pct < 0.3:
        if waist_chg is not None and abs(waist_chg) < 0.5:
            reasons.append(f"P2: perdita peso {loss_pct:.2f}%/sett < 0.3% e vita stabile ({waist_chg:+.1f} cm)")
            return -STEP, reasons

    # P3 — cut subottimale
    cut_min = targets["cut_min"]
    if loss_pct is not None and cut_min <= loss_pct < 0.5:
        reasons.append(f"P3: perdita peso {loss_pct:.2f}%/sett sotto target ({cut_min}-{targets['cut_max']}%)")
        return -STEP_SMALL, reasons

    if not reasons:
        reasons.append(
            f"Cut nella norma: perdita {loss_pct:.2f}%/sett" if loss_pct is not None
            else "Dati insufficienti per analisi"
        )
    return 0, reasons


def analyze_bulk(prev: dict, curr: dict, targets: dict) -> tuple[int, list[str]]:
    reasons = []

    gain_pct  = weight_gain_pct_per_week(prev, curr)
    waist_chg = waist_change(prev, curr)

    if targets["bulk_min"] is None:
        reasons.append("ATTENZIONE: BF > 18%, bulk sconsigliato")
        return 0, reasons

    # P4 — bulk eccessivo
    if gain_pct is not None and gain_pct > 0.75:
        if waist_chg is not None and waist_chg > 1.0:
            reasons.append(f"P4: guadagno {gain_pct:.2f}%/sett > 0.75% e vita +{waist_chg:.1f} cm")
            return -STEP, reasons

    # P5 — bulk inefficace
    if gain_pct is not None and gain_pct < 0.1:
        reasons.append(f"P5: guadagno {gain_pct:.2f}%/sett < 0.1%/sett")
        return +STEP, reasons

    # P6 — bulk lento
    bulk_min = targets["bulk_min"]
    if gain_pct is not None and 0.1 <= gain_pct < bulk_min:
        reasons.append(f"P6: guadagno {gain_pct:.2f}%/sett sotto target ({bulk_min}-{targets['bulk_max']}%)")
        return +STEP_SMALL, reasons

    if not reasons:
        reasons.append(
            f"Bulk nella norma: guadagno {gain_pct:.2f}%/sett" if gain_pct is not None
            else "Dati insufficienti per analisi"
        )
    return 0, reasons


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run(fase: str, kcal_attuali: int, temp_path: Path | None, kcal_extra_settimana: int = 0) -> None:
    # Carica misurazioni
    measurements = load_json(MEASUREMENTS_PATH)
    if temp_path and temp_path.exists():
        measurements = sorted(measurements + load_json(temp_path), key=lambda x: x["data"])

    if len(measurements) < 2:
        print("ERRORE: servono almeno 2 misurazioni per l'analisi.")
        sys.exit(1)

    prev, curr = measurements[-2], measurements[-1]

    days = days_between(prev, curr)
    if days < 7:
        print(f"ATTENZIONE: solo {days} giorni tra le ultime 2 misurazioni — attendi almeno 7 giorni.")
        sys.exit(0)

    # Carica feedback e calcola attendibilita'
    feedback = load_feedback(FEEDBACK_PATH)
    attendibilita, att_notes = calc_attendibilita(feedback, kcal_attuali)

    # Kcal extra da altre attivita'
    kcal_extra_giorno = round(kcal_extra_settimana / 7) if kcal_extra_settimana > 0 else 0

    # Analisi fisiologica
    bf_curr = curr.get("body_fat_pct")
    targets = bf_targets(bf_curr if bf_curr is not None else 15)

    if fase == "cut":
        delta_raw, reasons = analyze_cut(prev, curr, targets)
    elif fase == "bulk":
        delta_raw, reasons = analyze_bulk(prev, curr, targets)
    else:
        delta_raw, reasons = analyze_mantenimento(prev, curr)

    # Applica attendibilita' al delta
    delta = apply_attendibilita(delta_raw, attendibilita)
    delta = max(-MAX_DELTA, min(MAX_DELTA, delta))
    nuove_kcal = kcal_attuali + delta + kcal_extra_giorno

    # --- Output ---
    print("=" * 62)
    print(f"ANALISI CALORICA — fase: {fase.upper()}")
    print(f"Periodo: {prev['data']} -> {curr['data']} ({days} giorni)")
    print(f"Peso:    {prev['peso_kg']} kg -> {curr['peso_kg']} kg")
    if bf_curr:
        target_str = (f"cut {targets['cut_min']}-{targets['cut_max']}%/sett"
                      if fase == "cut"
                      else f"bulk {targets['bulk_min']}-{targets['bulk_max']}%/sett")
        print(f"BF%:     {bf_curr}%  (target {target_str})")

    print("-" * 62)
    print("Attendibilita' aderenza dieta:")
    for n in att_notes:
        print(f"  - {n}")
    print(f"  => Coefficiente: {attendibilita:.0%}")

    print("-" * 62)
    print("Analisi fisiologica:")
    for r in reasons:
        print(f"  - {r}")

    if kcal_extra_settimana > 0:
        print("-" * 62)
        print("Altre attivita' (dispendio extra):")
        print(f"  {kcal_extra_settimana} kcal/sett  =>  +{kcal_extra_giorno} kcal/die in media")
        print("  NOTA: il dietologo deve distribuire questo extra per tipo di giorno")

    print("-" * 62)
    if delta_raw != delta:
        print(f"Delta adattamento: {delta_raw:+d} kcal grezzo -> {delta:+d} kcal dopo attendibilita'")
    if kcal_extra_giorno > 0:
        print(f"Delta attivita' extra: +{kcal_extra_giorno} kcal/die (media)")
    total_delta = delta + kcal_extra_giorno
    if total_delta > 0:
        print(f"RACCOMANDAZIONE: +{total_delta} kcal/die (adattamento {delta:+d} + attivita' extra {kcal_extra_giorno:+d})")
    elif total_delta < 0:
        print(f"RACCOMANDAZIONE: {total_delta} kcal/die (adattamento {delta:+d} + attivita' extra {kcal_extra_giorno:+d})")
    else:
        if attendibilita < 0.3 and delta_raw != 0:
            print(f"RACCOMANDAZIONE: nessuna modifica (attendibilita' {attendibilita:.0%} insufficiente per agire)")
        else:
            print("RACCOMANDAZIONE: nessuna modifica")
    print(f"Kcal attuali:    {kcal_attuali} kcal/die")
    print(f"Kcal suggerite:  {nuove_kcal} kcal/die")
    print("=" * 62)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Adattamento automatico kcal giornaliere")
    parser.add_argument("--fase", required=True, choices=["cut", "bulk", "mantenimento"])
    parser.add_argument("--kcal-attuali", required=True, type=int,
                        help="Kcal giornaliere attuali (target base)")
    parser.add_argument("--temp", type=Path, default=None,
                        help="Path opzionale a measurements-temp.json")
    parser.add_argument("--kcal-extra-settimana", type=int, default=0,
                        help="Kcal extra settimanali da altre attivita' (corsa, ciclismo, ecc.)")
    args = parser.parse_args()

    temp = args.temp or (TEMP_PATH if TEMP_PATH.exists() else None)
    run(args.fase, args.kcal_attuali, temp, args.kcal_extra_settimana)
