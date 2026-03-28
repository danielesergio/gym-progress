/* ============================================================
   diet.js — Logica pagina Dieta
   Pattern: (1) costanti, (2) stato, (3) funzioni render, (4) DOMContentLoaded
   ============================================================ */

// ── Costanti ──────────────────────────────────────────────
const DATA_PATH = 'data/diet.json';

/** Mappa id → abbreviazione breve per i bottoni del selettore */
const DAY_TYPE_LABELS = {
  riposo:         'Riposo',
  palestra:       'Palestra',
  attivita_extra: 'Beach V.'
};

// ── Stato interno ─────────────────────────────────────────
let dietData = null;
let currentDayTypeId = 'riposo'; // default: primo tipo (riposo)

/**
 * Mappa slotId → indice opzione correntemente visualizzata (default 0).
 * Lo stato persiste attraverso i cambi di tipo giorno.
 * @type {Object.<string, number>}
 */
let slotOptionIndices = {};

/**
 * Totali calcolati dei pasti correntemente selezionati.
 * Popolato dopo il primo fetch e aggiornato ad ogni interazione utente.
 * @type {{ kcal: number, proteineG: number, carboG: number, grassiG: number }|null}
 */
let selectedTotals = null;

// ── Utility ───────────────────────────────────────────────

/**
 * Mostra un messaggio di errore nel container dedicato.
 * @param {Element} container
 * @param {Error}   error
 */
function showError(container, error) {
  const el = document.getElementById('diet-error');
  if (!el) return;
  el.textContent = 'Dati non disponibili. Riprova più tardi.';
  el.hidden = false;
  console.error('[diet.js]', error);
}

/**
 * Calcola i totali (kcal, macros) sommando le varianti delle opzioni
 * correntemente selezionate per ogni slot, nel tipo giorno indicato.
 * Funzione pura: nessun side effect, non modifica lo stato globale.
 * Le varianti null o assenti contribuiscono 0 (non generano eccezioni).
 *
 * @param {Object}              data    — dati da diet.json
 * @param {string}              dayTypeId — id del tipo giorno corrente
 * @param {Object.<string,number>} indices — mappa slotId → indice opzione selezionata
 * @returns {{ kcal: number, proteineG: number, carboG: number, grassiG: number }}
 */
function calculateSelectedTotals(data, dayTypeId, indices) {
  let totKcal     = 0;
  let totProteine = 0;
  let totCarbo    = 0;
  let totGrassi   = 0;

  const slots = data?.slot_pasto ?? [];
  for (const slot of slots) {
    const opzioni  = slot?.opzioni ?? [];
    const maxIndex = opzioni.length - 1;
    const rawIdx   = indices[slot.id] ?? 0;
    const idx      = Math.max(0, Math.min(rawIdx, maxIndex));
    const opzione  = opzioni[idx];
    const variante = opzione?.varianti?.[dayTypeId];
    const totale   = variante?.totale;

    totKcal     += totale?.kcal      ?? 0;
    totProteine += totale?.proteine  ?? 0;
    totCarbo    += totale?.carbo     ?? 0;
    totGrassi   += totale?.grassi    ?? 0;
  }

  return {
    kcal:      Math.round(totKcal),
    proteineG: Math.round(totProteine),
    carboG:    Math.round(totCarbo),
    grassiG:   Math.round(totGrassi)
  };
}

// ── Render header fase ────────────────────────────────────

/**
 * Aggiorna il campo fase nell'header.
 * @param {Object} data — dati da diet.json
 */
function renderDietHeader(data) {
  const el = document.getElementById('header-diet-fase');
  if (el) {
    el.textContent = data?.meta?.fase ?? '—';
  }
}

// ── Render selettore tipo giorno ─────────────────────────

/**
 * Genera dinamicamente un bottone per ogni elemento di meta.tipi_giorno[].
 * Usa event delegation sul container #day-toggle.
 * Le abbreviazioni brevi vengono da DAY_TYPE_LABELS; il label completo
 * viene da tipoGiorno.label (usato come aria-label per accessibilità).
 * Se tipiGiorno[] è vuoto mostra messaggio empty state.
 * @param {Array} tipiGiorno — array da meta.tipi_giorno[] in diet.json
 */
function renderDaySelector(tipiGiorno) {
  const container = document.getElementById('day-toggle');
  if (!container) return;

  if (!tipiGiorno || tipiGiorno.length === 0) {
    container.innerHTML = '<p class="diet-empty">Nessun tipo di giorno pianificato</p>';
    return;
  }

  container.innerHTML = tipiGiorno.map(tipo => {
    const isActive = tipo.id === currentDayTypeId;
    const labelBreve = DAY_TYPE_LABELS[tipo.id] ?? tipo.label ?? tipo.id;
    const labelCompleto = tipo.label ?? labelBreve;
    return `<button
      type="button"
      class="diet-toggle-btn${isActive ? ' active' : ''}"
      data-day-type-id="${tipo.id}"
      aria-label="${labelCompleto}"
      aria-pressed="${isActive ? 'true' : 'false'}">${labelBreve}</button>`;
  }).join('');
}

