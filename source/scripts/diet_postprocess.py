"""
Postprocessing della dieta grezza generata dal gym-dietologo.

Legge:  data/output/diet_<id>_raw.yaml   (generato dall'LLM con grammi indicativi)
Legge:  data/output/food.yaml             (valori nutrizionali per 100g)

Per ogni slot/opzione/tipo_giorno:
  - Recupera i valori nutrizionali reali da food.yaml
  - Scala i grammi con un solver lineare (scipy) per centrare kcal sul target
  - Ricalcola tutti i totali aritmeticamente
  - Garantisce l'intercambiabilita' tra opzioni dello stesso slot (±50 kcal)

Scrive: data/output/diet_<id>.yaml
"""

import sys
import copy
import math
from pathlib import Path

import yaml
import numpy as np
from scipy.optimize import linprog


# ──────────────────────────────────────────────────────────────────────────────
# I/O
# ──────────────────────────────────────────────────────────────────────────────

def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ──────────────────────────────────────────────────────────────────────────────
# Food database
# ──────────────────────────────────────────────────────────────────────────────

def build_food_db(food_yaml: dict) -> dict[str, dict]:
    """Restituisce {nome_lower: {kcal, proteine, carboidrati, grassi}} per 100g."""
    db = {}
    for item in food_yaml.get("alimenti", []):
        key = item["nome"].strip().lower()
        db[key] = {
            "kcal":        float(item.get("kcal", 0)),
            "proteine":    float(item.get("proteine", 0)),
            "carboidrati": float(item.get("carboidrati", 0)),
            "grassi":      float(item.get("grassi", 0)),
        }
    return db


def lookup(food_db: dict, nome: str) -> dict | None:
    """Cerca un alimento nel DB con fallback case-insensitive e fuzzy."""
    key = nome.strip().lower()
    if key in food_db:
        return food_db[key]
    # Cerca se il nome e' contenuto in una chiave o viceversa
    for db_key, val in food_db.items():
        if key in db_key or db_key in key:
            return val
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Solver
# ──────────────────────────────────────────────────────────────────────────────

def scale_grams(
        alimenti: list[dict],
        food_db: dict,
        kcal_target: float,
        *,
        macro_tolerance: float = 0.1,  # 10%
        min_scale: float = 0.5,
        max_scale: float = 2.5,
) -> list[dict]:

    n = len(alimenti)
    if n == 0:
        return alimenti

    nutri = []
    g_ind = []

    for a in alimenti:
        nd = lookup(food_db, a["nome"])
        if nd is None:
            g = float(a.get("grammi", 100))
            if g > 0:
                nd = {
                    "kcal":        float(a.get("kcal", 0)) / g * 100,
                    "proteine":    float(a.get("proteine", 0)) / g * 100,
                    "carboidrati": float(a.get("carbo", a.get("carboidrati", 0))) / g * 100,
                    "grassi":      float(a.get("grassi", 0)) / g * 100,
                }
            else:
                nd = {"kcal": 0, "proteine": 0, "carboidrati": 0, "grassi": 0}

        nutri.append(nd)
        g_ind.append(max(float(a.get("grammi", 100)), 1.0))

    g_ind = np.array(g_ind)

    kcal_per_g = np.array([nd["kcal"] / 100.0 for nd in nutri])
    prot_per_g = np.array([nd["proteine"] / 100.0 for nd in nutri])
    carb_per_g = np.array([nd["carboidrati"] / 100.0 for nd in nutri])
    fat_per_g  = np.array([nd["grassi"] / 100.0 for nd in nutri])

    # Target macro stimati dai dati raw
    kcal_current = float(kcal_per_g @ g_ind)
    prot_current = float(prot_per_g @ g_ind)
    carb_current = float(carb_per_g @ g_ind)
    fat_current  = float(fat_per_g @ g_ind)

    if kcal_current == 0:
        return _recompute(alimenti, nutri, g_ind.tolist())

    # Variabili: grammi x_i
    # Obiettivo: minimizzare deviazione dai grammi originali

    c = np.concatenate([
        np.zeros(n),          # x
        np.ones(n)            # slack per deviazione assoluta
    ])

    # x_i - t_i <= g_ind
    # -x_i - t_i <= -g_ind
    A_ub = []
    b_ub = []

    for i in range(n):
        row1 = np.zeros(2*n)
        row1[i] = 1
        row1[n+i] = -1
        A_ub.append(row1)
        b_ub.append(g_ind[i])

        row2 = np.zeros(2*n)
        row2[i] = -1
        row2[n+i] = -1
        A_ub.append(row2)
        b_ub.append(-g_ind[i])

    A_ub = np.array(A_ub)
    b_ub = np.array(b_ub)

    # === VINCOLI ===

    A_eq = []

    # kcal hard constraint
    row_kcal = np.zeros(2*n)
    row_kcal[:n] = kcal_per_g
    A_eq.append(row_kcal)
    b_eq = [kcal_target]

    A_eq = np.array(A_eq)
    b_eq = np.array(b_eq)

    # macro soft constraints come bounds
    def add_macro_constraint(vec, target):
        lower = target * (1 - macro_tolerance)
        upper = target * (1 + macro_tolerance)
        return vec, lower, upper

    constraints = [
        add_macro_constraint(prot_per_g, prot_current),
        add_macro_constraint(carb_per_g, carb_current),
        add_macro_constraint(fat_per_g, fat_current),
    ]

    # Convert macro bounds into inequality constraints
    for vec, lower, upper in constraints:
        # lower <= sum(x_i * vec_i) <= upper

        row = np.zeros(2*n)
        row[:n] = vec
        A_ub = np.vstack([A_ub, row])
        b_ub = np.append(b_ub, upper)

        row = np.zeros(2*n)
        row[:n] = -vec
        A_ub = np.vstack([A_ub, row])
        b_ub = np.append(b_ub, -lower)

    # bounds su x_i
    bounds = [(min_scale * g, max_scale * g) for g in g_ind] + [(0, None)] * n

    res = linprog(
        c,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs"
    )

    if res.success:
        x = res.x[:n]
    else:
        # fallback: scaling globale
        scale = kcal_target / kcal_current
        x = g_ind * np.clip(scale, min_scale, max_scale)

    new_grams = [round(g) for g in x]
    return _recompute(alimenti, nutri, new_grams.tolist())


