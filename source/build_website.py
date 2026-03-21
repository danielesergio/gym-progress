#!/usr/bin/env python3
"""
Orchestratore Python per la pipeline di costruzione/miglioramento del sito web fitness.

Comportamento di default: IDEMPOTENTE.
Ogni fase salta se il suo file di output esiste gia'. Il loop developer/tester
riprende dall'iterazione successiva a quella gia' eseguita.

Pipeline:
  1. [LLM] gym-web-analyst     → data/web-actor/output/web_tasks.json
  2. [LLM] gym-web-prioritizer → data/web-actor/output/web_tasks_ordered.json
  3. [LLM] gym-web-architect   → data/web-actor/output/web_architecture.json
  4. Per ogni task (in ordine):
       a. [LLM] gym-web-planner   → data/web-actor/output/plan_<ID>.json
       b. [Loop max N, riprende dall'ultima iterazione]
            [LLM] gym-web-developer  implementa il task
            [LLM] gym-web-task-tester verifica → data/web-actor/output/test_<ID>_iter<N>.json
            Se esito=OK: prossimo task
            Se esito=PARZIALE/FALLITO e iter < max: torna al developer
            Se esito=PARZIALE/FALLITO e iter == max: log WARN, prossimo task

Uso:
    python source/build_website.py                    # idempotente: riprende da dove si era fermato
    python source/build_website.py --force            # rigenera tutto da zero
    python source/build_website.py --force-analysis   # rigenera solo analyst+prioritizer
    python source/build_website.py --force-architect  # rigenera solo architect
    python source/build_website.py --web-dir docs --max-iter 2
    python source/build_website.py --dry-run
    python source/build_website.py --only-tasks T01,T03
    python source/build_website.py --log-context
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR     = PROJECT_ROOT / "data"
OUTPUT_DIR   = DATA_DIR / "output"
ACTOR_DIR    = DATA_DIR / "web-actor" / "output"

DATE_STR = datetime.now().strftime("%Y-%m-%d")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_LABELS = {
    "INFO":   "INFO  ",
    "ACTION": "ACTION",
    "OK":     "OK    ",
    "WARN":   "WARN  ",
    "ERROR":  "ERROR ",
    "SKIP":   "SKIP  ",
    "FASE":   "FASE  ",
    "LOOP":   "LOOP  ",
}


def log(level: str, msg: str) -> None:
    print(f"[{_LABELS.get(level, level)}] {msg}", flush=True)


def separator(title: str = "") -> None:
    line = "=" * 60
    if title:
        print(f"\n{line}\n  {title}\n{line}")
    else:
        print(line)


# ---------------------------------------------------------------------------
# LLM invocation via claude CLI
# ---------------------------------------------------------------------------


def run_agent(agent_type: str, prompt: str, dry_run: bool = False) -> str:
    """Invoca un agente Claude via CLI in modalita' non-interattiva."""
    log("ACTION", f"LLM: {agent_type}")
    if dry_run:
        log("SKIP", f"dry-run: {agent_type} non invocato")
        return ""
    cmd = [
        "claude",
        "--print",
        "--agent", agent_type,
        "--dangerously-skip-permissions",
        "--output-format", "text",
        prompt,
    ]
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


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log("ERROR", f"JSON non valido in {path.name}: {e}")
        return default


def _rel(path: Path) -> Path:
    try:
        return path.relative_to(PROJECT_ROOT)
    except ValueError:
        return path


def _file_size(path: Path) -> str:
    return f"{path.stat().st_size:>7} B" if path.exists() else "  MANCANTE"


def _glob_list(directory: Path, pattern: str = "*") -> list[str]:
    """Lista di path relativi a PROJECT_ROOT per i file trovati."""
    if not directory.exists():
        return []
    return [str(_rel(p)) for p in sorted(directory.glob(pattern)) if p.is_file()]


# ---------------------------------------------------------------------------
# log_context
# ---------------------------------------------------------------------------