/**
 * Aggiorna lo stato visivo active/aria-pressed dei bottoni selettore
 * in base a currentDayTypeId (stringa id, non indice numerico).
 * @param {string} dayTypeId — id del tipo giorno corrente
 */
function renderDayTypeToggle(dayTypeId) {
  const btns = document.querySelectorAll('.diet-toggle-btn');
  btns.forEach(btn => {
    const isActive = btn.dataset.dayTypeId === dayTypeId;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
  });
}

// ── Render macros summary ─────────────────────────────────

/**
 * Costruisce la barra a segmenti colorati proporzionali a proteine/carbo/grassi.
 * Le larghezze percentuali sono calcolate in kcal (P/C: 4 kcal/g, G: 9 kcal/g).
 * Restituisce stringa HTML vuota se i macros sono 0 o null.
 * @param {number|null} proteineG
 * @param {number|null} carboG
 * @param {number|null} grassiG
 * @returns {string} HTML
 */
function buildProportionBar(proteineG, carboG, grassiG) {
  const p = typeof proteineG === 'number' ? proteineG : 0;
  const c = typeof carboG    === 'number' ? carboG    : 0;
  const g = typeof grassiG   === 'number' ? grassiG   : 0;

  const pKcal = p * 4;
  const cKcal = c * 4;
  const gKcal = g * 9;
  const totale = pKcal + cKcal + gKcal;

  if (totale === 0) return '';

  const pPerc = parseFloat((pKcal / totale * 100).toFixed(1));
  const cPerc = parseFloat((cKcal / totale * 100).toFixed(1));
  const gPerc = parseFloat((gKcal / totale * 100).toFixed(1));

  return `
    <div class="diet-macros-proportion-bar" role="img" aria-label="Proporzioni macros: proteine ${pPerc}%, carboidrati ${cPerc}%, grassi ${gPerc}%">
      <div class="diet-macros-proportion-bar__segment diet-macros-proportion-bar__segment--proteine"
           style="width: ${pPerc}%"
           title="Proteine ${pPerc}%"></div>
      <div class="diet-macros-proportion-bar__segment diet-macros-proportion-bar__segment--carbo"
           style="width: ${cPerc}%"
           title="Carboidrati ${cPerc}%"></div>
      <div class="diet-macros-proportion-bar__segment diet-macros-proportion-bar__segment--grassi"
           style="width: ${gPerc}%"
           title="Grassi ${gPerc}%"></div>
    </div>
    <div class="diet-macros-proportion-bar__legend" aria-hidden="true">
      <span class="diet-macros-proportion-bar__legend-item diet-macros-proportion-bar__legend-item--proteine">P ${pPerc}%</span>
      <span class="diet-macros-proportion-bar__legend-item diet-macros-proportion-bar__legend-item--carbo">C ${cPerc}%</span>
      <span class="diet-macros-proportion-bar__legend-item diet-macros-proportion-bar__legend-item--grassi">G ${gPerc}%</span>
    </div>
  `;
}

/**
 * Popola #macros-summary con la griglia kcal/proteine/carbo/grassi,
 * la barra a segmenti proporzionali e la strategia nutrizionale sintetica.
 * @param {Object}      tipoGiorno    — elemento di meta.tipi_giorno[] selezionato
 * @param {string|null} notaStrategia — valore di meta.note_strategia (stringa multiriga)
 */
function renderMacrosSummary(tipoGiorno, notaStrategia) {
  const container = document.getElementById('macros-summary');
  if (!container) return;

  if (!tipoGiorno) {
    container.innerHTML = '<p class="diet-empty">Dati macros non disponibili.</p>';
    return;
  }

  const kcal      = tipoGiorno.kcal_target                    ?? '—';
  const proteine  = tipoGiorno.macros_target?.proteine         ?? '—';
  const carbo     = tipoGiorno.macros_target?.carboidrati       ?? '—';
  const grassi    = tipoGiorno.macros_target?.grassi            ?? '—';
  const nome      = tipoGiorno.label                           ?? '—';

  // Strategia sintetica: prima riga di note_strategia
  const strategiaSintetica = (typeof notaStrategia === 'string' && notaStrategia.trim().length > 0)
    ? notaStrategia.split('\n')[0].trim()
    : null;

  // Barra proporzioni (valori numerici o null se '—')
  const proteineNum = typeof proteine === 'number' ? proteine : null;
  const carboNum    = typeof carbo    === 'number' ? carbo    : null;
  const grassiNum   = typeof grassi   === 'number' ? grassi   : null;
  const proportionBarHTML = buildProportionBar(proteineNum, carboNum, grassiNum);

  container.innerHTML = `
    <h2 class="diet-macros-summary__title">${nome}</h2>
    ${strategiaSintetica ? `<p class="diet-macros-strategy">${strategiaSintetica}</p>` : ''}
    <div class="diet-macros-bar" role="list" aria-label="Macros giornalieri">
      <div class="diet-macros-bar__item diet-macros-bar__item--kcal" role="listitem">
        <span class="diet-macros-bar__value">${typeof kcal === 'number' ? Math.round(kcal) : kcal}</span>
        <span class="diet-macros-bar__label">kcal</span>
      </div>
      <div class="diet-macros-bar__item diet-macros-bar__item--proteine" role="listitem">
        <span class="diet-macros-bar__value">${typeof proteine === 'number' ? Math.round(proteine) : proteine}<span class="diet-macros-bar__unit">g</span></span>
        <span class="diet-macros-bar__label">Proteine</span>
      </div>
      <div class="diet-macros-bar__item diet-macros-bar__item--carbo" role="listitem">
        <span class="diet-macros-bar__value">${typeof carbo === 'number' ? Math.round(carbo) : carbo}<span class="diet-macros-bar__unit">g</span></span>
        <span class="diet-macros-bar__label">Carboidrati</span>
      </div>
      <div class="diet-macros-bar__item diet-macros-bar__item--grassi" role="listitem">
        <span class="diet-macros-bar__value">${typeof grassi === 'number' ? Math.round(grassi) : grassi}<span class="diet-macros-bar__unit">g</span></span>
        <span class="diet-macros-bar__label">Grassi</span>
      </div>
    </div>
    ${proportionBarHTML}
  `;
}

