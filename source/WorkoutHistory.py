import json
import uuid
from datetime import datetime
from typing import Optional

from source.Config import Config
from source.BodyCalc import BodyCalc
from source.Score import Score


class WorkoutHistory:
    def __init__(self, config: Config):
        self._config = config
        self._body_calc: Optional[BodyCalc] = None

    def _set_body_calc(self, body_calc: BodyCalc) -> None:
        self._body_calc = body_calc

    def load(self) -> list:
        path = self._config.OUTPUT_DIR / "workout_history.json"
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"[WARN  ] workout_history.json non valido: {e}", flush=True)
            return []

    def save(self, history: list) -> None:
        path = self._config.OUTPUT_DIR / "workout_history.json"
        path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")

    def build_from_seed(self, measurements: list) -> None:
        """
        Genera workout_history.json dai dati storici gia' enriched.
        Chiamata una sola volta dopo enrich_missing_body_composition,
        solo se workout_history.json non esiste ancora.
        """
        wh_path = self._config.OUTPUT_DIR / "workout_history.json"
        if wh_path.exists() or len(measurements) < 2:
            return

        history = []
        for i in range(len(measurements) - 1):
            prev = measurements[i]
            curr = measurements[i + 1]
            delta_squat = round(curr["squat_1rm"] - prev["squat_1rm"], 1) if (curr.get("squat_1rm") and prev.get("squat_1rm")) else None
            delta_panca = round(curr["panca_1rm"] - prev["panca_1rm"], 1) if (curr.get("panca_1rm") and prev.get("panca_1rm")) else None
            delta_stacco = round(curr["stacco_1rm"] - prev["stacco_1rm"], 1) if (curr.get("stacco_1rm") and prev.get("stacco_1rm")) else None
            deltas = [delta_squat, delta_panca, delta_stacco]
            valid_deltas = [d for d in deltas if d is not None]
            totale_delta = round(sum(valid_deltas), 1) if valid_deltas else None
            entry = {
                "id":                uuid.uuid4().hex[:8],
                "start":             prev["id"],
                "end":               curr["id"],
                "delta_squat_kg":    delta_squat,
                "delta_panca_kg":    delta_panca,
                "delta_stacco_kg":   delta_stacco,
                "delta_totale_kg":   totale_delta,
                "delta_weight_kg":   round(curr["peso_kg"] - prev["peso_kg"], 1) if (curr.get("peso_kg") is not None and prev.get("peso_kg") is not None) else None,
                "duration_days":     (datetime.strptime(curr["data"], "%Y-%m-%d") - datetime.strptime(prev["data"], "%Y-%m-%d")).days if (curr.get("data") and prev.get("data")) else None,
                "delta_bf_pct":      round(curr["body_fat_pct"] - prev["body_fat_pct"], 1) if (curr.get("body_fat_pct") is not None and prev.get("body_fat_pct") is not None) else None,
                "delta_mm_kg":       round(curr["massa_magra_kg"] - prev["massa_magra_kg"], 1) if (curr.get("massa_magra_kg") is not None and prev.get("massa_magra_kg") is not None) else None,
                "fase_teorica":      self._body_calc._calc_fase_teorica(prev, curr) if self._body_calc else "sconosciuto",
                "score":             {"workout": None, "diet": None, "system": None},
                "note":              prev.get("note", ""),
            }
            history.append(entry)
            entry["score"] = Score.calc(entry, None, history)

        last = measurements[-1]
        history.append({
            "id":                uuid.uuid4().hex[:8],
            "start":             last["id"],
            "end":               None,
            "delta_squat_kg":    None,
            "delta_panca_kg":    None,
            "delta_stacco_kg":   None,
            "delta_totale_kg":   None,
            "delta_weight_kg":   None,
            "duration_days":     None,
            "delta_bf_pct":      None,
            "delta_mm_kg":       None,
            "fase_teorica":      None,
            "score":             {"workout": None, "diet": None, "system": None},
            "note":              last.get("note", ""),
        })

        wh_path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[OK    ] workout_history.json creato da dati storici ({len(history)} entry, ultima incompleta)", flush=True)

    def complete_last_entry(self, feedback: dict, history: list, measurements: list) -> bool:
        """
        Completa l'ultima entry di workout_history con i dati dell'ultima misurazione.
        L'entry N-1 diventa completa: end, delta massimali, delta BF, delta MM, fase_teorica.
        Ritorna True se un'entry e' stata completata.
        """
        if not history or len(measurements) < 2:
            return False

        last_entry = history[-1]
        if last_entry.get("end") is not None:
            return False

        start_id = last_entry.get("start")
        curr     = measurements[-1]

        prev = next((m for m in measurements if m.get("id") == start_id), None)
        if not prev:
            print(f"[WARN  ] workout_history: measurement start_id={start_id} non trovata — delta non calcolabili", flush=True)
            prev = measurements[-2] if len(measurements) >= 2 else curr

        last_entry["end"] = curr.get("id")

        for lift, key in [("squat", "squat_1rm"), ("panca", "panca_1rm"), ("stacco", "stacco_1rm")]:
            c, p = curr.get(key), prev.get(key)
            last_entry[f"delta_{lift}_kg"] = round(c - p, 1) if (c is not None and p is not None) else None

        c_bf, p_bf = curr.get("body_fat_pct"), prev.get("body_fat_pct")
        last_entry["delta_bf_pct"] = round(c_bf - p_bf, 1) if (c_bf is not None and p_bf is not None) else None

        c_mm, p_mm = curr.get("massa_magra_kg"), prev.get("massa_magra_kg")
        last_entry["delta_mm_kg"] = round(c_mm - p_mm, 1) if (c_mm is not None and p_mm is not None) else None

        last_entry["fase_teorica"] = (
            self._body_calc._calc_fase_teorica(prev, curr) if self._body_calc else "sconosciuto"
        )

        c_tot, p_tot = curr.get("totale_1rm"), prev.get("totale_1rm")
        last_entry["delta_totale_kg"] = round(c_tot - p_tot, 1) if (c_tot is not None and p_tot is not None) else None

        c_w, p_w = curr.get("peso_kg"), prev.get("peso_kg")
        last_entry["delta_weight_kg"] = round(c_w - p_w, 1) if (c_w is not None and p_w is not None) else None

        c_d, p_d = curr.get("data"), prev.get("data")
        last_entry["duration_days"] = (
            (datetime.strptime(c_d, "%Y-%m-%d") - datetime.strptime(p_d, "%Y-%m-%d")).days
            if (c_d and p_d) else None
        )

        last_entry["score"] = Score.calc(last_entry, feedback, history)
        last_entry["injure"] = Score.injury_fraction(last_entry, feedback)
        print(f"[OK    ] workout_history entry {last_entry['id']} completata (end={last_entry['end']})", flush=True)
        return True

    def annotate_completed_entry(self, history: list, feedback_data: dict | None) -> None:
        """
        Aggiunge alla nota dell'ultima entry completata (periodo appena concluso):
          - allenamento.note (prima riga)
          - per ogni infortunio:
              guarito: no  → "Infortunio: <descrizione>"
              guarito: si  → "Infortunio risolto: <descrizione> (<durata_giorni>gg)"
        """
        if not feedback_data:
            return

        note      = WorkoutHistory._first_line((feedback_data.get("allenamento") or {}).get("note"))
        infortuni = WorkoutHistory._parse_infortuni(feedback_data)

        if not note and not infortuni:
            return

        last_complete = next(
            (e for e in reversed(history) if e.get("end") is not None), None
        )
        if not last_complete:
            return

        parts = [last_complete.get("note") or ""]
        if note and note not in parts[0]:
            parts.append(note)
        for inj in infortuni:
            if inj["guarito"]:
                durata_str = f" ({inj['durata_giorni']}gg)" if inj["durata_giorni"] else ""
                tag = f"Infortunio risolto: {inj['descrizione']}{durata_str}"
            else:
                tag = f"Infortunio: {inj['descrizione']}"
            if tag not in parts[0]:
                parts.append(tag)

        last_complete["note"] = " — ".join(p for p in parts if p)
        print(f"[OK    ] note aggiornate su entry {last_complete['id']}: {last_complete['note']}", flush=True)

    @staticmethod
    def _first_line(val) -> str:
        if not val:
            return ""
        if isinstance(val, list):
            val = next((v for v in val if v), "")
        return str(val).strip().splitlines()[0].strip() if val else ""

    @staticmethod
    def _parse_infortuni(feedback_data: dict | None) -> list[dict]:
        """
        Estrae e normalizza la lista infortuni da feedback_atleta.yaml.
        Ogni elemento ritornato ha: descrizione (str), guarito (bool), durata_giorni (int|None).
        """
        if not feedback_data:
            return []
        raw = feedback_data.get("infortuni") or []
        if not isinstance(raw, list):
            return []
        result = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            desc = WorkoutHistory._first_line(item.get("descrizione"))
            if not desc:
                continue
            guarito_val = item.get("guarito")
            if isinstance(guarito_val, bool):
                guarito = guarito_val
            else:
                guarito = str(guarito_val or "").lower().strip() == "si"
            durata = item.get("durata_giorni") or item.get("durata")
            try:
                durata = int(durata) if durata not in (None, "", "?") else None
            except (ValueError, TypeError):
                durata = None
            result.append({"descrizione": desc, "guarito": guarito, "durata_giorni": durata})
        return result

    def append_entry(self, history: list, measurements: list, feedback_data: dict | None = None) -> dict:
        """
        Aggiunge la nuova entry N in workout_history per l'iterazione corrente.
        start = id dell'ultima measurement (quella appena aggiunta).
        I campi end, delta*, fase_teorica restano null (verranno popolati alla prossima iterazione).

        La nota viene estratta da feedback_data: allenamento.note se presente,
        altrimenti altro.infortuni come contesto del periodo.
        """
        iteration_id = self._config.iteration_id
        new_entry = {
            "id":                iteration_id,
            "start":             measurements[-1].get("id") if measurements else None,
            "end":               None,
            "delta_squat_kg":    None,
            "delta_panca_kg":    None,
            "delta_stacco_kg":   None,
            "delta_totale_kg":   None,
            "delta_weight_kg":   None,
            "duration_days":     None,
            "delta_bf_pct":      None,
            "delta_mm_kg":       None,
            "fase_teorica":      None,
            "score":             {"workout": None, "diet": None, "system": None},
            "note":              self._extract_note(feedback_data),
        }
        history.append(new_entry)
        print(f"[OK    ] workout_history nuova entry aggiunta (id={iteration_id}, start={new_entry['start']})", flush=True)
        return new_entry

    @staticmethod
    def _extract_note(feedback_data: dict | None) -> str:
        """
        Nota per la nuova entry (periodo che inizia ora).
        Solo gli infortuni NON ancora guariti generano nota: "Riabilitazione per: <descrizione>".
        Infortuni già guariti non compaiono (il periodo corrente non ne è condizionato).
        """
        if not feedback_data:
            return ""
        infortuni = WorkoutHistory._parse_infortuni(feedback_data)
        attivi = [inj["descrizione"] for inj in infortuni if not inj["guarito"]]
        if attivi:
            return "Riabilitazione per: " + "; ".join(attivi)
        return ""

    def set_tipo_fase(self, history: list, iteration_id: str, tipo_fase: str) -> None:
        """
        Scrive tipo_fase nell'entry corrente (quella con id == iteration_id).
        Chiamato dopo la selezione del mesociclo attivo per arricchire l'entry
        con il tipo di fase, necessario per il calcolo dello score.
        """
        for entry in history:
            if entry.get("id") == iteration_id:
                entry["tipo_fase"] = tipo_fase
                return

    def write_score(self, history: list, feedback_data: dict | None = None) -> None:
        """
        Ricalcola lo score matematico per ogni entry completa di workout_history.

        feedback_data: dict parsato da feedback_atleta.yaml dell'iterazione corrente.
        Viene usato per estrarre adherence e fatigue dell'entry N-1 (quella appena
        completata con i dati del feedback odierno).
        """
        feedback = self._parse_feedback_for_score(feedback_data) if feedback_data else None

        updated = 0
        for i, entry in enumerate(history):
            if entry.get("end") is None:
                continue
            # Il feedback dell'iterazione corrente descrive il PERIODO appena concluso
            # → si applica all'ultima entry completata (history[-2] se esiste history[-1] aperta,
            #   altrimenti history[-1]).
            last_complete_idx = max(
                (j for j, e in enumerate(history) if e.get("end") is not None),
                default=None,
            )
            fb = feedback if (i == last_complete_idx) else None
            entry["score"] = Score.calc(entry, fb, history)
            updated += 1

        print(f"[OK    ] score ricalcolato per {updated} entry di workout_history", flush=True)

    @staticmethod
    def _parse_feedback_for_score(feedback_data: dict) -> dict:
        """
        Estrae i campi rilevanti per Score da feedback_atleta.yaml parsato.
        Ritorna un dict con le chiavi attese da Score._adherence_multiplier
        e Score._fatigue_score.
        """
        sensazioni = feedback_data.get("sensazioni") or {}
        allenamento = feedback_data.get("allenamento") or {}

        def _safe_num(val):
            try:
                return float(val) if val not in (None, "", "?") else None
            except (ValueError, TypeError):
                return None

        dieta = feedback_data.get("dieta") or {}
        return {
            "seguito_scheda": str(allenamento.get("seguito_scheda") or "").lower().strip() or None,
            "dieta_seguita":  str(dieta.get("seguita") or "").lower().strip() or None,
            "energia_gen":    _safe_num(sensazioni.get("energia_generale")),
            "qualita_sonno":  _safe_num(sensazioni.get("qualita_sonno")),
            "stress":         str(sensazioni.get("stress") or "").lower().strip() or None,
            "infortuni":      WorkoutHistory._parse_infortuni(feedback_data),
        }
