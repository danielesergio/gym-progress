#!/usr/bin/env python3
"""
Orchestratore Python per la generazione/aggiornamento del sito web statico.

Filosofia:
  - Tutta la logica (loop, parsing report, decisioni, esecuzione script) e'
    in Python puro.
  - Gli LLM vengono invocati solo quando servono davvero: per correggere
    codice (gym-web-developer), per fare QA tecnico (gym-web-tester) e
    per la review UX (gym-ux-reviewer).
  - L'esecuzione degli script Python (generate_site.py, generate_data.py)
    avviene direttamente via subprocess, senza passare per l'LLM.
  - I report degli agenti sono JSON con schema fisso (source/schemas/).
    Nessun parsing fragile di Markdown o YAML.

Flusso per iterazione:
  1. [Python] Genera/aggiorna il sito eseguendo lo script appropriato.
     Solo se lo script fallisce -> [LLM] gym-web-developer per diagnostica.
  2. [LLM x2 in parallelo] gym-web-tester + gym-ux-reviewer scrivono i report JSON.
  3. [Python] Legge i JSON e decide se continuare o uscire.
  4. Se problemi -> [LLM] gym-web-developer legge i report e corregge gli script.
  5. [Python] Ri-esegue gli script corretti. Torna a 2.

Uso:
    python source/generate_website.py
    python source/generate_website.py --max-iter 2
"""

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
SCHEMAS_DIR = Path(__file__).parent / "schemas"
DOCS_DIR = PROJECT_ROOT / "docs"
REVIEW_DIR = PROJECT_ROOT / "data" / "output" / "review" / "web-site"

DATE_STR = datetime.now().strftime("%Y-%m-%d")
WEB_REPORT = REVIEW_DIR / f"review_web_{DATE_STR}.json"
UX_REPORT  = REVIEW_DIR / f"review_ux_{DATE_STR}.json"

WEB_SCHEMA = SCHEMAS_DIR / "review_web.schema.json"
UX_SCHEMA  = SCHEMAS_DIR / "review_ux.schema.json"

REVIEW_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_LABELS = {
    "INFO":   "INFO  ",
    "ACTION": "ACTION",
    "FIX":    "FIX   ",
    "OK":     "OK    ",
    "WARN":   "WARN  ",
    "ERROR":  "ERROR ",
}


def log(level: str, msg: str) -> None:
    label = _LABELS.get(level, level)
    print(f"[{label}] {msg}", flush=True)


def separator(title: str = "") -> None:
    line = "=" * 56
    if title:
        print(f"\n{line}\n  {title}\n{line}")
    else:
        print(line)


# ---------------------------------------------------------------------------
# Script execution (Python puro, nessun LLM)
# ---------------------------------------------------------------------------


