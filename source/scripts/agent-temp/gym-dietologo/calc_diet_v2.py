# File temporaneo creato da gym-dietologo il 2026-03-23
# Scopo: verifica calcoli macro v2 - porzioni corrette per target calorici
# Puo' essere eliminato al termine dell'iterazione

foods = {
    "Yogurt greco 0%": {"kcal": 57, "p": 10.3, "c": 4.0, "g": 0.7},
    "Muesli proteico": {"kcal": 360, "p": 29.6, "c": 45.3, "g": 5.5},
    "Pasta di semola": {"kcal": 356, "p": 12.5, "c": 72.0, "g": 1.5},
    "Sugo al pomodoro": {"kcal": 40, "p": 1.5, "c": 6.0, "g": 1.0},
    "Parmigiano grattugiato": {"kcal": 392, "p": 33.0, "c": 0.0, "g": 28.0},
    "Petto di pollo": {"kcal": 110, "p": 23.1, "c": 0.0, "g": 1.2},
    "Riso basmati": {"kcal": 350, "p": 7.0, "c": 78.0, "g": 0.6},
    "Zucchine": {"kcal": 17, "p": 1.2, "c": 2.0, "g": 0.3},
    "Olio EVO": {"kcal": 884, "p": 0.0, "c": 0.0, "g": 100.0},
    "Banana": {"kcal": 89, "p": 1.1, "c": 22.8, "g": 0.3},
    "Whey proteine": {"kcal": 400, "p": 80.0, "c": 8.0, "g": 4.0},
    "Latte parz. scremato": {"kcal": 46, "p": 3.3, "c": 5.0, "g": 1.5},
    "Mela": {"kcal": 52, "p": 0.3, "c": 13.8, "g": 0.2},
    "Pane integrale": {"kcal": 247, "p": 8.0, "c": 44.0, "g": 3.5},
    "Salmone fresco": {"kcal": 208, "p": 20.4, "c": 0.0, "g": 13.4},
    "Patate": {"kcal": 77, "p": 2.0, "c": 17.0, "g": 0.1},
    "Insalata mista": {"kcal": 15, "p": 1.0, "c": 2.0, "g": 0.2},
    "Mozzarella": {"kcal": 280, "p": 22.0, "c": 1.0, "g": 20.5},
    "Pomodoro fresco": {"kcal": 18, "p": 0.9, "c": 3.9, "g": 0.1},
    "Tonno in scatola sgocciolato": {"kcal": 130, "p": 26.0, "c": 0.0, "g": 2.5},
    "Uova intere": {"kcal": 143, "p": 12.4, "c": 0.7, "g": 9.9},
    "Bresaola": {"kcal": 151, "p": 32.0, "c": 0.0, "g": 2.6},
    "Trota": {"kcal": 119, "p": 20.5, "c": 0.0, "g": 3.5},
    "Branzino": {"kcal": 97, "p": 18.4, "c": 0.0, "g": 2.0},
    "Manzo macinato magro": {"kcal": 170, "p": 21.0, "c": 0.0, "g": 9.0},
    "Pizza margherita": {"kcal": 271, "p": 12.0, "c": 33.0, "g": 10.0},
    "Hamburger completo": {"kcal": 250, "p": 17.0, "c": 20.0, "g": 11.0},
    "Lenticchie secche": {"kcal": 353, "p": 25.0, "c": 54.0, "g": 1.0},
    "Verdure miste per minestra": {"kcal": 25, "p": 1.5, "c": 4.0, "g": 0.3},
    "Pesto alla genovese": {"kcal": 440, "p": 5.0, "c": 4.0, "g": 44.0},
    "Guanciale": {"kcal": 655, "p": 10.0, "c": 0.5, "g": 68.0},
    "Pecorino romano": {"kcal": 387, "p": 26.0, "c": 0.0, "g": 31.0},
    "Piselli surgelati": {"kcal": 81, "p": 5.4, "c": 14.5, "g": 0.4},
    "Fiocchi avena": {"kcal": 370, "p": 13.0, "c": 60.0, "g": 7.0},
    "Pane di segale": {"kcal": 230, "p": 7.0, "c": 45.0, "g": 2.5},
    "Mandorle": {"kcal": 579, "p": 21.0, "c": 22.0, "g": 49.0},
    "Noci": {"kcal": 654, "p": 15.0, "c": 14.0, "g": 65.0},
    "Crackers integrali": {"kcal": 420, "p": 10.0, "c": 65.0, "g": 13.0},
}

def calc(name, grams):
    f = foods[name]
    factor = grams / 100.0
    return {
        "nome": name,
        "grammi": grams,
        "kcal": round(f["kcal"] * factor),
        "proteine": round(f["p"] * factor, 1),
        "carbo": round(f["c"] * factor, 1),
        "grassi": round(f["g"] * factor, 1),
    }

