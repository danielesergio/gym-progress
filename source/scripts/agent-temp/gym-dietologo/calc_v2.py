# Ricalcolo con distribuzione piu' equilibrata
# Atleta: 4 pasti + merenda opzionale (datteri/mandorle tra colazione e pranzo)
# Vuole colazione abbondante, pranzo e cena moderati
# Merenda: frutto + whey semplice

# Rivedo macros con grassi leggermente piu' alti per ridurre carbo
peso = 85.9
prot_g = 172  # 2.0 g/kg
fat_g = 80    # ~0.93 g/kg (leggermente piu' alto)

for label, kcal_tot in [("riposo", 2800), ("palestra", 3000), ("beach", 3250)]:
    prot_kcal = prot_g * 4
    fat_kcal = fat_g * 9
    carb_kcal = kcal_tot - prot_kcal - fat_kcal
    carb_g = carb_kcal / 4
    print(f"{label}: {kcal_tot} kcal | P {prot_g}g | C {carb_g:.0f}g | F {fat_g}g")

# Slot: colazione, spuntino (opzionale tra colazione e pranzo), pranzo, merenda (whey+frutto), cena
# Atleta dice "se serve un altro pasto aggiuntivo vorrei che fosse super semplice (frutto + proteine whey)"
# e "ogni tanto faccio una merenda aggiuntiva (tra colazione e pranzo) con datteri e mandorle o noci"
# Quindi: 5 slot -> colazione, spuntino mattina, pranzo, merenda pomeriggio, cena

# Distribuzione: colazione ~20%, spuntino ~7%, pranzo ~28%, merenda ~12%, cena ~33%
print("\n=== DISTRIBUZIONE 5 SLOT ===")
for tipo, tot in [("riposo", 2800), ("palestra", 3000), ("beach", 3250)]:
    col = round(tot * 0.20 / 10) * 10
    spu = round(tot * 0.07 / 10) * 10
    pra = round(tot * 0.28 / 10) * 10
    mer = round(tot * 0.13 / 10) * 10
    cen = tot - col - spu - pra - mer
    print(f"{tipo}: col={col} spu={spu} pra={pra} mer={mer} cen={cen} SUM={col+spu+pra+mer+cen}")

# Hmm, but atleta says "Numero pasti preferito al giorno: 4" and 
# "se serve un altro pasto aggiuntivo vorrei che fosse super semplice"
# So let's keep 4 main slots + 1 optional spuntino
# colazione(abbondante) ~22%, spuntino(optional) ~7%, pranzo ~28%, merenda ~12%, cena ~31%
print("\n=== DISTRIBUZIONE 5 SLOT v2 ===")
for tipo, tot in [("riposo", 2800), ("palestra", 3000), ("beach", 3250)]:
    col = 600 if tipo == "riposo" else (650 if tipo == "palestra" else 700)
    spu = 200  # sempre uguale, semplice
    pra = 780 if tipo == "riposo" else (840 if tipo == "palestra" else 920)
    mer = 350 if tipo == "riposo" else (380 if tipo == "palestra" else 400)
    cen = tot - col - spu - pra - mer
    print(f"{tipo}: col={col} spu={spu} pra={pra} mer={mer} cen={cen} SUM={col+spu+pra+mer+cen}")