// ── Render pannello totali vs target ─────────────────────

/**
 * Popola #diet-totals-panel con tre righe: Selezionati / Target / Delta.
 * Per ogni macros (kcal, proteine, carboidrati, grassi) mostra il valore
 * selezionato, il target del tipo giorno attivo e il delta con classe
 * modificatrice --positive / --negative / --neutral.
 * Il delta è neutro quando è compreso tra -5 e +5 (soglia inclusiva).
 *
 * @param {{ kcal: number, proteineG: number, carboG: number, grassiG: number }|null} totals
 * @param {Object|null} tipoGiorno — elemento di meta.tipi_giorno[] selezionato
 */
function renderDietTotalsPanel(totals, tipoGiorno) {
  const container = document.getElementById('diet-totals-panel');
  if (!container) return;

  // Se non ci sono dati mostra placeholder
  if (!totals || !tipoGiorno) {
    container.innerHTML = '<p class="diet-empty">Totali non disponibili.</p>';
    return;
  }

  // Valori selezionati (già arrotondati da calculateSelectedTotals)
  const selKcal     = totals.kcal     != null ? totals.kcal     : null;
  const selProteine = totals.proteineG != null ? totals.proteineG : null;
  const selCarbo    = totals.carboG   != null ? totals.carboG   : null;
  const selGrassi   = totals.grassiG  != null ? totals.grassiG  : null;

  // Valori target
  const tgtKcal     = tipoGiorno.kcal_target                   != null ? Math.round(tipoGiorno.kcal_target)                  : null;
  const tgtProteine = tipoGiorno.macros_target?.proteine        != null ? Math.round(tipoGiorno.macros_target.proteine)        : null;
  const tgtCarbo    = tipoGiorno.macros_target?.carboidrati      != null ? Math.round(tipoGiorno.macros_target.carboidrati)     : null;
  const tgtGrassi   = tipoGiorno.macros_target?.grassi          != null ? Math.round(tipoGiorno.macros_target.grassi)          : null;

  /**
   * Calcola il delta e restituisce la classe modificatrice BEM.
   * Neutro: |delta| <= 5
   * @param {number|null} sel
   * @param {number|null} tgt
   * @returns {string} classe modificatrice CSS
   */
  function deltaClass(sel, tgt) {
    if (sel == null || tgt == null) return 'diet-totals-panel__delta--neutral';
    const d = sel - tgt;
    if (Math.abs(d) <= 5) return 'diet-totals-panel__delta--neutral';
    return d > 0 ? 'diet-totals-panel__delta--positive' : 'diet-totals-panel__delta--negative';
  }

  /**
   * Formatta il delta con segno (es. +12, -8, 0).
   * @param {number|null} sel
   * @param {number|null} tgt
   * @returns {string}
   */
  function fmtDelta(sel, tgt) {
    if (sel == null || tgt == null) return '—';
    const d = sel - tgt;
    if (d === 0) return '0';
    return d > 0 ? `+${d}` : `${d}`;
  }

  /** Formatta un valore intero o mostra — */
  function fmtVal(v) {
    return v != null ? String(v) : '—';
  }

  const dKcalClass     = deltaClass(selKcal, tgtKcal);
  const dProteineClass = deltaClass(selProteine, tgtProteine);
  const dCarboClass    = deltaClass(selCarbo, tgtCarbo);
  const dGrassiClass   = deltaClass(selGrassi, tgtGrassi);

  container.innerHTML = `
    <h2 class="diet-totals-panel__title">Confronto con il target</h2>
    <div class="diet-totals-panel__table" role="table" aria-label="Confronto totali selezionati vs target">
      <!-- intestazione colonne -->
      <div class="diet-totals-panel__row diet-totals-panel__row--header" role="row">
        <div class="diet-totals-panel__cell diet-totals-panel__cell--label" role="columnheader"></div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--col" role="columnheader" aria-label="Kilocalorie">kcal</div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--col" role="columnheader" aria-label="Proteine in grammi">Prot</div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--col" role="columnheader" aria-label="Carboidrati in grammi">Carb</div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--col" role="columnheader" aria-label="Grassi in grammi">Gras</div>
      </div>
      <!-- riga selezionati -->
      <div class="diet-totals-panel__row diet-totals-panel__row--selected" role="row" aria-label="Totali pasti selezionati">
        <div class="diet-totals-panel__cell diet-totals-panel__cell--label" role="rowheader">Selezionati</div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--val" role="cell">${fmtVal(selKcal)}</div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--val" role="cell">${fmtVal(selProteine)}g</div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--val" role="cell">${fmtVal(selCarbo)}g</div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--val" role="cell">${fmtVal(selGrassi)}g</div>
      </div>
      <!-- riga target -->
      <div class="diet-totals-panel__row diet-totals-panel__row--target" role="row" aria-label="Valori target giornalieri">
        <div class="diet-totals-panel__cell diet-totals-panel__cell--label" role="rowheader">Target</div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--val" role="cell">${fmtVal(tgtKcal)}</div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--val" role="cell">${fmtVal(tgtProteine)}g</div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--val" role="cell">${fmtVal(tgtCarbo)}g</div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--val" role="cell">${fmtVal(tgtGrassi)}g</div>
      </div>
      <!-- riga delta -->
      <div class="diet-totals-panel__row diet-totals-panel__row--delta" role="row" aria-label="Delta selezionati meno target">
        <div class="diet-totals-panel__cell diet-totals-panel__cell--label" role="rowheader">Delta</div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--delta ${dKcalClass}" role="cell" aria-label="delta kcal">${fmtDelta(selKcal, tgtKcal)}</div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--delta ${dProteineClass}" role="cell" aria-label="delta proteine">${fmtDelta(selProteine, tgtProteine)}</div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--delta ${dCarboClass}" role="cell" aria-label="delta carboidrati">${fmtDelta(selCarbo, tgtCarbo)}</div>
        <div class="diet-totals-panel__cell diet-totals-panel__cell--delta ${dGrassiClass}" role="cell" aria-label="delta grassi">${fmtDelta(selGrassi, tgtGrassi)}</div>
      </div>
    </div>
  `;
}