def run_script(cmd: list[str]) -> tuple[bool, str]:
    """Esegue un comando, cattura stdout+stderr, ritorna (ok, output)."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=PROJECT_ROOT,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output


def generate_site(force: bool = False) -> tuple[bool, str]:
    cmd = ["python", "scripts/generate_site.py", "--outdir", "docs"]
    if force:
        cmd.append("--force")
    log("ACTION", f"Eseguo: {' '.join(cmd)}")
    return run_script(cmd)


def generate_data() -> tuple[bool, str]:
    cmd = ["python", "scripts/generate_data.py", "--outdir", "docs/data"]
    log("ACTION", f"Eseguo: {' '.join(cmd)}")
    return run_script(cmd)


def step_generate(iteration: int, web: dict, ux: dict) -> tuple[bool, str]:
    """
    Iterazione 1: genera il sito da zero o aggiorna i dati.
    Iterazioni successive: il developer ha modificato gli script,
    qui li rieseguiamo per produrre i file docs/ aggiornati.
    """
    if iteration == 1:
        if not (DOCS_DIR / "dashboard.html").exists():
            log("INFO", "docs/dashboard.html non trovato → generate_site.py")
            return generate_site()
        else:
            log("INFO", "docs/dashboard.html esiste → generate_data.py")
            return generate_data()
    else:
        # Il developer ha corretto gli script; rieseguiamo quelli modificati.
        if ux["problemi"]["Alta"] > 0:
            # Problemi UX: generate_site.py e' stato modificato → rigenera tutto
            log("ACTION", "Problemi UX Alta → rigenero sito con --force")
            ok, out = generate_site(force=True)
            if ok:
                ok, out = generate_data()
            return ok, out
        else:
            # Solo errori nei dati: generate_data.py e' stato modificato
            log("ACTION", "Errori tecnici → rigenero dati JSON")
            return generate_data()


# ---------------------------------------------------------------------------
# LLM invocation via claude CLI
# ---------------------------------------------------------------------------


def run_agent(agent_type: str, prompt: str) -> str:
    """Invoca un agente Claude via CLI in modalita' non-interattiva."""
    cmd = [
        "claude",
        "--print",
        "--agent", agent_type,
        "--dangerously-skip-permissions",
        "--output-format", "text",
        prompt,
    ]
    log("ACTION", f"Lancio LLM: {agent_type}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        log("ERROR", f"Agente {agent_type} fallito (rc={result.returncode}): {result.stderr[:300]}")
    return result.stdout.strip()


def run_agents_parallel(tasks: list[tuple[str, str]]) -> dict[str, str]:
    """Lancia piu' agenti in parallelo. tasks = [(agent_type, prompt), ...]"""
    results: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {
            executor.submit(run_agent, agent, prompt): agent
            for agent, prompt in tasks
        }
        for future in as_completed(futures):
            agent = futures[future]
            try:
                results[agent] = future.result()
            except Exception as e:
                log("ERROR", f"Agente {agent} eccezione: {e}")
                results[agent] = ""
    return results


# ---------------------------------------------------------------------------
# Report parsing — JSON con schema fisso, nessuna regex
# ---------------------------------------------------------------------------

_WEB_DEFAULT = {"esito": "UNKNOWN", "errori_critici": 0, "warning": 0, "dettagli": []}
_UX_DEFAULT  = {"valutazione": 0.0, "problemi": {"Alta": 0, "Media": 0, "Bassa": 0}, "lista_alta": [], "lista_media": [], "lista_bassa": []}


def read_web_report() -> dict:
    if not WEB_REPORT.exists():
        log("WARN", f"Report web non trovato: {WEB_REPORT.name}")
        return _WEB_DEFAULT.copy()
    try:
        return json.loads(WEB_REPORT.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log("ERROR", f"JSON non valido in {WEB_REPORT.name}: {e}")
        return {**_WEB_DEFAULT, "esito": "ERROR", "errori_critici": 1}


def read_ux_report() -> dict:
    if not UX_REPORT.exists():
        log("WARN", f"Report UX non trovato: {UX_REPORT.name}")
        return _UX_DEFAULT.copy()
    try:
        return json.loads(UX_REPORT.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log("ERROR", f"JSON non valido in {UX_REPORT.name}: {e}")
        return {**_UX_DEFAULT, "problemi": {"Alta": 1, "Media": 0, "Bassa": 0}}


def is_completed(web: dict, ux: dict) -> bool:
    return web["esito"] in ("OK", "WARNING") and ux["problemi"]["Alta"] == 0


# ---------------------------------------------------------------------------
# Contratti JS↔JSON (Python puro, nessun LLM)
#
# Derivati dall'analisi statica di generate_site.py: per ogni pagina,
# quali chiavi del JSON deve trovare il JS per renderizzare qualcosa.
# Se mancano, la pagina resta su "Caricamento..." senza errori visibili.
# ---------------------------------------------------------------------------

# Struttura contratto:
#   "json_file": path relativo a PROJECT_ROOT
#   "page":      pagina HTML che lo carica
#   "required":  chiavi top-level obbligatorie (assenza → pagina vuota)
#   "non_empty": chiavi che devono essere array non vuoti (vuoto → nessun tab/contenuto)
#   "nested":    list di (percorso_descrittivo, json_path_list, chiavi_richieste)
#                json_path_list: lista di chiavi per navigare il JSON fino al nodo padre
#                                usa None per indicare "primo elemento di un array"

_CONTRACTS = [
    {
        "json_file": "docs/data/workout.json",
        "page": "workout.html",
        "required": ["settimane", "meta"],
        "non_empty": ["settimane"],
        "nested": [
            ("settimane[0]",          ["settimane", None],          ["numero", "giorni"]),
            ("settimane[0].giorni[0]",["settimane", None, "giorni", None], ["giorno", "tipo"]),
        ],
    },
    {
        "json_file": "docs/data/plan.json",
        "page": "plan.html",
        # Il JS accetta sia {html:...} (legacy) sia struttura completa.
        # Se non c'e' html, servono queste chiavi per mostrare contenuto utile.
        "required_any": [["html"], ["meta", "fasi", "target"]],
        "non_empty": [],
        "nested": [],
    },
    {
        "json_file": "docs/data/diet.json",
        "page": "diet.html",
        "required_any": [["html"], ["meta", "giorni"]],
        "non_empty": [],
        "nested": [],
    },
    {
        "json_file": "docs/data/volume.json",
        "page": "volume.html",
        # Il JS legge volumi come volumeData.volumi oppure volumeData stesso (array)
        "required": [],
        "non_empty": [],
        "nested": [],
        "custom_check": "volume",
    },
    {
        "json_file": "docs/data/measurements.json",
        "page": "dashboard.html",
        "required": [],
        "non_empty_root_array": True,  # il file e' un array di misurazioni
        "nested": [],
    },
    {
        "json_file": "docs/data/feedback.json",
        "page": "feedback.html",
        "required": ["html"],
        "non_empty": [],
        "nested": [],
    },
]


def _get_nested(data: dict | list, path: list):
    """Naviga data seguendo path. None in path significa 'primo elemento di array'."""
    node = data
    for key in path:
        if key is None:
            if not isinstance(node, list) or len(node) == 0:
                return None
            node = node[0]
        elif isinstance(node, dict):
            node = node.get(key)
        else:
            return None
        if node is None:
            return None
    return node


def check_json_contracts() -> list[str]:
    """
    Controlla che i JSON in docs/data/ abbiano le chiavi attese dal JS.
    Ritorna una lista di problemi trovati (stringhe descrittive).
    Nessun LLM — pura analisi statica Python.
    """
    issues = []

    for contract in _CONTRACTS:
        json_path = PROJECT_ROOT / contract["json_file"]
        page = contract["page"]

        if not json_path.exists():
            issues.append(f"[{page}] File mancante: {contract['json_file']}")
            continue

        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            issues.append(f"[{page}] JSON non valido in {contract['json_file']}: {e}")
            continue

        # Controllo custom per volume (struttura doppia)
        if contract.get("custom_check") == "volume":
            volumi = data.get("volumi", data) if isinstance(data, dict) else data
            if not isinstance(volumi, list) or len(volumi) == 0:
                issues.append(f"[{page}] volume.json: nessun dato di volume (lista vuota o struttura errata)")
            continue

        # Controllo array root (measurements.json e' un array)
        if contract.get("non_empty_root_array"):
            if not isinstance(data, list) or len(data) == 0:
                issues.append(f"[{page}] {contract['json_file']}: array vuoto o non e' un array")
            continue

        # required_any: almeno uno dei gruppi di chiavi deve essere presente
        if "required_any" in contract:
            groups = contract["required_any"]
            ok = any(all(k in data for k in group) for group in groups)
            if not ok:
                desc = " OPPURE ".join([str(g) for g in groups])
                issues.append(f"[{page}] {contract['json_file']}: nessuna struttura valida trovata. Atteso: {desc}")
            continue

        # required: chiavi obbligatorie
        for key in contract.get("required", []):
            if key not in data:
                issues.append(f"[{page}] {contract['json_file']}: chiave '{key}' mancante")

        # non_empty: array non vuoti
        for key in contract.get("non_empty", []):
            val = data.get(key)
            if not isinstance(val, list) or len(val) == 0:
                issues.append(
                    f"[{page}] {contract['json_file']}: '{key}' e' assente o array vuoto "
                    f"→ nessun contenuto renderizzato"
                )

        # nested: controlli annidati
        for desc, path, keys in contract.get("nested", []):
            node = _get_nested(data, path)
            if node is None:
                issues.append(f"[{page}] {contract['json_file']}: percorso '{desc}' non raggiungibile")
                continue
            for key in keys:
                if key not in node:
                    issues.append(f"[{page}] {contract['json_file']}: '{desc}.{key}' mancante")

    return issues


def build_contract_fix_prompt(issues: list[str]) -> str:
    issues_text = "\n".join(f"  - {i}" for i in issues)
    return f"""Sei il web developer del progetto fitness.
L'analisi statica dei contratti JS↔JSON ha trovato i seguenti problemi che causano
pagine bloccate su "Caricamento...":

{issues_text}

Il JS delle pagine HTML si aspetta queste strutture in docs/data/:
  - workout.json : {{ "settimane": [...], "meta": {{...}} }}
  - plan.json    : {{ "meta": {{...}}, "fasi": [...], "target": [...], "strategia_nutrizionale": {{...}}, "rischi": [...] }}
                   oppure {{ "html": "..." }} (legacy)
  - diet.json    : {{ "meta": {{...}}, "giorni": [...], "integratori": [...] }}
                   oppure {{ "html": "..." }} (legacy)
  - volume.json  : {{ "volumi": [...], "meta": {{...}} }}  oppure direttamente [...]
  - measurements.json : [ {{...}}, ... ]  (array di misurazioni)
  - feedback.json: {{ "html": "..." }}

Correggi `scripts/generate_data.py` (e/o `scripts/volume_calc.py` se il problema
riguarda il volume) in modo che produca la struttura attesa.
NON eseguire gli script — ci pensa l'orchestratore.

Descrivi cosa hai corretto."""


# ---------------------------------------------------------------------------
# Prompt builder — include lo schema JSON per guidare l'agente
# ---------------------------------------------------------------------------

def _schema_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else "(schema non trovato)"


def build_tester_prompt() -> str:
    return f"""Sei il QA tecnico del progetto fitness.
Verifica la correttezza del sito web statico generato (HTML in docs/, dati in docs/data/).

Controlla:
- Esistenza di tutti i file HTML e JSON attesi
- Validita' dei JSON (struttura, chiavi obbligatorie, tipi)
- Coerenza dei dati tra i file

Al termine scrivi il risultato ESCLUSIVAMENTE come JSON valido nel file:
  {WEB_REPORT}

Il JSON deve rispettare questo schema:
```json
{_schema_text(WEB_SCHEMA)}
```

Non scrivere nulla altro oltre al file JSON. Niente testo libero, niente markdown."""


def build_ux_prompt() -> str:
    return f"""Sei l'esperto UX del progetto fitness.
Analizza la dashboard statica (docs/*.html + docs/data/*.json) dal punto di vista
dell'usabilita', gerarchia visiva, leggibilita' e presentazione dei dati.

Al termine scrivi il risultato ESCLUSIVAMENTE come JSON valido nel file:
  {UX_REPORT}

Il JSON deve rispettare questo schema:
```json
{_schema_text(UX_SCHEMA)}
```

Regole per il campo "problemi":
- Alta: bug che nascondono dati critici o causano informazioni errate
- Media: problemi di usabilita' che degradano l'esperienza
- Bassa: miglioramenti estetici o cosmetici

In "lista_alta", "lista_media", "lista_bassa" metti un titolo sintetico per ogni
problema della rispettiva priorita' (max 80 caratteri per voce).

Non scrivere nulla altro oltre al file JSON. Niente testo libero, niente markdown."""


def build_developer_fix_prompt() -> str:
    web_text = WEB_REPORT.read_text(encoding="utf-8") if WEB_REPORT.exists() else "{}"
    ux_text  = UX_REPORT.read_text(encoding="utf-8")  if UX_REPORT.exists()  else "{}"
    return f"""Sei il web developer del progetto fitness.
Leggi i report JSON di review e correggi gli script di generazione.

## Report web-tester ({WEB_REPORT.name})
```json
{web_text}
```

## Report UX-reviewer ({UX_REPORT.name})
```json
{ux_text}
```

## Istruzioni

Il sito viene generato da script Python in `scripts/`:
  - `scripts/generate_site.py`  — genera docs/*.html (struttura HTML, CSS, JS di rendering)
  - `scripts/generate_data.py`  — genera docs/data/*.json (dati letti dagli HTML via fetch)
  - `scripts/volume_calc.py`    — mapping esercizi → muscoli

**Modifica gli script**, NON i file in `docs/` (verrebbero sovrascritti alla prossima esecuzione).
NON eseguire gli script — ci pensa l'orchestratore dopo che hai finito.

### Per problemi UX Alta priorita' (lista_alta nel report UX):
- Modifica `scripts/generate_site.py`: correggi la funzione JS/HTML/CSS che genera
  la parte difettosa (es. aggiungi colonna, fix calcolo, aggiorna stile)

### Per errori tecnici nei dati (dettagli web-tester):
- Modifica `scripts/generate_data.py`: correggi la logica che produce il JSON errato

### Per esercizi non mappati (warning volume):
- Aggiorna `EXERCISE_MUSCLES` in `scripts/volume_calc.py`

Al termine elenca gli script modificati e le correzioni applicate."""


def build_developer_error_prompt(script_output: str) -> str:
    return f"""Sei il web developer del progetto fitness.
Lo script di generazione del sito ha fallito:

```
{script_output[:3000]}
```

Analizza l'errore e correggi il problema negli script in `scripts/`.
NON eseguire gli script — ci pensa l'orchestratore.

Descrivi cosa hai corretto."""


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-iter", type=int, default=3, help="Iterazioni massime (default: 3)")
    args = parser.parse_args()
    max_iter = args.max_iter

    web: dict = _WEB_DEFAULT.copy()
    ux: dict  = _UX_DEFAULT.copy()
    last_iteration = 0

    for iteration in range(1, max_iter + 1):
        last_iteration = iteration
        separator(f"ITERAZIONE {iteration}/{max_iter}")

        # ------------------------------------------------------------------
        # Step A: genera/aggiorna sito (Python puro)
        # ------------------------------------------------------------------
        ok, script_output = step_generate(iteration, web, ux)

        if not ok:
            log("ERROR", f"Script fallito:\n{script_output}")
            log("FIX", "Invoco gym-web-developer per diagnostica...")
            run_agent("gym-web-developer", build_developer_error_prompt(script_output))
            ok2, out2 = generate_data()
            if not ok2:
                log("WARN", f"Script ancora fallito dopo correzione: {out2[:300]}")

        # ------------------------------------------------------------------
        # Step A2: contratti JS↔JSON (Python puro)
        # Verifica che i JSON abbiano le chiavi attese dal JS prima di
        # sprecare token LLM su una pagina che mostra solo "Caricamento..."
        # ------------------------------------------------------------------
        contract_issues = check_json_contracts()
        if contract_issues:
            log("ERROR", f"Contratti JS↔JSON violati ({len(contract_issues)} problemi):")
            for issue in contract_issues:
                log("ERROR", f"  {issue}")
            log("FIX", "Invoco gym-web-developer per correggere la struttura JSON...")
            run_agent("gym-web-developer", build_contract_fix_prompt(contract_issues))
            log("ACTION", "Ri-eseguo generate_data.py dopo la correzione...")
            ok3, out3 = generate_data()
            if not ok3:
                log("WARN", f"generate_data.py ancora fallito: {out3[:300]}")
            # Ri-verifica dopo il fix
            remaining = check_json_contracts()
            if remaining:
                log("WARN", f"Ancora {len(remaining)} problemi di contratto dopo il fix:")
                for issue in remaining:
                    log("WARN", f"  {issue}")
            else:
                log("OK", "Contratti JS↔JSON verificati dopo il fix.")

        # ------------------------------------------------------------------
        # Step B: web-tester + ux-reviewer in parallelo (LLM)
        # ------------------------------------------------------------------
        log("ACTION", "Lancio web-tester e ux-reviewer in parallelo...")
        run_agents_parallel([
            ("gym-web-tester",  build_tester_prompt()),
            ("gym-ux-reviewer", build_ux_prompt()),
        ])

        # ------------------------------------------------------------------
        # Step C: legge i JSON e decide (Python puro)
        # ------------------------------------------------------------------
        web = read_web_report()
        ux  = read_ux_report()

        log("INFO", f"Web-tester  → esito={web['esito']} "
            f"errori={web['errori_critici']} warning={web['warning']}")
        log("INFO", f"UX-reviewer → valutazione={ux['valutazione']} | "
            f"Alta={ux['problemi']['Alta']} Media={ux['problemi']['Media']} Bassa={ux['problemi']['Bassa']}")

        if is_completed(web, ux):
            log("OK", "Nessun problema bloccante. Loop completato.")
            break

        if iteration < max_iter:
            # ------------------------------------------------------------------
            # Step D: gym-web-developer corregge il codice (LLM)
            # ------------------------------------------------------------------
            log("FIX", "Invoco gym-web-developer per correggere i problemi...")
            run_agent("gym-web-developer", build_developer_fix_prompt())
    else:
        log("WARN", f"Raggiunte {max_iter} iterazioni. Problemi residui presenti.")

    # ------------------------------------------------------------------
    # Sommario finale
    # ------------------------------------------------------------------
    separator("SOMMARIO FINALE")
    print(f"ITERAZIONI    : {last_iteration}/{max_iter}")
    print(f"WEB-TESTER    : {web['esito']}")
    print(f"UX-REVIEWER   : {ux['valutazione']}/10 — Alta={ux['problemi']['Alta']} "
          f"Media={ux['problemi']['Media']} Bassa={ux['problemi']['Bassa']}")
    print(f"REPORT        :")
    print(f"  {WEB_REPORT}")
    print(f"  {UX_REPORT}")

    for livello, key in [("ALTA", "lista_alta"), ("MEDIA", "lista_media"), ("BASSA", "lista_bassa")]:
        items = ux.get(key, [])
        if items:
            print(f"\nPROBLEMI {livello} PRIORITA':")
            for item in items:
                print(f"  - {item}")

    if web.get("dettagli"):
        print(f"\nDETTAGLI WEB-TESTER:")
        for d in web["dettagli"]:
            print(f"  [{d['gravita']}] {d['file']}: {d['problema']}")

    if web["esito"] == "ERROR" or ux["problemi"]["Alta"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
