import json
import sys

from source.AgentRunner import AgentRunner
from source.Archiver import Archiver
from source.BodyCalc import BodyCalc
from source.DataLoader import DataLoader
from source.Logger import Logger
from source.MesoSelector import MesoSelector
from source.PromptBuilder import PromptBuilder
from source.ReviewParser import ReviewParser
from source.WorkoutHistory import WorkoutHistory
from source.Config import Config

from abc import ABC, abstractmethod

class Skippable(ABC):

    @abstractmethod
    def skip(self) -> bool:
        """Ritorna True se l'azione deve essere saltata"""
        pass

    @abstractmethod
    def action(self):
        """Azione principale da eseguire se non si salta"""
        pass

    @abstractmethod
    def on_skip(self):
        """Azione da eseguire se viene fatto skip"""
        pass

    def run(self):
        """Esegue action o on_skip in base al risultato di skip"""
        if self.skip():
            return self.on_skip()
        else:
            return self.action()



class Orchestrator:
    def __init__(
        self,
        config: Config,
        logger: Logger,
        data_loader: DataLoader,
        body_calc: BodyCalc,
        workout_history: WorkoutHistory,
        agent_runner: AgentRunner,
        review_parser: ReviewParser,
        prompt_builder: PromptBuilder,
        meso_selector: MesoSelector,
        archiver: Archiver,
    ):
        self._cfg             = config
        self._logger          = logger
        self._data_loader     = data_loader
        self._body_calc       = body_calc
        self._workout_history = workout_history
        self._agent_runner    = agent_runner
        self._review_parser   = review_parser
        self._prompt_builder  = prompt_builder
        self._meso_selector   = meso_selector
        self._archiver        = archiver

    def run(self, args) -> None:
        cfg    = self._cfg
        logger = self._logger

        RESUME      = args.mode == "resume"
        MAX_ITER    = args.max_iter

        plan_approved    = False
        workout_approved = False

        # ──────────────────────────────────────────────────────────────────
        # FASE 1 -Lettura dati e inizializzazione existing_today
        # ──────────────────────────────────────────────────────────────────
        logger.separator("FASE 1 -Lettura dati")
        ctx = self._data_loader.load_all_data(self._body_calc, logger)

        existing_today = ctx["measurements"][-1] if ctx["measurements"] else None

        if RESUME and existing_today and existing_today.get("id") and existing_today["id"] != cfg.iteration_id:
            logger.log("INFO", f"RESUME: riuso ITERATION_ID={existing_today['id']} dall'entry {cfg.DATE_STR}")
            cfg.iteration_id = existing_today["id"]
        elif not RESUME and existing_today:
            logger.log("INFO", f"NEW: entry {cfg.DATE_STR} esistente con id={existing_today['id']} -sara' ignorata, nuovo id={cfg.iteration_id}")
            existing_today = None
        # ──────────────────────────────────────────────────────────────────
        # FASE 2 -Calcoli
        # ──────────────────────────────────────────────────────────────────
        logger.separator("FASE 2 -Calcoli progressione e composizione corporea")

        athlete_profile = self._body_calc.parse_athlete_profile(ctx["athlete_text"])
        feedback        = self._body_calc.parse_feedback(ctx["feedback_data"])

        logger.log("INFO", f"Profilo: altezza={athlete_profile.get('altezza_cm')} cm, "
                   f"sesso={athlete_profile.get('sesso')}, eta={athlete_profile.get('eta')} anni")
        logger.log("INFO", f"Feedback: peso={feedback.get('peso_kg')} kg | "
                   f"squat={feedback.get('squat_test')}, panca={feedback.get('panca_test')}, "
                   f"stacco={feedback.get('stacco_test')}")

        enriched_count = self._body_calc.enrich_missing_body_composition(ctx["measurements"], athlete_profile)
        if enriched_count > 0:
            (cfg.OUTPUT_DIR / "measurements.json").write_text(
                json.dumps(ctx["measurements"], indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            logger.log("OK", f"Arricchite {enriched_count} entry storiche con body composition")

        self._workout_history._set_body_calc(self._body_calc)
        self._workout_history.build_from_seed(ctx["measurements"])

        misure_mancanti = [k for k in ("vita_cm", "collo_cm", "fianchi_cm", "petto_cm", "braccio_dx_cm", "coscia_dx_cm")
                           if not feedback.get(k)]
        if misure_mancanti:
            logger.log("WARN", f"Misure non trovate nel feedback: {', '.join(misure_mancanti)}")

        rates_raw    = self._body_calc.calc_progression_rates(ctx["measurements"])
        rates        = self._body_calc.apply_corrections(rates_raw, ctx["measurements"], ctx["feedback_text"])
        ctx["rates"] = rates

        print()
        print("RATE DI PROGRESSIONE STORICA:")
        for lift, d in rates.items():
            print(f"  - {lift.capitalize()}: storico {d['media']} kg/anno "
                  f"-> corretta {d['media_corretta']} kg/anno "
                  f"(range {d['min']}..{d['max']}, n={d['n']})")

        # ──────────────────────────────────────────────────────────────────
        # FASE 3a -Aggiorna measurements.json
        # ──────────────────────────────────────────────────────────────────
        logger.separator("FASE 3a -Aggiornamento measurements.json")

        workout_history_list = self._workout_history.load()

        new_m = self._body_calc.build_new_measurement(feedback, athlete_profile, ctx["measurements"])
        if new_m:
            if existing_today:
                logger.log("WARN", f"Entry {cfg.DATE_STR} gia' presente (id={cfg.iteration_id}) -non duplicata")
            else:
                ctx["measurements"].append(new_m)
                (cfg.OUTPUT_DIR / "measurements.json").write_text(
                    json.dumps(ctx["measurements"], indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
                logger.log("OK", f"measurements.json aggiornato: BF%={new_m.get('body_fat_pct')}, "
                           f"MM={new_m.get('massa_magra_kg')} kg, FFMI={new_m.get('ffmi_adj')}")

                if self._workout_history.complete_last_entry(workout_history_list, ctx["measurements"]):
                    self._workout_history.save(workout_history_list)

            if not any(e.get("id") == cfg.iteration_id for e in workout_history_list):
                self._workout_history.append_entry(workout_history_list, ctx["measurements"])
                self._workout_history.save(workout_history_list)
            else:
                logger.log("INFO", f"RESUME: entry workout_history {cfg.iteration_id} gia' presente")
        else:
            logger.log("SKIP", "measurements.json non aggiornato (dati insufficienti nel feedback)")

        if args.dry_run:
            logger.log("INFO", "Dry-run: terminato. Nessun LLM invocato.")
            return

        cfg.REVIEW_PT_DIR.mkdir(parents=True, exist_ok=True)
        plan_review_path    = cfg.REVIEW_PT_DIR / f"review_plan_{cfg.iteration_id}.json"
        workout_review_path = cfg.REVIEW_PT_DIR / f"review_workout_{cfg.iteration_id}.json"

        logger.log("INFO", f"plan_review_path.yaml {plan_review_path.exists()} - ${plan_review_path.absolute()}")
        logger.log("INFO", f"workout_review_path.yaml {workout_review_path.exists()} - ${workout_review_path.absolute()}")

        # ──────────────────────────────────────────────────────────────────
        # FASE 3b -Piano a lungo termine
        # ──────────────────────────────────────────────────────────────────
        logger.separator("FASE 3b -Generazione piano a lungo termine")
        plan_file       = cfg.OUTPUT_DIR / "plan.yaml"
        plan_start_iter = 1
        plan_need_regen = False

        if RESUME and plan_file.exists() and plan_review_path.exists():
            approved, score, problems, num_rev = self._review_parser.parse(plan_review_path)
            if approved:
                logger.log("OK", f"Piano gia' APPROVATO (review {num_rev}, {score}/10) -3b saltata")
                plan_approved = True
            else:
                plan_start_iter = num_rev + 1
                plan_need_regen = True
                logger.log("INFO", f"Piano esistente, review {num_rev} BOCCIATA -riprendo da iter {plan_start_iter}")
        elif RESUME and plan_file.exists():
            logger.log("INFO", "plan.yaml esistente, nessuna review trovata -inizio revisione")
        else:
            logger.log("ACTION", "gym-pt-macro -> plan.yaml")
            logger.log_context("gym-pt-macro [build_plan]", [
                ("data/athlete.md",           "incorporato"),
                ("data/feedback_atleta.yaml",   "incorporato"),
                ("data/output/plan.yaml",     "incorporato"),
                ("data/output/performance_analysis.yaml", "incorporato"),
            ], ["Misurazioni storiche (ultime 5) — tabella markdown",
                "Rate progressione corretti per eta'/infortuni/stallo"])
            self._agent_runner.run("gym-pt-macro", self._prompt_builder.build_plan(ctx))

        if not plan_approved:
            if plan_need_regen:
                logger.log("WARN", f"Rigenerazione piano prima di review {plan_start_iter}")
                logger.log_context("gym-pt-macro [regen_plan]", [
                    (cfg.OUTPUT_DIR / f"review/pt/review_plan_{cfg.iteration_id}.json", "obbligatorio"),
                    ("data/output/plan.yaml",                                             "obbligatorio"),
                    ("data/athlete.md",                                                   "discrezione"),
                    (cfg.OUTPUT_DIR / f"feedback_atleta_{cfg.iteration_id}.md",          "discrezione"),
                ], ["Rate progressione corretti per eta'/infortuni/stallo"])
                self._agent_runner.run("gym-pt-macro", self._prompt_builder.build_plan_regen(ctx))

            for i in range(plan_start_iter, MAX_ITER + 1):
                logger.separator(f"FASE 3b-loop -Revisione piano ({i}/{MAX_ITER})")
                logger.log("ACTION", "gym-pt-senior-reviewer -> review_plan")
                logger.log_context("gym-pt-senior-reviewer [review_plan]", [
                    ("data/output/plan.yaml",     "incorporato"),
                    ("data/athlete.md",           "incorporato"),
                    ("data/feedback_atleta.yaml",   "incorporato"),
                ], [f"Misurazioni storiche (ultime 5) — tabella markdown",
                    "Rate progressione corretti per eta'/infortuni/stallo",
                    f"Schema JSON review: source/schemas/review_pt.schema.json"])
                self._agent_runner.run("gym-pt-senior-reviewer", self._prompt_builder.build_plan_review(ctx, i))

                approved, score, problems, _ = self._review_parser.parse(plan_review_path)
                logger.log("INFO", f"Piano: valutazione={score}/10, approvato={approved}, "
                           f"problemi_critici={len(problems)}")

                if approved:
                    logger.log("OK", f"Piano APPROVATO ({score}/10)")
                    plan_approved = True
                    break

                if i < MAX_ITER:
                    logger.log("WARN", f"Piano BOCCIATO -rigenerazione (iter {i + 1}/{MAX_ITER})")
                    self._agent_runner.run("gym-pt-macro", self._prompt_builder.build_plan_regen(ctx))

            if not plan_approved:
                logger.log("WARN", f"Piano non approvato dopo {MAX_ITER} iterazioni -procedo con ultima versione")

        # ──────────────────────────────────────────────────────────────────
        # FASE 3c -Feedback coach
        # ──────────────────────────────────────────────────────────────────
        logger.separator("FASE 3c -Generazione feedback coach")
        feedback_coach_path = cfg.OUTPUT_DIR / f"feedback_coach_{cfg.iteration_id}.md"
        if RESUME and feedback_coach_path.exists():
            logger.log("SKIP", f"feedback_coach_{cfg.iteration_id}.md gia' presente -salto generazione")
        else:
            logger.log("ACTION", f"gym-personal-trainer -> feedback_coach_{cfg.iteration_id}.md")
            logger.log_context("gym-personal-trainer [feedback_coach]", [
                ("data/feedback_atleta.yaml",   "incorporato"),
                ("data/output/plan.yaml",     "incorporato"),
            ], ["Delta mensile massimali e composizione corporea (calcolato da Python)",
                "Misurazioni storiche (ultime 3) — tabella markdown",
                "Rate progressione corretti per eta'/infortuni/stallo"])
            self._agent_runner.run("gym-personal-trainer", self._prompt_builder.build_feedback_coach(ctx))
        self._workout_history.write_efficacia(workout_history_list)
        self._workout_history.save(workout_history_list)

        # ──────────────────────────────────────────────────────────────────
        # FASE 3d -Selezione mesociclo attivo e agente micro
        # ──────────────────────────────────────────────────────────────────
        logger.separator("FASE 3d -Selezione mesociclo attivo")
        active_meso        = self._meso_selector.select_active_mesociclo()
        micro_agent        = self._meso_selector.select_micro_agent(active_meso)
        ctx["active_meso"] = active_meso

        if active_meso:
            logger.log("OK", f"Mesociclo attivo: [{active_meso.get('numero')}] {active_meso.get('nome')} "
                       f"(tipo_fase={active_meso.get('tipo_fase')}, {active_meso.get('durata_settimane')} sett)")
        else:
            logger.log("WARN", "Nessun mesociclo attivo trovato nel piano -agente fallback attivo")
        logger.log("INFO", f"Agente micro selezionato: {micro_agent}")

        # ──────────────────────────────────────────────────────────────────
        # FASE 3e+3f -Dieta + Scheda in parallelo
        # ──────────────────────────────────────────────────────────────────
        logger.separator("FASE 3e+3f -Dieta e scheda allenamento (parallelo)")
        diet_file       = cfg.OUTPUT_DIR / f"diet_{cfg.iteration_id}.yaml"
        workout_file_de = cfg.OUTPUT_DIR / f"workout_data_{cfg.iteration_id}.yaml"
        tasks = []
        if RESUME and diet_file.exists():
            logger.log("SKIP", f"diet_{cfg.iteration_id}.yaml esistente -dietologo saltato")
            self._prompt_builder.build_diet(ctx)
        else:
            logger.log_context("gym-dietologo [build_diet]", [
                ("data/athlete.md",                "incorporato"),
                ("data/feedback_atleta.yaml",      "incorporato"),
                ("data/output/plan.yaml",          "incorporato"),
                (cfg.OUTPUT_DIR / "diet_*.yaml",   "incorporato"),
                ("scripts/kcal_adjust.py",         "eseguito — output incorporato"),
            ], ["Misurazioni storiche (ultime 2) — tabella markdown",
                "Analisi adattamento calorico (fase, attendibilita', raccomandazione)"])
            tasks.append(("gym-dietologo", self._prompt_builder.build_diet(ctx)))
        if RESUME and workout_file_de.exists():
            logger.log("SKIP", f"workout_data_{cfg.iteration_id}.yaml esistente -micro agent saltato")
        else:
            meso_info = (f"mesociclo {active_meso.get('numero')} '{active_meso.get('nome')}' "
                         f"tipo_fase={active_meso.get('tipo_fase')}") if active_meso else "nessun mesociclo"
            logger.log_context(f"{micro_agent} [build_workout]", [
                ("data/athlete.md",                       "incorporato"),
                ("data/feedback_atleta.yaml",             "incorporato"),
                (cfg.OUTPUT_DIR / "feedback_coach_*.md",  "incorporato"),
                ("data/output/plan.yaml",                 "incorporato"),
                (cfg.OUTPUT_DIR / "workout_data_*.yaml",  "incorporato"),
                ("data/output/performance_analysis.yaml", "incorporato"),
            ], ["Misurazioni storiche (ultime 3) — tabella markdown",
                "Rate progressione corretti per eta'/infortuni/stallo",
                f"Mesociclo attivo iniettato nel prompt: {meso_info}"])
            tasks.append((micro_agent, self._prompt_builder.build_workout(ctx)))
        if tasks:
            logger.log("ACTION", f"Agenti da eseguire: {', '.join(t[0] for t in tasks)}")
            self._agent_runner.run_parallel(tasks, timeout=1200)
        else:
            logger.log("INFO", "Dieta e scheda gia' presenti -fase 3e+3f saltata")

        # ──────────────────────────────────────────────────────────────────
        # FASE 3g -Loop revisione scheda
        # ──────────────────────────────────────────────────────────────────
        logger.separator("FASE 3g -Revisione scheda")
        workout_file        = cfg.OUTPUT_DIR / f"workout_data_{cfg.iteration_id}.yaml"
        workout_start_iter  = 1
        workout_need_regen  = False

        if RESUME and workout_file.exists() and workout_review_path.exists():
            approved, score, problems, num_rev = self._review_parser.parse(workout_review_path)
            if approved:
                logger.log("OK", f"Scheda gia' APPROVATA (review {num_rev}, {score}/10) -3g saltata")
                workout_approved = True
            else:
                workout_start_iter = num_rev + 1
                workout_need_regen = True
                logger.log("INFO", f"Scheda esistente, review {num_rev} BOCCIATA -riprendo da iter {workout_start_iter}")
        elif RESUME and workout_file.exists():
            logger.log("INFO", f"workout_data_{cfg.iteration_id}.yaml esistente, nessuna review -inizio revisione")
        else:
            logger.log("WARN", f"workout_data_{cfg.iteration_id}.yaml non trovato -deve essere generato prima")

        if not workout_approved:
            if workout_need_regen:
                logger.log("WARN", f"Rigenerazione scheda prima di review {workout_start_iter}")
                logger.log_context(f"{micro_agent} [regen_workout]", [
                    (cfg.OUTPUT_DIR / f"review/pt/review_workout_{cfg.iteration_id}.json", "obbligatorio"),
                    (cfg.OUTPUT_DIR / f"workout_data_{cfg.iteration_id}.yaml",             "obbligatorio"),
                    ("data/athlete.md",                                                    "discrezione"),
                    (cfg.OUTPUT_DIR / f"feedback_atleta_{cfg.iteration_id}.md",            "discrezione"),
                    ("data/output/plan.yaml",                                              "discrezione"),
                    ("data/output/measurements.json",                                      "discrezione"),
                ], ["Rate progressione corretti per eta'/infortuni/stallo"])
                self._agent_runner.run(micro_agent, self._prompt_builder.build_workout_regen(ctx))

            for i in range(workout_start_iter, MAX_ITER + 1):
                logger.separator(f"FASE 3g-loop -Revisione scheda ({i}/{MAX_ITER})")
                logger.log("ACTION", "gym-pt-senior-reviewer -> review_workout")
                logger.log_context("gym-pt-senior-reviewer [review_workout]", [
                    (cfg.OUTPUT_DIR / f"workout_data_{cfg.iteration_id}.yaml", "incorporato"),
                    ("data/output/plan.yaml",                                  "incorporato"),
                    ("data/athlete.md",                                        "incorporato"),
                    ("data/feedback_atleta.yaml",                              "incorporato"),
                    ("data/output/performance_analysis.yaml",                  "incorporato"),
                ], ["Misurazioni storiche (ultime 3) — tabella markdown",
                    "Rate progressione corretti per eta'/infortuni/stallo",
                    "Schema JSON review: source/schemas/review_pt.schema.json"])
                self._agent_runner.run("gym-pt-senior-reviewer", self._prompt_builder.build_workout_review(ctx, i))

                approved, score, problems, _ = self._review_parser.parse(workout_review_path)
                logger.log("INFO", f"Scheda: valutazione={score}/10, approvata={approved}, "
                           f"problemi_critici={len(problems)}")

                if approved:
                    logger.log("OK", f"Scheda APPROVATA ({score}/10)")
                    workout_approved = True
                    break

                if i < MAX_ITER:
                    logger.log("WARN", f"Scheda BOCCIATA -rigenerazione (iter {i + 1}/{MAX_ITER})")
                    self._agent_runner.run(micro_agent, self._prompt_builder.build_workout_regen(ctx))

        if not workout_approved:
            logger.log("WARN", f"Scheda non approvata dopo {MAX_ITER} iterazioni -procedo con ultima versione")

        # ──────────────────────────────────────────────────────────────────
        # FASE 4 -Archiviazione
        # ──────────────────────────────────────────────────────────────────
        if RESUME and (cfg.OUTPUT_DIR / f"feedback_atleta_{cfg.iteration_id}.yaml").exists():
            logger.separator("FASE 4 -SALTATA (gia' completata)")
            logger.log("INFO", f"feedback_atleta_{cfg.iteration_id}.yaml trovato -fase 4 gia' eseguita")
        else:
            logger.separator("FASE 4 -Archiviazione")

            self._archiver.archive_feedback()
            self._archiver.archive_old_output_files()

            m_today = cfg.TODAY.month
            y_today = cfg.TODAY.year
            if m_today == 12:
                next_m, next_y = 1, y_today + 1
            else:
                next_m, next_y = m_today + 1, y_today
            months_it = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
                         "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
            next_label = f"{months_it[next_m - 1]} {next_y}"
            self._archiver.create_empty_feedback(next_label)

        # ──────────────────────────────────────────────────────────────────
        # Sommario finale
        # ──────────────────────────────────────────────────────────────────
        logger.separator("SOMMARIO FINALE")
        print(f"MODALITA'    : {'RESUME' if RESUME else 'NEW'}")
        print(f"DATA         : {cfg.DATE_STR}")
        print(f"ITERATION_ID : {cfg.iteration_id}")
        print(f"PIANO        : {'APPROVATO' if plan_approved else 'NON APPROVATO (ultima versione)'}")
        print(f"SCHEDA       : {'APPROVATA' if workout_approved else 'NON APPROVATA (ultima versione)'}")
        print()
        print("FILE OUTPUT (data/output/):")
        for name in [
            "measurements.json",
            "workout_history.json",
            "performance_analysis.yaml",
            "plan.yaml",
            f"feedback_coach_{cfg.iteration_id}.md",
            f"diet_{cfg.iteration_id}.yaml",
            f"workout_data_{cfg.iteration_id}.yaml",
            f"feedback_atleta_{cfg.iteration_id}.yaml",
        ]:
            status = "OK" if (cfg.OUTPUT_DIR / name).exists() else "MANCANTE"
            print(f"  [{status}] {name}")

        print()
        print("REVIEW:")
        print(f"  {cfg.REVIEW_PT_DIR / f'review_plan_{cfg.iteration_id}.json'}")
        print(f"  {cfg.REVIEW_PT_DIR / f'review_workout_{cfg.iteration_id}.json'}")

        if not (plan_approved and workout_approved):
            sys.exit(1)
