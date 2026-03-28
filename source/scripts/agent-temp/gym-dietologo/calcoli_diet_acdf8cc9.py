# File temporaneo creato da gym-dietologo il 2026-03-27
# Scopo: verifica calcoli macro e kcal per la dieta acdf8cc9
# Puo' essere eliminato al termine dell'iterazione

# === DATI ATLETA ===
peso = 85.9  # kg
altezza = 188  # cm
eta = 38
bf_pct = 17.1
massa_magra = 71.2  # kg
bmr = 1839  # kcal
tdee = 2850  # kcal (BMR * 1.55)

# === FASE ===
# Piano dice: mantenimento (rehab TOS)
# BF% = 17.1% -> sopra soglia cut (15%) ma piano dice mantenimento per rehab
# Analisi automatica raccomanda: +150 kcal -> 3000 kcal
# Motivazione: catabolismo rilevato (massa magra persa = 66% della perdita totale)
# Da 89.4 a 85.9 = -3.5 kg totali, di cui 73.5-71.2 = -2.3 kg massa magra (66%)
# Questo e' preoccupante: l'atleta sta perdendo troppa massa magra

# DECISIONE: mantenimento a 2950 kcal (base giorno palestra)
# Motivazione:
# - L'analisi suggerisce 3000 ma l'atleta ha BF 17.1% (sopra 15%)
# - L'atleta e' in rehab con solo 3 sessioni/sett a bassa intensita' (RPE 5-7)
# - Il catabolismo va fermato con proteine alte, non necessariamente con surplus
# - Un leggero aumento rispetto al TDEE base (2850) e' sufficiente
# - Non voglio surplus eccessivo dato il BF alto e l'attivita' ridotta

# === TARGET PER TIPO DI GIORNO ===
# Giorno palestra (3x/sett): 2950 kcal (TDEE + 100)
# Giorno beach volley (1x/sett giovedi): 3200 kcal (TDEE + 350, sport 90min media intensita' ~300-400 kcal extra)
# Giorno riposo (3x/sett): 2700 kcal (TDEE - 150)

# Media settimanale: (3*2950 + 1*3200 + 3*2700) / 7 = (8850 + 3200 + 8100) / 7 = 20150 / 7 = 2878 kcal
# Circa 2880 kcal/die media -> leggermente sopra TDEE, anti-catabolico

kcal_palestra = 2950
kcal_beach = 3200
kcal_riposo = 2700

media = (3*kcal_palestra + 1*kcal_beach + 3*kcal_riposo) / 7
print(f"Media settimanale: {media:.0f} kcal/die")

# === MACRO ===
# Proteine: 2.0 g/kg (priorita' anti-catabolismo in rehab) = 172 g -> arrotondiamo a 175g
# Grassi: 0.9 g/kg = 77g -> arrotondiamo a 80g
# Carboidrati: resto delle kcal

prot_g = 175
grassi_g_riposo = 78
grassi_g_palestra = 80
grassi_g_beach = 82

# Kcal da proteine e grassi
prot_kcal = prot_g * 4  # 700

# Riposo
grassi_kcal_r = grassi_g_riposo * 9  # 702
carbo_kcal_r = kcal_riposo - prot_kcal - grassi_kcal_r  # 2700 - 700 - 702 = 1298
carbo_g_r = carbo_kcal_r / 4  # 324.5 -> 325

# Palestra
grassi_kcal_p = grassi_g_palestra * 9  # 720
carbo_kcal_p = kcal_palestra - prot_kcal - grassi_kcal_p  # 2950 - 700 - 720 = 1530
carbo_g_p = carbo_kcal_p / 4  # 382.5 -> 383

# Beach volley
grassi_kcal_b = grassi_g_beach * 9  # 738
carbo_kcal_b = kcal_beach - prot_kcal - grassi_kcal_b  # 3200 - 700 - 738 = 1762
carbo_g_b = carbo_kcal_b / 4  # 440.5 -> 440

print(f"\nRiposo: {kcal_riposo} kcal | P {prot_g}g | C {carbo_g_r:.0f}g | G {grassi_g_riposo}g")
print(f"Verifica: {prot_g*4 + carbo_g_r*4 + grassi_g_riposo*9:.0f}")
print(f"\nPalestra: {kcal_palestra} kcal | P {prot_g}g | C {carbo_g_p:.0f}g | G {grassi_g_palestra}g")
print(f"Verifica: {prot_g*4 + carbo_g_p*4 + grassi_g_palestra*9:.0f}")
print(f"\nBeach V: {kcal_beach} kcal | P {prot_g}g | C {carbo_g_b:.0f}g | G {grassi_g_beach}g")
print(f"Verifica: {prot_g*4 + carbo_g_b*4 + grassi_g_beach*9:.0f}")

# === DISTRIBUZIONE SLOT ===
# Atleta vuole: colazione abbondante, pranzo e cena non troppo voluminosi
# 4 pasti + merenda opzionale (datteri+noci) + eventuale shaker whey
# Slot: colazione, spuntino (opzionale), pranzo, merenda (whey+frutto), cena

# Distribuzione %:
# Colazione: 20-22% (abbondante come richiesto)
# Spuntino: 7-8%
# Pranzo: 28-30%
# Merenda: 10-12%
# Cena: 28-30%

print("\n=== DISTRIBUZIONE SLOT ===")
for label, tot in [("Riposo", 2700), ("Palestra", 2950), ("Beach", 3200)]:
    col = round(tot * 0.21)
    spu = round(tot * 0.07)
    pra = round(tot * 0.29)
    mer = round(tot * 0.12)
    cen = round(tot * 0.31)
    somma = col + spu + pra + mer + cen
    print(f"{label}: Col {col} + Spu {spu} + Pra {pra} + Mer {mer} + Cen {cen} = {somma} (target {tot}, diff {somma-tot})")
