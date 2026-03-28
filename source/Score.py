"""
Score.py — Calcolo matematico degli score per ogni entry di workout_history.

score = {
    "workout": int | None,   # 0-100
    "diet":    int | None,   # 0-100  (body_comp 50% + adherence 30% + energy 20%)
    "system":  int | None,   # 0-100  (workout 40% + diet 35% + consistency 25%)
}

I campi sono None se i dati necessari sono assenti (entry incompleta o dati mancanti).

Dipendenze esterne:
  - entry["tipo_fase"]   : tipo mesociclo (da workout_history, vedi _normalize_tipo)
  - feedback             : dict opzionale estratto da feedback_atleta.yaml
                           {
                             "seguito_scheda":  "si" | "parzialmente" | "no",
                             "dieta_seguita":   "si" | "parzialmente" | "no",
                             "energia_gen":     1-10 | None,
                             "qualita_sonno":   1-10 | None,
                             "stress":          "basso" | "medio" | "alto" | None,
                           }
  - history              : lista completa delle entry (per consistency_score)
  - feedback["infortuni"] : lista normalizzata [{descrizione, guarito, durata_giorni}]
                            usata per calcolare la frazione del periodo coperta da
                            infortuni e modulare bench e reg_mult (progressi più
                            facili da raggiungere, regressioni meno penalizzate)
                            e il peso del body_comp nel diet score.
                            Fallback: nota dell'entry ("Riabilitazione per:" / "Infortun*").
"""

from __future__ import annotations
import math
import re


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> int:
    return round(max(lo, min(hi, value)))


def _lift_sub_score(rate: float, bench: float) -> float:
    """
    Trasforma un rate di progressione (kg/mese) in un punteggio 0-100
    usando una curva logaritmica che evita la saturazione a 100.

    Progressi positivi:
        score = log2(1 + rate/bench) * 100
        rate == bench    → ~58   (buono, nella norma)
        rate == 2*bench  → ~100  (eccellente, difficile da raggiungere)
        rate == 0        →   0

    Regressioni: penalità lineare scalata per _REGRESSION_MULT del tipo.
    Questa funzione gestisce solo i progressi; le regressioni sono
    calcolate direttamente in _calc_workout.
    """
    if rate <= 0:
        return 0.0
    return min(100.0, math.log2(1.0 + rate / bench) * 100.0)


def _normalize_tipo(tipo_fase: str | None) -> str:
    """
    Normalizza il campo tipo_fase a un set canonico:
      accumulo | intensificazione | peaking | tapering |
      mini_cut | cut | mantenimento | rehab | sconosciuto
    """
    if not tipo_fase:
        return "sconosciuto"
    t = tipo_fase.lower().strip().replace("-", "_").replace(" ", "_")
    aliases = {
        "bulk":           "accumulo",
        "volume":         "accumulo",
        "hypertrophy":    "accumulo",
        "ipertrofia":     "accumulo",
        "strength":       "intensificazione",
        "forza":          "intensificazione",
        "peak":           "peaking",
        "deload":         "tapering",
        "scarico":        "tapering",
        "cut":            "cut",
        "mini_cut":       "mini_cut",
        "minicut":        "mini_cut",
        "maint":          "mantenimento",
        "maintenance":    "mantenimento",
        "rehab":          "rehab",
        "recupero":       "rehab",
        "ramp_up":        "rehab",
        "rampup":         "rehab",
        "reintroduzione": "rehab",
    }
    return aliases.get(t, t)


