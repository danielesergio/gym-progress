import re
import sys
from datetime import datetime
from typing import Optional

from source.Config import Config

# MET (Metabolic Equivalent of Task) per tipo di attivita' e intensita'
# kcal bruciate = MET * peso_kg * ore
_MET_TABLE = {
    "corsa":      {"bassa": 6.0, "media": 9.0, "alta": 12.0},
    "ciclismo":   {"bassa": 5.0, "media": 7.5, "alta": 10.0},
    "nuoto":      {"bassa": 5.0, "media": 7.0, "alta": 9.5},
    "camminata":  {"bassa": 2.8, "media": 3.5, "alta": 4.5},
    "sport":      {"bassa": 5.0, "media": 7.0, "alta": 10.0},
    "yoga":       {"bassa": 2.0, "media": 2.5, "alta": 3.0},
    "altro":      {"bassa": 3.5, "media": 5.0, "alta": 7.0},
}


class BodyCalc:
    def __init__(self, config: Config):
        self._config = config
        self._body_calc_ok = False
        self._body_fat_navy = None
        self._bmr_mifflin = None
        self._ffmi_adjusted = None
        self._stima_1rm_epley = None
        self._load_body_calc()

    def _load_body_calc(self) -> None:
        sys.path.insert(0, str(self._config.SCRIPTS_DIR))
        try:
            from body_calc import body_fat_navy, bmr_mifflin, ffmi_adjusted, stima_1rm_epley
            self._body_fat_navy   = body_fat_navy
            self._bmr_mifflin     = bmr_mifflin
            self._ffmi_adjusted   = ffmi_adjusted
            self._stima_1rm_epley = stima_1rm_epley
            self._body_calc_ok    = True
        except ImportError:
            self._body_calc_ok = False
            print("[WARN  ] body_calc.py non trovato -calcoli body composition disabilitati", flush=True)

    def parse_feedback(self, feedback_data: dict) -> dict:
        """
        Estrae i dati numerici da feedback_atleta.yaml (dict gia' parsato).
        I campi mancanti o non compilati restano None.
        """
        def _num(val) -> Optional[float]:
            try:
                return float(val) if val not in (None, "", "?") else None
            except (ValueError, TypeError):
                return None

        def _lift(val) -> Optional[tuple]:
            if not val:
                return None
            if isinstance(val, dict):
                kg   = _num(val.get("kg"))
                reps = _num(val.get("reps"))
                return (kg, int(reps)) if kg and reps else None
            return None

        corpo    = feedback_data.get("corpo", {}) or {}
        misure   = corpo.get("misure", {}) or {}
        massimali = feedback_data.get("massimali", {}) or {}

        return {
            "peso_kg":       _num(corpo.get("peso_kg")),
            "vita_cm":       _num(misure.get("vita_cm")),
            "fianchi_cm":    _num(misure.get("fianchi_cm")),
            "petto_cm":      _num(misure.get("petto_cm")),
            "braccio_dx_cm": _num(misure.get("braccio_dx_cm")),
            "coscia_dx_cm":  _num(misure.get("coscia_dx_cm")),
            "collo_cm":      _num(misure.get("collo_cm")),
            "squat_test":    _lift(massimali.get("squat")),
            "panca_test":    _lift(massimali.get("panca")),
            "stacco_test":   _lift(massimali.get("stacco")),
        }

    def parse_athlete_profile(self, athlete_text: str) -> dict:
        """Estrae altezza, sesso, eta' dall'athlete.md."""
        t = athlete_text
        profile: dict = {}

        m = re.search(r"Altezza.*?(\d{3})", t)
        if m:
            profile["altezza_cm"] = float(m.group(1))

        m = re.search(r"Sesso[^:]*:\s*([MFmf])", t)
        if m:
            profile["sesso"] = m.group(1).upper()

        m = re.search(r"Data di na[^:]*:\s*(\d{4}-\d{2}-\d{2})", t)
        if m:
            try:
                dob = datetime.strptime(m.group(1), "%Y-%m-%d").date()
                profile["eta"] = (self._config.TODAY - dob).days // 365
            except ValueError:
                pass

        return profile

    def calc_progression_rates(self, measurements: list) -> dict:
        """
        Calcola rate di progressione annuale (kg/anno) per squat, panca, stacco.
        Considera solo entry con massimali validi.
        """
        lifts = {
            "squat":  "squat_1rm",
            "panca":  "panca_1rm",
            "stacco": "stacco_1rm",
        }
        rates: dict = {k: [] for k in lifts}

        valid = [m for m in measurements if all(m.get(v) for v in lifts.values())]

        for i in range(1, len(valid)):
            prev, curr = valid[i - 1], valid[i]
            try:
                d_prev = datetime.strptime(prev["data"], "%Y-%m-%d").date()
                d_curr = datetime.strptime(curr["data"], "%Y-%m-%d").date()
                days = (d_curr - d_prev).days
                if days <= 0:
                    continue
                years = days / 365.25
                for label, key in lifts.items():
                    delta = curr[key] - prev[key]
                    rates[label].append(round(delta / years, 1))
            except (ValueError, KeyError):
                continue

        result = {}
        for label, vals in rates.items():
            if vals:
                result[label] = {
                    "media": round(sum(vals) / len(vals), 1),
                    "min":   min(vals),
                    "max":   max(vals),
                    "n":     len(vals),
                }
            else:
                result[label] = {"media": 0.0, "min": 0.0, "max": 0.0, "n": 0}

        return result

    def apply_corrections(self, rates: dict, measurements: list, feedback_text: str) -> dict:
        """Applica fattori correttivi conservativi ai rate (infortunio, eta', stallo)."""
        latest = measurements[-1] if measurements else {}
        eta = latest.get("eta", 30)

        has_injury = bool(re.search(
            r"infortun|dolor|lesion|TOS|tendin|stiram|contrat",
            feedback_text, re.IGNORECASE
        ))
        age_penalty = eta > 35

        corrected = {}
        for lift, data in rates.items():
            media = data["media"]
            factor = 1.0
            if media <= 0:
                factor *= 0.5
            elif has_injury:
                factor *= 0.7
            if age_penalty:
                factor *= 0.9

            corrected[lift] = {
                **data,
                "media_corretta": round(media * factor, 1),
                "fattori": {
                    "infortunio":  has_injury,
                    "eta_over_35": age_penalty,
                    "stallo":      media <= 0,
                },
            }
        return corrected

    def build_new_measurement(
        self,
        feedback: dict,
        profile: dict,
        measurements: list,
    ) -> Optional[dict]:
        """
        Costruisce la nuova entry di measurements.json.
        Ritorna None se il peso non e' disponibile nel feedback.
        """
        cfg  = self._config
        peso = feedback.get("peso_kg")
        if not peso:
            print("[WARN  ] Peso non trovato nel feedback -misurazioni non aggiornate", flush=True)
            return None

        altezza = profile.get("altezza_cm", 188.0)
        sesso   = profile.get("sesso", "M")
        eta     = profile.get("eta", 38)
        vita    = feedback.get("vita_cm")
        collo   = feedback.get("collo_cm")
        fianchi = feedback.get("fianchi_cm")

        entry: dict = {
            "id":            cfg.iteration_id,
            "data":          cfg.DATE_STR,
            "eta":           eta,
            "peso_kg":       peso,
            "vita_cm":       vita,
            "fianchi_cm":    fianchi,
            "petto_cm":      feedback.get("petto_cm"),
            "collo_cm":      collo,
            "braccio_dx_cm": feedback.get("braccio_dx_cm"),
            "coscia_dx_cm":  feedback.get("coscia_dx_cm"),
        }

        if self._body_calc_ok and vita and collo and altezza:
            try:
                bf          = self._body_fat_navy(sesso, vita, collo, altezza, fianchi or 0)
                massa_magra = round(peso * (1 - bf / 100), 1)
                entry["body_fat_pct"]   = bf
                entry["massa_magra_kg"] = massa_magra
                entry["ffmi_adj"]       = self._ffmi_adjusted(massa_magra, altezza)
                entry["bmr_kcal"]       = int(self._bmr_mifflin(peso, altezza, eta, sesso))
                entry["tdee_kcal"]      = int(entry["bmr_kcal"] * 1.55)
            except Exception as e:
                print(f"[WARN  ] Calcolo body composition fallito: {e}", flush=True)
                self._fill_body_nulls(entry)
        else:
            missing = [k for k, v in [("vita_cm", vita), ("collo_cm", collo), ("altezza_cm", altezza)] if not v]
            print(f"[WARN  ] Body composition non calcolata -campi mancanti: {', '.join(missing)}", flush=True)
            self._fill_body_nulls(entry)

        lifts_map = [
            ("Squat",  "squat_1rm",  "squat_test"),
            ("Panca",  "panca_1rm",  "panca_test"),
            ("Stacco", "stacco_1rm", "stacco_test"),
        ]
        last = measurements[-1] if measurements else {}
        tipo = "R"
        for _, key, fb_key in lifts_map:
            test = feedback.get(fb_key)
            if test:
                p, r = test
                if self._body_calc_ok:
                    entry[key] = self._stima_1rm_epley(p, r)
                else:
                    entry[key] = round(p * (1 + r / 30), 1)
                tipo = "S"
            else:
                entry[key] = last.get(key)

        entry["massimali_tipo"] = tipo
        entry["note"]           = ""

        vals = [entry.get(k) for k in ("squat_1rm", "panca_1rm", "stacco_1rm")]
        entry["totale_1rm"] = round(sum(vals), 1) if all(v is not None for v in vals) else None

        return entry

    def _fill_body_nulls(self, entry: dict) -> None:
        for k in ("body_fat_pct", "massa_magra_kg", "ffmi_adj", "bmr_kcal", "tdee_kcal"):
            entry[k] = None

    def enrich_missing_body_composition(self, measurements: list, profile: dict) -> int:
        """
        Calcola body_fat_pct, massa_magra_kg, ffmi_adj, bmr_kcal, tdee_kcal per le
        entry storiche che hanno i dati antropometrici ma mancano dei valori calcolati.
        Ritorna il numero di entry arricchite.
        """
        if not self._body_calc_ok:
            return 0

        altezza  = profile.get("altezza_cm", 188.0)
        sesso    = profile.get("sesso", "M")
        enriched = 0

        for entry in measurements:
            if entry.get("body_fat_pct") is not None:
                continue

            vita    = entry.get("vita_cm")
            collo   = entry.get("collo_cm")
            fianchi = entry.get("fianchi_cm")
            peso    = entry.get("peso_kg")
            eta     = entry.get("eta", profile.get("eta", 30))

            if not (vita and collo and peso):
                continue

            try:
                bf          = self._body_fat_navy(sesso, vita, collo, altezza, fianchi or 0)
                massa_magra = round(peso * (1 - bf / 100), 1)
                entry["body_fat_pct"]   = bf
                entry["massa_magra_kg"] = massa_magra
                entry["ffmi_adj"]       = self._ffmi_adjusted(massa_magra, altezza)
                entry["bmr_kcal"]       = int(self._bmr_mifflin(peso, altezza, eta, sesso))
                entry["tdee_kcal"]      = int(entry["bmr_kcal"] * 1.55)
                enriched += 1
            except Exception as e:
                print(f"[WARN  ] Enrichment entry {entry.get('data','?')}: {e}", flush=True)

        return enriched

    def calc_kcal_extra_attivita(self, altre_attivita: list, peso_kg: float) -> dict:
        """
        Calcola il dispendio calorico settimanale e giornaliero medio
        dalle attivita' aggiuntive dichiarate nel feedback.
        """
        if not altre_attivita or not peso_kg:
            return {"kcal_extra_settimana": 0, "kcal_extra_giorno_medio": 0, "dettaglio": []}

        dettaglio = []
        totale_settimana = 0

        for att in (altre_attivita or []):
            if not isinstance(att, dict):
                continue
            tipo       = str(att.get("tipo") or "altro").lower().strip()
            durata_min = att.get("durata_min")
            volte      = att.get("volte_settimana")
            intensita  = str(att.get("intensita") or "media").lower().strip()
            nome       = att.get("nome") or tipo

            try:
                durata_min = float(durata_min)
                volte      = float(volte)
            except (TypeError, ValueError):
                continue
            if durata_min <= 0 or volte <= 0:
                continue

            met_map = _MET_TABLE.get(tipo, _MET_TABLE["altro"])
            met = met_map.get(intensita, met_map["media"])

            ore_sessione   = durata_min / 60
            kcal_sessione  = round(met * peso_kg * ore_sessione)
            kcal_settimana = round(kcal_sessione * volte)

            dettaglio.append({
                "nome":            nome,
                "tipo":            tipo,
                "met":             met,
                "kcal_sessione":   kcal_sessione,
                "volte_settimana": int(volte),
                "kcal_settimana":  kcal_settimana,
            })
            totale_settimana += kcal_settimana

        kcal_giorno_medio = round(totale_settimana / 7)
        return {
            "kcal_extra_settimana":    totale_settimana,
            "kcal_extra_giorno_medio": kcal_giorno_medio,
            "dettaglio":               dettaglio,
        }

    def format_attivita_extra(self, kcal_extra: dict) -> str:
        """Formatta il risultato di calc_kcal_extra_attivita per i prompt."""
        if not kcal_extra or kcal_extra["kcal_extra_settimana"] == 0:
            return "(nessuna attivita' aggiuntiva dichiarata)"
        lines = []
        for d in kcal_extra["dettaglio"]:
            lines.append(
                f"  - {d['nome']} ({d['tipo']}, MET {d['met']}): "
                f"{d['kcal_sessione']} kcal/sessione x {d['volte_settimana']}/sett "
                f"= {d['kcal_settimana']} kcal/sett"
            )
        lines.append(f"  Totale extra: {kcal_extra['kcal_extra_settimana']} kcal/sett "
                     f"({kcal_extra['kcal_extra_giorno_medio']} kcal/die in media)")
        return "\n".join(lines)

    def _calc_fase_teorica(self, prev: dict, curr: dict) -> str:
        """Determina la fase teorica in base a delta BF% e massa magra."""
        delta_bf = (
            curr.get("body_fat_pct", 0) - prev.get("body_fat_pct", 0)
            if (curr.get("body_fat_pct") is not None and prev.get("body_fat_pct") is not None)
            else None
        )
        delta_mm = (
            curr.get("massa_magra_kg", 0) - prev.get("massa_magra_kg", 0)
            if (curr.get("massa_magra_kg") is not None and prev.get("massa_magra_kg") is not None)
            else None
        )

        if delta_bf is None or delta_mm is None:
            return "sconosciuto"
        if delta_bf < -0.3:
            return "cut"
        if delta_mm > 0.5 and delta_bf >= -0.3:
            return "bulk"
        return "mantenimento"