Sei l'orchestratore della nuova iterazione mensile del programma fitness. Coordini 4 agenti specializzati.

## Contesto

**Leggi TUTTI i file presenti in `data/` e nelle sue sottocartelle** per analizzare la storia completa dell'atleta. Cartelle da NON leggere: `data/output/site/` (sito generato) e `data/output/review/pt/` (review del loop corrente, non rilevanti per la nuova iterazione).

Leggi quindi:
- `data/feedback_atleta.md` — feedback corrente dell'atleta (PUNTO DI PARTENZA)
- `data/athlete.md` — dati anagrafici e profilo
- `data/goals` — obiettivi a lungo termine
- `data/preferences` — preferenze di allenamento
- `data/previous_data.json` — **(se esiste)** dati storici pre-sistema da importare in measurements.json alla prima iterazione
- `data/output/measurements.json` — tutte le misurazioni storiche
- `data/output/plan.yaml` — piano a lungo termine corrente (fallback: `data/output/plan.html` se plan.yaml non esiste)
- `data/output/workout_data_*.yaml` — scheda dell'iterazione corrente (nella root di output; fallback: `workout_data_*.json`)
- `data/output/feedback_coach_*.md` — feedback coach dell'iterazione corrente (fallback: `feedback_*.html`)
- `data/output/diet_*.yaml` — dieta dell'iterazione corrente (fallback: `diet_*.html`)
- `data/output/feedback_atleta_*.md` — feedback atleta archiviato dell'iterazione corrente
- `data/output/history/YYYY/` — **tutto lo storico** delle iterazioni passate, organizzato per anno:
  - `feedback_atleta_YYYY-MM-DD.md` — feedback dell'atleta (copie archiviate)
  - `workout_data_YYYY-MM-DD.yaml` — schede passate (o `.json` per iterazioni precedenti al refactoring)
  - `feedback_coach_YYYY-MM-DD.md` — feedback del coach passati (o `feedback_YYYY-MM-DD.html` per iterazioni precedenti)
  - `diet_YYYY-MM-DD.yaml` — diete passate (o `diet_YYYY-MM-DD.html` per iterazioni precedenti)

## IMPORTANTE: Storico completo

**DEVI leggere TUTTO lo storico prima di generare qualsiasi output.** Usa lo storico per:
- **Valutare l'efficacia** delle schede passate (quali metodologie hanno funzionato meglio)
- **Evitare ripetizioni** di approcci che non hanno dato risultati
- **Costruire progressione** reale basata sui dati, non su ipotesi
- **Assegnare `efficacia_workout`** (1-10) nella nuova entry di measurements.json, confrontando massimali, composizione corporea e feedback soggettivo tra iterazione precedente e attuale
- **Leggere i feedback_atleta archiviati** per capire pattern ricorrenti (infortuni, problemi di aderenza, richieste passate)

## IMPORTANTE: feedback_atleta.md

**Il file `data/feedback_atleta.md` e' il punto di partenza obbligatorio.** Leggilo PRIMA di qualsiasi altro file. Contiene:
- Stato soggettivo (energia, sonno, stress)
- Aderenza a scheda e dieta
- Progressi percepiti
- Massimali del mese (peso x rep, da convertire con Epley)
- Misurazioni corporee aggiornate
- **Infortuni, dolori, richieste specifiche** (sezione "Altro")

**Tutto l'output deve essere coerente con il contenuto di feedback_atleta.md.** Se l'atleta segnala un infortunio, la scheda DEVE adattarsi. Se chiede un programma specifico, DEVI rispondere a quella richiesta. Se un esercizio causa dolore, DEVE essere sostituito. Non generare mai una scheda standard ignorando infortuni o richieste esplicite dell'atleta.

## Loop di lavoro

### Fase 1: Lettura e analisi (TU — orchestratore)