# ────────────────────────────────────────────────────────────────────────────
# Benchmark forza per tipo mesociclo
# ────────────────────────────────────────────────────────────────────────────
_BENCH: dict[str, dict[str, float]] = {
    # kg/mese di riferimento per un atleta intermedio-avanzato.
    # Score = log2(1 + rate/bench) * 100 — vedi _lift_sub_score().
    # Con rate == bench → score ≈ 58 (buono ma non eccelso).
    # Con rate == 2*bench → score ≈ 100 (eccellente).
    # Con rate == 0 → score = 0.
    # Valori derivati da letteratura (NSCA) per intermedio → avanzato:
    #   squat ~15-20 kg/anno, panca ~10-15 kg/anno, stacco ~20-25 kg/anno.
    "accumulo":         {"squat": 1.5, "panca": 1.0, "stacco": 2.0},
    "intensificazione": {"squat": 0.8, "panca": 0.5, "stacco": 1.0},
    "peaking":          {"squat": 0.3, "panca": 0.2, "stacco": 0.4},
    "tapering":         {"squat": 0.2, "panca": 0.1, "stacco": 0.2},
    "mini_cut":         {"squat": 0.3, "panca": 0.2, "stacco": 0.4},
    "cut":              {"squat": 0.2, "panca": 0.1, "stacco": 0.3},
    "mantenimento":     {"squat": 0.3, "panca": 0.2, "stacco": 0.4},
    "rehab":            {"squat": 0.2, "panca": 0.1, "stacco": 0.2},
    "sconosciuto":      {"squat": 1.0, "panca": 0.7, "stacco": 1.5},
}

_REGRESSION_MULT: dict[str, float] = {
    "accumulo":         3.0,
    "intensificazione": 2.5,
    "peaking":          1.5,
    "tapering":         0.5,
    "mini_cut":         1.0,
    "cut":              0.5,
    "mantenimento":     1.5,
    "rehab":            0.3,
    "sconosciuto":      2.0,
}

_LIFT_WEIGHTS = {"squat": 0.35, "panca": 0.30, "stacco": 0.35}

_BENCH_MM_BULK_KG_MESE   = 0.8
_BENCH_BF_CUT_PCT_MESE   = 0.6
_BENCH_MM_CUT_LOSS_MESE  = 0.3


# ────────────────────────────────────────────────────────────────────────────
# Sub-score primitivi (restituiscono float 0-100)
# ────────────────────────────────────────────────────────────────────────────

def _adherence_score(feedback: dict | None) -> float:
    """
    Score di aderenza alla scheda di allenamento (0-100).
      si          → 100
      parzialmente→  60
      no          →  20
      assente     → None  (dato mancante, non penalizza)
    """
    if not feedback:
        return None
    val = str(feedback.get("seguito_scheda") or "").lower().strip()
    return {"si": 100.0, "parzialmente": 60.0, "no": 20.0}.get(val, None)


def _diet_adherence_score(feedback: dict | None) -> float | None:
    """
    Score di aderenza alla dieta (0-100).
    Usa 'dieta_seguita' se disponibile, altrimenti 'seguito_scheda' come proxy.
      si          → 100
      parzialmente→  60
      no          →  20
      assente     → None  (dato mancante, non penalizza)
    """
    if not feedback:
        return None
    val = (
        str(feedback.get("dieta_seguita") or "").lower().strip()
        or str(feedback.get("seguito_scheda") or "").lower().strip()
    )
    return {"si": 100.0, "parzialmente": 60.0, "no": 20.0}.get(val, None)


def _energy_score(feedback: dict | None) -> float | None:
    """
    Score energia/recupero (0-100) basato su energia generale, qualità del sonno
    e livello di stress percepito.

    Componenti e pesi:
        energia_gen    (1-10) → 35%
        qualita_sonno  (1-10) → 40%
        stress                → 25%   (basso=100, medio=50, alto=10)

    Assente → None (dato mancante, non influenza lo score)
    """
    if not feedback:
        return None

    components: list[tuple[float, float]] = []

    energia = feedback.get("energia_gen")
    if energia is not None:
        try:
            components.append((float(energia) / 10.0 * 100.0, 0.35))
        except (ValueError, TypeError):
            pass

    sonno = feedback.get("qualita_sonno")
    if sonno is not None:
        try:
            components.append((float(sonno) / 10.0 * 100.0, 0.40))
        except (ValueError, TypeError):
            pass

    stress = str(feedback.get("stress") or "").lower().strip()
    if stress:
        stress_val = {"basso": 100.0, "medio": 50.0, "alto": 10.0}.get(stress, None)
        if stress_val is not None:
            components.append((stress_val, 0.25))

    if not components:
        return None

    total_w = sum(w for _, w in components)
    return sum(v * w for v, w in components) / total_w


_INJURY_RE = re.compile(r"riabilitazione per:|infortun", re.IGNORECASE)