// ── Render alimenti ───────────────────────────────────────

/**
 * Costruisce le righe degli alimenti di un pasto.
 * @param {Array} alimenti
 * @returns {string} HTML
 */
function renderAlimentiRows(alimenti) {
  if (!alimenti || alimenti.length === 0) {
    return '<tr><td colspan="6" class="diet-meal-table__empty">Nessun alimento.</td></tr>';
  }
  return alimenti.map(a => `
    <tr class="diet-meal-table__row">
      <td class="diet-meal-table__nome">${a.nome ?? '—'}</td>
      <td class="diet-meal-table__num">${a.grammi != null ? a.grammi + 'g' : '—'}</td>
      <td class="diet-meal-table__num">${a.kcal != null ? Math.round(a.kcal) : '—'}</td>
      <td class="diet-meal-table__num">${a.proteine != null ? Math.round(a.proteine) + 'g' : '—'}</td>
      <td class="diet-meal-table__num">${a.carbo != null ? Math.round(a.carbo) + 'g' : '—'}</td>
      <td class="diet-meal-table__num">${a.grassi != null ? Math.round(a.grassi) + 'g' : '—'}</td>
    </tr>
  `).join('');
}

/**
 * Costruisce l'HTML di una singola card pasto.
 * @param {Object} pasto
 * @returns {string} HTML
 */
function renderMealCard(pasto) {
  const nome    = pasto?.nome    ?? '—';
  const orario  = pasto?.orario  ?? '—';
  const alimenti = pasto?.alimenti ?? [];
  const totale   = pasto?.totale ?? {};

  const kcalTot     = totale.kcal      != null ? Math.round(totale.kcal)      : '—';
  const proteineTot = totale.proteine  != null ? Math.round(totale.proteine)  : '—';
  const carboTot    = totale.carbo     != null ? Math.round(totale.carbo)     : '—';
  const grassiTot   = totale.grassi    != null ? Math.round(totale.grassi)    : '—';

  return `
    <article class="diet-meal-card" aria-label="Pasto: ${nome}">
      <header class="diet-meal-card__header">
        <div class="diet-meal-card__title-group">
          <h3 class="diet-meal-card__nome">${nome}</h3>
          <span class="diet-meal-card__orario" aria-label="Orario">${orario}</span>
        </div>
        <div class="diet-meal-card__totale" aria-label="Totale pasto">
          <span class="diet-meal-card__totale-item">${kcalTot} kcal</span>
          <span class="diet-meal-card__totale-sep" aria-hidden="true">·</span>
          <span class="diet-meal-card__totale-item">${proteineTot}g P</span>
          <span class="diet-meal-card__totale-sep" aria-hidden="true">·</span>
          <span class="diet-meal-card__totale-item">${carboTot}g C</span>
          <span class="diet-meal-card__totale-sep" aria-hidden="true">·</span>
          <span class="diet-meal-card__totale-item">${grassiTot}g G</span>
        </div>
      </header>
      <div class="diet-meal-table-wrapper">
        <table class="diet-meal-table" aria-label="Alimenti ${nome}">
          <thead>
            <tr class="diet-meal-table__head">
              <th scope="col" class="diet-meal-table__th diet-meal-table__th--nome">Alimento</th>
              <th scope="col" class="diet-meal-table__th diet-meal-table__th--num">Grammi</th>
              <th scope="col" class="diet-meal-table__th diet-meal-table__th--num">Kcal</th>
              <th scope="col" class="diet-meal-table__th diet-meal-table__th--num">Prot</th>
              <th scope="col" class="diet-meal-table__th diet-meal-table__th--num">Carbo</th>
              <th scope="col" class="diet-meal-table__th diet-meal-table__th--num">Grassi</th>
            </tr>
          </thead>
          <tbody>
            ${renderAlimentiRows(alimenti)}
          </tbody>
        </table>
      </div>
    </article>
  `;
}

