Genera o aggiorna il sito web statico a partire dai dati di output gia' presenti, con loop di revisione automatico (max 3 iterazioni).

## Loop di generazione e revisione

Il flusso e' un ciclo: il web-developer genera/aggiorna il sito, poi web-tester e ux-reviewer lo analizzano in parallelo. Se trovano problemi, il web-developer corregge e si ripete. **Massimo 3 iterazioni.**

```
web-developer genera/aggiorna
         │
         ▼
┌─► web-tester + ux-reviewer (in parallelo)
│        │
│        ├── Nessun problema bloccante → COMPLETATO ✓
│        │
│        └── Problemi bloccanti trovati
│                  │
│                  ▼
│        web-developer legge i report e corregge
│                  │
│        (max 3 iterazioni)
└──────────────────┘
```

---

## Iterazione 1 (e successive)

### Step A: Lancia gym-web-developer

**Prima iterazione** — passagli queste istruzioni:

Il sito e' composto da HTML shell (`docs/*.html`) e dati JSON (`docs/data/*.json`).
1. Controlla se `docs/dashboard.html` esiste
2. Se NON esiste: esegui `python scripts/generate_site.py --outdir docs`
3. Se GIA' ESISTE: esegui solo `python scripts/generate_data.py --outdir docs/data`
4. Verifica che gli script terminino senza errori
5. In caso di errori negli script: analizza e correggi prima di procedere

**Iterazioni successive (rigenerazione)** — passagli queste istruzioni:

Leggi i report di review generati in questa iterazione:
- `data/output/review/web-site/review_web_(data).yaml` — problemi tecnici del web-tester
- `data/output/review/web-site/review_ux_(data).md` — problemi UX dell'ux-reviewer

Applica tutte le correzioni necessarie:
- Per errori tecnici (JSON mancanti, script che falliscono): correggi gli script in `scripts/` e riesegui `python scripts/generate_data.py --outdir docs/data`
- Per problemi UX Alta priorita': modifica `scripts/generate_site.py` (CSS, struttura HTML, JS di rendering) e rigenera con `python scripts/generate_site.py --force --outdir docs`
- Per esercizi non mappati (warning volume): aggiorna `EXERCISE_MUSCLES` in `scripts/volume_calc.py` e riesegui `generate_data.py`

Dopo le correzioni, conferma cosa hai modificato.

### Step B: Lancia gym-web-tester e gym-ux-reviewer (in parallelo)

Lancia i due agenti **contemporaneamente** (sono indipendenti):

- **gym-web-tester**: verifica correttezza tecnica, scrive `data/output/review/web-site/review_web_(data).yaml`
- **gym-ux-reviewer**: analisi UX, scrive `data/output/review/web-site/review_ux_(data).md`

### Step C: Valuta i risultati

Leggi i sommari restituiti dai due agenti e applica questa logica:

**Esci dal loop (COMPLETATO)** se:
- web-tester esito `OK` o `WARNING` (nessun ERROR critico)
- ux-reviewer ha 0 problemi di priorita' Alta

**Continua il loop (RIGENERAZIONE)** se:
- web-tester esito `ERROR` (file mancanti, JSON non validi)
- ux-reviewer ha 1+ problemi di priorita' Alta

**Dopo 3 iterazioni senza completamento**: accetta lo stato attuale e segnala all'utente i problemi residui dai report.

---

## Sommario finale all'utente

Al termine del loop, riporta:

```
ITERAZIONI: N/3
ESITO WEB-TESTER: OK | WARNING | ERROR
ESITO UX-REVIEWER: X/10 — N problemi alta priorita'
REPORT:
  - data/output/review/web-site/review_web_(data).yaml
  - data/output/review/web-site/review_ux_(data).md
[Se ci sono problemi residui: elencali brevemente]
```
