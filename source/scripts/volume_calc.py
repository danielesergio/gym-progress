#!/usr/bin/env python3
"""
Calcolatore volume allenante per distretto muscolare.

Legge la scheda workout (markdown) ed estrae le serie allenanti,
pesandole in base al coinvolgimento muscolare:
  - Muscolo principale:  1.0 per serie
  - Muscolo secondario:  0.5 per serie
  - Muscolo terziario:   0.3 per serie

Uso:
    python source/scripts/volume_calc.py data/output/workout_2026-03-18.md
    python source/scripts/volume_calc.py data/output/workout_2026-03-18.md --json
"""

import argparse
import json
import re
import sys

# Mapping esercizio -> muscoli coinvolti (principale, secondario, terziario)
EXERCISE_MUSCLES = {
    "squat con bilanciere": {
        "principale": ["quadricipiti", "glutei"],
        "secondario": ["femorali", "core"],
        "terziario": ["erettori spinali"],
    },
    "panca piana con bilanciere": {
        "principale": ["petto"],
        "secondario": ["tricipiti", "deltoidi anteriori"],
        "terziario": [],
    },
    "leg press": {
        "principale": ["quadricipiti"],
        "secondario": ["glutei"],
        "terziario": [],
    },
    "dips alle parallele": {
        "principale": ["petto", "tricipiti"],
        "secondario": ["deltoidi anteriori"],
        "terziario": [],
    },
    "leg curl sdraiato": {
        "principale": ["femorali"],
        "secondario": [],
        "terziario": [],
    },
    "plank": {
        "principale": ["core"],
        "secondario": [],
        "terziario": [],
    },
    "stacco da terra convenzionale": {
        "principale": ["femorali", "glutei", "erettori spinali"],
        "secondario": ["quadricipiti", "dorsali", "trapezi"],
        "terziario": ["core", "avambracci"],
    },
    "trazioni alla sbarra": {
        "principale": ["dorsali"],
        "secondario": ["bicipiti"],
        "terziario": ["deltoidi posteriori", "core"],
    },
    "rematore con bilanciere": {
        "principale": ["dorsali", "trapezi"],
        "secondario": ["bicipiti", "deltoidi posteriori"],
        "terziario": ["erettori spinali"],
    },
    "curl con bilanciere": {
        "principale": ["bicipiti"],
        "secondario": [],
        "terziario": [],
    },
    "face pull al cavo": {
        "principale": ["deltoidi posteriori", "cuffia dei rotatori"],
        "secondario": ["trapezi"],
        "terziario": [],
    },
    "farmer's walk": {
        "principale": ["core", "avambracci"],
        "secondario": ["trapezi"],
        "terziario": [],
    },
    "military press con bilanciere": {
        "principale": ["deltoidi anteriori", "deltoidi mediali"],
        "secondario": ["tricipiti"],
        "terziario": ["core"],
    },
    "alzate laterali con manubri": {
        "principale": ["deltoidi mediali"],
        "secondario": [],
        "terziario": [],
    },
    "french press con bilanciere ez": {
        "principale": ["tricipiti"],
        "secondario": [],
        "terziario": [],
    },
    "crunch ai cavi": {
        "principale": ["core"],
        "secondario": [],
        "terziario": [],
    },
    "stacco rumeno": {
        "principale": ["femorali", "glutei"],
        "secondario": ["erettori spinali"],
        "terziario": ["dorsali"],
    },
    "rematore con bilanciere (presa supina)": {
        "principale": ["dorsali"],
        "secondario": ["bicipiti", "trapezi"],
        "terziario": ["erettori spinali"],
    },
    "bulgarian split squat": {
        "principale": ["quadricipiti", "glutei"],
        "secondario": ["femorali"],
        "terziario": [],
    },
    "trazioni presa neutra": {
        "principale": ["dorsali"],
        "secondario": ["bicipiti"],
        "terziario": ["deltoidi posteriori"],
    },
    "curl a martello con manubri": {
        "principale": ["bicipiti", "brachiale"],
        "secondario": [],
        "terziario": [],
    },
    "ab wheel rollout": {
        "principale": ["core"],
        "secondario": [],
        "terziario": [],
    },
    "leg extension": {
        "principale": ["quadricipiti"],
        "secondario": [],
        "terziario": [],
    },
    "cable row presa neutra (cavo basso)": {
        "principale": ["dorsali", "trapezi"],
        "secondario": ["bicipiti", "deltoidi posteriori"],
        "terziario": ["erettori spinali"],
    },
    "chest-supported dumbbell row presa neutra": {
        "principale": ["dorsali", "trapezi"],
        "secondario": ["bicipiti", "deltoidi posteriori"],
        "terziario": [],
    },
    "hip thrust con bilanciere": {
        "principale": ["glutei"],
        "secondario": ["femorali"],
        "terziario": ["core"],
    },
    "lat pulldown presa neutra": {
        "principale": ["dorsali"],
        "secondario": ["bicipiti"],
        "terziario": ["deltoidi posteriori"],
    },
    "dead bug": {
        "principale": ["core"],
        "secondario": [],
        "terziario": [],
    },
    "pallof press al cavo": {
        "principale": ["core"],
        "secondario": [],
        "terziario": [],
    },
    "leg raise al parallele (o a terra)": {
        "principale": ["core"],
        "secondario": [],
        "terziario": [],
    },
    "external rotation al cavo basso (presa neutra)": {
        "principale": ["cuffia dei rotatori"],
        "secondario": ["deltoidi posteriori"],
        "terziario": [],
    },
    "band pull-apart": {
        "principale": ["deltoidi posteriori", "romboidi"],
        "secondario": ["trapezi"],
        "terziario": [],
    },
    "wall angel": {
        "principale": ["cuffia dei rotatori", "trapezi"],
        "secondario": ["deltoidi posteriori"],
        "terziario": [],
    },
    "calf raise in piedi": {
        "principale": ["polpacci"],
        "secondario": [],
        "terziario": [],
    },
    "lat machine presa larga": {
        "principale": ["dorsali"],
        "secondario": ["bicipiti", "romboidi"],
        "terziario": ["deltoidi posteriori", "core"],
    },
    "rematore al cavo presa neutra": {
        "principale": ["dorsali", "trapezi"],
        "secondario": ["bicipiti", "deltoidi posteriori"],
        "terziario": ["erettori spinali"],
    },
    "stacco rumeno": {
        "principale": ["femorali", "glutei"],
        "secondario": ["erettori spinali"],
        "terziario": ["dorsali"],
    },
    "lat pulldown presa neutra": {
        "principale": ["dorsali"],
        "secondario": ["bicipiti"],
        "terziario": ["deltoidi posteriori"],
    },
    "alzate frontali con manubri": {
        "principale": ["deltoidi anteriori"],
        "secondario": [],
        "terziario": [],
    },
    "pushdown al cavo (corda)": {
        "principale": ["tricipiti"],
        "secondario": [],
        "terziario": [],
    },
    "pushdown al cavo": {
        "principale": ["tricipiti"],
        "secondario": [],
        "terziario": [],
    },
    "romanian deadlift (stacco rumeno)": {
        "principale": ["femorali", "glutei"],
        "secondario": ["erettori spinali"],
        "terziario": ["dorsali"],
    },
    "alzate laterali con manubri": {
        "principale": ["deltoidi mediali"],
        "secondario": [],
        "terziario": [],
    },
    "alzate frontali con manubri": {
        "principale": ["deltoidi anteriori"],
        "secondario": [],
        "terziario": [],
    },
    "curl a martello con manubri": {
        "principale": ["bicipiti", "brachiale"],
        "secondario": [],
        "terziario": [],
    },
    "calf raise in piedi": {
        "principale": ["polpacci"],
        "secondario": [],
        "terziario": [],
    },
    "bulgarian split squat": {
        "principale": ["quadricipiti", "glutei"],
        "secondario": ["femorali"],
        "terziario": [],
    },
    "hip thrust con bilanciere": {
        "principale": ["glutei"],
        "secondario": ["femorali"],
        "terziario": ["core"],
    },
    "stacco da terra convenzionale": {
        "principale": ["femorali", "glutei", "erettori spinali"],
        "secondario": ["quadricipiti", "dorsali", "trapezi"],
        "terziario": ["core", "avambracci"],
    },
    "squat con bilanciere": {
        "principale": ["quadricipiti", "glutei"],
        "secondario": ["femorali", "core"],
        "terziario": ["erettori spinali"],
    },
    "rematore con bilanciere": {
        "principale": ["dorsali", "trapezi"],
        "secondario": ["bicipiti", "deltoidi posteriori"],
        "terziario": ["erettori spinali"],
    },
    "wall slide": {
        "principale": ["cuffia dei rotatori", "trapezi"],
        "secondario": ["deltoidi posteriori"],
        "terziario": [],
    },
    "external rotation con elastico": {
        "principale": ["cuffia dei rotatori"],
        "secondario": ["deltoidi posteriori"],
        "terziario": [],
    },
    "shoulder cars": {
        "principale": ["cuffia dei rotatori"],
        "secondario": ["deltoidi posteriori", "trapezi"],
        "terziario": [],
    },
    "stacco rumeno": {
        "principale": ["femorali", "glutei"],
        "secondario": ["erettori spinali"],
        "terziario": ["dorsali"],
    },
    "pushdown al cavo (corda)": {
        "principale": ["tricipiti"],
        "secondario": [],
        "terziario": [],
    },
}