def meal_total(items):
    return {
        "kcal": sum(i["kcal"] for i in items),
        "proteine": round(sum(i["proteine"] for i in items), 1),
        "carbo": round(sum(i["carbo"] for i in items), 1),
        "grassi": round(sum(i["grassi"] for i in items), 1),
    }

def day_total(meals):
    return {
        "kcal": sum(m["total"]["kcal"] for m in meals),
        "proteine": round(sum(m["total"]["proteine"] for m in meals), 1),
        "carbo": round(sum(m["total"]["carbo"] for m in meals), 1),
        "grassi": round(sum(m["total"]["grassi"] for m in meals), 1),
    }

def print_day(name, target, meals_data):
    print(f"\n{'='*60}")
    print(f"{name} - Target {target} kcal")
    print(f"{'='*60}")
    meal_objs = []
    for mname, items in meals_data:
        t = meal_total(items)
        meal_objs.append({"total": t})
        print(f"  {mname}: {t['kcal']} kcal | P:{t['proteine']} C:{t['carbo']} G:{t['grassi']}")
    dt = day_total(meal_objs)
    diff = dt['kcal'] - target
    status = "OK" if abs(diff) <= 50 else "KO"
    print(f"  TOTALE: {dt['kcal']} kcal | P:{dt['proteine']} C:{dt['carbo']} G:{dt['grassi']} | diff:{diff:+d} [{status}]")
    return dt

# TARGET: allenamento 2850, riposo 2650, beach volley 3100, sgarro ~2800
# MACRO TARGET: P 180g, C adattato, G 75-80g

# ============================================================
# DAY 1 - Lunedi - Allenamento Pesi (target 2850)
# ============================================================
d1 = print_day("G1 Lunedi - Allenamento Pesi", 2850, [
    ("Colazione", [
        calc("Yogurt greco 0%", 150),
        calc("Muesli proteico", 30),
        calc("Banana", 120),
        calc("Mandorle", 20),
    ]),
    ("Pranzo", [
        calc("Pasta di semola", 120),
        calc("Sugo al pomodoro", 80),
        calc("Parmigiano grattugiato", 10),
        calc("Olio EVO", 10),
        calc("Petto di pollo", 200),
        calc("Insalata mista", 100),
        calc("Pane integrale", 40),
    ]),
    ("Merenda", [
        calc("Banana", 120),
        calc("Whey proteine", 35),
        calc("Latte parz. scremato", 250),
    ]),
    ("Cena", [
        calc("Salmone fresco", 200),
        calc("Patate", 350),
        calc("Zucchine", 200),
        calc("Olio EVO", 15),
        calc("Pane integrale", 60),
    ]),
])

# ============================================================
# DAY 2 - Martedi - Riposo (target 2650)
# ============================================================
d2 = print_day("G2 Martedi - Riposo", 2650, [
    ("Colazione", [
        calc("Yogurt greco 0%", 150),
        calc("Muesli proteico", 30),
        calc("Mela", 180),
        calc("Noci", 15),
    ]),
    ("Pranzo", [
        calc("Lenticchie secche", 80),
        calc("Verdure miste per minestra", 200),
        calc("Pasta di semola", 50),
        calc("Olio EVO", 10),
        calc("Parmigiano grattugiato", 10),
        calc("Pane integrale", 80),
        calc("Banana", 120),
    ]),
    ("Merenda", [
        calc("Mela", 180),
        calc("Whey proteine", 35),
        calc("Latte parz. scremato", 250),
    ]),
    ("Cena", [
        calc("Petto di pollo", 250),
        calc("Riso basmati", 90),
        calc("Zucchine", 200),
        calc("Olio EVO", 15),
        calc("Pane integrale", 40),
    ]),
])

# ============================================================
# DAY 3 - Mercoledi - Allenamento Pesi (target 2850)
# ============================================================
d3 = print_day("G3 Mercoledi - Allenamento Pesi", 2850, [
    ("Colazione", [
        calc("Yogurt greco 0%", 150),
        calc("Muesli proteico", 30),
        calc("Banana", 120),
        calc("Mandorle", 20),
    ]),
    ("Pranzo", [
        calc("Pasta di semola", 120),
        calc("Pesto alla genovese", 25),
        calc("Parmigiano grattugiato", 10),
        calc("Petto di pollo", 180),
        calc("Insalata mista", 100),
        calc("Pane integrale", 40),
    ]),
    ("Merenda", [
        calc("Banana", 120),
        calc("Whey proteine", 35),
        calc("Latte parz. scremato", 250),
    ]),
    ("Cena", [
        calc("Trota", 300),
        calc("Patate", 350),
        calc("Insalata mista", 150),
        calc("Olio EVO", 15),
        calc("Pane integrale", 60),
    ]),
])

