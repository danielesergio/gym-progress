# File temporaneo creato da gym-dietologo il 2026-03-23
# Scopo: verifica calcoli macro v3 - final adjustments
# Puo' essere eliminato al termine dell'iterazione

# === GIORNO ALLENAMENTO (v2 - OK) ===
print("=== GIORNO ALLENAMENTO ===")
training_meals = {
    "Colazione": [
        ("Fiocchi d'avena", 100, 372, 13, 64, 7),
        ("Latte parzialmente scremato", 250, 115, 8, 12, 4),
        ("Banana", 120, 107, 1, 27, 0),
        ("Miele", 15, 48, 0, 13, 0),
        ("Proteine whey", 30, 120, 24, 2, 1),
    ],
    "Pranzo": [
        ("Pasta di semola", 130, 460, 16, 94, 2),
        ("Petto di pollo", 200, 220, 44, 0, 3),
        ("Olio extravergine d'oliva", 15, 135, 0, 0, 15),
        ("Zucchine", 150, 24, 2, 2, 0),
        ("Parmigiano Reggiano", 15, 59, 5, 0, 4),
    ],
    "Merenda pre-workout": [
        ("Yogurt greco 0%", 170, 95, 17, 7, 0),
        ("Riso soffiato", 40, 156, 3, 36, 1),
        ("Marmellata", 20, 50, 0, 13, 0),
    ],
    "Cena": [
        ("Riso basmati", 110, 385, 8, 86, 1),
        ("Salmone fresco", 200, 416, 40, 0, 28),
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
print()

# === GIORNO RIPOSO (v3 - adjusted) ===
# Target: ~2700 kcal, P:190, C:280, G:78
print("=== GIORNO RIPOSO ===")
rest_meals = {
    "Colazione": [
        ("Fiocchi d'avena", 80, 298, 10, 51, 6),
        ("Latte parzialmente scremato", 250, 115, 8, 12, 4),
        ("Uova intere", 120, 172, 15, 1, 12),  # 2 uova
        ("Pane integrale", 50, 117, 5, 21, 2),
    ],
    "Pranzo": [
        ("Pasta di semola", 120, 424, 15, 87, 2),
        ("Tonno al naturale sgocciolato", 120, 122, 28, 0, 1),
        ("Olio extravergine d'oliva", 15, 135, 0, 0, 15),
        ("Pomodori", 150, 27, 1, 5, 0),
        ("Parmigiano Reggiano", 15, 59, 5, 0, 4),
    ],
    "Merenda": [
        ("Yogurt greco 0%", 200, 112, 20, 8, 0),
        ("Mandorle", 20, 116, 4, 4, 10),
        ("Banana", 120, 107, 1, 27, 0),
    ],
    "Cena": [
        ("Petto di pollo", 200, 220, 44, 0, 3),
        ("Patate", 300, 231, 6, 51, 0),
        ("Olio extravergine d'oliva", 10, 90, 0, 0, 10),
        ("Broccoli", 200, 54, 6, 7, 1),
        ("Mozzarella", 60, 150, 11, 0, 12),
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