def normalize_exercise_name(name: str) -> str:
    """Normalizza il nome dell'esercizio per il matching."""
    name = name.lower().strip()
    name = re.sub(r"\*+", "", name)  # rimuovi bold markdown
    name = name.strip()
    # Rimuovi parentesi con contenuto opzionale per matching
    clean = re.sub(r"\s*\(.*?\)", "", name).strip()
    return clean


def match_exercise(name: str) -> dict | None:
    """Trova il mapping muscolare per un esercizio."""
    normalized = normalize_exercise_name(name)
    # Match esatto
    if normalized in EXERCISE_MUSCLES:
        return EXERCISE_MUSCLES[normalized]
    # Match parziale: cerca se il nome normalizzato è contenuto in una chiave o viceversa
    for key, muscles in EXERCISE_MUSCLES.items():
        if key in normalized or normalized in key:
            return muscles
    return None


def parse_sets(serie_str: str) -> int:
    """
    Parsa la colonna 'Serie x Reps' e restituisce il numero totale di serie.

    Esempi:
        "3×10"          -> 3
        "4×6-8"         -> 4
        "3×8-10/gamba"  -> 3
        "Ramping: 3×5, 2×3, 1×3 (top set)" -> 6
        "4×max (obiettivo 6-8)" -> 4
        "3×45 sec"      -> 3
        "3×30 m"        -> 3
    """
    serie_str = serie_str.strip()
    # Ramping: somma tutte le serie
    if "ramping" in serie_str.lower():
        total = 0
        for m in re.finditer(r"(\d+)\s*[×x]", serie_str):
            total += int(m.group(1))
        return total
    # Formato standard: NxM
    m = re.search(r"(\d+)\s*[×x]", serie_str)
    if m:
        return int(m.group(1))
    return 0