def _recompute(alimenti: list[dict], nutri: list[dict], new_grams: list[float]) -> list[dict]:
    """Ricostruisce la lista alimenti con grammi aggiornati e macro ricalcolati."""
    result = []
    for a, nd, g in zip(alimenti, nutri, new_grams):
        g = max(round(g), 1)
        factor = g / 100.0
        new_a = copy.deepcopy(a)
        new_a["grammi"]   = g
        new_a["kcal"]     = round(nd["kcal"]        * factor, 1)
        new_a["proteine"] = round(nd["proteine"]     * factor, 1)
        new_a["carbo"]    = round(nd["carboidrati"]  * factor, 1)
        new_a["grassi"]   = round(nd["grassi"]       * factor, 1)
        result.append(new_a)
    return result


def compute_totale(alimenti: list[dict]) -> dict:
    """Somma aritmetica esatta dei macro."""
    totale = {"kcal": 0.0, "proteine": 0.0, "carbo": 0.0, "grassi": 0.0}
    for a in alimenti:
        totale["kcal"]     += float(a.get("kcal", 0))
        totale["proteine"] += float(a.get("proteine", 0))
        totale["carbo"]    += float(a.get("carbo", a.get("carboidrati", 0)))
        totale["grassi"]   += float(a.get("grassi", 0))
    return {k: round(v, 1) for k, v in totale.items()}


# ──────────────────────────────────────────────────────────────────────────────
# Intercambiabilita'
# ──────────────────────────────────────────────────────────────────────────────

def enforce_interchangeability(
    slot: dict,
    food_db: dict,
    tipo_kcal: dict[str, float],
    *,
    tolerance: float = 50.0,
) -> None:
    """
    Garantisce che tutte le opzioni di un slot abbiano kcal entro ±tolerance
    dal target per ogni tipo di giorno. Modifica le opzioni in-place.
    """
    for tipo_id, kcal_target in tipo_kcal.items():
        for opzione in slot.get("opzioni", []):
            variante = opzione.get("varianti", {}).get(tipo_id)
            if not variante:
                continue
            alimenti = variante.get("alimenti", [])
            if not alimenti:
                variante["totale"] = {"kcal": 0.0, "proteine": 0.0, "carbo": 0.0, "grassi": 0.0}
                continue

            # Prima passata: porta kcal vicino al target
            scaled = scale_grams(alimenti, food_db, kcal_target)
            variante["alimenti"] = scaled
            variante["totale"]   = compute_totale(scaled)

        # Seconda passata: normalizza le opzioni al target comune dello slot
        # (usa la media kcal delle opzioni come riferimento se spread < tolerance)
        kcal_vals = []
        for opzione in slot.get("opzioni", []):
            variante = opzione.get("varianti", {}).get(tipo_id, {})
            if variante.get("alimenti"):
                kcal_vals.append(variante["totale"]["kcal"])

        if len(kcal_vals) <= 1:
            continue

        spread = max(kcal_vals) - min(kcal_vals)
        if spread <= tolerance:
            continue

        # Lo spread supera la tolleranza: forza tutte al target dello slot
        for opzione in slot.get("opzioni", []):
            variante = opzione.get("varianti", {}).get(tipo_id)
            if not variante or not variante.get("alimenti"):
                continue
            scaled = scale_grams(variante["alimenti"], food_db, kcal_target)
            variante["alimenti"] = scaled
            variante["totale"]   = compute_totale(scaled)


