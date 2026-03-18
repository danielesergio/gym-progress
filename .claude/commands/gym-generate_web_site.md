Genera il sito web statico a partire dai dati di output gia' presenti.

## Cosa fare

Esegui lo script di generazione del sito:
```
python scripts/generate_site.py --outdir docs
```

Questo assembla il sito HTML statico in `docs/` utilizzando i file di output presenti in `data/output/` (feedback, dieta, workout_data, measurements, plan).

## Verifica

Dopo l'esecuzione, verifica che:
- Lo script sia terminato senza errori
- La cartella `docs/` contenga i file HTML generati
- Se ci sono errori, analizza il problema e suggerisci la correzione