// ── Render lista pasti ────────────────────────────────────

/**
 * Costruisce l'HTML di una singola opzione con gli alimenti della variante
 * corretta per il tipo di giorno selezionato.
 * @param {Object} opzione    — elemento di slot.opzioni[]
 * @param {string} dayTypeId  — id tipo giorno corrente
 * @param {number} index      — indice 0-based dell'opzione nello slot
 * @returns {string} HTML
 */
function renderOpzioneCard(opzione, dayTypeId, index) {
  const nomeOpzione = opzione?.nome ?? `Opzione ${index + 1}`;
  const variante = opzione?.varianti?.[dayTypeId] ?? null;

  if (!variante) {
    return `
      <article class="diet-opzione-card" aria-label="Opzione: ${nomeOpzione}">
        <h4 class="diet-opzione-card__nome">${nomeOpzione}</h4>
        <p class="diet-empty diet-opzione-card__unavailable">Variante non disponibile per questo tipo di giorno.</p>
      </article>
    `;
  }

  const alimenti = variante.alimenti ?? [];
  const totale   = variante.totale   ?? {};

  const kcalTot     = totale.kcal      != null ? Math.round(totale.kcal)      : '—';
  const proteineTot = totale.proteine  != null ? Math.round(totale.proteine)  : '—';
  const carboTot    = totale.carbo     != null ? Math.round(totale.carbo)     : '—';
  const grassiTot   = totale.grassi    != null ? Math.round(totale.grassi)    : '—';

  return `
    <article class="diet-opzione-card" aria-label="Opzione: ${nomeOpzione}">
      <h4 class="diet-opzione-card__nome">${nomeOpzione}</h4>
      <div class="diet-meal-table-wrapper">
        <table class="diet-meal-table" aria-label="Alimenti opzione ${nomeOpzione}">
          <thead>
            <tr class="diet-meal-table__head">
              <th scope="col" class="diet-meal-table__th diet-meal-table__th--nome">Alimento</th>
              <th scope="col" class="diet-meal-table__th diet-meal-table__th--num">Grammi</th>
              <th scope="col" class="diet-meal-table__th diet-meal-table__th--num">Kcal</th>
              <th scope="col" class="diet-meal-table__th diet-meal-table__th--num">Prot</th>
              <th scope="col" class="diet-meal-table__th diet-meal-table__th--num">Carbo</th>
              <th scope="col" class="diet-meal-table__th diet-meal-table__th--num">Grassi</th>
            </tr>
          </thead>
          <tbody>
            ${renderAlimentiRows(alimenti)}
          </tbody>
        </table>
      </div>
      <footer class="diet-opzione-card__totale" aria-label="Totale opzione">
        <span class="diet-opzione-card__totale-item diet-opzione-card__totale-item--kcal">${kcalTot} kcal</span>
        <span class="diet-opzione-card__totale-sep" aria-hidden="true">·</span>
        <span class="diet-opzione-card__totale-item">${proteineTot}g P</span>
        <span class="diet-opzione-card__totale-sep" aria-hidden="true">·</span>
        <span class="diet-opzione-card__totale-item">${carboTot}g C</span>
        <span class="diet-opzione-card__totale-sep" aria-hidden="true">·</span>
        <span class="diet-opzione-card__totale-item">${grassiTot}g G</span>
      </footer>
    </article>
  `;
}

/**
 * Costruisce l'HTML di un intero slot con orario, kcal target e l'opzione corrente.
 * Mostra UN'UNICA opzione alla volta (indice da slotOptionIndices[slot.id]).
 * Se lo slot ha più di una opzione, genera i controlli di navigazione (.diet-slot-nav).
 * @param {Object} slot       — elemento di slot_pasto[]
 * @param {string} dayTypeId  — id tipo giorno corrente
 * @returns {string} HTML
 */
