import json
import re
import uuid
from datetime import datetime
from typing import Optional

from source.Config import Config
from source.BodyCalc import BodyCalc


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
            entry = {
                "id":                uuid.uuid4().hex[:8],
                "start":             prev["id"],
                "end":               curr["id"],
                "delta_squat_kg":    round(curr["squat_1rm"] - prev["squat_1rm"], 1) if (curr.get("squat_1rm") and prev.get("squat_1rm")) else None,
                "delta_panca_kg":    round(curr["panca_1rm"] - prev["panca_1rm"], 1) if (curr.get("panca_1rm") and prev.get("panca_1rm")) else None,
                "delta_stacco_kg":   round(curr["stacco_1rm"] - prev["stacco_1rm"], 1) if (curr.get("stacco_1rm") and prev.get("stacco_1rm")) else None,
                "delta_totale_kg":   round(curr["totale_1rm"] - prev["totale_1rm"], 1) if (curr.get("totale_1rm") is not None and prev.get("totale_1rm") is not None) else None,
                "delta_weight_kg":   round(curr["peso_kg"] - prev["peso_kg"], 1) if (curr.get("peso_kg") is not None and prev.get("peso_kg") is not None) else None,
                "duration_days":     (datetime.strptime(curr["data"], "%Y-%m-%d") - datetime.strptime(prev["data"], "%Y-%m-%d")).days if (curr.get("data") and prev.get("data")) else None,
                "delta_bf_pct":      round(curr["body_fat_pct"] - prev["body_fat_pct"], 1) if (curr.get("body_fat_pct") is not None and prev.get("body_fat_pct") is not None) else None,
                "delta_mm_kg":       round(curr["massa_magra_kg"] - prev["massa_magra_kg"], 1) if (curr.get("massa_magra_kg") is not None and prev.get("massa_magra_kg") is not None) else None,
                "fase_teorica":      self._body_calc._calc_fase_teorica(prev, curr) if self._body_calc else "sconosciuto",
                "efficacia_workout": None,
                "note":              prev.get("note", ""),
            }
            history.append(entry)

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
            "efficacia_workout": None,
            "note":              last.get("note", ""),
        })

        wh_path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[OK    ] workout_history.json creato da dati storici ({len(history)} entry, ultima incompleta)", flush=True)

    def complete_last_entry(self, history: list, measurements: list) -> bool:
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

        print(f"[OK    ] workout_history entry {last_entry['id']} completata (end={last_entry['end']})", flush=True)
        return True

    def append_entry(self, history: list, measurements: list) -> dict:
        """
        Aggiunge la nuova entry N in workout_history per l'iterazione corrente.
        start = id dell'ultima measurement (quella appena aggiunta).
        I campi end, delta*, fase_teorica, efficacia_workout restano null.
        Ritorna la nuova entry.
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
            "efficacia_workout": None,
            "note":              "",
        }
        history.append(new_entry)
        print(f"[OK    ] workout_history nuova entry aggiunta (id={iteration_id}, start={new_entry['start']})", flush=True)
        return new_entry

    def write_efficacia(self, history: list) -> None:
        """
        Legge EFFICACIA_WORKOUT dal feedback_coach appena generato e lo scrive
        nell'ultima entry di workout_history (quella dell'iterazione corrente).
        """
        cfg = self._config
        feedback_coach_path = cfg.OUTPUT_DIR / f"feedback_coach_{cfg.iteration_id}.md"
        if not feedback_coach_path.exists():
            print("[WARN  ] feedback_coach non trovato — efficacia_workout non aggiornata", flush=True)
            return

        text = feedback_coach_path.read_text(encoding="utf-8")
        m = re.search(r"EFFICACIA_WORKOUT:\s*(\d+)", text)
        if not m:
            print("[WARN  ] EFFICACIA_WORKOUT non trovata nel feedback_coach — workout_history non aggiornata", flush=True)
            return

        valore = int(m.group(1))
        if not (1 <= valore <= 10):
            print(f"[WARN  ] EFFICACIA_WORKOUT={valore} fuori range 1-10 — ignorato", flush=True)
            return

        if len(history) < 2:
            print("[WARN  ] workout_history ha meno di 2 entry — nessuna entry precedente da aggiornare", flush=True)
            return

        target = history[-2]
        target["efficacia_workout"] = valore
        print(f"[OK    ] efficacia_workout={valore} scritto in workout_history entry {target.get('id', '?')}", flush=True)