1. **Leggi TUTTI i dati** seguendo l'ordine sopra
2. **Analizza stato attuale**: peso, misure, massimali, feedback soggettivo
3. **Confronta con la storia**: progressi, regressioni, trend
4. **Identifica** punti di forza, aree di miglioramento, infortuni

### Fase 2: Calcolo rate di progressione storica (TU — orchestratore)

**Prima di generare QUALSIASI target, DEVI:**

1. Leggere `measurements.json` e calcolare il rate di progressione storica per ogni lift:
   - Per ogni coppia di misurazioni consecutive con massimali, calcola: `(massimale_nuovo - massimale_vecchio) / (giorni_trascorsi / 365)` = kg/anno
   - Calcola la **media** e il **range** (min-max) del rate annuale per ogni lift
2. **Stampare a schermo** i rate calcolati:
   ```
   RATE DI PROGRESSIONE STORICA:
   - Squat: media X kg/anno (range: Y - Z kg/anno)
   - Panca: media X kg/anno (range: Y - Z kg/anno)
   - Stacco: media X kg/anno (range: Y - Z kg/anno)
   ```
3. I target a 6 e 12 mesi DEVONO essere calcolati come: `massimale_attuale + (rate_medio * mesi/12)`
4. Applicare **fattori correttivi conservativi** (che riducono, mai aumentano):
   - Infortunio in corso: -30% sul rate del lift coinvolto
   - Stallo attivo (>6 mesi senza progressi): -50% sul rate di quel lift
   - Fase di cut: -20% su tutti i rate
   - Eta' >35: -10% su tutti i rate
5. **Mai proiettare una progressione superiore al rate storico** senza giustificazione esplicita

### Fase 3: Genera output (TU + AGENTI)

#### 3a. Aggiorna measurements.json (TU — orchestratore)
Aggiungi la nuova entry a `data/output/measurements.json` con tutti i campi calcolati (body_fat, FFMI, BMR, TDEE, efficacia_workout, ecc.). Segui le formule descritte sotto.

**Prima iterazione con `data/previous_data.json`**: se `measurements.json` non esiste ancora e il file `data/previous_data.json` esiste, leggilo e importa tutte le entry come base storica iniziale. Calcola i campi mancanti.

Formule:
- **Body Fat %** (US Navy/Hodgdon-Beckett):
  - Maschi: `BF% = 495 / (1.0324 - 0.19077 x log10(vita - collo) + 0.15456 x log10(altezza)) - 450`
  - Femmine: `BF% = 495 / (1.29579 - 0.35004 x log10(vita + fianchi - collo) + 0.22100 x log10(altezza)) - 450`
  - Se disponibile, usa `scripts/body_calc.py`
- **Massimali**: se in feedback_atleta.md sono indicati come `peso x rep`, converti con **Epley**: `1RM = peso x (1 + reps / 30)`. Indica `massimali_tipo: "S"` (stimato).
- **Efficacia Workout (1-10)**: valutazione oggettiva basata su progressione massimali, aderenza, feedback e trend composizione corporea. `null` per la prima iterazione.

#### 3b. Lancia agente PERSONAL TRAINER per plan.yaml (gym-personal-trainer)
Lancia l'agente **gym-personal-trainer** chiedendogli di generare il piano a lungo termine `data/output/plan.yaml`. Passagli tutti i dati necessari (profilo, obiettivi, preferenze, feedback, measurements, schede precedenti, piano precedente se esiste) e i **rate di progressione storica calcolati nella Fase 2** con i relativi fattori correttivi.

#### 3b-loop. Loop di revisione: PT SENIOR REVIEWER ↔ PERSONAL TRAINER per il piano (max 3 iterazioni)

Questo loop funziona esattamente come quello della scheda (fase 3f). **Massimo 3 iterazioni.**

**Iterazione 1:**
1. Lancia l'agente **gym-pt-senior-reviewer** in modalita' revisione piano, passandogli:
   - Il piano appena generato (`plan.yaml`)
   - Tutto lo storico (measurements, schede precedenti, feedback, piano precedente)
   - Profilo atleta, obiettivi, infortuni
   - I rate di progressione storica calcolati nella Fase 2
