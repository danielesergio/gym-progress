import json
from pathlib import Path


class ReviewParser:
    def parse(self, path: Path) -> tuple:
        """
        Legge un review JSON.
        Ritorna (approvato: bool, valutazione: int, problemi: list, numero_review: int).
        Approvato = valutazione >= 8 AND nessun problema critico, oppure esito == APPROVATA.
        """
        if not path.exists():
            print(f"[WARN  ] Review non trovato: {path.name} -considerato BOCCIATO", flush=True)
            return False, 0, ["(file non trovato)"], 0
        try:
            data          = json.loads(path.read_text(encoding="utf-8"))
            meta          = data.get("meta", {}) or {}
            valutazione   = int(meta.get("valutazione", 0))
            esito         = str(meta.get("esito", "")).upper()
            numero_review = int(meta.get("numero_review", 1))
            problemi      = data.get("problemi_critici", []) or []
            if not isinstance(problemi, list):
                problemi = [problemi]
            approvato = (valutazione >= 8 and len(problemi) == 0) or esito == "APPROVATA"
            return approvato, valutazione, problemi, numero_review
        except json.JSONDecodeError as e:
            print(f"[ERROR ] JSON non valido in {path.name}: {e}", flush=True)
            return False, 0, [f"JSON invalido: {e}"], 0
        except Exception as e:
            print(f"[ERROR ] Errore parsing review {path.name}: {e}", flush=True)
            return False, 0, [str(e)], 0
