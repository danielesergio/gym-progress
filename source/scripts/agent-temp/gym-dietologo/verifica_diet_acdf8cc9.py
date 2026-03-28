# File temporaneo creato da gym-dietologo il 2026-03-27
# Scopo: verifica intercambiabilita' e coerenza della dieta acdf8cc9
# Puo' essere eliminato al termine dell'iterazione

import yaml
import sys

with open("data/output/diet_acdf8cc9.yaml", "r", encoding="utf-8") as f:
    diet = yaml.safe_load(f)

tipi = [t["id"] for t in diet["meta"]["tipi_giorno"]]
targets = {t["id"]: t["kcal_target"] for t in diet["meta"]["tipi_giorno"]}

print("=== TARGET GIORNALIERI ===")
for t in tipi:
    print(f"  {t}: {targets[t]} kcal")

print("\n=== AUTOCHECK: SOMMA SLOT vs TARGET ===")
all_ok = True
for tipo in tipi:
    parts = []
    tot = 0
    for slot in diet["slot_pasto"]:
        v = slot["kcal_per_tipo"][tipo]
        parts.append(f"{slot['id']}({v})")
        tot += v
    diff = abs(tot - targets[tipo])
    status = "OK" if diff <= 50 else "KO"
    if status == "KO":
        all_ok = False
    print(f"  Tipo [{tipo}]: {' + '.join(parts)} = {tot} vs TARGET {targets[tipo]} — diff {diff} — {status}")

print("\n=== INTERCAMBIABILITA' PER SLOT ===")
for slot in diet["slot_pasto"]:
    for tipo in tipi:
        target_slot = slot["kcal_per_tipo"][tipo]
        kcals = []
        for opt in slot["opzioni"]:
            # Verify totale matches sum of alimenti
            variante = opt["varianti"][tipo]
            calc_kcal = sum(a["kcal"] for a in variante["alimenti"])
            calc_prot = sum(a["proteine"] for a in variante["alimenti"])
            calc_carbo = sum(a["carbo"] for a in variante["alimenti"])
            calc_grassi = sum(a["grassi"] for a in variante["alimenti"])

            tot = variante["totale"]
            # Check arithmetic
            if abs(calc_kcal - tot["kcal"]) > 2:
                print(f"  ERRORE ARITMETICO [{slot['id']}] [{tipo}] [{opt['nome']}]: kcal calcolate={calc_kcal} vs dichiarate={tot['kcal']}")
                all_ok = False
            if abs(calc_prot - tot["proteine"]) > 1:
                print(f"  ERRORE ARITMETICO [{slot['id']}] [{tipo}] [{opt['nome']}]: proteine calcolate={calc_prot:.1f} vs dichiarate={tot['proteine']}")
                all_ok = False

            kcals.append(tot["kcal"])

        # Check intercambiability: all options within ±50 of slot target
        spread = max(kcals) - min(kcals)
        deviations = [abs(k - target_slot) for k in kcals]
        max_dev = max(deviations)
        names = [o["nome"][:20] for o in slot["opzioni"]]
        vals = [f"{n}({k})" for n, k in zip(names, kcals)]
        status = "OK" if max_dev <= 50 else "ATTENZIONE"
        if max_dev > 50:
            all_ok = False
        print(f"  Slot [{slot['id']}] tipo [{tipo}]: {' '.join(vals)} — target {target_slot} — max_dev {max_dev} — spread {spread} — {status}")

print(f"\n{'TUTTI I CHECK PASSATI' if all_ok else 'ATTENZIONE: ALCUNI CHECK FALLITI'}")
