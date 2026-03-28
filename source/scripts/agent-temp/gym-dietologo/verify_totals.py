# File temporaneo creato da gym-dietologo il 2026-03-27
# Scopo: verifica che i totali per ogni opzione siano la somma esatta degli alimenti
# e che le opzioni dello stesso slot siano intercambiabili (±50 kcal)

# I'll use this after writing the YAML to verify
import yaml, sys

def verify(path):
    with open(path) as f:
        d = yaml.safe_load(f)
    
    tipi = [t["id"] for t in d["meta"]["tipi_giorno"]]
    targets = {t["id"]: t["kcal_target"] for t in d["meta"]["tipi_giorno"]}
    
    errors = []
    
    for slot in d["slot_pasto"]:
        slot_id = slot["id"]
        kcal_per_tipo = slot["kcal_per_tipo"]
        
        for tipo in tipi:
            kcals = []
            for opt in slot["opzioni"]:
                var = opt["varianti"][tipo]
                # Verify totals are sums of alimenti
                sum_kcal = sum(a["kcal"] for a in var["alimenti"])
                sum_prot = sum(a["proteine"] for a in var["alimenti"])
                sum_carb = sum(a["carbo"] for a in var["alimenti"])
                sum_fat = sum(a["grassi"] for a in var["alimenti"])
                
                tot = var["totale"]
                if abs(sum_kcal - tot["kcal"]) > 1:
                    errors.append(f"ERRORE SOMMA: {slot_id}/{opt['nome']}/{tipo}: kcal somma={sum_kcal:.1f} vs totale={tot['kcal']}")
                if abs(sum_prot - tot["proteine"]) > 0.5:
                    errors.append(f"ERRORE SOMMA: {slot_id}/{opt['nome']}/{tipo}: prot somma={sum_prot:.1f} vs totale={tot['proteine']}")
                if abs(sum_carb - tot["carbo"]) > 0.5:
                    errors.append(f"ERRORE SOMMA: {slot_id}/{opt['nome']}/{tipo}: carbo somma={sum_carb:.1f} vs totale={tot['carbo']}")
                if abs(sum_fat - tot["grassi"]) > 0.5:
                    errors.append(f"ERRORE SOMMA: {slot_id}/{opt['nome']}/{tipo}: grassi somma={sum_fat:.1f} vs totale={tot['grassi']}")
                
                kcals.append((opt["nome"], tot["kcal"]))
            
            # Check intercambiabilita
            if len(kcals) > 1:
                vals = [k[1] for k in kcals]
                spread = max(vals) - min(vals)
                target = kcal_per_tipo[tipo]
                print(f"Slot [{slot_id}] tipo [{tipo}]: " + " ".join(f"{n}({v:.0f})" for n,v in kcals) + f" -- target {target} -- spread {spread:.0f} kcal")
                if spread > 50:
                    errors.append(f"SPREAD >50: {slot_id}/{tipo}: spread={spread:.0f}")
                for name, val in kcals:
                    if abs(val - target) > 50:
                        errors.append(f"OFF TARGET >50: {slot_id}/{tipo}/{name}: {val:.0f} vs target {target}")
    
    # Check daily sums
    print("\n=== VERIFICA SOMME GIORNALIERE ===")
    for tipo in tipi:
        slot_sum = sum(s["kcal_per_tipo"][tipo] for s in d["slot_pasto"])
        target = targets[tipo]
        diff = slot_sum - target
        status = "OK" if abs(diff) <= 50 else "KO"
        print(f"Tipo [{tipo}]: " + " + ".join(f"{s['id']}({s['kcal_per_tipo'][tipo]})" for s in d["slot_pasto"]) + f" = {slot_sum} vs TARGET {target} -- {status} (diff={diff})")
    
    if errors:
        print(f"\n=== {len(errors)} ERRORI TROVATI ===")
        for e in errors:
            print(e)
    else:
        print("\nTUTTO OK - nessun errore trovato")

if __name__ == "__main__":
    verify(sys.argv[1])
