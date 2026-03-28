# File temporaneo creato da gym-dietologo il 2026-03-27
# Scopo: definire e verificare i target calorici per slot arrotondati
# Puo' essere eliminato al termine dell'iterazione

# Slot distribution (arrotondati a multipli di 10-25)
slots = {
    "colazione": {"riposo": 550, "palestra": 600, "beach_volley": 650},
    "spuntino":  {"riposo": 200, "palestra": 200, "beach_volley": 225},
    "pranzo":    {"riposo": 750, "palestra": 850, "beach_volley": 925},
    "merenda":   {"riposo": 325, "palestra": 350, "beach_volley": 375},
    "cena":      {"riposo": 875, "palestra": 950, "beach_volley": 1025},
}

targets = {"riposo": 2700, "palestra": 2950, "beach_volley": 3200}

for tipo, target in targets.items():
    tot = sum(s[tipo] for s in slots.values())
    print(f"Tipo [{tipo}]: ", end="")
    parts = []
    for slot_name, vals in slots.items():
        parts.append(f"{slot_name}({vals[tipo]})")
    print(" + ".join(parts), f"= {tot} vs TARGET {target} — diff {tot-target} — {'OK' if abs(tot-target) <= 50 else 'KO'}")
