# File temporaneo creato da gym-dietologo il 2026-03-23
# Scopo: verifica calcoli macro v2 - aggiustamenti
# Puo' essere eliminato al termine dell'iterazione

# === GIORNO ALLENAMENTO ===
# Target: ~2950 kcal, P:190, C:350, G:82
print("=== GIORNO ALLENAMENTO ===")
training_meals = {
    "Colazione": [
        ("Fiocchi d'avena", 100, 372, 13, 64, 7),
        ("Latte parzialmente scremato", 250, 115, 8, 12, 4),
        ("Banana", 120, 107, 1, 27, 0),
        ("Miele", 15, 48, 0, 13, 0),
        ("Proteine whey", 30, 120, 24, 2, 1),  # aggiunto shake
    ],
    "Pranzo": [
        ("Pasta di semola", 130, 460, 16, 94, 2),  # +10g pasta
        ("Petto di pollo", 200, 220, 44, 0, 3),  # +20g pollo
        ("Olio extravergine d'oliva", 15, 135, 0, 0, 15),
        ("Zucchine", 150, 24, 2, 2, 0),
        ("Parmigiano Reggiano", 15, 59, 5, 0, 4),
    ],
    "Merenda pre-workout": [
        ("Yogurt greco 0%", 170, 95, 17, 7, 0),
        ("Riso soffiato", 40, 156, 3, 36, 1),  # +10g
        ("Marmellata", 20, 50, 0, 13, 0),
    ],
    "Cena": [
        ("Riso basmati", 110, 385, 8, 86, 1),  # +10g riso
        ("Salmone fresco", 200, 416, 40, 0, 28),  # +20g salmone
        ("Olio extravergine d'oliva", 10, 90, 0, 0, 10),
        ("Insalata mista", 100, 18, 1, 3, 0),
        ("Mozzarella", 50, 125, 9, 0, 10),
    ],
}

day_total = {"kcal": 0, "P": 0, "C": 0, "G": 0}
for meal_name, foods in training_meals.items():
    meal_kcal = sum(f[2] for f in foods)
    meal_p = sum(f[3] for f in foods)
    meal_c = sum(f[4] for f in foods)
    meal_g = sum(f[5] for f in foods)
    print(f"  {meal_name}: kcal={meal_kcal}, P={meal_p}, C={meal_c}, G={meal_g}")
    day_total["kcal"] += meal_kcal
    day_total["P"] += meal_p
    day_total["C"] += meal_c
    day_total["G"] += meal_g

print(f"  TOTALE: kcal={day_total['kcal']}, P={day_total['P']}, C={day_total['C']}, G={day_total['G']}")
print(f"  Kcal check: P*4+C*4+G*9 = {day_total['P']*4 + day_total['C']*4 + day_total['G']*9}")
print()

# === GIORNO RIPOSO ===
# Target: ~2700 kcal, P:190, C:280, G:78
print("=== GIORNO RIPOSO ===")
rest_meals = {
    "Colazione": [
        ("Fiocchi d'avena", 80, 298, 10, 51, 6),
        ("Latte parzialmente scremato", 250, 115, 8, 12, 4),
        ("Uova intere", 120, 172, 15, 1, 12),
        ("Pane integrale", 60, 140, 6, 25, 2),  # +20g pane
    ],
    "Pranzo": [
        ("Pasta di semola", 110, 389, 13, 79, 2),  # +10g
        ("Tonno al naturale sgocciolato", 160, 163, 37, 0, 1),
        ("Olio extravergine d'oliva", 15, 135, 0, 0, 15),
        ("Pomodori", 150, 27, 1, 5, 0),
        ("Parmigiano Reggiano", 15, 59, 5, 0, 4),
    ],
    "Merenda": [
        ("Yogurt greco 0%", 200, 112, 20, 8, 0),
        ("Mandorle", 25, 145, 5, 5, 13),  # +5g
        ("Mela", 150, 78, 0, 19, 0),
        ("Proteine whey", 30, 120, 24, 2, 1),  # aggiunto
    ],
    "Cena": [
        ("Petto di pollo", 220, 242, 48, 0, 3),  # +20g
        ("Patate", 250, 193, 5, 43, 0),  # +50g
        ("Olio extravergine d'oliva", 10, 90, 0, 0, 10),
        ("Broccoli", 200, 54, 6, 7, 1),
        ("Mozzarella", 50, 125, 9, 0, 10),
    ],
}

day_total_r = {"kcal": 0, "P": 0, "C": 0, "G": 0}
for meal_name, foods in rest_meals.items():
    meal_kcal = sum(f[2] for f in foods)
    meal_p = sum(f[3] for f in foods)
    meal_c = sum(f[4] for f in foods)
    meal_g = sum(f[5] for f in foods)
    print(f"  {meal_name}: kcal={meal_kcal}, P={meal_p}, C={meal_c}, G={meal_g}")
    day_total_r["kcal"] += meal_kcal
    day_total_r["P"] += meal_p
    day_total_r["C"] += meal_c
    day_total_r["G"] += meal_g

print(f"  TOTALE: kcal={day_total_r['kcal']}, P={day_total_r['P']}, C={day_total_r['C']}, G={day_total_r['G']}")
print(f"  Kcal check: P*4+C*4+G*9 = {day_total_r['P']*4 + day_total_r['C']*4 + day_total_r['G']*9}")