def make_log_context(enabled: bool):
    LABEL = {
        "incorporato":  "Incorporato  ",
        "obbligatorio": "Da leggere   ",
        "discrezione":  "A discrezione",
    }

    def log_context(agent: str, files: list, calcs: list = None) -> None:
        if not enabled:
            return
        print(f"\n  [CONTEXT] {agent}")
        for path_raw, modalita in files:
            p = path_raw if isinstance(path_raw, Path) else Path(path_raw)
            abs_p = p if p.is_absolute() else PROJECT_ROOT / p
            if "*" in str(abs_p):
                matches = sorted(abs_p.parent.glob(abs_p.name), reverse=True)
                if matches:
                    abs_p = matches[0]
                else:
                    print(f"    [{LABEL.get(modalita, modalita)}] {p}  (  MANCANTE)")
                    continue
            label = LABEL.get(modalita, modalita)
            stato = _file_size(abs_p)
            print(f"    [{label}] {_rel(abs_p)}  ({stato})")
        for desc in (calcs or []):
            print(f"    [Info calcolata ] {desc}")

    return log_context


# ---------------------------------------------------------------------------
# Idempotency helpers
# ---------------------------------------------------------------------------


def _should_run(output_path: Path, force: bool, label: str) -> bool:
    """True se l'agente deve essere eseguito, False se l'output esiste gia'."""
    if force:
        return True
    if output_path.exists():
        log("SKIP", f"{label} — output gia' presente: {_rel(output_path)}")
        return False
    return True


def get_last_test_iteration(actor_dir: Path, task_id: str) -> int:
    """
    Ritorna il numero dell'ultima iterazione per cui esiste un file test_<ID>_iter<N>.json,
    oppure 0 se nessuna iterazione e' mai stata eseguita.
    """
    iterations = []
    for p in actor_dir.glob(f"test_{task_id}_iter*.json"):
        try:
            n = int(p.stem.split("_iter")[-1])
            iterations.append(n)
        except ValueError:
            pass
    return max(iterations) if iterations else 0


def is_task_ok(actor_dir: Path, task_id: str) -> bool:
    """True se esiste almeno un test con esito OK per questo task."""
    for p in actor_dir.glob(f"test_{task_id}_iter*.json"):
        data = read_json(p, default={})
        if data.get("esito") == "OK":
            return True
    return False


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def build_analyst_prompt(web_dir: Path, actor_dir: Path, goal: str) -> str:
    output_path = actor_dir / "web_tasks.json"
    mandatory_data = _glob_list(OUTPUT_DIR, "*.json")
    site_html  = _glob_list(web_dir, "*.html")
    site_data  = _glob_list(web_dir / "data", "*.json")
    review_files = _glob_list(OUTPUT_DIR / "review" / "web-site", "*.json")

    mandatory_lines = "\n".join(f"  - {f}" for f in mandatory_data) if mandatory_data else "  (nessun file dati trovato)"
    optional_site   = "\n".join(f"  - {f}" for f in site_html + site_data) if (site_html or site_data) else "  (sito non ancora generato)"
    optional_review = "\n".join(f"  - {f}" for f in review_files) if review_files else "  (nessun report)"

    return f"""Sei il gym-web-analyst del progetto fitness.
Analizza il progetto e produci una lista strutturata di task per il sito web.

## Obiettivo
{goal}

## File da leggere

### Obbligatori
  - data/web-site-goal  (obiettivi e requisiti del sito — leggilo per primo)
{mandatory_lines}

### A discrezione (leggi se utile per capire il contesto)
Sito esistente:
{optional_site}

Report di review precedenti:
{optional_review}

  - data/feedback_atleta.md
  - data/athlete.md

## Output
Scrivi il risultato nel file:
  {output_path}

Tutti i percorsi in `file_coinvolti` devono essere relativi alla root del progetto."""


