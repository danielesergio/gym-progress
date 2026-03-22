/* ============================================================
   diet.js — Logica pagina Dieta
   Pattern: (1) costanti, (2) stato, (3) funzioni render, (4) DOMContentLoaded
   ============================================================ */

// ── Costanti ──────────────────────────────────────────────
const DATA_PATH = 'data/diet.json';

// ── Stato interno ─────────────────────────────────────────
let dietData = null;
let currentDayIndex = 0; // default: primo giorno dell'array

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

// ── Render selettore giorni ───────────────────────────────

/**
 * Genera dinamicamente un bottone per ogni elemento di giorni[].
 * Usa event delegation sul container #day-toggle.
 * Se giorni[] è vuoto mostra messaggio empty state.
 * @param {Array} giorni — array giorni dal diet.json
 */
function renderDaySelector(giorni) {
  const container = document.getElementById('day-toggle');
  if (!container) return;

  if (!giorni || giorni.length === 0) {
    container.innerHTML = '<p class="diet-empty">Nessun giorno pianificato</p>';
    return;
  }

  container.innerHTML = giorni.map((giorno, index) => {
    const isActive = index === currentDayIndex;
    const nome = giorno.nome ?? `Giorno ${index + 1}`;
    return `<button
      type="button"
      class="diet-toggle-btn${isActive ? ' active' : ''}"
      data-day-index="${index}"
      aria-pressed="${isActive ? 'true' : 'false'}">${nome}</button>`;
  }).join('');
}

/**
 * Aggiorna lo stato visivo active/aria-pressed dei bottoni selettore.
 * @param {number} dayIndex — indice del giorno corrente
 */
function renderToggle(dayIndex) {
  const btns = document.querySelectorAll('.diet-toggle-btn');
  btns.forEach(btn => {
    const isActive = parseInt(btn.dataset.dayIndex, 10) === dayIndex;
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
 * @param {Object}      dayData       — elemento di giorni[] filtrato per tipo
 * @param {string|null} notaStrategia — valore di meta.note_strategia (stringa multiriga)
 */
function renderMacrosSummary(dayData, notaStrategia) {
  const container = document.getElementById('macros-summary');
  if (!container) return;

  if (!dayData) {
    container.innerHTML = '<p class="diet-empty">Dati macros non disponibili.</p>';
    return;
  }

  const kcal      = dayData.kcal               ?? '—';
  const proteine  = dayData.macros?.proteine    ?? '—';
  const carbo     = dayData.macros?.carboidrati ?? '—';
  const grassi    = dayData.macros?.grassi      ?? '—';
  const nome      = dayData.nome                ?? '—';

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
 * Popola #meals-list con le card pasti del giorno selezionato.
 * @param {Object} dayData — elemento di giorni[] filtrato per tipo
 */
function renderMealsList(dayData) {
  const container = document.getElementById('meals-list');
  if (!container) return;

  if (!dayData) {
    container.innerHTML = '<p class="diet-empty">Pasti non disponibili.</p>';
    return;
  }

  const pasti = dayData.pasti ?? [];

  if (pasti.length === 0) {
    container.innerHTML = '<p class="diet-empty">Nessun pasto definito per questo giorno.</p>';
    return;
  }

  container.innerHTML = `
    <h2 class="diet-section-title">Pasti del giorno</h2>
    <div class="diet-meals-stack">
      ${pasti.map(p => renderMealCard(p)).join('')}
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

// ── Render principale ─────────────────────────────────────

/**
 * Funzione principale di rendering della pagina dieta.
 * Riceve l'intero diet.json, usa currentDayIndex per selezionare il giorno,
 * aggiorna tutti i blocchi della pagina.
 * @param {Object} data — dati da diet.json
 */
function renderDiet(data) {
  // Header fase
  renderDietHeader(data);

  // Seleziona il giorno per indice (non per tipo)
  const giorni = data?.giorni ?? [];
  const dayData = giorni[currentDayIndex] ?? null;

  // Aggiorna toggle visivo
  renderToggle(currentDayIndex);

  // Aggiorna macros summary
  renderMacrosSummary(dayData, data?.meta?.note_strategia ?? null);

  // Aggiorna lista pasti
  renderMealsList(dayData);

  // Aggiorna integratori (sempre visibili, indipendenti dal selettore)
  renderSupplements(data?.integratori ?? []);
}

// ── Entry point ───────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  // Event delegation sul container #day-toggle
  // Intercetta i click sui bottoni generati dinamicamente da renderDaySelector()
  const dayToggleContainer = document.getElementById('day-toggle');
  if (dayToggleContainer) {
    dayToggleContainer.addEventListener('click', (event) => {
      const btn = event.target.closest('.diet-toggle-btn');
      if (!btn) return;
      const index = parseInt(btn.dataset.dayIndex, 10);
      if (isNaN(index)) return;
      currentDayIndex = index;
      if (dietData) {
        renderDiet(dietData);
      }
    });
  }

  try {
    const res = await fetch(DATA_PATH);

    if (!res.ok) {
      throw new Error(`HTTP ${res.status} — ${res.statusText}`);
    }

    dietData = await res.json();

    // Genera il selettore giorni dinamico prima del rendering principale
    renderDaySelector(dietData?.giorni ?? []);
    renderDiet(dietData);

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
