import re
import subprocess
import sys
from datetime import datetime
from typing import Optional

from source.GlobalConstant import GlobalConstant
from source.Config import Config
from source.BodyCalc import BodyCalc


class PromptBuilder:
    def __init__(self, config: Config, body_calc: BodyCalc):
        self._config    = config
        self._body_calc = body_calc

    def _rates_text(self, rates: dict) -> str:
        lines = ["RATE DI PROGRESSIONE STORICA (kg/anno, corretti):"]
        for lift, d in rates.items():
            flags = []
            if d["fattori"]["infortunio"]:  flags.append("infortunio -30%")
            if d["fattori"]["eta_over_35"]: flags.append("eta' -10%")
            if d["fattori"]["stallo"]:      flags.append("stallo -50%")
            flags_str = f"  [{', '.join(flags)}]" if flags else ""
            lines.append(
                f"  - {lift.capitalize()}: storico {d['media']} kg/anno "
                f"-> corretta {d['media_corretta']} kg/anno "
                f"(range {d['min']}..{d['max']}){flags_str}"
            )
        return "\n".join(lines)

    def _last_n_measurements(self, measurements: list, n: int = 5) -> str:
        rows = measurements[-n:] if len(measurements) > n else measurements
        if not rows:
            return "(nessuna misurazione)"

        cols = [
            ("data",            "data"),
            ("peso_kg",         "peso"),
            ("body_fat_pct",    "bf%"),
            ("massa_magra_kg",  "massa_magra"),
            ("ffmi_adj",        "ffmi"),
            ("bmr_kcal",        "bmr"),
            ("tdee_kcal",       "tdee"),
            ("squat_1rm",       "squat"),
            ("panca_1rm",       "panca"),
            ("stacco_1rm",      "stacco"),
            ("massimali_tipo",  "tipo"),
            ("efficacia_workout", "efficacia"),
            ("note",            "note"),
        ]

        def fmt(v):
            if v is None:
                return "-"
            if isinstance(v, float):
                return f"{v:.1f}"
            return str(v)

        header = "| " + " | ".join(label for _, label in cols) + " |"
        sep    = "| " + " | ".join("---" for _ in cols) + " |"
        lines  = [header, sep]
        for row in rows:
            lines.append("| " + " | ".join(fmt(row.get(key)) for key, _ in cols) + " |")
        return "\n".join(lines)

    def _latest_file(self, pattern: str) -> str:
        files = sorted(self._config.OUTPUT_DIR.glob(pattern), reverse=True)
        if not files:
            return ""
        return files[0].read_text(encoding="utf-8") if files[0].exists() else ""

    def _schema_pt(self) -> str:
        """Ritorna lo schema JSON del review PT da includere nei prompt."""
        schema_path = self._config.PROJECT_ROOT / "source" / "schemas" / "review_pt.schema.json"
        if schema_path.exists() and schema_path.is_file():
            return schema_path.read_text(encoding="utf-8")
        return "(schema non trovato)"

    def _performance_analysis_text(self) -> str:
        """Legge il report dell'analista performance se disponibile."""
        path = self._config.OUTPUT_DIR / "performance_analysis.yaml"
        if path.exists() and path.is_file():
            text = path.read_text(encoding="utf-8")
        else:
            text = ""
        if text:
            return f"## Analisi performance empirica (gym-performance-analyst)\n```yaml\n{text}\n```"
        return "## Analisi performance empirica\n(non disponibile - prima iterazione o analisi saltata)"

    def _calc_nutrition_context(self, measurements: list, feedback_data: dict, plan_text: str) -> str:
        """
        Calcola il contesto nutrizionale da passare al piano:
        - Delta peso e BF% rispetto alla misurazione precedente (con durata in giorni)
        - kcal_media_stimata dal feedback atleta
        - kcal target della dieta precedente (lette dal plan.yaml corrente)
        - Segnali di allarme (es. BF sale troppo in bulk, peso cala in mantenimento)
        Ritorna una stringa markdown pronta per essere inclusa nel prompt.
        """
        lines = ["## Analisi aderenza calorica e composizione corporea"]

        if len(measurements) >= 2:
            prev = measurements[-2]
            curr = measurements[-1]

            peso_prev = prev.get("peso_kg")
            peso_curr = curr.get("peso_kg")
            bf_prev   = prev.get("body_fat_pct")
            bf_curr   = curr.get("body_fat_pct")
            mm_prev   = prev.get("massa_magra_kg")
            mm_curr   = curr.get("massa_magra_kg")
            d_prev    = prev.get("data")
            d_curr    = curr.get("data")

            days = None
            if d_prev and d_curr:
                try:
                    days = (datetime.strptime(d_curr, "%Y-%m-%d") - datetime.strptime(d_prev, "%Y-%m-%d")).days
                except ValueError:
                    pass

            periodo_str = f" in {days} giorni" if days else ""

            if peso_prev is not None and peso_curr is not None:
                delta_peso = round(peso_curr - peso_prev, 1)
                sign = "+" if delta_peso >= 0 else ""
                lines.append(f"- Peso: {peso_prev} → {peso_curr} kg ({sign}{delta_peso} kg{periodo_str})")

            if bf_prev is not None and bf_curr is not None:
                delta_bf = round(bf_curr - bf_prev, 1)
                sign = "+" if delta_bf >= 0 else ""
                lines.append(f"- Body Fat %: {bf_prev}% → {bf_curr}% ({sign}{delta_bf}%{periodo_str})")
                if days and days > 0:
                    bf_rate_week = delta_bf / days * 7
                    if bf_rate_week > 0.5:
                        lines.append(f"  ⚠ BF sta salendo a ~{bf_rate_week:.1f}%/settimana — eccessivo anche in bulk (max accettabile: ~0.3-0.5%/sett)")
                    elif bf_rate_week < -0.7:
                        lines.append(f"  ⚠ BF sta scendendo a ~{abs(bf_rate_week):.1f}%/settimana — rischio catabolismo muscolare se in cut aggressivo")

            if mm_prev is not None and mm_curr is not None:
                delta_mm = round(mm_curr - mm_prev, 1)
                sign = "+" if delta_mm >= 0 else ""
                lines.append(f"- Massa magra: {mm_prev} → {mm_curr} kg ({sign}{delta_mm} kg{periodo_str})")
        else:
            lines.append("- (storico insufficiente per calcolare delta composizione corporea)")

        dieta_feedback = (feedback_data or {}).get("dieta", {}) or {}
        kcal_media     = dieta_feedback.get("kcal_media_stimata")
        kcal_media_val = None
        if kcal_media and str(kcal_media).strip() not in ("", "null", "None"):
            try:
                kcal_media_val = float(kcal_media)
                lines.append(f"- kcal effettive medie dichiarate dall'atleta: {int(kcal_media_val)} kcal/giorno")
            except (ValueError, TypeError):
                pass
        else:
            lines.append("- kcal effettive medie: non dichiarate dall'atleta")

        kcal_all_match = re.search(r"kcal_allenamento:\s*(\d+)", plan_text or "")
        kcal_rip_match = re.search(r"kcal_riposo:\s*(\d+)", plan_text or "")
        if kcal_all_match or kcal_rip_match:
            targets = []
            if kcal_all_match:
                targets.append(f"allenamento={kcal_all_match.group(1)} kcal")
            if kcal_rip_match:
                targets.append(f"riposo={kcal_rip_match.group(1)} kcal")
            lines.append(f"- kcal target piano precedente: {', '.join(targets)}")

            if kcal_media_val and kcal_all_match:
                target_all = float(kcal_all_match.group(1))
                scarto = int(kcal_media_val - target_all)
                sign = "+" if scarto >= 0 else ""
                lines.append(f"- Scarto kcal effettive vs target allenamento: {sign}{scarto} kcal/giorno")
                if abs(scarto) > 200:
                    lines.append(f"  ⚠ Scarto significativo: adegua il target calorico nel nuovo piano")

        lines.append("")
        lines.append("### Istruzioni per la correzione calorica nel nuovo piano")
        lines.append("Basandoti sui dati sopra, correggi `kcal_allenamento` e `kcal_riposo` nel piano secondo queste regole:")
        lines.append("- **Bulk**: peso deve salire ~0.2-0.4 kg/sett, BF non deve salire >0.3-0.5%/sett.")
        lines.append("  - Se peso non sale → aumenta kcal di 150-200")
        lines.append("  - Se BF sale troppo velocemente → riduci kcal di 100-150 o sposta carbo nei giorni allenamento")
        lines.append("- **Mantenimento**: peso deve restare stabile (±0.5 kg/mese), BF stabile.")
        lines.append("  - Se peso scende → aumenta kcal di 100-200")
        lines.append("  - Se peso sale con BF in aumento → riduci kcal di 100-150")
        lines.append("- **Cut**: peso deve scendere ~0.3-0.5 kg/sett, massa magra deve restare stabile o calare minimamente.")
        lines.append("  - Se peso non scende → riduci kcal di 150-200")
        lines.append("  - Se massa magra scende troppo → aumenta proteine, riduci deficit")
        lines.append("- Se l'atleta non riesce a mangiare le kcal target (scarto > 200 kcal): considera di semplificare i pasti o ridurre il target temporaneamente")

        return "\n".join(lines)

    def _calc_efficacia_context(self, measurements: list, feedback_text: str) -> str:
        """
        Calcola i delta tra la nuova entry (oggi, risultati del mese) e quella precedente (inizio mese).
        La nuova entry e' measurements[-1], quella da valutare (penultima) e' measurements[-2].
        """
        if len(measurements) < 2:
            return "(storico insufficiente per calcolare delta)"

        prev = measurements[-2]
        curr = measurements[-1]

        lines = ["DELTA RISPETTO AL MESE SCORSO (misura attuale - misura precedente):"]

        for label, key in [("Squat 1RM", "squat_1rm"), ("Panca 1RM", "panca_1rm"), ("Stacco 1RM", "stacco_1rm")]:
            c, p = curr.get(key), prev.get(key)
            if c is not None and p is not None:
                delta = round(c - p, 1)
                sign = "+" if delta >= 0 else ""
                lines.append(f"  - {label}: {p} -> {c} kg ({sign}{delta})")
            else:
                lines.append(f"  - {label}: dato mancante")

        for label, key in [("Peso", "peso_kg"), ("Body Fat %", "body_fat_pct"), ("Massa magra", "massa_magra_kg")]:
            c, p = curr.get(key), prev.get(key)
            if c is not None and p is not None:
                delta = round(c - p, 1)
                sign = "+" if delta >= 0 else ""
                lines.append(f"  - {label}: {p} -> {c} ({sign}{delta})")

        patterns = [
            ("Aderenza scheda",   r"Hai seguito la scheda\?[^\n]*:\s*([^\n]+)"),
            ("Energia generale",  r"Energia generale[^\n]*:\s*([^\n]+)"),
            ("Qualita' sonno",    r"Qualita'?\s+del\s+sonno[^\n]*:\s*([^\n]+)"),
            ("Stress",            r"Stress[^\n]*:\s*([^\n]+)"),
        ]
        for label, pattern in patterns:
            m = re.search(pattern, feedback_text, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if val and val not in ("(1-10)", "(basso / medio / alto)", "(si' / parzialmente / no)"):
                    lines.append(f"  - {label}: {val}")

        return "\n".join(lines)

    def _extract_fase_from_plan(self) -> str:
        """Estrae fase_corrente (cut/bulk/mantenimento) da strategia_nutrizionale nel plan.yaml."""
        plan_path = self._config.OUTPUT_DIR / "plan.yaml"
        if not plan_path.exists():
            return "mantenimento"
        if not GlobalConstant.YAML_OK:
            return "mantenimento"
        try:
            data = GlobalConstant.yaml_module.safe_load(plan_path.read_text(encoding="utf-8")) or {}
            fase = (data.get("strategia_nutrizionale", {}) or {}).get("fase_corrente", "")
            if fase and str(fase).lower() in ("cut", "bulk", "mantenimento"):
                return str(fase).lower()
            print("[WARN  ] plan.yaml: fase_corrente mancante o non valida, uso 'mantenimento'", flush=True)
            return "mantenimento"
        except Exception:
            return "mantenimento"

    def run_kcal_adjust(self, ctx: dict) -> str:
        """
        Esegue scripts/kcal_adjust.py e ritorna l'output testuale.
        Ricava fase e kcal_attuali dal piano e dal contesto.
        In caso di errore ritorna una stringa vuota.
        """
        cfg  = self._config
        fase = self._extract_fase_from_plan()

        kcal_attuali = None
        plan_path = cfg.OUTPUT_DIR / "plan.yaml"
        if plan_path.exists() and GlobalConstant.YAML_OK:
            try:
                data = GlobalConstant.yaml_module.safe_load(plan_path.read_text(encoding="utf-8")) or {}
                sn   = data.get("strategia_nutrizionale", {}) or {}
                kal  = sn.get("kcal_allenamento")
                krip = sn.get("kcal_riposo")
                if kal and krip:
                    kcal_attuali = int((int(kal) + int(krip)) / 2)
            except Exception:
                pass
        if kcal_attuali is None and ctx.get("measurements"):
            tdee = ctx["measurements"][-1].get("tdee_kcal")
            if tdee:
                kcal_attuali = int(tdee)
        if kcal_attuali is None:
            print("[WARN  ] kcal_adjust: impossibile determinare kcal_attuali, skip", flush=True)
            return ""

        script   = cfg.SCRIPTS_DIR / "kcal_adjust.py"
        cmd      = [sys.executable, str(script), "--fase", fase, "--kcal-attuali", str(kcal_attuali)]
        kcal_extra = ctx.get("kcal_extra", {})
        if kcal_extra.get("kcal_extra_settimana", 0) > 0:
            cmd += ["--kcal-extra-settimana", str(kcal_extra["kcal_extra_settimana"])]
        print(f"[ACTION] kcal_adjust: fase={fase}, kcal_attuali={kcal_attuali}, "
              f"kcal_extra_sett={kcal_extra.get('kcal_extra_settimana', 0)}", flush=True)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                cwd=cfg.PROJECT_ROOT, timeout=30,
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                print(f"[WARN  ] kcal_adjust rc={result.returncode}: {result.stderr[:200]}", flush=True)
            return output
        except Exception as e:
            print(f"[WARN  ] kcal_adjust errore: {e}", flush=True)
            return ""

    def _format_meso_context(self, meso: Optional[dict]) -> str:
        """Formatta il mesociclo attivo come sezione markdown da iniettare nel prompt."""
        if not meso:
            return "## Mesociclo attivo\n(non determinato — segui il piano generale)"
        lines = ["## Mesociclo attivo (da rispettare OBBLIGATORIAMENTE)"]
        for k, v in meso.items():
            lines.append(f"- **{k}**: {v}")
        return "\n".join(lines)

    def build_plan(self, ctx: dict) -> str:
        nutrition_ctx = self._calc_nutrition_context(
            ctx["measurements"], ctx["feedback_data"], ctx["plan_text"] or ""
        )
        return f"""Sei il personal trainer certificato del progetto fitness.
Genera il piano a lungo termine `data/output/plan.yaml` con la struttura standard.

## Profilo atleta
{ctx['athlete_text']}

## Feedback atleta corrente (PUNTO DI PARTENZA)
{ctx['feedback_text']}

## Piano precedente (se esiste)
{ctx['plan_text'] if ctx['plan_text'] else '(nessun piano precedente)'}

## Misurazioni storiche -ultime 5
```json
{self._last_n_measurements(ctx['measurements'], 5)}
```

## {self._rates_text(ctx['rates'])}

## Altre attivita' (oltre all'allenamento in palestra)
{self._body_calc.format_attivita_extra(ctx.get('kcal_extra', {}))}

{nutrition_ctx}

{self._performance_analysis_text()}

## Schema YAML obbligatorio

```yaml
meta:
  data_aggiornamento: "YYYY-MM-DD"
  atleta: "Daniele"
situazione:
  infortunio: "..."    # o 'nessuno'
  note: "..."
massimali_attuali:
  squat: 0.0           # float kg
  panca: 0.0
  stacco: 0.0
target:                # 4 voci: 3 mesi, 6 mesi, 12 mesi, Lungo termine
  - orizzonte: "3 mesi"
    data: "YYYY-MM"
    squat: 0.0
    panca: 0.0
    stacco: 0.0
    note: "..."
macrocicli:
  - numero: 1
    nome: "..."
    data_inizio: "YYYY-MM"
    data_fine: "YYYY-MM"
    durata_settimane: 52    # somma mesocicli DEVE corrispondere
    obiettivo: "..."
    note: "..."
    mesocicli:
      - numero: 1
        nome: "..."
        tipo: "Forza"       # Recupero | Forza | Ipertrofia | Volume | Intensita'
        fase_nutrizionale: "mantenimento"   # cut | bulk | mantenimento
        data_inizio: "YYYY-MM"
        durata_settimane: 8
        obiettivo: "..."
        metodologia: "..."
        note: "..."
        incrocio_stimolo_ambiente: "..."
macrocicli_futuri:          # solo se orizzonte > primo macrociclo
  - numero: 2
    orizzonte: "Anno 2 (YYYY-YYYY)"
    obiettivo_indicativo: "..."
    note: "..."
strategia_nutrizionale:
  fase_corrente: "mantenimento"   # OBBLIGATORIO: cut | bulk | mantenimento
  sessioni_allenamento_settimana: 4
  note: "..."
rischi:
  - area: "..."
    livello: "alto"         # alto | medio | basso
    azione: "..."
proiezione_obiettivi:
  timeframe_desiderato: "..."
  stima_raggiungimento_anni:
    min: 3.0
    max: 5.0
  fattibilita: "FATTIBILE"  # FATTIBILE | OTTIMISTICO | IRREALISTICO
  motivazione: "..."
```

## Istruzioni
- La somma di `durata_settimane` dei mesocicli DEVE corrispondere a quella del macrociclo
- Target a 3/6/12 mesi: usa i rate corretti sopra, mai proiettare di piu'
- `incrocio_stimolo_ambiente`: spiega la razionale abbinamento tipo-allenamento x fase-nutrizionale
- `strategia_nutrizionale`: NON definire kcal, macro o trigger — competenza del dietologo
- Infortuni e richieste atleta hanno precedenza assoluta
- Considera metodologie efficaci dal report performance (se disponibile)
- Scrivi SOLO il file plan.yaml, nessun testo aggiuntivo"""

    def build_plan_review(self, ctx: dict, numero_review: int = 1) -> str:
        cfg       = self._config
        plan_path = cfg.OUTPUT_DIR / "plan.yaml"
        plan_text = plan_path.read_text(encoding="utf-8") if plan_path.exists() else ""
        return f"""Sei il personal trainer senior (revisore).
Valuta il piano a lungo termine in `data/output/plan.yaml`.
Questo e' il tentativo di revisione numero {numero_review} — scrivi `"numero_review": {numero_review}` nel campo meta del JSON.

## Piano da revisionare
```yaml
{plan_text}
```

## Profilo atleta
{ctx['athlete_text']}

## Feedback corrente
{ctx['feedback_text']}

## {self._rates_text(ctx['rates'])}

## Misurazioni storiche -ultime 5
```json
{self._last_n_measurements(ctx['measurements'], 5)}
```

## Istruzioni
Scrivi il report in `data/output/review/pt/review_plan_{cfg.iteration_id}.json` come JSON valido.

Schema richiesto:
```json
{self._schema_pt()}
```

Regole:
- Valutazione >= 8 e problemi_critici vuoto -> esito APPROVATA, altrimenti BOCCIATA
- Correggi direttamente in plan.yaml gli errori di calcolo numerici (poi mettili in correzioni_applicate)
- Nessun testo fuori dal file JSON"""

    def build_plan_regen(self, ctx: dict) -> str:
        cfg = self._config
        return f"""Sei il personal trainer senior specializzato in pianificazione macroperiodica. Il piano e' stato bocciato.
Leggi `data/output/review/pt/review_plan_{cfg.iteration_id}.json` e correggi `data/output/plan.yaml`
applicando TUTTI i problemi_critici e i suggerimenti indicati.

## {self._rates_text(ctx['rates'])}

## Dati disponibili per la rigenerazione
- Profilo: data/athlete.md
- Feedback archiviato: data/output/feedback_atleta_{cfg.iteration_id}.yaml
- Misurazioni: data/output/measurements.json

Leggi autonomamente la review e genera la versione corretta di plan.yaml."""

    def build_feedback_coach(self, ctx: dict) -> str:
        cfg           = self._config
        efficacia_ctx = self._calc_efficacia_context(ctx["measurements"], ctx["feedback_text"])
        plan_path     = cfg.OUTPUT_DIR / "plan.yaml"
        plan_text     = plan_path.read_text(encoding="utf-8") if plan_path.exists() else ""

        return f"""Sei il coach del progetto fitness.
Genera il file `data/output/feedback_coach_{cfg.iteration_id}.md`.

Il documento deve contenere le seguenti sezioni nell'ordine:

## Valutazione scheda precedente

La scheda del mese scorso ha prodotto questi risultati oggettivi:

{efficacia_ctx}

Analizza i risultati e assegna un voto `efficacia_workout` (intero 1-10) usando questa scala:
- 9-10: progressione eccellente su tutti i lift, composizione migliorata, aderenza alta, energia/sonno buoni
- 7-8:  progressione buona su almeno 2 lift, situazione stabile, stato soggettivo nella norma
- 5-6:  progressione minima o solo su 1 lift, aderenza parziale o stress/sonno negativi
- 3-4:  regressione o stallo, problemi di aderenza, energia bassa o stress alto
- 1-2:  regressione significativa, infortuni, aderenza molto bassa

Fattori contestuali:
- Infortunio in corso: non penalizzare i lift coinvolti, valuta solo quelli non interessati
- Stress alto o sonno scarso: attenua il giudizio (recupero compromesso indipendentemente dalla scheda)
- Aderenza parziale o assente: i risultati non riflettono la scheda, segnalalo

**IMPORTANTE**: il documento deve contenere esattamente questa riga (con il valore scelto):
`EFFICACIA_WORKOUT: <valore>`

Esempio: `EFFICACIA_WORKOUT: 7`

## Progressi del mese
Commento ai delta numerici sopra, punti di forza e aree di miglioramento.

## Risposta a infortuni e richieste
Rispondi a quanto segnalato dall'atleta nella sezione "Altro" del feedback.

## Indicazioni per il mese successivo
Consigli pratici su allenamento, recupero e nutrizione.

---

## Feedback atleta (input del mese)
{ctx['feedback_text']}

## Piano approvato (fase attuale)
{plan_text}

## {self._rates_text(ctx['rates'])}

## Ultime 3 misurazioni
```json
{self._last_n_measurements(ctx['measurements'], 3)}
```

Formato Markdown, tono professionale ma diretto."""

    def build_diet(self, ctx: dict) -> str:
        cfg              = self._config
        last_diet        = self._latest_file("diet_*.yaml")
        kcal_adjust_out  = self.run_kcal_adjust(ctx)
        plan_path        = cfg.OUTPUT_DIR / "plan.yaml"
        plan_text        = plan_path.read_text(encoding="utf-8") if plan_path.exists() else ""

        if kcal_adjust_out:
            kcal_adjust_section = f"""## Analisi adattamento calorico (script automatico)
L'analisi seguente e' calcolata da Python in base a misurazioni, aderenza dieta e fase.
Usala come punto di partenza: puoi modificare i valori se hai motivazioni cliniche o nutrizionali,
ma devi **spiegare esplicitamente** nel campo `note_strategia` perche' ti discosti dal suggerimento.

```
{kcal_adjust_out}
```
"""
        else:
            kcal_adjust_section = "## Analisi adattamento calorico\n(non disponibile — calcola autonomamente dal TDEE)\n"

        return f"""Sei il dietologo del progetto fitness.
Genera la dieta settimanale `data/output/diet_{cfg.iteration_id}.yaml`.

## Profilo atleta
{ctx['athlete_text']}

## Feedback atleta (aderenza dieta, difficolta')
{ctx['feedback_text']}

## Piano approvato (fase corrente e contesto sportivo)
{plan_text}

## Altre attivita' (oltre all'allenamento in palestra)
{self._body_calc.format_attivita_extra(ctx.get('kcal_extra', {}))}

## TDEE attuale
TDEE ultima misurazione: {ctx['measurements'][-1].get('tdee_kcal', 'N/D')} kcal/die (BMR {ctx['measurements'][-1].get('bmr_kcal', 'N/D')} kcal x 1.55).

## Ultime 2 misurazioni (BMR/TDEE)
```json
{self._last_n_measurements(ctx['measurements'], 2)}
```

{kcal_adjust_section}
## Dieta precedente (riferimento)
{last_diet if last_diet else '(nessuna dieta precedente)'}

## Istruzioni
- **Parti dall'analisi adattamento calorico** per determinare kcal_allenamento e kcal_riposo
- Puoi modificare i valori suggeriti se hai motivazioni nutrizionali fondate, ma devi **motivare esplicitamente** in `note_strategia`
- Differenzia le kcal per tipologia di giorno: allenamento pesi, corsa/cardio, riposo (e altri se presenti nel piano)
- Per ogni tipologia di giorno spiega in `note_strategia` perche' hai scelto quel fabbisogno calorico
- Rispetta preferenze e difficolta' riportate nel feedback
- Struttura: meta, giorni, integratori
- **Usa il tool Write per salvare il file** `data/output/diet_{cfg.iteration_id}.yaml` sul disco. Non stampare il contenuto su stdout."""

    def build_workout(self, ctx: dict) -> str:
        cfg           = self._config
        workout_files = sorted(cfg.OUTPUT_DIR.glob("workout_data_*.yaml"), reverse=True)[:2]
        workouts_text = "\n\n".join(
            f"### {f.name}\n{f.read_text(encoding='utf-8')}" for f in workout_files
        ) or "(nessuna scheda precedente)"

        last_coach = self._latest_file("feedback_coach_*.md")
        meso       = ctx.get("active_meso")
        meso_ctx   = self._format_meso_context(meso)

        return f"""Genera la scheda `data/output/workout_data_{cfg.iteration_id}.yaml` per il mesociclo indicato sotto.

{meso_ctx}

## Profilo atleta
{ctx['athlete_text']}

## Feedback atleta corrente (PUNTO DI PARTENZA -infortuni hanno precedenza assoluta)
{ctx['feedback_text']}

## Feedback coach del mese
{last_coach if last_coach else '(nessuno)'}

## Piano annuale completo
{(cfg.OUTPUT_DIR / 'plan.yaml').read_text(encoding='utf-8') if (cfg.OUTPUT_DIR / 'plan.yaml').exists() else ''}

## {self._rates_text(ctx['rates'])}

## Altre attivita' (oltre all'allenamento in palestra)
{self._body_calc.format_attivita_extra(ctx.get('kcal_extra', {}))}

## Ultime 3 misurazioni (massimali reali)
```json
{self._last_n_measurements(ctx['measurements'], 3)}
```

## Schede precedenti
{workouts_text}

{self._performance_analysis_text()}

## Istruzioni
- RISPETTA il mesociclo attivo indicato sopra: tipo, metodologia, durata e obiettivo sono vincolanti
- Infortuni -> escludi TUTTI gli esercizi che coinvolgono le aree interessate
- Aggiorna EXERCISE_MUSCLES in scripts/volume_calc.py per ogni nuovo esercizio
- Carichi basati sui massimali reali in measurements.json
- Privilegia le metodologie empiricamente efficaci dal report performance (se disponibile)
- ITERATION_ID per il nome del file: {cfg.iteration_id}"""

    def build_workout_review(self, ctx: dict, numero_review: int = 1) -> str:
        cfg          = self._config
        workout_path = cfg.OUTPUT_DIR / f"workout_data_{cfg.iteration_id}.yaml"
        workout_text = workout_path.read_text(encoding="utf-8") if workout_path.exists() else ""
        plan_path    = cfg.OUTPUT_DIR / "plan.yaml"
        plan_text    = plan_path.read_text(encoding="utf-8") if plan_path.exists() else ""

        return f"""Sei il personal trainer senior (revisore).
Valuta la scheda di allenamento in `data/output/workout_data_{cfg.iteration_id}.yaml`.
Questo e' il tentativo di revisione numero {numero_review} — scrivi `"numero_review": {numero_review}` nel campo meta del JSON.

## Scheda da revisionare
```yaml
{workout_text}
```

## Piano annuale approvato
{plan_text}

## Profilo e feedback atleta
{ctx['athlete_text']}
{ctx['feedback_text']}

## {self._rates_text(ctx['rates'])}

## Ultime 3 misurazioni
```json
{self._last_n_measurements(ctx['measurements'], 3)}
```

{self._performance_analysis_text()}

## Istruzioni
Scrivi il report in `data/output/review/pt/review_workout_{cfg.iteration_id}.json` come JSON valido.

Schema richiesto:
```json
{self._schema_pt()}
```

Regole:
- Valutazione >= 8 e problemi_critici vuoto -> esito APPROVATA, altrimenti BOCCIATA
- Correggi direttamente nella scheda gli errori di calcolo numerici (poi mettili in correzioni_applicate)
- Verifica che la scheda privilegia le metodologie con efficacia storica alta (dal report performance)
- Nessun testo fuori dal file JSON"""

    def build_workout_regen(self, ctx: dict) -> str:
        cfg      = self._config
        meso_ctx = self._format_meso_context(ctx.get("active_meso"))
        return f"""La scheda e' stata bocciata.
Leggi `data/output/review/pt/review_workout_{cfg.iteration_id}.json` e correggi `data/output/workout_data_{cfg.iteration_id}.yaml`
applicando TUTTI i problemi_critici e i suggerimenti indicati.

{meso_ctx}

## {self._rates_text(ctx['rates'])}

## Dati disponibili
- Profilo: data/athlete.md
- Feedback archiviato: data/output/feedback_atleta_{cfg.iteration_id}.yaml
- Piano: data/output/plan.yaml
- Misurazioni: data/output/measurements.json

Leggi autonomamente la review. Rispetta il mesociclo attivo indicato sopra."""