def build_prioritizer_prompt(tasks_path: Path, actor_dir: Path) -> str:
    output_path = actor_dir / "web_tasks_ordered.json"
    tasks_text  = tasks_path.read_text(encoding="utf-8") if tasks_path.exists() else "{}"
    return f"""Sei il gym-web-prioritizer del progetto fitness.
Ordina la lista di task seguendo le regole di dipendenza, categoria e priorità.

## Task list da ordinare
File: {tasks_path}

```json
{tasks_text[:8000]}
```

## Output
Scrivi la lista ordinata nel file:
  {output_path}"""


def build_architect_prompt(web_dir: Path, actor_dir: Path, tasks_path: Path) -> str:
    output_path = actor_dir / "web_architecture.json"
    site_html   = _glob_list(web_dir, "*.html")
    site_data   = _glob_list(web_dir / "data", "*.json")
    optional    = "\n".join(f"  - {f}" for f in site_html + site_data) if (site_html or site_data) else "  (sito non ancora generato)"

    return f"""Sei il gym-web-architect del progetto fitness.
Definisci l'architettura del sito web statico.

## Vincoli obbligatori
- Nessun build step (no webpack, no npm run build)
- Deploy su GitHub Pages (cartella {_rel(web_dir)}/)
- HTML, CSS e JS sono scritti direttamente dal developer in {_rel(web_dir)}/
- I soli file generati da script Python sono i dati JSON in {_rel(web_dir)}/data/ — il developer non li tocca
- Compatibile con fetch() da file statici (no SSR)

## File da leggere

### Obbligatori
  - {_rel(tasks_path)}
  - data/output/measurements.json

### A discrezione
{optional}
  - data/athlete.md

## Output
Scrivi la definizione di architettura nel file:
  {output_path}"""


def build_planner_prompt(task: dict, actor_dir: Path, web_dir: Path, arch_path: Path, tasks_ordered_path: Path) -> str:
    task_id     = task["id"]
    output_path = actor_dir / f"plan_{task_id}.json"
    site_html   = _glob_list(web_dir, "*.html")
    site_data   = _glob_list(web_dir / "data", "*.json")
    optional    = "\n".join(f"  - {f}" for f in site_html + site_data) if (site_html or site_data) else "  (nessun file HTML/JSON esistente)"
    task_text   = json.dumps(task, ensure_ascii=False, indent=2)

    return f"""Sei il gym-web-planner del progetto fitness.
Prepara il pacchetto di lavoro completo per il task {task_id}.

## Task da pianificare
```json
{task_text}
```

## File da leggere

### Obbligatori
  - {_rel(arch_path)}
  - {_rel(tasks_ordered_path)}

### A discrezione
{optional}
  - data/output/measurements.json

## Output
Scrivi il pacchetto di lavoro nel file:
  {output_path}"""


def build_developer_prompt(task: dict, plan_path: Path, arch_path: Path, iteration: int, prev_test_path: Path | None) -> str:
    task_id    = task["id"]
    plan_text  = plan_path.read_text(encoding="utf-8") if plan_path.exists() else "{}"
    iter_note  = ""
    if iteration > 1 and prev_test_path and prev_test_path.exists():
        prev = read_json(prev_test_path, default={})
        criteri_falliti = [c["criterio"] for c in prev.get("criteri", []) if not c.get("soddisfatto")]
        anomalie = [f"[{a['gravita']}] {a['descrizione']}" for a in prev.get("anomalie", [])]
        lines = []
        if criteri_falliti:
            lines.append("**Criteri non soddisfatti nell'iterazione precedente:**")
            lines.extend(f"  - {c}" for c in criteri_falliti)
        if anomalie:
            lines.append("**Anomalie segnalate:**")
            lines.extend(f"  - {a}" for a in anomalie)
        if lines:
            iter_note = "\n> **Iterazione " + str(iteration) + "** — il tester ha segnalato:\n" + "\n".join(lines) + "\n"

    return f"""Sei il gym-web-developer del progetto fitness.
Implementa il task {task_id}.{iter_note}

## Pacchetto di lavoro
File: {plan_path}

```json
{plan_text[:10000]}
```

## File da leggere sempre
  - {_rel(arch_path)}  (stack, convenzioni, naming — non deviare)

## Istruzioni
1. Leggi il pacchetto di lavoro completo
2. Leggi tutti i file in `file.da_leggere` del pacchetto
3. Scrivi o modifica i file in `file.da_modificare` — HTML, CSS e JS in docs/
4. Usa **Write** per file nuovi, **Edit** per modifiche a file esistenti
5. NON toccare i file in docs/data/ (generati da script Python)
6. Tocca SOLO i file elencati in `file.da_modificare` — nessun refactoring extra
7. Rispetta rigorosamente stack e convenzioni in {_rel(arch_path)}

Al termine stampa:
TASK: {task_id}
FILE: lista dei file modificati/creati
CRITERI: [OK/NO] per ogni criterio
ANOMALIE: eventuali problemi trovati"""


