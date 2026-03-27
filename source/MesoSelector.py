from datetime import datetime
from typing import Optional

from source.GlobalConstant import GlobalConstant
from source.Config import Config


class MesoSelector:
    _TIPO_TO_MICRO_AGENT = {
        "REHAB":            "gym-pt-micro-rehab",
        "Ramp-up":          "gym-pt-micro-rehab",
        "Accumulo":         "gym-pt-micro-accumulo",
        "Mini-cut":         "gym-pt-micro-mini-cut",
        "Intensificazione": "gym-pt-micro-intensificazione",
        "Peaking":          "gym-pt-micro-peaking",
        "Tapering & Test":  "gym-pt-micro-tapering",
    }

    def __init__(self, config: Config):
        self._config = config

    def select_active_mesociclo(self) -> Optional[dict]:
        """
        Legge plan.yaml e restituisce il mesociclo attivo in base alla data odierna.
        Scorre i mesocicli in ordine e restituisce il primo il cui intervallo
        [data_inizio, data_inizio + durata_settimane) copre TODAY.
        Se nessuno copre today, restituisce l'ultimo mesociclo del piano.
        """
        cfg       = self._config
        plan_path = cfg.OUTPUT_DIR / "plan.yaml"
        if not plan_path.exists():
            return None
        if not GlobalConstant.YAML_OK:
            print("[WARN  ] yaml non disponibile: select_active_mesociclo impossibile", flush=True)
            return None
        try:
            data       = GlobalConstant.yaml_module.safe_load(plan_path.read_text(encoding="utf-8")) or {}
            macrocicli = data.get("macrocicli") or []
            all_meso   = []
            for mac in macrocicli:
                for m in (mac.get("mesocicli") or []):
                    all_meso.append(m)

            import datetime as _dt
            for meso in all_meso:
                start_str = str(meso.get("data_inizio", ""))
                weeks     = int(meso.get("durata_settimane") or 0)
                if not start_str or not weeks:
                    continue
                start = datetime.strptime(start_str + "-01", "%Y-%m-%d").date()
                end   = start + _dt.timedelta(weeks=weeks)
                if start <= cfg.TODAY < end:
                    return meso

            return all_meso[-1] if all_meso else None
        except Exception as e:
            print(f"[WARN  ] select_active_mesociclo: errore lettura plan.yaml: {e}", flush=True)
            return None

    def select_micro_agent(self, meso: Optional[dict]) -> str:
        """
        Restituisce il nome dell'agente pt-micro corretto in base a tipo_fase del mesociclo.
        Fallback: gym-personal-trainer se il tipo non e' riconosciuto.
        """
        if not meso:
            print("[WARN  ] Nessun mesociclo attivo trovato -uso gym-personal-trainer come fallback", flush=True)
            return "gym-personal-trainer"
        tipo  = str(meso.get("tipo_fase") or "").strip()
        agent = self._TIPO_TO_MICRO_AGENT.get(tipo)
        if not agent:
            print(f"[WARN  ] tipo_fase '{tipo}' non mappato -uso gym-personal-trainer come fallback", flush=True)
            return "gym-personal-trainer"
        return agent