def _consistency_score(history: list, current_id: str) -> float:
    """
    Score di consistenza (0-100) basato sulle entry complete precedenti.

    Misura due cose:
    1. Trend dei system score: quante delle ultime N entry hanno system > 50
       e mostrano miglioramento rispetto alla precedente.
    2. Continuità: penalizza periodi con duration_days molto lunghi (>180gg)
       che indicano discontinuità.

    Formula:
        trend_score    = (n_miglioramenti / n_entry) * 100   [peso 60%]
        continuity_score = media(clamp(90/duration_months, 0, 100))  [peso 40%]
           → 1 mese = 90, 2 mesi = 45, 3 mesi = 30 ecc.
              (mesocicli brevi e frequenti = alta continuità)

    Usa al massimo le ultime 5 entry complete prima di quella corrente.
    Ritorna 50 se non ci sono entry precedenti sufficienti.
    """
    # Raccogli le entry complete precedenti (end != None) esclusa quella corrente
    completed = [
        e for e in history
        if e.get("end") is not None and e.get("id") != current_id
    ]
    if not completed:
        return 50.0

    window = completed[-5:]   # ultimi 5 mesocicli

    # ── Trend score ──────────────────────────────────────────────────────────
    system_vals = [
        e["score"]["system"]
        for e in window
        if isinstance(e.get("score"), dict) and e["score"].get("system") is not None
    ]

    if len(system_vals) >= 2:
        improvements = sum(
            1 for i in range(1, len(system_vals))
            if system_vals[i] >= system_vals[i - 1]
        )
        trend_score = (improvements / (len(system_vals) - 1)) * 100.0
    elif len(system_vals) == 1:
        trend_score = 60.0 if system_vals[0] >= 50 else 40.0
    else:
        trend_score = 50.0

    # ── Continuity score ─────────────────────────────────────────────────────
    durations = [
        e["duration_days"]
        for e in window
        if e.get("duration_days") and e["duration_days"] > 0
    ]

    if durations:
        cont_scores = [min(100.0, 90.0 / (d / 30.0)) for d in durations]
        continuity_score = sum(cont_scores) / len(cont_scores)
    else:
        continuity_score = 50.0

    return trend_score * 0.60 + continuity_score * 0.40


# ────────────────────────────────────────────────────────────────────────────
# Classe principale
# ────────────────────────────────────────────────────────────────────────────