def build_tester_prompt(task: dict, plan_path: Path, actor_dir: Path, iteration: int) -> str:
    task_id     = task["id"]
    output_path = actor_dir / f"test_{task_id}_iter{iteration}.json"
    plan_text   = plan_path.read_text(encoding="utf-8") if plan_path.exists() else "{}"

    return f"""Sei il gym-web-task-tester del progetto fitness.
Verifica l'implementazione del task {task_id} (iterazione {iteration}).

## Pacchetto di lavoro
File: {plan_path}

```json
{plan_text[:8000]}
```

## Istruzioni
1. Per ogni file in `file.da_modificare` del pacchetto: verifica che esista
2. Leggi ogni file HTML/CSS/JS implementato
3. Per ogni criterio in `criteri_accettazione`: cerca evidenza diretta nel codice
4. Segnala anomalie bloccanti (crash, pagina vuota), warning (null non gestiti, fetch errata) e info

## Output
Scrivi il report nel file:
  {output_path}

```json
{{
  "meta": {{"data": "YYYY-MM-DD", "task_id": "{task_id}", "task_titolo": "...", "iterazione": {iteration}}},
  "esito": "OK | PARZIALE | FALLITO",
  "criteri": [{{"criterio": "...", "soddisfatto": true, "dettaglio": "..."}}],
  "file_verificati": [{{"path": "...", "esiste": true, "note": "..."}}],
  "anomalie": [{{"gravita": "bloccante|warning|info", "descrizione": "...", "file": "..."}}]
}}
```

Al termine stampa:
TASK: {task_id} — iterazione {iteration}
ESITO: OK | PARZIALE | FALLITO
CRITERI: <n soddisfatti>/<n totali>
ANOMALIE: <n bloccanti> bloccanti, <n warning> warning"""


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------


def load_ordered_tasks(path: Path) -> list[dict]:
    """Carica la lista flat ordinata prodotta dal prioritizer (tasks[])."""
    data = read_json(path, default={})
    return data.get("tasks", []) if data else []