# ──────────────────────────────────────────────────────────────────────────────
# Validazione e report
# ──────────────────────────────────────────────────────────────────────────────

def validate_and_report(diet: dict) -> list[str]:
    """Ritorna una lista di warning (stringa) per anomalie rilevate."""
    warnings = []
    tipi = {t["id"]: t for t in diet.get("meta", {}).get("tipi_giorno", [])}
    tolerance = 50.0

    for tipo_id, tipo in tipi.items():
        kcal_target = tipo.get("kcal_target", 0)
        slot_sum = 0.0
        for slot in diet.get("slot_pasto", []):
            slot_sum += slot.get("kcal_per_tipo", {}).get(tipo_id, 0)
        diff = abs(slot_sum - kcal_target)
        if diff > tolerance:
            warnings.append(
                f"[WARN] tipo={tipo_id}: somma slot_kcal={slot_sum} vs target={kcal_target} (diff={diff:.0f})"
            )

    for slot in diet.get("slot_pasto", []):
        slot_id = slot.get("id", "?")
        for tipo_id in tipi:
            kcal_slot_target = slot.get("kcal_per_tipo", {}).get(tipo_id, 0)
            kcal_vals = []
            for opzione in slot.get("opzioni", []):
                variante = opzione.get("varianti", {}).get(tipo_id, {})
                if variante.get("alimenti"):
                    kcal_vals.append(variante["totale"]["kcal"])
            if not kcal_vals:
                continue
            spread = max(kcal_vals) - min(kcal_vals)
            avg    = sum(kcal_vals) / len(kcal_vals)
            diff   = abs(avg - kcal_slot_target)
            if spread > tolerance:
                warnings.append(
                    f"[WARN] slot={slot_id} tipo={tipo_id}: spread opzioni={spread:.0f} kcal (>50)"
                )
            if diff > tolerance:
                warnings.append(
                    f"[WARN] slot={slot_id} tipo={tipo_id}: media opzioni={avg:.0f} vs target={kcal_slot_target} (diff={diff:.0f})"
                )

    return warnings


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def postprocess(raw_path: Path, food_path: Path, out_path: Path) -> list[str]:
    """
    Esegue il postprocessing completo.
    Ritorna la lista di warning.
    """
    raw  = load_yaml(raw_path)
    food = load_yaml(food_path)

    food_db = build_food_db(food)
    diet    = copy.deepcopy(raw)

    tipi_kcal_per_slot: dict[str, dict[str, float]] = {}
    for slot in diet.get("slot_pasto", []):
        slot_id = slot.get("id", "")
        tipi_kcal_per_slot[slot_id] = slot.get("kcal_per_tipo", {})

    for slot in diet.get("slot_pasto", []):
        slot_id   = slot.get("id", "")
        tipo_kcal = tipi_kcal_per_slot.get(slot_id, {})
        enforce_interchangeability(slot, food_db, tipo_kcal)

    warnings = validate_and_report(diet)

    save_yaml(out_path, diet)
    return warnings


def main():
    if len(sys.argv) < 2:
        print("Usage: python diet_postprocess.py <iteration_id>")
        print("       python diet_postprocess.py <raw_path> <food_path> <out_path>")
        sys.exit(1)

    base = Path(__file__).parent.parent / "data" / "output"

    if len(sys.argv) == 2:
        iteration_id = sys.argv[1]
        raw_path  = base / f"diet_{iteration_id}_raw.yaml"
        food_path = base / "food.yaml"
        out_path  = base / f"diet_{iteration_id}.yaml"
    else:
        raw_path  = Path(sys.argv[1])
        food_path = Path(sys.argv[2])
        out_path  = Path(sys.argv[3])

    if not raw_path.exists():
        print(f"ERROR: file non trovato: {raw_path}")
        sys.exit(1)
    if not food_path.exists():
        print(f"ERROR: food.yaml non trovato: {food_path}")
        sys.exit(1)

    print(f"Input  : {raw_path}")
    print(f"Food DB: {food_path}")
    print(f"Output : {out_path}")

    warnings = postprocess(raw_path, food_path, out_path)

    if warnings:
        print("\nWARNINGS:")
        for w in warnings:
            print(f"  {w}")
    else:
        print("\nOK: nessun warning.")

    print(f"\nScritto: {out_path}")


if __name__ == "__main__":
    main()