function renderSlotCard(slot, dayTypeId) {
  const slotId  = slot?.id               ?? '';
  const label   = slot?.label              ?? '—';
  const orario  = slot?.orario_indicativo  ?? '—';
  const kcal    = slot?.kcal_per_tipo?.[dayTypeId] != null ? Math.round(slot.kcal_per_tipo[dayTypeId]) : '—';
  const opzioni = slot?.opzioni ?? [];

  // Inizializza l'indice a 0 se non ancora presente
  if (slotId && !(slotId in slotOptionIndices)) {
    slotOptionIndices[slotId] = 0;
  }

  const currentIndex = slotOptionIndices[slotId] ?? 0;
  const clampedIndex = Math.min(Math.max(currentIndex, 0), Math.max(opzioni.length - 1, 0));

  let opzioneHtml;
  let navHtml = '';

  if (opzioni.length === 0) {
    opzioneHtml = '<p class="diet-empty">Nessuna opzione disponibile per questo slot.</p>';
  } else {
    // Mostra solo l'opzione all'indice corrente
    opzioneHtml = renderOpzioneCard(opzioni[clampedIndex], dayTypeId, clampedIndex);

    // Genera i controlli di navigazione solo se ci sono più opzioni
    if (opzioni.length > 1) {
      const isPrevDisabled = clampedIndex === 0;
      const isNextDisabled = clampedIndex === opzioni.length - 1;
      navHtml = `
        <div class="diet-slot-nav" aria-label="Navigazione opzioni ${label}">
          <button
            type="button"
            class="diet-slot-nav__btn diet-slot-nav__btn--prev"
            data-slot-id="${slotId}"
            data-direction="prev"
            aria-label="Opzione precedente"
            ${isPrevDisabled ? 'disabled' : ''}
          >&#8249;</button>
          <span class="diet-slot-nav__indicator" aria-live="polite" aria-atomic="true">${clampedIndex + 1} / ${opzioni.length}</span>
          <button
            type="button"
            class="diet-slot-nav__btn diet-slot-nav__btn--next"
            data-slot-id="${slotId}"
            data-direction="next"
            aria-label="Opzione successiva"
            ${isNextDisabled ? 'disabled' : ''}
          >&#8250;</button>
        </div>
      `;
    }
  }

  return `
    <section class="diet-slot-card" aria-label="Slot: ${label}">
      <header class="diet-slot-card__header">
        <h3 class="diet-slot-card__label">${label}</h3>
        <span class="diet-slot-card__orario" aria-label="Orario indicativo">${orario}</span>
        <span class="diet-slot-card__kcal" aria-label="Kcal target">${kcal} kcal</span>
      </header>
      ${navHtml}
      <div class="diet-slot-card__opzioni">
        ${opzioneHtml}
      </div>
    </section>
  `;
}

/**
 * Popola #meals-list con le card slot-pasto per il tipo di giorno selezionato.
 * Per ogni slot mostra TUTTE le opzioni con la variante corretta per dayTypeId.
 * @param {Object} data          — dati completi da diet.json
 * @param {string} dayTypeId     — id tipo giorno corrente (es. 'riposo')
 */
function renderMealsList(data, dayTypeId) {
  const container = document.getElementById('meals-list');
  if (!container) return;

  const slotPasto = data?.slot_pasto ?? [];

  if (slotPasto.length === 0) {
    container.innerHTML = '<p class="diet-empty">Nessun pasto definito per questo tipo di giorno.</p>';
    return;
  }

  const slotsHtml = slotPasto.map(slot => renderSlotCard(slot, dayTypeId)).join('');

  container.innerHTML = `
    <h2 class="diet-section-title">Pasti del giorno</h2>
    <div class="diet-slots-stack">
      ${slotsHtml}
    </div>
  `;
}

// ── Render integratori ────────────────────────────────────

/**
 * Costruisce l'HTML di una singola card integratore.
 * @param {Object} integratore
 * @returns {string} HTML
 */
function renderSupplementCard(integratore) {
  const nome   = integratore?.nome   ?? '—';
  const dose   = integratore?.dose   ?? '—';
  const timing = integratore?.timing ?? '—';
  const note   = integratore?.note   ?? '';

  return `
    <article class="diet-supplement-card" aria-label="Integratore: ${nome}">
      <div class="diet-supplement-card__header">
        <h3 class="diet-supplement-card__nome">${nome}</h3>
        <span class="diet-supplement-card__dose" aria-label="Dose">${dose}</span>
      </div>
      <p class="diet-supplement-card__timing">
        <span class="diet-supplement-card__timing-label">Timing:</span>
        ${timing}
      </p>
      ${note ? `<p class="diet-supplement-card__note">${note}</p>` : ''}
    </article>
  `;
}

/**
 * Popola #supplements-list con le card integratori.
 * @param {Array} integratori — array root di diet.json
 */
function renderSupplements(integratori) {
  const container = document.getElementById('supplements-list');
  if (!container) return;

  if (!integratori || integratori.length === 0) {
    container.innerHTML = '<p class="diet-empty">Nessun integratore definito.</p>';
    return;
  }

  container.innerHTML = integratori.map(i => renderSupplementCard(i)).join('');
}

// ── Render strategia nutrizionale ────────────────────────

/**
 * Popola #strategy-note con il testo completo di note_strategia formattato in paragrafi.
 * Usa un elemento <details>/<summary> nativo per il pannello collassabile.
 * Se notaStrategia è null, undefined o stringa vuota, nasconde la sezione.
 * @param {string|null} notaStrategia — valore di meta.note_strategia (stringa multiriga)
 */
