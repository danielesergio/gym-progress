#!/usr/bin/env python3
"""
Orchestratore Python per la nuova iterazione mensile del programma fitness.

Filosofia:
  - Tutta la logica (loop, calcoli, parsing, archivazione) e' in Python puro.
  - Gli LLM vengono invocati solo quando servono: generazione piano, scheda, dieta,
    feedback coach, revisioni PT senior.
  - I report di review sono JSON con schema fisso -Python decide approve/reject.
  - I calcoli (body fat, BMR, TDEE, 1RM, rate progressione) sono Python puro
    usando le funzioni di source/scripts/body_calc.py.
  - L'archiviazione (copia, spostamento file) e' Python puro via shutil.
  - Gli agenti LLM vengono invocati tramite CLI: claude --print --agent <nome>

Flusso:
  1. [Python] Legge tutti i file in data/
  2. [Python] Calcola rate progressione storica e body composition
  3. [Python] Aggiorna measurements.json con nuova entry
  4. [LLM] gym-pt-macro genera plan.yaml
  5. [Loop] gym-pt-senior-reviewer valuta piano (max N iter)
  6. [LLM] gym-personal-trainer genera feedback_coach_(data).md
  7. [Python] Seleziona mesociclo attivo da plan.yaml e agente pt-micro corrispondente
  8. [LLM x2 parallelo] gym-dietologo + pt-micro selezionato -> diet + workout
  9. [Loop] gym-pt-senior-reviewer valuta scheda (max N iter)
 10. [Python] Archivia file, crea nuovo feedback_atleta.yaml vuoto

Mappa tipo_fase (vocabolario fisso gym-pt-macro) -> agente micro:
  REHAB            -> gym-pt-micro-rehab
  Ramp-up          -> gym-pt-micro-rehab
  Accumulo         -> gym-pt-micro-accumulo
  Mini-cut         -> gym-pt-micro-mini-cut
  Intensificazione -> gym-pt-micro-intensificazione
  Peaking          -> gym-pt-micro-peaking
  Tapering & Test  -> gym-pt-micro-tapering

Uso:
    python source/new_iteration.py
    python source/new_iteration.py --max-iter 3
    python source/new_iteration.py --dry-run   # solo parsing e calcoli, nessun LLM
"""

import argparse

from source.AgentRunner import AgentRunner
from source.Archiver import Archiver
from source.BodyCalc import BodyCalc
from source.Config import Config
from source.DataLoader import DataLoader
from source.Logger import Logger
from source.MesoSelector import MesoSelector
from source.Orchestrator import Orchestrator
from source.PromptBuilder import PromptBuilder
from source.ReviewParser import ReviewParser
from source.WorkoutHistory import WorkoutHistory


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-iter",    type=int,  default=3,    help="Iterazioni max loop revisione (default: 3)")
    parser.add_argument("--dry-run",     action="store_true",     help="Solo fase 1-2-3a (calcoli, nessun LLM)")
    parser.add_argument("--log-context", action="store_true", default=True, help="Logga file e info calcolate passati nel prompt di ogni agente")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--new",    dest="mode", action="store_const", const="new",
                            help="Nuova esecuzione: nuovo ITERATION_ID, tutte le fasi LLM eseguite")
    mode_group.add_argument("--resume", dest="mode", action="store_const", const="resume",
                            help="Riprendi esecuzione parziale: riusa ITERATION_ID di oggi, salta fasi gia' completate")
    args = parser.parse_args()

    if args.mode is None:
        print("Modalita':")
        print("  1. new    -nuova esecuzione (nuovo ID, tutte le fasi)")
        print("  2. resume -riprendi esecuzione parziale (riusa ID, salta fasi completate)")
        choice = input("Scelta [1/2]: ").strip()
        args.mode = "resume" if choice == "2" else "new"
        print(f"Modalita': {args.mode}\n")

    config          = Config()
    logger          = Logger(log_context_enabled=args.log_context, config=config)
    body_calc       = BodyCalc(config)
    data_loader     = DataLoader(config)
    workout_history = WorkoutHistory(config)
    agent_runner    = AgentRunner(config)
    review_parser   = ReviewParser()
    prompt_builder  = PromptBuilder(config, body_calc)
    meso_selector   = MesoSelector(config)
    archiver        = Archiver(config)

    orchestrator = Orchestrator(
        config=config,
        logger=logger,
        data_loader=data_loader,
        body_calc=body_calc,
        workout_history=workout_history,
        agent_runner=agent_runner,
        review_parser=review_parser,
        prompt_builder=prompt_builder,
        meso_selector=meso_selector,
        archiver=archiver,
    )
    orchestrator.run(args)


if __name__ == "__main__":
    main()