2. Il reviewer **scrive** `data/output/review/pt/review_plan_(data).yaml` e restituisce il sommario con valutazione ed esito.

**Valutazione del sommario:**
- **Valutazione >= 8 e nessun problema critico** → piano APPROVATO, esci dal loop
- **Valutazione < 8 O problemi critici presenti** → piano BOCCIATO, procedi con la rigenerazione

**Se bocciato — rigenerazione:**
3. Rilancia l'agente **gym-personal-trainer** dicendogli:
   - Tutti i dati originali (profilo, storico, rate, ecc.)
   - "Leggi `data/output/review/pt/review_plan_(data).yaml` e correggi il piano applicando tutti i problemi critici e i suggerimenti indicati."
4. Il personal trainer legge autonomamente il file di review e genera una nuova versione di `plan.yaml`.

**Iterazione 2-3:** ripeti dal punto 1 con il piano aggiornato.

**Dopo 3 iterazioni senza approvazione:** accetta il piano dell'ultima iterazione e segnala all'utente che il reviewer ha ancora riserve (leggi i problemi residui da `review/review_plan_(data).yaml`).

**Schema del loop:**
```
Personal Trainer genera piano
      │
      ▼
┌─► PT Senior Reviewer valuta e scrive review/review_plan_(data).yaml
│     │
│     ├── Valutazione >= 8, no problemi critici → APPROVATO ✓
│     │
│     └── Valutazione < 8 O problemi critici → BOCCIATO
│           │
│           ▼
│     Personal Trainer legge review/review_plan_(data).yaml e rigenera
│           │
│     (max 3 iterazioni)
└───────────┘
```

#### 3c. Genera feedback coach (TU — orchestratore)
Genera `data/output/feedback_coach_(data).md` in formato Markdown con valutazione progressi, risposta a infortuni/richieste, consigli pratici.

#### 3d. Lancia agente DIETOLOGO (gym-dietologo)
Lancia l'agente **gym-dietologo** passandogli tutti i dati necessari (profilo atleta, obiettivi, preferenze, feedback, measurements, diete precedenti, scheda corrente). L'agente genera `data/output/diet_(data).yaml`.

#### 3e. Lancia agente PERSONAL TRAINER (gym-personal-trainer)
Lancia l'agente **gym-personal-trainer** passandogli tutti i dati necessari (profilo, obiettivi, preferenze, feedback, measurements, schede precedenti, piano annuale, feedback coach). L'agente genera `data/output/workout_data_(data).yaml`.

**NOTA**: gli agenti dietologo e personal-trainer (per la scheda) possono essere lanciati **in parallelo** poiche' sono indipendenti. Il loop piano (3b + 3b-loop) DEVE completarsi PRIMA di lanciare il personal trainer per la scheda (3e), poiche' la scheda deve essere coerente con il piano approvato.

#### 3f. Loop di revisione: PT SENIOR REVIEWER ↔ PERSONAL TRAINER (max 3 iterazioni)

Questo e' un ciclo di feedback tra il reviewer senior e il personal trainer. **Massimo 3 iterazioni** per evitare loop infiniti.

**Iterazione 1:**
1. Lancia l'agente **gym-pt-senior-reviewer** passandogli:
   - La scheda appena generata (`workout_data_(data).yaml`)
   - Tutto lo storico (measurements, schede precedenti, feedback, piano)
   - Profilo atleta, obiettivi, infortuni
2. Il reviewer **scrive** `data/output/review/pt/review_workout_(data).yaml` e restituisce il sommario con valutazione ed esito.

**Valutazione del sommario:**
- **Valutazione >= 8 e nessun problema critico** → scheda APPROVATA, esci dal loop
- **Valutazione < 8 O problemi critici presenti** → scheda BOCCIATA, procedi con la rigenerazione