function renderStrategyNote(notaStrategia) {
  const container = document.getElementById('strategy-note');
  if (!container) return;

  if (!notaStrategia || typeof notaStrategia !== 'string' || notaStrategia.trim().length === 0) {
    container.hidden = true;
    return;
  }

  const paragraphs = notaStrategia
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0);

  if (paragraphs.length === 0) {
    container.hidden = true;
    return;
  }

  const paragraphsHtml = paragraphs
    .map(p => `<p class="diet-strategy-note__paragraph">${p}</p>`)
    .join('');

  container.innerHTML = `
    <details class="diet-strategy-note__details">
      <summary class="diet-strategy-note__toggle">
        <span class="diet-strategy-note__toggle-label">Strategia nutrizionale completa</span>
        <span class="diet-strategy-note__toggle-icon" aria-hidden="true">▸</span>
      </summary>
      <div class="diet-strategy-note__body">
        ${paragraphsHtml}
      </div>
    </details>
  `;

  container.hidden = false;
}

// ── Export CSV ───────────────────────────────────────────

/**
 * Racchiude un valore stringa in doppi apici se contiene ; o doppi apici.
 * Esegue l'escaping dei doppi apici interni raddoppiandoli.
 * @param {string} val
 * @returns {string}
 */
function csvEscapeField(val) {
  const str = String(val);
  if (str.includes(';') || str.includes('"') || str.includes('\n')) {
    return '"' + str.replace(/"/g, '""') + '"';
  }
  return str;
}

/**
 * Genera il CSV della dieta completa (tutti i tipi di giorno × tutti gli slot
 * × tutte le opzioni × tutti gli alimenti) e avvia il download via Blob URL.
 * Usa BOM UTF-8 per compatibilità Excel italiano.
 * Separatore di campo: punto e virgola (;).
 */
function exportDietCSV() {
  if (!dietData) return;

  const tipiGiorno = dietData?.meta?.tipi_giorno ?? [];
  const slotPasto  = dietData?.slot_pasto ?? [];

  const intestazione = 'tipo_giorno;slot;opzione;alimento;grammi;kcal;proteine_g;carbo_g;grassi_g';
  const righe = [intestazione];

  for (const tipoGiorno of tipiGiorno) {
    const tipoId    = tipoGiorno.id    ?? '';
    const tipoLabel = tipoGiorno.label ?? tipoId;

    for (const slot of slotPasto) {
      const slotLabel = slot?.label ?? '';
      const opzioni   = slot?.opzioni ?? [];

      for (const opzione of opzioni) {
        const opzioneNome = opzione?.nome ?? '';
        const variante    = opzione?.varianti?.[tipoId];

        // Salta varianti non disponibili per questo tipo giorno
        if (!variante) continue;

        const alimenti = variante?.alimenti ?? [];

        for (const alimento of alimenti) {
          const nome    = alimento?.nome    ?? '';
          const grammi  = alimento?.grammi  ?? 0;
          const kcal    = alimento?.kcal    != null ? Math.round(alimento.kcal) : 0;
          const prot    = alimento?.proteine != null ? parseFloat(alimento.proteine.toFixed(1)) : 0;
          const carbo   = alimento?.carbo   != null ? parseFloat(alimento.carbo.toFixed(1))    : 0;
          const grassi  = alimento?.grassi  != null ? parseFloat(alimento.grassi.toFixed(1))   : 0;

          const riga = [
            csvEscapeField(tipoLabel),
            csvEscapeField(slotLabel),
            csvEscapeField(opzioneNome),
            csvEscapeField(nome),
            grammi,
            kcal,
            prot,
            carbo,
            grassi
          ].join(';');

          righe.push(riga);
        }
      }
    }
  }

  const csvContent = righe.join('\r\n');

  // BOM UTF-8 per compatibilità Excel italiano
  const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });

  // Nome file: dieta-daniele-YYYY-MM.csv
  let nomeFile = 'dieta-daniele.csv';
  const dataStr = dietData?.meta?.data;
  if (dataStr && typeof dataStr === 'string' && dataStr.length >= 7) {
    const anno = dataStr.slice(0, 4);
    const mese = dataStr.slice(5, 7);
    nomeFile = `dieta-daniele-${anno}-${mese}.csv`;
  }

  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', nomeFile);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// ── Render principale ─────────────────────────────────────

/**
 * Funzione principale di rendering della pagina dieta.
 * Riceve l'intero diet.json, usa currentDayTypeId per selezionare il tipo giorno,
 * aggiorna tutti i blocchi della pagina.
 * @param {Object} data — dati da diet.json
 */
function renderDiet(data) {
  // Header fase
  renderDietHeader(data);

  // Seleziona il tipo giorno per id stringa (non per indice numerico)
  const tipiGiorno = data?.meta?.tipi_giorno ?? [];
  const tipoSelezionato = tipiGiorno.find(t => t.id === currentDayTypeId) ?? tipiGiorno[0] ?? null;

  // Aggiorna toggle visivo in base all'id corrente
  renderDayTypeToggle(currentDayTypeId);

  // Aggiorna macros summary usando tipoSelezionato
  renderMacrosSummary(tipoSelezionato, data?.meta?.note_strategia ?? null);

  // Aggiorna lista pasti con il tipo giorno corrente
  renderMealsList(data, currentDayTypeId);

  // Aggiorna integratori (sempre visibili, indipendenti dal selettore)
  renderSupplements(data?.integratori ?? []);

  // Mostra la strategia nutrizionale completa (nota multiriga, pannello collassabile)
  renderStrategyNote(data?.meta?.note_strategia ?? null);
}

