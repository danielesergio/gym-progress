#!/usr/bin/env python3
"""
Calcolatore composizione corporea e fabbisogno calorico per atleta.

Uso:
    python source/scripts/body_calc.py --peso 87.2 --altezza 188 --eta 38 --vita 89 --collo 39 --fianchi 100 --sesso M
    python source/scripts/body_calc.py --peso 87.2 --altezza 188 --eta 38 --vita 89 --collo 39 --fianchi 100 --sesso M --surplus 300

Formule utilizzate:
    - Body Fat %: US Navy (Hodgdon-Beckett)
        Maschi:  BF% = 495 / (1.0324 - 0.19077 * log10(vita - collo) + 0.15456 * log10(altezza)) - 450
        Femmine: BF% = 495 / (1.29579 - 0.35004 * log10(vita + fianchi - collo) + 0.22100 * log10(altezza)) - 450
    - BMR: Mifflin-St Jeor
        Maschi:  BMR = 10 * peso + 6.25 * altezza - 5 * eta - 5
        Femmine: BMR = 10 * peso + 6.25 * altezza - 5 * eta - 161
    - FFMI: massa_magra_kg / altezza_m^2
    - 1RM stimato (Epley): peso * (1 + reps / 30)
    - 1RM stimato (Brzycki): peso * (36 / (37 - reps))
"""

import argparse
import math
import json
import sys


def body_fat_navy(sesso: str, vita: float, collo: float, altezza: float, fianchi: float = 0) -> float:
    """Calcola BF% con formula US Navy (Hodgdon-Beckett)."""
    if sesso.upper() == "M":
        bf = 495 / (1.0324 - 0.19077 * math.log10(vita - collo) + 0.15456 * math.log10(altezza)) - 450
    else:
        if fianchi <= 0:
            raise ValueError("Per le femmine serve la misura dei fianchi")
        bf = 495 / (1.29579 - 0.35004 * math.log10(vita + fianchi - collo) + 0.22100 * math.log10(altezza)) - 450
    return round(bf, 1)


def bmr_mifflin(peso: float, altezza: float, eta: int, sesso: str) -> float:
    """Calcola BMR con Mifflin-St Jeor."""
    if sesso.upper() == "M":
        return round(10 * peso + 6.25 * altezza - 5 * eta - 5)
    else:
        return round(10 * peso + 6.25 * altezza - 5 * eta - 161)


def ffmi(massa_magra: float, altezza_cm: float) -> float:
    """Calcola FFMI (Fat-Free Mass Index)."""
    altezza_m = altezza_cm / 100
    return round(massa_magra / (altezza_m ** 2), 1)


def ffmi_adjusted(massa_magra: float, altezza_cm: float) -> float:
    """Calcola FFMI normalizzato a 1.80m."""
    altezza_m = altezza_cm / 100
    raw = massa_magra / (altezza_m ** 2)
    return round(raw + 6.1 * (1.8 - altezza_m), 1)


def stima_1rm_epley(peso: float, reps: int) -> float:
    """Stima 1RM con formula di Epley."""
    if reps == 1:
        return peso
    return round(peso * (1 + reps / 30), 1)


def stima_1rm_brzycki(peso: float, reps: int) -> float:
    """Stima 1RM con formula di Brzycki."""
    if reps == 1:
        return peso
    return round(peso * (36 / (37 - reps)), 1)


