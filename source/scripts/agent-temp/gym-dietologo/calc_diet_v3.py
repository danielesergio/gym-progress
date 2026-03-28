# File temporaneo creato da gym-dietologo il 2026-03-23
# Scopo: verifica calcoli macro v3 - porzioni finali corrette
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
        for item in items:
            print(f"    - {item['nome']} {item['grammi']}g: {item['kcal']}kcal P:{item['proteine']} C:{item['carbo']} G:{item['grassi']}")
    dt = day_total(meal_objs)
    diff = dt['kcal'] - target
    status = "OK" if abs(diff) <= 50 else "KO"
    print(f"  TOTALE: {dt['kcal']} kcal | P:{dt['proteine']} C:{dt['carbo']} G:{dt['grassi']} | diff:{diff:+d} [{status}]")
    return dt

# ============================================================
# DAY 1 - Lunedi - Allenamento Pesi (target 2850)
# Strategy: bigger lunch portion, add bread/carbs to hit target
# ============================================================
d1 = print_day("G1 Lunedi - Allenamento Pesi", 2850, [
    ("Colazione", [
        calc("Yogurt greco 0%", 150),   # 86 P:15.5 C:6.0 G:1.1
        calc("Muesli proteico", 30),     # 108 P:8.9 C:13.6 G:1.7
        calc("Banana", 130),             # 116 P:1.4 C:29.6 G:0.4
        calc("Mandorle", 25),            # 145 P:5.3 C:5.5 G:12.3
    ]),
    ("Pranzo", [
        calc("Pasta di semola", 120),    # 427 P:15.0 C:86.4 G:1.8
        calc("Sugo al pomodoro", 100),   # 40 P:1.5 C:6.0 G:1.0
        calc("Parmigiano grattugiato", 10), # 39 P:3.3 C:0.0 G:2.8
        calc("Olio EVO", 15),            # 133 P:0 C:0 G:15
        calc("Petto di pollo", 200),     # 220 P:46.2 C:0 G:2.4
        calc("Insalata mista", 100),     # 15 P:1.0 C:2.0 G:0.2
        calc("Pane integrale", 60),      # 148 P:4.8 C:26.4 G:2.1
    ]),
    ("Merenda", [
        calc("Banana", 130),
        calc("Whey proteine", 35),
        calc("Latte parz. scremato", 250),
    ]),
    ("Cena", [
        calc("Salmone fresco", 200),     # 416 P:40.8 C:0 G:26.8
        calc("Patate", 400),             # 308 P:8.0 C:68.0 G:0.4
        calc("Zucchine", 200),           # 34 P:2.4 C:4.0 G:0.6
        calc("Olio EVO", 10),            # 88 P:0 C:0 G:10
        calc("Pane integrale", 60),      # 148 P:4.8 C:26.4 G:2.1
    ]),
])

# ============================================================
# DAY 2 - Martedi - Riposo (target 2650)
# ============================================================
d2 = print_day("G2 Martedi - Riposo", 2650, [
    ("Colazione", [
        calc("Yogurt greco 0%", 150),
        calc("Muesli proteico", 30),
        calc("Mela", 200),
        calc("Noci", 20),
    ]),
    ("Pranzo", [
        calc("Lenticchie secche", 90),   # 318 P:22.5 C:48.6 G:0.9
        calc("Verdure miste per minestra", 200), # 50 P:3 C:8 G:0.6
        calc("Pasta di semola", 60),     # 214 P:7.5 C:43.2 G:0.9
        calc("Olio EVO", 15),
        calc("Parmigiano grattugiato", 10),
        calc("Pane integrale", 80),
        calc("Banana", 130),
    ]),
    ("Merenda", [
        calc("Mela", 200),
        calc("Whey proteine", 35),
        calc("Latte parz. scremato", 250),
    ]),
    ("Cena", [
        calc("Petto di pollo", 250),
        calc("Riso basmati", 100),
        calc("Zucchine", 200),
        calc("Olio EVO", 10),
        calc("Pane integrale", 50),
    ]),
])