# ============================================================
# DAY 4 - Giovedi - Beach Volley (target 3100)
# ============================================================
d4 = print_day("G4 Giovedi - Beach Volley", 3100, [
    ("Colazione", [
        calc("Yogurt greco 0%", 150),
        calc("Muesli proteico", 30),
        calc("Banana", 120),
        calc("Fiocchi avena", 50),
        calc("Mandorle", 20),
    ]),
    ("Pranzo", [
        calc("Pasta di semola", 130),
        calc("Sugo al pomodoro", 80),
        calc("Tonno in scatola sgocciolato", 120),
        calc("Parmigiano grattugiato", 10),
        calc("Olio EVO", 10),
        calc("Pane integrale", 50),
        calc("Banana", 120),
    ]),
    ("Merenda", [
        calc("Banana", 120),
        calc("Whey proteine", 40),
        calc("Latte parz. scremato", 300),
    ]),
    ("Cena", [
        calc("Petto di pollo", 250),
        calc("Riso basmati", 100),
        calc("Zucchine", 200),
        calc("Olio EVO", 15),
        calc("Pane integrale", 60),
    ]),
])

# ============================================================
# DAY 5 - Venerdi - Allenamento Pesi (target 2850)
# ============================================================
d5 = print_day("G5 Venerdi - Allenamento Pesi", 2850, [
    ("Colazione", [
        calc("Yogurt greco 0%", 150),
        calc("Muesli proteico", 30),
        calc("Banana", 120),
        calc("Mandorle", 20),
    ]),
    ("Pranzo", [  # Carbonara
        calc("Pasta di semola", 120),
        calc("Guanciale", 25),
        calc("Pecorino romano", 20),
        calc("Uova intere", 60),  # 1 uovo
        calc("Insalata mista", 100),
        calc("Pane integrale", 40),
    ]),
    ("Merenda", [
        calc("Mela", 180),
        calc("Whey proteine", 35),
        calc("Latte parz. scremato", 250),
    ]),
    ("Cena", [
        calc("Manzo macinato magro", 220),
        calc("Patate", 350),
        calc("Insalata mista", 150),
        calc("Olio EVO", 15),
        calc("Pane integrale", 50),
    ]),
])

# ============================================================
# DAY 6 - Sabato - Riposo SGARRO (target ~2800)
# ============================================================
d6 = print_day("G6 Sabato - Riposo Sgarro", 2800, [
    ("Colazione", [
        calc("Yogurt greco 0%", 150),
        calc("Muesli proteico", 30),
        calc("Banana", 120),
    ]),
    ("Pranzo - Sgarro", [
        calc("Pizza margherita", 400),  # una pizza intera
        calc("Insalata mista", 100),
    ]),
    ("Merenda", [
        calc("Mela", 180),
        calc("Whey proteine", 35),
        calc("Latte parz. scremato", 200),
    ]),
    ("Cena", [
        calc("Bresaola", 100),
        calc("Parmigiano grattugiato", 20),
        calc("Insalata mista", 150),
        calc("Olio EVO", 10),
        calc("Pane integrale", 60),
    ]),
])

# ============================================================
# DAY 7 - Domenica - Riposo (target 2650)
# ============================================================
d7 = print_day("G7 Domenica - Riposo", 2650, [
    ("Colazione", [
        calc("Yogurt greco 0%", 150),
        calc("Muesli proteico", 30),
        calc("Mela", 180),
        calc("Noci", 15),
    ]),
    ("Pranzo", [  # Minestra con piselli
        calc("Piselli surgelati", 120),
        calc("Verdure miste per minestra", 200),
        calc("Pasta di semola", 60),
        calc("Olio EVO", 10),
        calc("Parmigiano grattugiato", 10),
        calc("Pane integrale", 80),
        calc("Banana", 120),
    ]),
    ("Merenda", [
        calc("Mela", 180),
        calc("Whey proteine", 35),
        calc("Latte parz. scremato", 250),
    ]),
    ("Cena", [
        calc("Uova intere", 120),  # 2 uova grandi
        calc("Mozzarella", 150),
        calc("Pomodoro fresco", 200),
        calc("Pane integrale", 80),
        calc("Olio EVO", 10),
    ]),
])

# Summary
print(f"\n{'='*60}")
print("RIEPILOGO SETTIMANALE")
print(f"{'='*60}")
days = [("Lun pesi", d1), ("Mar rip", d2), ("Mer pesi", d3),
        ("Gio beach", d4), ("Ven pesi", d5), ("Sab sgarro", d6), ("Dom rip", d7)]
for name, d in days:
    print(f"  {name}: {d['kcal']} kcal | P:{d['proteine']}g C:{d['carbo']}g G:{d['grassi']}g")
avg = sum(d['kcal'] for _, d in days) / 7
avg_p = sum(d['proteine'] for _, d in days) / 7
print(f"\n  Media: {avg:.0f} kcal | P:{avg_p:.0f}g")
