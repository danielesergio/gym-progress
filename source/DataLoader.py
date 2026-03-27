import json
import uuid
from pathlib import Path

from source.BodyCalc import BodyCalc
from source.GlobalConstant import GlobalConstant
from source.Config import Config
from source.Logger import Logger

class DataLoader:
    def __init__(self, config: Config):
        self._config = config

    def read_text(self, path: Path, default: str = "") -> str:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")
        return default

    def read_json(self, path: Path, default=None):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"[WARN  ] JSON non valido in {path.name}: {e}", flush=True)
            return default

    def _read_path_or_dir(self, p: Path) -> str:
        """Legge un file o tutti i file in una directory."""
        if not p.exists():
            return ""
        if p.is_file():
            return self.read_text(p)
        parts = []
        for f in sorted(p.iterdir()):
            if f.is_file():
                parts.append(f"### {f.name}\n{self.read_text(f)}")
        return "\n\n".join(parts)

    def load_all_data(self, body_calc: "BodyCalc", logger: Logger) -> dict:
        """Legge tutti i file di input necessari all'iterazione."""
        cfg = self._config
        logger.log("INFO", "Caricamento file dati...")

        athlete_text      = self.read_text(cfg.DATA_DIR / "athlete.md")
        feedback_path     = cfg.DATA_DIR / "feedback_atleta.yaml"
        measurements_path = cfg.OUTPUT_DIR / "measurements.json"

        if not measurements_path.exists():
            cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            previous_path = cfg.DATA_DIR / "previous_data.json"
            if previous_path.exists():
                seed = self.read_json(previous_path, default=[])
                for entry in seed:
                    if not entry.get("id"):
                        entry["id"] = uuid.uuid4().hex[:8]
                measurements_path.write_text(
                    json.dumps(seed, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                logger.log("OK", f"measurements.json creato da previous_data.json ({len(seed)} entry, ID generati)")
            else:
                measurements_path.write_text("[]", encoding="utf-8")
                logger.log("OK", "measurements.json creato (lista vuota - previous_data.json non trovato)")

        measurements = self.read_json(measurements_path, default=[])
        plan_text    = self.read_text(cfg.OUTPUT_DIR / "plan.yaml") or self.read_text(cfg.OUTPUT_DIR / "plan.html")

        feedback_data: dict = {}
        if feedback_path.exists():
            if GlobalConstant.YAML_OK:
                try:
                    feedback_data = GlobalConstant.yaml_module.safe_load(feedback_path.read_text(encoding="utf-8")) or {}
                except Exception as e:
                    logger.log("WARN", f"feedback_atleta.yaml non parsabile: {e}")
            else:
                logger.log("WARN", "yaml non disponibile: feedback_atleta.yaml non parsato")
        else:
            logger.log("WARN", "feedback_atleta.yaml non trovato")

        altre_attivita = (feedback_data.get("altre_attivita") or []) if feedback_data else []
        ultimo_peso    = measurements[-1].get("peso_kg") if measurements else None
        kcal_extra     = body_calc.calc_kcal_extra_attivita(altre_attivita, ultimo_peso or 80.0)

        logger.log("INFO", f"  {len(measurements)} misurazioni storiche")
        logger.log("INFO", f"  feedback_atleta.yaml: {len(feedback_data)} sezioni")
        logger.log("INFO", f"  altre_attivita: {len(altre_attivita)} attivita', "
                           f"{kcal_extra['kcal_extra_settimana']} kcal/sett extra")

        return {
            "athlete_text":  athlete_text,
            "feedback_data": feedback_data,
            "feedback_text": feedback_path.read_text(encoding="utf-8") if feedback_path.exists() else "",
            "measurements":  measurements,
            "plan_text":     plan_text,
            "rates":         {},
            "kcal_extra":    kcal_extra,
        }