class Score:
    """Calcola gli score di workout, diet e system a partire da un'entry di workout_history."""

    @staticmethod
    def calc(entry: dict, feedback: dict | None = None, history: list | None = None) -> dict:
        """
        Parametri:
            entry    : entry di workout_history (deve avere end != None per essere calcolata)
            feedback : dict estratto da feedback_atleta.yaml (sensazioni + allenamento + dieta)
            history  : lista completa di workout_history (necessaria per consistency_score)

        Ritorna:
            {
                "workout":     int | None,   # 0-100
                "diet":        int | None,   # 0-100
                "system":      int | None,   # 0-100
            }
        """
        if entry.get("end") is None:
            return {"workout": None, "diet": None, "system": None}

        # tipo_fase = tipo di mesociclo programmato (da plan).
        # fase_teorica = outcome metabolico (da BF/MM delta) — usato solo per diet.
        # Per il workout benchmark usiamo tipo_fase; se assente, sconosciuto.
        tipo_workout = _normalize_tipo(entry.get("tipo_fase"))
        if tipo_workout == "sconosciuto":
            tipo_workout = "sconosciuto"   # benchmark medi, non bench da mantenimento/cut
        tipo = tipo_workout

        adh_raw    = _adherence_score(feedback)     # float 0-100 o None
        energy_raw = _energy_score(feedback)         # float 0-100 o None
        inj_frac   = Score.injury_fraction(entry, feedback)   # 0.0 – 1.0

        tipo_diet = _normalize_tipo(
            entry.get("fase_teorica") or entry.get("tipo_fase")
        )

        workout = Score._calc_workout(entry, tipo, adh_raw, energy_raw, inj_frac)
        diet    = Score._calc_diet(entry, tipo_diet, feedback, inj_frac)
        consistency = _consistency_score(history or [], entry.get("id", ""))
        system  = Score._calc_system(workout, diet, consistency)

        return {"workout": workout, "diet": diet, "system": system}

    @staticmethod
    def apply_to_history(history: list, feedback_map: dict | None = None) -> None:
        """
        Ricalcola e scrive lo score su ogni entry della lista workout_history.
        Modifica la lista in-place. Passa tutta la history a ogni calc()
        in modo che consistency_score possa guardare le entry precedenti.
        """
        for entry in history:
            fb = (feedback_map or {}).get(entry.get("id"))
            entry["score"] = Score.calc(entry, fb, history)


    @staticmethod
    def injury_fraction(entry: dict, feedback: dict | None) -> float:
        """
        Ritorna la frazione del periodo coperta da infortuni attivi [0.0 – 1.0].

        Fonte primaria: feedback["infortuni"] (lista normalizzata con durata_giorni).
        Fonte secondaria: nota dell'entry (rileva "Riabilitazione per:" o "Infortuni:").

        Con feedback strutturato:
          - Per ogni infortunio NON guarito: durata = durata_giorni se disponibile,
            altrimenti si assume l'intero periodo (worst case).
          - Per ogni infortunio guarito: durata = durata_giorni se disponibile,
            altrimenti si assume 0 (già risolto, impatto minimo).
          - fraction = min(1.0, sum(durate) / duration_days)

        Senza feedback (entry storica): rileva dalla nota e assume fraction = 1.0
        se la nota indica riabilitazione, 0.0 altrimenti.
        """
        duration = entry.get("duration_days") or 0

        infortuni = (feedback or {}).get("infortuni") or []

        if infortuni:
            total_days = 0
            for inj in infortuni:
                durata = inj.get("durata_giorni")
                guarito = inj.get("guarito", False)
                if durata is not None:
                    total_days += durata
                elif not guarito:
                    # Infortunio attivo senza durata → assume tutto il periodo
                    total_days += duration
                # Guarito senza durata → ignora (già risolto)
            return min(1.0, total_days / duration) if duration > 0 else 0.0

        # Fallback sulla nota dell'entry
        if _INJURY_RE.search(entry.get("note") or ""):
            return 1.0
        return 0.0
    # ────────────────────────────────────────────────────────────────────────
    # Score Workout
    # ────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _calc_workout(
        entry: dict,
        tipo: str,
        adh_raw: float | None,
        energy_raw: float | None,
        inj_frac: float = 0.0,
    ) -> int | None:
        """
        Score di efficacia allenamento (0-100).

        Per ogni alzata:
            rate = delta_kg / duration_days * 30   [kg/mese]
            Progresso:  sub = log2(1 + rate/bench) * 100  (cap 100)
            Regressione: sub = -(|rate|/bench) * 100 * regression_mult

        Score base = media pesata (squat 35%, panca 30%, stacco 35%).
        Adherence e energy sono componenti additive opzionali.

        Infortunio (inj_frac 0.0–1.0): sia bench che reg_mult vengono
        interpolati verso i valori rehab in proporzione alla frazione del
        periodo coperta dall'infortunio.
            bench_eff = bench_normale * (1 - inj_frac) + bench_rehab * inj_frac
            reg_mult  = reg_mult_nom  * (1 - inj_frac) + reg_mult_rehab * inj_frac

        Abbassare il bench significa che anche piccoli progressi vengono
        premiati di più (fare +0.5 kg/mese con un infortunio è eccellente).

        Regressioni con infortunio: la penalità è ulteriormente limitata a
            max(sub, -100 * (1 - inj_frac))
        Così con inj_frac=0.68 la penalità massima è -32: stare fermi e
        perdere un po' di forza durante un lungo stop è atteso, non punibile.
        """
        duration = entry.get("duration_days")
        if not duration or duration <= 0:
            return None

        bench_nom    = _BENCH.get(tipo, _BENCH["sconosciuto"])
        bench_rehab  = _BENCH["rehab"]
        bench = {
            lift: bench_nom[lift] * (1.0 - inj_frac) + bench_rehab[lift] * inj_frac
            for lift in bench_nom
        }

        reg_mult_nom = _REGRESSION_MULT.get(tipo, 2.0)
        reg_mult     = reg_mult_nom * (1.0 - inj_frac) + _REGRESSION_MULT["rehab"] * inj_frac

        lifts = [
            (entry.get("delta_squat_kg"),  bench["squat"],  _LIFT_WEIGHTS["squat"]),
            (entry.get("delta_panca_kg"),  bench["panca"],  _LIFT_WEIGHTS["panca"]),
            (entry.get("delta_stacco_kg"), bench["stacco"], _LIFT_WEIGHTS["stacco"]),
        ]

        available = [(d, b, w) for d, b, w in lifts if d is not None]
        if len(available) < 2:
            return None

        weighted_net = 0.0
        total_weight = 0.0

        for delta, b, weight in available:
            rate = delta / duration * 30
            if rate >= 0:
                sub = _lift_sub_score(rate, b)
            else:
                sub = -(abs(rate) / b) * 100.0 * reg_mult
                # Con infortunio significativo, la regressione è attesa:
                # la penalità massima è proporzionale alla frazione NON infortunata.
                # Es. inj_frac=0.68 → penalità max = -32 (non illimitata).
                sub = max(sub, -100.0 * (1.0 - inj_frac))
            weighted_net += sub * weight
            total_weight += weight

        base = weighted_net / total_weight   # può essere negativo

        # Adherence e energy: componenti additive solo se disponibili
        subjective: list[tuple[float, float]] = []
        if adh_raw is not None:
            subjective.append((adh_raw, 0.15))
        if energy_raw is not None:
            subjective.append((energy_raw, 0.15))

        if not subjective:
            return _clamp(base)

        # Redistribuisci i pesi: base occupa il resto
        subj_weight = sum(w for _, w in subjective)
        base_weight = 1.0 - subj_weight
        raw = base * base_weight + sum(v * w for v, w in subjective)
        return _clamp(raw)

    # ────────────────────────────────────────────────────────────────────────
    # Score Diet
    # ────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _calc_diet(entry: dict, tipo: str, feedback: dict | None, inj_frac: float = 0.0) -> int | None:
        """
        Diet score (0-100) come media pesata di tre componenti:

            body_comp  : interpolato 50% → 25% in base a inj_frac
            adherence  : interpolato 30% → 35% in base a inj_frac
            energy     : interpolato 20% → 40% in base a inj_frac

        Con infortuni prolungati la composizione corporea è meno controllabile
        (stop forzato, catabolismo, ritenzione idrica) quindi pesa meno.
        Adherence e energy (recupero) diventano le componenti dominanti.

        La componente body_comp richiede almeno uno tra delta_mm e delta_bf.
        Se entrambi mancano, il diet score è calcolato solo su adherence + energy.
        """
        duration = entry.get("duration_days")
        if not duration or duration <= 0:
            return None

        months = duration / 30.0

        delta_mm = entry.get("delta_mm_kg")
        delta_bf = entry.get("delta_bf_pct")

        # ── Body composition score (outcome) ─────────────────────────────────
        if delta_mm is not None or delta_bf is not None:
            if tipo in ("accumulo", "intensificazione", "peaking"):
                body_comp = Score._diet_bulk(delta_mm, delta_bf, months)
            elif tipo in ("cut", "mini_cut"):
                body_comp = Score._diet_cut(delta_mm, delta_bf, months)
            else:
                body_comp = Score._diet_maintenance(delta_mm, delta_bf, months)
            body_comp_weight = 0.50
        else:
            body_comp        = None
            body_comp_weight = 0.0

        # ── Adherence score (dieta seguita) ───────────────────────────────────
        adh  = _diet_adherence_score(feedback)   # float 0-100 o None

        # ── Energy score (recupero/sensazioni) ────────────────────────────────
        enrg = _energy_score(feedback)            # float 0-100 o None

        # ── Media pesata adattiva ─────────────────────────────────────────────
        # Pesi interpolati in base alla frazione del periodo con infortunio
        w_body = 0.50 * (1.0 - inj_frac) + 0.25 * inj_frac
        w_adh  = 0.30 * (1.0 - inj_frac) + 0.35 * inj_frac
        w_enrg = 0.20 * (1.0 - inj_frac) + 0.40 * inj_frac

        components: list[tuple[float, float]] = []
        if body_comp is not None:
            components.append((body_comp, w_body))
        if adh is not None:
            components.append((adh, w_adh))
        if enrg is not None:
            components.append((enrg, w_enrg))

        if not components:
            return None

        total_w = sum(w for _, w in components)
        raw = sum(v * w for v, w in components) / total_w
        return _clamp(raw)

    @staticmethod
    def _diet_bulk(delta_mm, delta_bf, months: float) -> float:
        """
        Bulk ideale: guadagno MM rapido, BF contenuto.
          70% = velocità guadagno MM vs benchmark
          30% = pulizia bulk (BF non esploso)
        """
        if delta_mm is None:
            score_mm = 50.0
        else:
            rate_mm = delta_mm / months
            if rate_mm >= 0:
                score_mm = min(100.0, (rate_mm / _BENCH_MM_BULK_KG_MESE) * 100.0)
            else:
                score_mm = max(0.0, 100.0 + (rate_mm / _BENCH_MM_BULK_KG_MESE) * 200.0)

        if delta_bf is None:
            score_purity = 70.0
        else:
            rate_bf = delta_bf / months
            excess  = max(0.0, rate_bf - 0.3)
            score_purity = max(0.0, 100.0 - excess * 100.0)

        return score_mm * 0.70 + score_purity * 0.30

    @staticmethod
    def _diet_cut(delta_mm, delta_bf, months: float) -> float:
        """
        Cut ideale: calo BF rapido, MM conservata.
          60% = velocità perdita BF vs benchmark
          40% = conservazione MM
        """
        if delta_bf is None:
            score_bf = 50.0
        else:
            rate_bf = delta_bf / months
            if rate_bf <= 0:
                score_bf = min(100.0, (-rate_bf / _BENCH_BF_CUT_PCT_MESE) * 100.0)
            else:
                score_bf = max(0.0, 100.0 - (rate_bf / _BENCH_BF_CUT_PCT_MESE) * 200.0)

        if delta_mm is None:
            score_mm = 70.0
        else:
            rate_mm = delta_mm / months
            if rate_mm >= -_BENCH_MM_CUT_LOSS_MESE:
                score_mm = min(100.0, 100.0 + rate_mm / _BENCH_MM_CUT_LOSS_MESE * 20.0)
            else:
                excess_loss = abs(rate_mm) - _BENCH_MM_CUT_LOSS_MESE
                score_mm = max(0.0, 100.0 - excess_loss / _BENCH_MM_CUT_LOSS_MESE * 100.0)

        return score_bf * 0.60 + score_mm * 0.40

    @staticmethod
    def _diet_maintenance(delta_mm, delta_bf, months: float) -> float:
        """
        Mantenimento/rehab/tapering: stabilità di BF e MM.
        Score inversamente proporzionale alla deviazione assoluta mensile.
        """
        components = []

        if delta_bf is not None:
            rate_bf = abs(delta_bf / months)
            excess  = max(0.0, rate_bf - 0.2)
            s_bf    = max(0.0, 100.0 - (excess / 0.5) * 20.0)
            components.append((s_bf, 0.50))

        if delta_mm is not None:
            rate_mm = abs(delta_mm / months)
            excess  = max(0.0, rate_mm - 0.2)
            s_mm    = max(0.0, 100.0 - (excess / 0.3) * 20.0)
            components.append((s_mm, 0.50))

        if not components:
            return 50.0

        total_w = sum(w for _, w in components)
        return sum(v * w for v, w in components) / total_w

    # ────────────────────────────────────────────────────────────────────────
    # Score System
    # ────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _calc_system(
        workout: int | None,
        diet: int | None,
        consistency: float,
    ) -> int | None:
        """
        System score (0-100).

        Base = media pesata workout (55%) + diet (45%), invariata rispetto a prima.
        Consistency è un bonus puro [0, +10]: non può abbassare il system score,
        solo alzarlo quando l'atleta mostra un trend storico positivo.

            bonus = (consistency - 50) / 50 * 10   se consistency > 50
                  = 0                               altrimenti

        Così un atleta con ottima continuità guadagna fino a +10 punti,
        ma chi non ha storia o ha storia negativa non viene penalizzato.
        """
        if workout is None and diet is None:
            return None
        if workout is None:
            base = float(diet)
        elif diet is None:
            base = float(workout)
        else:
            base = workout * 0.55 + diet * 0.45

        # Consistency: bonus puro, max +10
        consistency_bonus = max(0.0, (consistency - 50.0) / 50.0 * 10.0)
        raw = base + consistency_bonus

        return _clamp(raw)