def main():
    parser = argparse.ArgumentParser(description="Calcolatore composizione corporea e fabbisogno calorico")
    parser.add_argument("--peso", type=float, required=True, help="Peso in kg")
    parser.add_argument("--altezza", type=float, required=True, help="Altezza in cm")
    parser.add_argument("--eta", type=int, required=True, help="Età in anni")
    parser.add_argument("--vita", type=float, required=True, help="Circonferenza vita (ombelico) in cm")
    parser.add_argument("--collo", type=float, required=True, help="Circonferenza collo in cm")
    parser.add_argument("--fianchi", type=float, default=0, help="Circonferenza fianchi in cm (obbligatorio per F)")
    parser.add_argument("--sesso", type=str, default="M", choices=["M", "F"], help="Sesso (M/F)")
    parser.add_argument("--attivita", type=float, default=1.55, help="Fattore attività (1.2 sedentario, 1.375 leggero, 1.55 moderato, 1.725 intenso)")
    parser.add_argument("--surplus", type=int, default=0, help="Surplus calorico in kcal (negativo per deficit)")
    parser.add_argument("--json", action="store_true", help="Output in formato JSON")

    # Sottoparsers per stima 1RM
    parser.add_argument("--rm-peso", type=float, help="Peso sollevato per stima 1RM")
    parser.add_argument("--rm-reps", type=int, help="Ripetizioni effettuate per stima 1RM")

    args = parser.parse_args()

    # Calcoli composizione corporea
    bf = body_fat_navy(args.sesso, args.vita, args.collo, args.altezza, args.fianchi)
    massa_grassa = round(args.peso * bf / 100, 1)
    massa_magra = round(args.peso - massa_grassa, 1)
    ffmi_val = ffmi(massa_magra, args.altezza)
    ffmi_adj = ffmi_adjusted(massa_magra, args.altezza)

    # Calcoli metabolici
    bmr = bmr_mifflin(args.peso, args.altezza, args.eta, args.sesso)
    tdee = round(bmr * args.attivita)
    target_kcal = tdee + args.surplus

    # Macro suggeriti (proteine 2g/kg, grassi 0.9g/kg, resto carbo)
    proteine_g = round(args.peso * 2)
    grassi_g = round(args.peso * 0.9)
    proteine_kcal = proteine_g * 4
    grassi_kcal = grassi_g * 9
    carbo_kcal = target_kcal - proteine_kcal - grassi_kcal
    carbo_g = round(carbo_kcal / 4)

    results = {
        "composizione_corporea": {
            "peso_kg": args.peso,
            "body_fat_pct": bf,
            "massa_grassa_kg": massa_grassa,
            "massa_magra_kg": massa_magra,
            "ffmi": ffmi_val,
            "ffmi_adjusted": ffmi_adj,
            "formula": "US Navy (Hodgdon-Beckett)"
        },
        "metabolismo": {
            "bmr_kcal": bmr,
            "fattore_attivita": args.attivita,
            "tdee_kcal": tdee,
            "surplus_kcal": args.surplus,
            "target_kcal": target_kcal,
            "formula": "Mifflin-St Jeor"
        },
        "macro_suggeriti": {
            "proteine_g": proteine_g,
            "grassi_g": grassi_g,
            "carboidrati_g": carbo_g,
            "proteine_kcal": proteine_kcal,
            "grassi_kcal": grassi_kcal,
            "carboidrati_kcal": carbo_kcal
        }
    }

    # Stima 1RM se richiesta
    if args.rm_peso and args.rm_reps:
        results["stima_1rm"] = {
            "peso_usato": args.rm_peso,
            "reps": args.rm_reps,
            "epley": stima_1rm_epley(args.rm_peso, args.rm_reps),
            "brzycki": stima_1rm_brzycki(args.rm_peso, args.rm_reps)
        }

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print("=" * 55)
        print("  COMPOSIZIONE CORPOREA")
        print("=" * 55)
        print(f"  Peso:            {args.peso} kg")
        print(f"  Body Fat:        {bf}%  (US Navy / Hodgdon-Beckett)")
        print(f"  Massa grassa:    {massa_grassa} kg")
        print(f"  Massa magra:     {massa_magra} kg")
        print(f"  FFMI:            {ffmi_val}  (adjusted: {ffmi_adj})")
        print()
        print("=" * 55)
        print("  METABOLISMO")
        print("=" * 55)
        print(f"  BMR:             {bmr} kcal  (Mifflin-St Jeor)")
        print(f"  TDEE:            {tdee} kcal  (x{args.attivita})")
        print(f"  Surplus:         {args.surplus:+d} kcal")
        print(f"  Target:          {target_kcal} kcal/giorno")
        print()
        print("=" * 55)
        print("  MACRO SUGGERITI")
        print("=" * 55)
        print(f"  Proteine:        {proteine_g}g  ({proteine_kcal} kcal) — 2g/kg")
        print(f"  Grassi:          {grassi_g}g  ({grassi_kcal} kcal) — 0.9g/kg")
        print(f"  Carboidrati:     {carbo_g}g  ({carbo_kcal} kcal) — resto")
        print(f"  Totale:          {proteine_kcal + grassi_kcal + carbo_g * 4} kcal")

        if args.rm_peso and args.rm_reps:
            print()
            print("=" * 55)
            print("  STIMA 1RM")
            print("=" * 55)
            print(f"  Test: {args.rm_peso} kg × {args.rm_reps} reps")
            print(f"  Epley:           {results['stima_1rm']['epley']} kg")
            print(f"  Brzycki:         {results['stima_1rm']['brzycki']} kg")


if __name__ == "__main__":
    main()
