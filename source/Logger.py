from pathlib import Path

from source.Config import Config


class Logger:
    _LABELS = {
        "INFO":   "INFO  ",
        "ACTION": "ACTION",
        "OK":     "OK    ",
        "WARN":   "WARN  ",
        "ERROR":  "ERROR ",
        "SKIP":   "SKIP  ",
    }

    def __init__(self, log_context_enabled: bool, config: "Config"):
        self._log_context_enabled = log_context_enabled
        self._config = config

    def log(self, level: str, msg: str) -> None:
        print(f"[{self._LABELS.get(level, level)}] {msg}", flush=True)

    def separator(self, title: str = "") -> None:
        line = "=" * 60
        if title:
            print(f"\n{line}\n  {title}\n{line}")
        else:
            print(line)

    def log_context(self, agent: str, files: list, calcs: list = None) -> None:
        """
        files  = [(path_str, modalita')]
                 modalita': "incorporato" | "obbligatorio" | "discrezione"
        calcs  = [descrizione_stringa, ...]  — info calcolate iniettate nel prompt
        """
        if not self._log_context_enabled:
            return
        LABEL = {
            "incorporato":  "Incorporato  ",
            "obbligatorio": "Da leggere   ",
            "discrezione":  "A discrezione",
        }
        PROJECT_ROOT = self._config.PROJECT_ROOT
        print(f"\n  [CONTEXT] {agent}")
        for path_raw, modalita in files:
            p = path_raw if isinstance(path_raw, Path) else Path(path_raw)
            abs_p = p if p.is_absolute() else PROJECT_ROOT / p
            if "*" in str(abs_p):
                matches = sorted(abs_p.parent.glob(abs_p.name), reverse=True)
                if matches:
                    abs_p = matches[0]
                    p = abs_p.relative_to(PROJECT_ROOT)
                else:
                    p = abs_p.relative_to(PROJECT_ROOT) if abs_p.is_relative_to(PROJECT_ROOT) else abs_p
                    print(f"    [{LABEL.get(modalita, modalita)}] {p}  (  MANCANTE)")
                    continue
            else:
                p = abs_p.relative_to(PROJECT_ROOT) if abs_p.is_relative_to(PROJECT_ROOT) else abs_p
            stato = f"{abs_p.stat().st_size:>7} B" if abs_p.exists() else "  MANCANTE"
            print(f"    [{LABEL.get(modalita, modalita)}] {p}  ({stato})")
        for desc in (calcs or []):
            print(f"    [Info calcolata ] {desc}")