# ============================================================
# DAY 3 - Mercoledi - Allenamento Pesi (target 2850)
# ============================================================
d3 = print_day("G3 Mercoledi - Allenamento Pesi", 2850, [
    ("Colazione", [
        calc("Yogurt greco 0%", 150),
        calc("Muesli proteico", 30),
        calc("Banana", 130),
        calc("Mandorle", 25),
    ]),
    ("Pranzo", [
        calc("Pasta di semola", 120),
        calc("Pesto alla genovese", 30),  # 132 P:1.5 C:1.2 G:13.2
        calc("Parmigiano grattugiato", 10),
        calc("Petto di pollo", 200),
        calc("Insalata mista", 100),
        calc("Pane integrale", 60),
    ]),
    ("Merenda", [
        calc("Banana", 130),
        calc("Whey proteine", 35),
        calc("Latte parz. scremato", 250),
    ]),
    ("Cena", [
        calc("Trota", 300),              # 357 P:61.5 C:0 G:10.5
        calc("Patate", 400),
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
        calc("Fiocchi avena", 50),
        calc("Banana", 130),
        calc("Mandorle", 25),
    ]),
    ("Pranzo", [
        calc("Pasta di semola", 140),
        calc("Sugo al pomodoro", 100),
        calc("Tonno in scatola sgocciolato", 120),
        calc("Parmigiano grattugiato", 10),
        calc("Olio EVO", 10),
        calc("Pane integrale", 60),
        calc("Banana", 130),
    ]),
    ("Merenda", [
        calc("Banana", 130),
        calc("Whey proteine", 40),
        calc("Latte parz. scremato", 300),
    ]),
    ("Cena", [
        calc("Petto di pollo", 250),
        calc("Riso basmati", 120),
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
        calc("Banana", 130),
        calc("Mandorle", 25),
    ]),
    ("Pranzo", [  # Carbonara
        calc("Pasta di semola", 120),
        calc("Guanciale", 30),
        calc("Pecorino romano", 20),
        calc("Uova intere", 120),  # 2 uova
        calc("Insalata mista", 100),
        calc("Pane integrale", 50),
    ]),
    ("Merenda", [
        calc("Mela", 200),
        calc("Whey proteine", 35),
        calc("Latte parz. scremato", 250),
    ]),
    ("Cena", [
        calc("Manzo macinato magro", 250),
        calc("Patate", 400),
        calc("Insalata mista", 150),
        calc("Olio EVO", 15),
        calc("Pane integrale", 60),
    ]),
])

# ============================================================
# DAY 6 - Sabato - Riposo SGARRO pizza (target ~2750)
# ============================================================
d6 = print_day("G6 Sabato - Riposo Sgarro", 2750, [
    ("Colazione", [
        calc("Yogurt greco 0%", 150),
        calc("Muesli proteico", 30),
        calc("Banana", 130),
        calc("Noci", 20),
    ]),
    ("Pranzo - Sgarro", [
        calc("Pizza margherita", 450),  # una pizza intera ~450g
        calc("Insalata mista", 150),
    ]),
    ("Merenda", [
        calc("Mela", 200),
        calc("Whey proteine", 35),
        calc("Latte parz. scremato", 250),
    ]),
    ("Cena", [
        calc("Bresaola", 100),
        calc("Parmigiano grattugiato", 20),
        calc("Riso basmati", 80),
        calc("Insalata mista", 150),
        calc("Olio EVO", 10),
    ]),
])

# ============================================================
# DAY 7 - Domenica - Riposo (target 2650)
# ============================================================
d7 = print_day("G7 Domenica - Riposo", 2650, [
    ("Colazione", [
        calc("Yogurt greco 0%", 150),
        calc("Muesli proteico", 30),
        calc("Mela", 200),
        calc("Noci", 20),
    ]),
    ("Pranzo", [  # Minestra piselli
        calc("Piselli surgelati", 150),
        calc("Verdure miste per minestra", 200),
        calc("Pasta di semola", 70),
        calc("Olio EVO", 15),
        calc("Parmigiano grattugiato", 10),
        calc("Pane integrale", 80),
        calc("Banana", 130),
    ]),
    ("Merenda", [
        calc("Mela", 200),
        calc("Whey proteine", 35),
        calc("Latte parz. scremato", 250),
    ]),
    ("Cena", [
        calc("Uova intere", 180),  # 3 uova
        calc("Mozzarella", 125),
        calc("Pomodoro fresco", 200),
        calc("Pane integrale", 80),
        calc("Olio EVO", 10),
    ]),
])

# Summary
print(f"\n{'='*60}")
print("RIEPILOGO SETTIMANALE")
print(f"{'='*60}")
days = [("Lun pesi", d1, 2850), ("Mar rip", d2, 2650), ("Mer pesi", d3, 2850),
        ("Gio beach", d4, 3100), ("Ven pesi", d5, 2850), ("Sab sgarro", d6, 2750), ("Dom rip", d7, 2650)]
for name, d, t in days:
    diff = d['kcal'] - t
    print(f"  {name}: {d['kcal']} kcal (target {t}, diff {diff:+d}) | P:{d['proteine']}g C:{d['carbo']}g G:{d['grassi']}g")
avg = sum(d['kcal'] for _, d, _ in days) / 7
avg_p = sum(d['proteine'] for _, d, _ in days) / 7
print(f"\n  Media: {avg:.0f} kcal | P:{avg_p:.0f}g")