def parse_workout(filepath: str) -> list[dict]:
    """
    Parsa il file markdown della scheda e restituisce una lista di esercizi.
    Ogni esercizio è un dict con: nome, serie, giorno.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    exercises = []
    current_day = ""

    for line in lines:
        line = line.rstrip()
        # Rileva il giorno (### GIORNO X — ...)
        day_match = re.match(r"^###\s+GIORNO\s+(\w+)\s*[—-]\s*(.*)", line)
        if day_match:
            current_day = f"Giorno {day_match.group(1)}"
            continue

        # Rileva righe tabella esercizi (formato: | # | Esercizio | Serie × Reps | ...)
        if line.startswith("|") and current_day:
            cols = [c.strip() for c in line.split("|")]
            # Filtra righe header e separatori
            if len(cols) < 5:
                continue
            # cols[0] è vuoto (prima del primo |), cols[1] è #, cols[2] è esercizio, cols[3] è serie
            num = cols[1]
            if not num or num == "#" or num.startswith("-"):
                continue
            try:
                int(num)
            except ValueError:
                continue

            exercise_name = cols[2]
            serie_str = cols[3]
            sets = parse_sets(serie_str)
            if sets > 0:
                exercises.append({
                    "nome": exercise_name,
                    "serie": sets,
                    "giorno": current_day,
                })

    return exercises


def calc_volume(exercises: list[dict]) -> dict:
    """
    Calcola il volume settimanale per distretto muscolare.
    Restituisce un dict: muscolo -> { serie_pesate, dettaglio: [...] }
    """
    volume = {}
    unmatched = []

    for ex in exercises:
        muscles = match_exercise(ex["nome"])
        if muscles is None:
            unmatched.append(ex["nome"])
            continue

        sets = ex["serie"]
        for role, weight in [("principale", 1.0), ("secondario", 0.5), ("terziario", 0.3)]:
            for muscle in muscles.get(role, []):
                if muscle not in volume:
                    volume[muscle] = {"serie_pesate": 0, "dettaglio": []}
                volume[muscle]["serie_pesate"] += sets * weight
                volume[muscle]["dettaglio"].append({
                    "esercizio": re.sub(r"\*+", "", ex["nome"]).strip(),
                    "giorno": ex["giorno"],
                    "serie": sets,
                    "ruolo": role,
                    "peso": weight,
                    "contributo": round(sets * weight, 1),
                })

    if unmatched:
        print(f"⚠ Esercizi non mappati: {', '.join(set(unmatched))}", file=sys.stderr)

    # Arrotonda
    for m in volume:
        volume[m]["serie_pesate"] = round(volume[m]["serie_pesate"], 1)

    return volume


def print_volume_table(volume: dict):
    """Stampa la tabella riassuntiva del volume per distretto muscolare."""
    sorted_muscles = sorted(volume.items(), key=lambda x: x[1]["serie_pesate"], reverse=True)

    print("=" * 60)
    print("  VOLUME SETTIMANALE PER DISTRETTO MUSCOLARE")
    print("  (1.0 principale | 0.5 secondario | 0.3 terziario)")
    print("=" * 60)
    print(f"  {'Distretto':<25} {'Serie pesate':>12}")
    print(f"  {'-' * 25} {'-' * 12}")
    for muscle, data in sorted_muscles:
        print(f"  {muscle:<25} {data['serie_pesate']:>10.1f}")

    print()
    print("=" * 60)
    print("  DETTAGLIO PER DISTRETTO")
    print("=" * 60)
    for muscle, data in sorted_muscles:
        print(f"\n  > {muscle.upper()} - {data['serie_pesate']} serie pesate")
        for d in data["dettaglio"]:
            tag = {"principale": "P", "secondario": "S", "terziario": "T"}[d["ruolo"]]
            print(f"    [{tag}] {d['esercizio']:<40} {d['giorno']:<12} {d['serie']}s × {d['peso']} = {d['contributo']}")


def main():
    parser = argparse.ArgumentParser(description="Calcolatore volume allenante per distretto muscolare")
    parser.add_argument("workout", help="Percorso del file workout markdown")
    parser.add_argument("--json", action="store_true", help="Output in formato JSON")
    args = parser.parse_args()

    exercises = parse_workout(args.workout)
    if not exercises:
        print("Nessun esercizio trovato nel file.", file=sys.stderr)
        sys.exit(1)

    volume = calc_volume(exercises)

    if args.json:
        print(json.dumps(volume, indent=2, ensure_ascii=False))
    else:
        print_volume_table(volume)


if __name__ == "__main__":
    main()
