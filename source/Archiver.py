import re
import shutil
from datetime import datetime

from source.Config import Config


class Archiver:
    def __init__(self, config: Config):
        self._config = config

    def archive_feedback(self) -> None:
        """Copia data/feedback_atleta.yaml -> data/output/feedback_atleta_(id).yaml."""
        cfg  = self._config
        src  = cfg.DATA_DIR / "feedback_atleta.yaml"
        dest = cfg.OUTPUT_DIR / f"feedback_atleta_{cfg.iteration_id}.yaml"
        if src.exists():
            shutil.copy2(src, dest)
            print(f"[OK    ] Archiviato: {dest.name}", flush=True)
        else:
            print("[WARN  ] feedback_atleta.yaml non trovato -nessuna copia archiviata", flush=True)

    def archive_old_output_files(self) -> None:
        """
        Sposta i file di ITERAZIONI PRECEDENTI da data/output/ a data/output/history/YYYY/.
        I file correnti hanno suffisso _{ITERATION_ID} e restano in root.
        I file permanenti (measurements.json, plan.yaml) restano sempre in root.
        Per determinare l'anno di archivio si usa la data di modifica del file.
        """
        cfg        = self._config
        ALWAYS_KEEP = {"measurements.json", "plan.yaml"}
        suffix_re  = re.compile(r"_([0-9a-f]{8})\.[^.]+$")

        for f in list(cfg.OUTPUT_DIR.iterdir()):
            if not f.is_file():
                continue
            if f.name in ALWAYS_KEEP:
                continue
            m = suffix_re.search(f.name)
            if not m:
                continue
            suffix = m.group(1)
            if suffix == cfg.iteration_id:
                continue

            year     = str(datetime.fromtimestamp(f.stat().st_mtime).year)
            dest_dir = cfg.HISTORY_DIR / year
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f.name

            if not dest.exists():
                shutil.move(str(f), str(dest))
                print(f"[OK    ] -> history/{year}/{f.name}", flush=True)
            else:
                print(f"[WARN  ] Gia' in history/{year}/{f.name} -non spostato", flush=True)

    def create_empty_feedback(self, next_label: str = "") -> None:
        """Sovrascrive data/feedback_atleta.yaml con il template vuoto."""
        cfg           = self._config
        label_comment = f"  # {next_label}" if next_label else ""
        template = f"""\
# Feedback Atleta{label_comment}
# Compila i campi lasciando i valori dopo i ':'. Lascia null se non disponibile.

sensazioni:
  energia_generale:   # numero 1-10
  qualita_sonno:      # numero 1-10
  stress:             # basso / medio / alto

allenamento:
  seguito_scheda:     # si / parzialmente / no
  esercizi_pesanti:
  esercizi_difficili:
  note:

dieta:
  seguita:            # si / parzialmente / no
  difficolta:
  note:

progressi:
  piu_forte:          # si / no / uguale
  cambiamenti_fisici:

# Inserisci peso (kg) e reps eseguiti. Il calcolo 1RM e' automatico.
massimali:
  squat:  {{kg: , reps: }}
  panca:  {{kg: , reps: }}
  stacco: {{kg: , reps: }}

corpo:
  peso_kg:
  misure:
    vita_cm:
    fianchi_cm:
    petto_cm:
    braccio_dx_cm:
    coscia_dx_cm:
    collo_cm:

altre_attivita:
  # Attivita' svolte OLTRE all'allenamento in palestra (corsa, ciclismo, nuoto, sport, ecc.)
  # tipo: corsa / ciclismo / nuoto / camminata / sport / yoga / altro
  - tipo:               # es. corsa
    nome:               # es. "Corsa lenta"
    durata_min:         # durata in minuti per sessione
    volte_settimana:    # numero di sessioni a settimana
    intensita:          # bassa / media / alta
    note:
  # Aggiungi altre righe se necessario (copia il blocco sopra)

altro:
  infortuni:
  note:
"""
        dest = cfg.DATA_DIR / "feedback_atleta.yaml"
        dest.write_text(template, encoding="utf-8")
        print(f"[OK    ] Nuovo feedback_atleta.yaml creato ({next_label or 'prossima iterazione'})", flush=True)