def load_raw_tasks(path: Path) -> dict[str, dict]:
    """
    Carica le definizioni complete dei task da web_tasks.json (formato analyst).
    Supporta sia il nuovo formato nested (features[].tasks[]) sia il vecchio flat (tasks[]).
    Ritorna dict {task_id: task_dict}.
    """
    data = read_json(path, default={})
    if not data:
        return {}
    # Nuovo formato: features[].tasks[]
    if "features" in data:
        result = {}
        for feature in data.get("features", []):
            for task in feature.get("tasks", []):
                result[task["id"]] = {**task, "_feature": feature.get("name", "")}
        return result
    # Vecchio formato flat: tasks[]
    return {t["id"]: t for t in data.get("tasks", [])}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-dir",        default="docs",      help="Directory root del sito web (default: docs)")
    parser.add_argument("--max-iter",        type=int, default=3, help="Iterazioni max per loop developer/tester per task (default: 3)")
    parser.add_argument("--dry-run",         action="store_true", help="Solo parsing, nessun LLM")
    parser.add_argument("--log-context",     default=True, action="store_true", help="Logga file e info passati nel prompt di ogni agente")
    parser.add_argument("--only-tasks",      default="",          help="Esegui solo questi task (es. T01,T03)")
    parser.add_argument("--goal",            default="",          help="Obiettivo dell'analisi (es. 'prima generazione')")
    # Flags per forzare la rigenerazione (override idempotenza)
    parser.add_argument("--force",           action="store_true", help="Rigenera tutto da zero (override idempotenza)")
    parser.add_argument("--force-analysis",  action="store_true", help="Rigenera solo analyst+prioritizer")
    parser.add_argument("--force-architect", action="store_true", help="Rigenera solo architect")
    args = parser.parse_args()

    web_dir   = PROJECT_ROOT / args.web_dir
    actor_dir = ACTOR_DIR
    actor_dir.mkdir(parents=True, exist_ok=True)

    log_context = make_log_context(args.log_context)

    only_tasks = {t.strip() for t in args.only_tasks.split(",") if t.strip()} if args.only_tasks else set()

    # Percorsi output delle fasi globali
    tasks_path         = actor_dir / "web_tasks.json"
    tasks_ordered_path = actor_dir / "web_tasks_ordered.json"
    arch_path          = actor_dir / "web_architecture.json"

    goal = args.goal or (
        "prima generazione del sito"
        if not web_dir.exists() or not list(web_dir.glob("*.html"))
        else "miglioramento del sito esistente"
    )

    # =========================================================================
    # FASE 1 — Analyst
    # =========================================================================
    separator("FASE 1 — Analyst")
    force_analysis = args.force or args.force_analysis

    if _should_run(tasks_path, force_analysis, "gym-web-analyst"):
        data_files   = list((OUTPUT_DIR).glob("*.json"))
        site_html    = list(web_dir.glob("*.html")) if web_dir.exists() else []
        review_files = list((OUTPUT_DIR / "review" / "web-site").glob("*.json")) if (OUTPUT_DIR / "review" / "web-site").exists() else []

        log_context("gym-web-analyst", [
            (DATA_DIR   / "web-site-goal",        "obbligatorio"),
            (OUTPUT_DIR / "measurements.json",    "obbligatorio"),
            (DATA_DIR   / "feedback_atleta.md",   "obbligatorio"),
            (DATA_DIR   / "athlete.md",           "discrezione"),
            *([(f, "discrezione") for f in site_html[:5]]),
            *([(f, "discrezione") for f in review_files[:3]]),
        ], [f"Obiettivo: {goal}", f"Output: {_rel(tasks_path)}"])

        run_agent("gym-web-analyst", build_analyst_prompt(web_dir, actor_dir, goal), args.dry_run)

        if not tasks_path.exists() and not args.dry_run:
            log("ERROR", f"L'analyst non ha prodotto {tasks_path.name} — impossibile continuare")
            sys.exit(1)

    # =========================================================================
    # FASE 2 — Prioritizer
    # =========================================================================
    separator("FASE 2 — Prioritizer")

    if _should_run(tasks_ordered_path, force_analysis, "gym-web-prioritizer"):
        log_context("gym-web-prioritizer", [
            (tasks_path, "obbligatorio"),
        ], [f"Output: {_rel(tasks_ordered_path)}"])

        run_agent("gym-web-prioritizer", build_prioritizer_prompt(tasks_path, actor_dir), args.dry_run)

        if not tasks_ordered_path.exists() and not args.dry_run:
            log("WARN", f"Prioritizer non ha prodotto {tasks_ordered_path.name} — uso task list non ordinata")
            import shutil
            shutil.copy(tasks_path, tasks_ordered_path)

    # =========================================================================
    # FASE 3 — Architect
    # =========================================================================
    separator("FASE 3 — Architect")
    force_arch = args.force or args.force_architect

    if _should_run(arch_path, force_arch, "gym-web-architect"):
        site_html = list(web_dir.glob("*.html")) if web_dir.exists() else []
        log_context("gym-web-architect", [
            (tasks_ordered_path if tasks_ordered_path.exists() else tasks_path, "obbligatorio"),
            (OUTPUT_DIR / "measurements.json", "obbligatorio"),
            *([(f, "discrezione") for f in site_html[:3]]),
            (DATA_DIR / "athlete.md", "discrezione"),
        ], [f"Vincoli: no build step, GitHub Pages, Python scripts",
            f"Output: {_rel(arch_path)}"])

        run_agent(
            "gym-web-architect",
            build_architect_prompt(web_dir, actor_dir, tasks_ordered_path if tasks_ordered_path.exists() else tasks_path),
            args.dry_run,
        )

        if not arch_path.exists() and not args.dry_run:
            log("ERROR", f"L'architect non ha prodotto {arch_path.name} — impossibile continuare")
            sys.exit(1)

    # =========================================================================
    # FASE 4 — Per ogni task: plan → developer → tester loop
    # =========================================================================
    separator("FASE 4 — Implementazione task")

    ordered_tasks = load_ordered_tasks(tasks_ordered_path if tasks_ordered_path.exists() else tasks_path)
    raw_tasks     = load_raw_tasks(tasks_path)

    if not ordered_tasks:
        log("WARN", "Nessun task trovato. Esci.")
        return

    if only_tasks:
        ordered_tasks = [t for t in ordered_tasks if t.get("id") in only_tasks]
        log("INFO", f"--only-tasks: {len(ordered_tasks)} task selezionati")

    log("INFO", f"Task da processare: {len(ordered_tasks)}")

    results_summary: list[dict] = []

    total_tasks = len(ordered_tasks)
    for task_index, task_entry in enumerate(ordered_tasks, start=1):
        task_id = task_entry.get("id", "??")
        task    = raw_tasks.get(task_id, task_entry)  # versione completa da web_tasks.json

        separator(f"TASK {task_index} di {total_tasks} — {task_id} — {task.get('titolo', task.get('title', ''))[:50]}")

        # ------------------------------------------------------------------
        # Salta task gia' completati con esito OK
        # ------------------------------------------------------------------
        if not args.force and is_task_ok(actor_dir, task_id):
            log("SKIP", f"{task_id} gia' completato con esito OK")
            results_summary.append({"id": task_id, "titolo": task.get("title", task.get("titolo", "")), "esito": "OK (skip)", "iterazioni": 0})
            continue

        # -----------------------------------------------------------------------
        # FASE 4a — Planner (idempotente: salta se plan_<ID>.json esiste gia')
        # -----------------------------------------------------------------------
        plan_path = actor_dir / f"plan_{task_id}.json"

        if _should_run(plan_path, args.force, f"gym-web-planner [{task_id}]"):
            log("FASE", f"{task_id} → planning")
            outputs_str = ", ".join(task.get("outputs", [])[:5])
            log_context(f"gym-web-planner [{task_id}]", [
                (arch_path,          "obbligatorio"),
                (tasks_ordered_path, "obbligatorio"),
            ], [f"Task: {task_id} — {task.get('title', task.get('titolo', ''))}",
                f"Outputs logici: {outputs_str}",
                f"Output: {_rel(plan_path)}"])

            run_agent("gym-web-planner", build_planner_prompt(task, actor_dir, web_dir, arch_path, tasks_ordered_path), args.dry_run)

            if not plan_path.exists() and not args.dry_run:
                log("ERROR", f"Planner non ha prodotto {plan_path.name} — salto task {task_id}")
                results_summary.append({"id": task_id, "titolo": task.get("title", task.get("titolo", "")), "esito": "ERRORE (planner)", "iterazioni": 0})
                continue

        # -----------------------------------------------------------------------
        # FASE 4b — Developer / Tester loop, riprende dall'ultima iterazione
        # -----------------------------------------------------------------------
        last_iter   = get_last_test_iteration(actor_dir, task_id)
        start_iter  = last_iter + 1
        task_esito  = "FALLITO"
        task_iters  = last_iter

        if last_iter > 0:
            # Controlla se l'ultima iterazione era gia' OK
            last_result = read_json(actor_dir / f"test_{task_id}_iter{last_iter}.json", default={})
            if last_result.get("esito") == "OK":
                log("SKIP", f"{task_id} — ultima iterazione ({last_iter}) gia' OK")
                results_summary.append({"id": task_id, "titolo": task.get("title", task.get("titolo", "")), "esito": "OK", "iterazioni": last_iter})
                continue
            log("INFO", f"{task_id} — riprendo da iterazione {start_iter} (ultima: {last_iter}, esito={last_result.get('esito')})")

        if start_iter > args.max_iter:
            log("WARN", f"{task_id} — gia' esaurite {last_iter} iterazioni (max={args.max_iter}), salto")
            last_result = read_json(actor_dir / f"test_{task_id}_iter{last_iter}.json", default={})
            results_summary.append({"id": task_id, "titolo": task.get("title", task.get("titolo", "")), "esito": last_result.get("esito", "FALLITO"), "iterazioni": last_iter})
            continue

        for iteration in range(start_iter, args.max_iter + 1):
            task_iters = iteration
            log("LOOP", f"{task_id} — iterazione {iteration}/{args.max_iter}")

            prev_test = actor_dir / f"test_{task_id}_iter{iteration - 1}.json" if iteration > 1 else None

            # Developer
            log_context(f"gym-web-developer [{task_id} iter{iteration}]", [
                (plan_path, "obbligatorio"),
                (arch_path, "obbligatorio"),
                *([( prev_test, "incorporato")] if prev_test and prev_test.exists() else []),
            ], [f"Iterazione {iteration}/{args.max_iter}"])

            run_agent("gym-web-developer", build_developer_prompt(task, plan_path, arch_path, iteration, prev_test), args.dry_run)

            # Tester
            test_path = actor_dir / f"test_{task_id}_iter{iteration}.json"
            log_context(f"gym-web-task-tester [{task_id} iter{iteration}]", [
                (plan_path, "obbligatorio"),
            ], [f"Output: {_rel(test_path)}"])

            run_agent("gym-web-task-tester", build_tester_prompt(task, plan_path, actor_dir, iteration), args.dry_run)

            if args.dry_run:
                task_esito = "OK (dry-run)"
                break

            test_result = read_json(test_path, default=None)
            if test_result is None:
                log("WARN", f"Tester non ha prodotto il report per {task_id} iter{iteration}")
                task_esito = "FALLITO (no report)"
                break

            esito        = test_result.get("esito", "FALLITO")
            n_soddisfatti = sum(1 for c in test_result.get("criteri", []) if c.get("soddisfatto"))
            n_totali      = len(test_result.get("criteri", []))
            n_bloccanti   = sum(1 for a in test_result.get("anomalie", []) if a.get("gravita") == "bloccante")
            log("INFO", f"Esito={esito} criteri={n_soddisfatti}/{n_totali} bloccanti={n_bloccanti}")

            task_esito = esito

            if esito == "OK":
                log("OK", f"{task_id} completato in {iteration} iterazione/i")
                break

            if iteration < args.max_iter:
                log("LOOP", f"{task_id}: esito={esito} — rilancio developer (iter {iteration + 1})")
            else:
                log("WARN", f"{task_id}: raggiunto max-iter={args.max_iter} con esito={esito}")

        results_summary.append({
            "id":        task_id,
            "titolo":    task.get("title", task.get("titolo", "")),
            "esito":     task_esito,
            "iterazioni": task_iters,
        })

    # =========================================================================
    # Sommario finale
    # =========================================================================
    separator("SOMMARIO FINALE")
    ok_count   = sum(1 for r in results_summary if r["esito"].startswith("OK"))
    fail_count = len(results_summary) - ok_count
    print(f"TASK PROCESSATI : {len(results_summary)}  (OK={ok_count}  KO={fail_count})")
    print()
    for r in results_summary:
        stato = "OK" if r["esito"].startswith("OK") else "!!"
        print(f"  [{stato}] {r['id']:<4}  iter={r['iterazioni']}  {r['esito']:<20}  {r.get('titolo','')[:50]}")

    print(f"\nOUTPUT DIR : {actor_dir}")
    print(f"WEB DIR    : {web_dir}")

    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