// ── Entry point ───────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  // Event delegation sul container #day-toggle
  // Intercetta i click sui bottoni generati dinamicamente da renderDaySelector()
  // Usa data-day-type-id (stringa id) invece di data-day-index (numero)
  const dayToggleContainer = document.getElementById('day-toggle');
  if (dayToggleContainer) {
    dayToggleContainer.addEventListener('click', (event) => {
      const btn = event.target.closest('.diet-toggle-btn');
      if (!btn) return;
      const typeId = btn.dataset.dayTypeId;
      if (!typeId) return;
      currentDayTypeId = typeId;
      if (dietData) {
        selectedTotals = calculateSelectedTotals(dietData, currentDayTypeId, slotOptionIndices);
        renderDiet(dietData);
        const tipiGiorno = dietData?.meta?.tipi_giorno ?? [];
        const tipoSelezionato = tipiGiorno.find(t => t.id === currentDayTypeId) ?? tipiGiorno[0] ?? null;
        renderDietTotalsPanel(selectedTotals, tipoSelezionato);
      }
    });
  }

  // Event delegation su #meals-list per i bottoni di navigazione opzioni slot.
  // I bottoni .diet-slot-nav__btn sono generati dinamicamente da renderSlotCard(),
  // quindi il listener va attaccato al container statico #meals-list.
  const mealsListContainer = document.getElementById('meals-list');
  if (mealsListContainer) {
    mealsListContainer.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-direction]');
      if (!btn) return;
      const slotId    = btn.dataset.slotId;
      const direction = btn.dataset.direction;
      if (!slotId || !direction) return;
      if (!dietData) return;

      const slotPasto = dietData?.slot_pasto ?? [];
      const slot = slotPasto.find(s => s.id === slotId);
      if (!slot) return;

      const opzioni    = slot?.opzioni ?? [];
      const maxIndex   = opzioni.length - 1;
      const currentIdx = slotOptionIndices[slotId] ?? 0;

      if (direction === 'next') {
        slotOptionIndices[slotId] = Math.min(currentIdx + 1, maxIndex);
      } else if (direction === 'prev') {
        slotOptionIndices[slotId] = Math.max(currentIdx - 1, 0);
      }

      renderMealsList(dietData, currentDayTypeId);

      // Restaura il focus sul bottone ricreato dopo il re-render del DOM.
      // renderMealsList() sostituisce l'innerHTML di #meals-list, distruggendo
      // il bottone che aveva ricevuto il click: slotId e direction sono stati
      // salvati prima del render e ora vengono usati per ritrovare il bottone
      // ricreato tramite data-attribute, evitando la perdita di focus.
      const focusTarget = mealsListContainer.querySelector(
        `[data-slot-id="${slotId}"][data-direction="${direction}"]`
      );
      if (focusTarget) focusTarget.focus();

      selectedTotals = calculateSelectedTotals(dietData, currentDayTypeId, slotOptionIndices);
      const tipiGiornoMeals = dietData?.meta?.tipi_giorno ?? [];
      const tipoSelezionatoMeals = tipiGiornoMeals.find(t => t.id === currentDayTypeId) ?? tipiGiornoMeals[0] ?? null;
      renderDietTotalsPanel(selectedTotals, tipoSelezionatoMeals);
    });
  }

  // Listener pulsante esporta CSV
  const exportBtn = document.getElementById('export-csv-btn');
  if (exportBtn) {
    exportBtn.addEventListener('click', exportDietCSV);
  }

  try {
    const res = await fetch(DATA_PATH);

    if (!res.ok) {
      throw new Error(`HTTP ${res.status} — ${res.statusText}`);
    }

    dietData = await res.json();

    // Inizializza currentDayTypeId con il primo tipo giorno disponibile
    const tipiGiorno = dietData?.meta?.tipi_giorno ?? [];
    if (tipiGiorno.length > 0) {
      currentDayTypeId = tipiGiorno[0].id ?? 'riposo';
    }

    // Abilita il pulsante export CSV dopo il caricamento
    if (exportBtn) {
      exportBtn.removeAttribute('disabled');
    }

    // Genera il selettore tipi giorno dinamico prima del rendering principale
    renderDaySelector(tipiGiorno);
    renderDiet(dietData);

    // Inizializza selectedTotals con i valori di default dopo il primo rendering
    selectedTotals = calculateSelectedTotals(dietData, currentDayTypeId, slotOptionIndices);
    const tipiGiornoInit = dietData?.meta?.tipi_giorno ?? [];
    const tipoSelezionatoInit = tipiGiornoInit.find(t => t.id === currentDayTypeId) ?? tipiGiornoInit[0] ?? null;
    renderDietTotalsPanel(selectedTotals, tipoSelezionatoInit);

  } catch (e) {
    showError(null, e);

    // Fallback: empty state nei container principali
    const macros = document.getElementById('macros-summary');
    if (macros) macros.innerHTML = '<p class="diet-empty">Dati non disponibili.</p>';

    const meals = document.getElementById('meals-list');
    if (meals) meals.innerHTML = '<p class="diet-empty">Dati non disponibili.</p>';

    const supplements = document.getElementById('supplements-list');
    if (supplements) supplements.innerHTML = '<p class="diet-empty">Dati non disponibili.</p>';
  }
});