**Se bocciata — rigenerazione:**
3. Rilancia l'agente **gym-personal-trainer** dicendogli:
   - Tutti i dati originali (profilo, storico, ecc.)
   - "Leggi `data/output/review/pt/review_workout_(data).yaml` e correggi la scheda applicando tutti i problemi critici e i suggerimenti indicati."
4. Il personal trainer legge autonomamente il file di review e genera una nuova versione di `workout_data_(data).yaml`.

**Iterazione 2-3:** ripeti dal punto 1 con la scheda aggiornata.

**Dopo 3 iterazioni senza approvazione:** accetta la scheda dell'ultima iterazione e segnala all'utente che il reviewer ha ancora riserve (leggi i problemi residui da `review/review_workout_(data).yaml`).

**Schema del loop:**
```
Personal Trainer genera scheda
      │
      ▼
┌─► PT Senior Reviewer valuta e scrive review/review_workout_(data).yaml
│     │
│     ├── Valutazione >= 8, no problemi critici → APPROVATA ✓
│     │
│     └── Valutazione < 8 O problemi critici → BOCCIATA
│           │
│           ▼
│     Personal Trainer legge review/review_workout_(data).yaml e rigenera
│           │
│     (max 3 iterazioni)
└───────────┘
```

#### 3g. Aggiorna dizionario esercizi
Ogni nuovo esercizio inserito nel workout deve essere aggiunto anche al dizionario `EXERCISE_MUSCLES` in `scripts/volume_calc.py`.

### Fase 4: Archiviazione (TU — orchestratore)

1. **Archivia feedback_atleta.md**: copia `data/feedback_atleta.md` in `data/output/feedback_atleta_(data).md`

2. **Rigenera feedback_atleta.md vuoto**: sovrascrivi con il template pronto per la prossima iterazione:

```markdown
# Feedback Atleta — (prossima data stimata)
## Come ti sei sentito questo mese?
- **Energia generale**: (1-10)
- **Qualita' del sonno**: (1-10)
- **Stress**: (basso / medio / alto)

## Allenamento
- **Hai seguito la scheda?**: (si' / parzialmente / no)
- **Esercizi troppo pesanti / leggeri**:
- **Esercizi che hai trovato difficili o problematici**:
- **Note sull'allenamento**:

## Dieta
- **Hai seguito la dieta?**: (si' / parzialmente / no)
- **Difficolta' riscontrate**:
- **Note sulla dieta**:

## Progressi Percepiti
- **Ti senti piu' forte?**: (si' / no / uguale)
- **Cambiamenti fisici notati**:

## Massimali / Test del mese
Inserisci il peso e le ripetizioni fatte (es. 100 kg x 5). La conversione a 1RM viene calcolata automaticamente.
- **Squat**: kg x rep
- **Panca**: kg x rep
- **Stacco**: kg x rep

## Composizione Corporea
- **Peso (kg)**:
- **Misure** (opzionale):
    - Vita ombelico (cm):
    - Fianchi (cm):
    - Petto (cm):
    - Braccio dx (cm):
    - Coscia dx (cm):
    - Collo (cm):

## Altro
- **Infortuni o dolori**:
- **Commenti liberi**:
```

3. **Archivia file precedenti**: sposta tutti i file datati delle iterazioni **precedenti** (NON quelli appena generati) dalla root di `data/output/` in `data/output/history/YYYY/`. Crea la cartella se non esiste.

4. **File che restano SEMPRE nella root**: `measurements.json`, `plan.yaml`, file dell'iterazione corrente (`workout_data_(data).yaml`, `diet_(data).yaml`, `feedback_coach_(data).md`, `feedback_atleta_(data).md`), cartelle `site/`, `history/` e `review/`.

   La cartella `data/output/review/pt/` contiene solo i file di review del loop corrente. **Non va mai letta nelle iterazioni successive** — le review delle schede passate non sono rilevanti per la generazione di nuove schede.

