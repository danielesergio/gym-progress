# File temporaneo creato da gym-dietologo il 2026-03-27
# Scopo: verifica calcoli macro e kcal per ogni slot e tipo giorno
# Puo' essere eliminato al termine dell'iterazione

peso = 85.9
prot_g = 172  # 2.0 g/kg
fat_g = 77    # 0.9 g/kg

kcal_riposo = 2800
kcal_palestra = 3000
kcal_beach = 3250

for label, kcal_tot in [("riposo", kcal_riposo), ("palestra", kcal_palestra), ("beach", kcal_beach)]:
    prot_kcal = prot_g * 4
    fat_kcal = fat_g * 9
    carb_kcal = kcal_tot - prot_kcal - fat_kcal
    carb_g = carb_kcal / 4
    print(f"{label}: {kcal_tot} kcal | P {prot_g}g ({prot_kcal}) | C {carb_g:.0f}g ({carb_kcal:.0f}) | F {fat_g}g ({fat_kcal})")

# Distribuzione slot - atleta vuole colazione abbondante
# colazione ~22%, pranzo ~30%, merenda ~15%, cena ~33%
print("\n=== DISTRIBUZIONE SLOT ===")
for tipo, tot in [("riposo", 2800), ("palestra", 3000), ("beach", 3250)]:
    c = round(tot * 0.22 / 10) * 10
    p = round(tot * 0.30 / 10) * 10
    m = round(tot * 0.15 / 10) * 10
    ce = tot - c - p - m  # cena = residuo per quadrare
    print(f"{tipo}: col={c} pranzo={p} mer={m} cena={ce} SUM={c+p+m+ce}")
