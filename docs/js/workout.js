/* ============================================================
   workout.js — Logica pagina Allenamento
   Pattern: (1) costanti, (2) funzioni render, (3) DOMContentLoaded
   ============================================================ */

// ── Costanti ──────────────────────────────────────────────
const DATA_PATH_WORKOUT = 'data/workout.json';

// ── Stato interno ─────────────────────────────────────────
let workoutData = null;
let settimanaAttiva = 1;

// ── Utility ───────────────────────────────────────────────

/**
 * Mostra un messaggio di errore nel container dedicato.
 * Non blocca la UI: usa il div #workout-error.
 * @param {string} message
 * @param {Error}  [error]
 */
function showWorkoutError(message, error) {
  const container = document.getElementById('workout-error');
  if (!container) return;
  container.textContent = message;
  container.hidden = false;
  if (error) console.error('[workout.js]', error);
}

// ── Render banner TOS ─────────────────────────────────────

/**
 * Aggiorna il titolo del banner TOS con il nome scheda proveniente
 * dal JSON (opzionale — il contenuto degli esercizi vietati è statico).
 * Il banner è già renderizzato nel markup HTML; questa funzione
 * arricchisce il titolo con i dati fetchati se disponibili.
 * @param {Object} data — dati da workout.json
 */
function renderTOSBanner(data) {
  const titleEl = document.querySelector('.workout-tos-banner__title');
  if (!titleEl) return;

  const nomeScheda = data?.meta?.titolo ?? null;
  if (nomeScheda) {
    titleEl.textContent = `Protocollo TOS — Esercizi vietati (${nomeScheda})`;
  }
}

// ── Render header scheda ──────────────────────────────────

/**
 * Popola #workout-scheda-nome con meta.titolo e
 * #workout-mesociclo-obiettivo con mesociclo.obiettivo.
 * @param {Object} data — dati workout.json
 */
function renderWorkoutHeader(data) {
  const elNome = document.getElementById('workout-scheda-nome');
  const elObiettivo = document.getElementById('workout-mesociclo-obiettivo');
  const elPeriodo = document.getElementById('header-workout-period');

  if (elNome) {
    elNome.textContent = data?.meta?.titolo ?? '—';
  }
  if (elObiettivo) {
    elObiettivo.textContent = data?.mesociclo?.obiettivo ?? '—';
  }
  if (elPeriodo) {
    elPeriodo.textContent = data?.meta?.periodo ?? '—';
  }
}

// ── Render selettore settimane ────────────────────────────

/**
 * Aggiorna lo stato visivo dei bottoni settimana.
 * Il bottone della settimana attiva riceve la classe 'active'
 * e aria-pressed="true"; gli altri vengono resettati.
 * @param {number} numeroSettimana — 1..4
 */
function renderWeekSelector(numeroSettimana) {
  for (let i = 1; i <= 4; i++) {
    const btn = document.getElementById(`week-btn-${i}`);
    if (!btn) continue;
    const isActive = i === numeroSettimana;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
  }
}

// ── Render dettaglio settimana ────────────────────────────

/**
 * Popola #workout-detail con il riepilogo della settimana selezionata.
 * Mostra intensità target, note settimana e l'elenco dei giorni/sessioni.
 * @param {Object} data            — dati workout.json
 * @param {number} numeroSettimana — 1..4
 */
function renderWorkoutDetail(data, numeroSettimana) {
  const container = document.getElementById('workout-detail');
  if (!container) return;

  const settimane = data?.settimane ?? [];
  const settimana = settimane.find(s => s.numero === numeroSettimana) ?? null;

  if (!settimana) {
    container.innerHTML = `<p class="workout-empty">Dati settimana ${numeroSettimana} non disponibili.</p>`;
    return;
  }

  const intensita = settimana.intensita_target ?? '—';
  const note = settimana.note_settimana ?? '';
  const giorni = settimana.giorni ?? [];

  // Costruisce le card delle sessioni giornaliere
  const giorniHtml = giorni.length > 0
    ? giorni.map(giorno => renderGiornoCard(giorno)).join('')
    : '<p class="workout-empty">Nessuna sessione per questa settimana.</p>';

  container.innerHTML = `
    <div class="workout-week-summary">
      <p class="workout-week-summary__intensita">
        <span class="workout-week-summary__label">Intensità target:</span>
        <span class="workout-week-summary__value">${intensita}</span>
      </p>
      ${note ? `<p class="workout-week-summary__note">${note}</p>` : ''}
    </div>
    <div class="workout-giorni">
      ${giorniHtml}
    </div>
  `;
}

/**
 * Costruisce l'HTML di una singola riga esercizio nella tabella.
 * @param {Object} esercizio
 * @returns {string} HTML della riga <tr>
 */
function renderEsercizioRow(esercizio) {
  const nome      = esercizio?.nome      ?? '—';
  const serie     = esercizio?.serie     ?? '—';
  const reps      = esercizio?.reps      ?? '—';
  const peso      = esercizio?.peso      ?? '—';
  const recupero  = esercizio?.recupero  ?? '—';
  const gruppo    = esercizio?.gruppo    ?? '';
  const isPrincipale = esercizio?.principale === true;

  return `
    <tr class="workout-esercizio-row${isPrincipale ? ' workout-esercizio-row--principale' : ''}">
      <td class="workout-esercizio-row__nome">
        <span class="workout-esercizio-row__nome-testo">${nome}</span>
        ${isPrincipale ? '<span class="workout-esercizio-principale" aria-label="Esercizio principale">★</span>' : ''}
        ${gruppo ? `<span class="workout-esercizio-row__gruppo">${gruppo}</span>` : ''}
      </td>
      <td class="workout-esercizio-row__serie">${serie}</td>
      <td class="workout-esercizio-row__reps">${reps}</td>
      <td class="workout-esercizio-row__peso">${peso}</td>
      <td class="workout-esercizio-row__recupero">${recupero}</td>
    </tr>
  `;
}

/**
 * Costruisce l'HTML di una singola riga serie nella tabella Test Day.
 * Le righe tentativo hanno classe distinta per evidenziazione visiva.
 * @param {Object} serie — { set, peso, reps, note, tentativo }
 * @returns {string} HTML della riga <tr>
 */
function renderTestDaySerieRow(serie) {
  const set      = serie?.set       ?? '—';
  const peso     = serie?.peso      ?? '—';
  const reps     = serie?.reps      ?? '—';
  const nota     = serie?.note      ?? '';
  const isTentativo = serie?.tentativo === true;

  return `
    <tr class="workout-testday-serie-row${isTentativo ? ' workout-testday-serie-row--tentativo' : ''}">
      <td class="workout-testday-serie-row__set">${set}</td>
      <td class="workout-testday-serie-row__peso">${peso}</td>
      <td class="workout-testday-serie-row__reps">${reps}</td>
      <td class="workout-testday-serie-row__note">${nota || '—'}</td>
    </tr>
  `;
}

/**
 * Costruisce l'HTML di una card protocollo Test Day (singolo esercizio).
 * Se il protocollo è escluso (serie vuota o target contiene 'ESCLUSA'),
 * mostra un blocco danger con la motivazione.
 * @param {Object} protocollo — { nome, target, serie[] }
 * @returns {string} HTML della card
 */
function renderTestDayCard(protocollo) {
  const nome   = protocollo?.nome   ?? '—';
  const target = protocollo?.target ?? '—';
  const serie  = protocollo?.serie  ?? [];

  const isEscluso = serie.length === 0 || target.includes('ESCLUSA');

  if (isEscluso) {
    return `
      <div class="workout-testday-card workout-testday-card--escluso" role="note" aria-label="${nome} — escluso">
        <div class="workout-testday-card__header">
          <h4 class="workout-testday-card__nome">${nome}</h4>
          <span class="workout-testday-card__badge workout-testday-card__badge--escluso" aria-label="Escluso">⛔ ESCLUSA</span>
        </div>
        <p class="workout-testday-card__target-escluso">${target}</p>
      </div>
    `;
  }

  const righe = serie.map(s => renderTestDaySerieRow(s)).join('');

  return `
    <div class="workout-testday-card" aria-label="Protocollo ${nome}">
      <div class="workout-testday-card__header">
        <h4 class="workout-testday-card__nome">${nome}</h4>
        <span class="workout-testday-card__badge" aria-label="Target">🎯 ${target}</span>
      </div>
      <div class="workout-testday-table-wrapper">
        <table class="workout-testday-table" aria-label="Protocollo ${nome}">
          <thead>
            <tr class="workout-testday-table__head">
              <th scope="col" class="workout-testday-table__th">Set</th>
              <th scope="col" class="workout-testday-table__th workout-testday-table__th--num">Peso</th>
              <th scope="col" class="workout-testday-table__th workout-testday-table__th--num">Reps</th>
              <th scope="col" class="workout-testday-table__th workout-testday-table__th--note">Note</th>
            </tr>
          </thead>
          <tbody>
            ${righe}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

/**
 * Costruisce l'HTML dell'intera sezione Test Day per un giorno con 'protocolli'.
 * Itera su giorno.protocolli[] e delega a renderTestDayCard() per ciascuno.
 * @param {Object} giorno — giorno con campo 'protocolli'
 * @returns {string} HTML della sezione Test Day
 */
function renderTestDaySection(giorno) {
  const protocolli   = giorno?.protocolli  ?? [];
  const noteSessione = giorno?.note_sessione ?? '';

  const cardsHtml = protocolli.length > 0
    ? protocolli.map(p => renderTestDayCard(p)).join('')
    : '<p class="workout-empty">Nessun protocollo disponibile.</p>';

  return `
    <section class="workout-testday-section" aria-label="Test Day — Protocolli">
      <div class="workout-testday-section__header">
        <span class="workout-testday-section__icon" aria-hidden="true">🏋️</span>
        <div>
          <h3 class="workout-testday-section__title">Test Day Submassimale</h3>
          <p class="workout-testday-section__subtitle">Valutazione forza — ~88-90% 1RM</p>
        </div>
      </div>
      ${noteSessione ? `<p class="workout-testday-section__note">${noteSessione}</p>` : ''}
      <div class="workout-testday-cards">
        ${cardsHtml}
      </div>
    </section>
  `;
}

/**
 * Costruisce l'HTML di una card sessione giornaliera completa.
 * Mostra header (giorno + badge tipo), note sessione opzionali e
 * tabella esercizi con colonne Nome | Serie | Reps | Peso | Recupero.
 * Se il giorno contiene il campo 'protocolli' (Test Day), delega a renderTestDaySection().
 * @param {Object} giorno
 * @returns {string} HTML della card
 */
function renderGiornoCard(giorno) {
  const nomeGiorno  = giorno?.giorno        ?? '—';
  const tipo        = giorno?.tipo          ?? '—';
  const noteSessione = giorno?.note_sessione ?? '';

  // Branch Test Day: se il giorno ha 'protocolli' invece di 'esercizi'
  if (Array.isArray(giorno?.protocolli)) {
    return `
      <article class="workout-giorno-card workout-giorno-card--testday" aria-label="Sessione ${nomeGiorno}">
        <header class="workout-giorno-card__header">
          <h3 class="workout-giorno-card__giorno">${nomeGiorno}</h3>
          <span class="workout-giorno-card__tipo">${tipo}</span>
        </header>
        ${renderTestDaySection(giorno)}
      </article>
    `;
  }

  const esercizi = giorno?.esercizi ?? [];

  // Costruisce le righe della tabella oppure un messaggio empty state
  let tabellaHtml;
  if (esercizi.length > 0) {
    const righe = esercizi.map(e => renderEsercizioRow(e)).join('');
    tabellaHtml = `
      <div class="workout-esercizi-table-wrapper">
        <table class="workout-esercizi-table" aria-label="Esercizi sessione ${nomeGiorno}">
          <thead>
            <tr class="workout-esercizi-table__head">
              <th scope="col" class="workout-esercizi-table__th workout-esercizi-table__th--nome">Esercizio</th>
              <th scope="col" class="workout-esercizi-table__th workout-esercizi-table__th--num">Serie</th>
              <th scope="col" class="workout-esercizi-table__th workout-esercizi-table__th--num">Reps</th>
              <th scope="col" class="workout-esercizi-table__th workout-esercizi-table__th--peso">Peso</th>
              <th scope="col" class="workout-esercizi-table__th workout-esercizi-table__th--num">Recupero</th>
            </tr>
          </thead>
          <tbody>
            ${righe}
          </tbody>
        </table>
      </div>
    `;
  } else {
    tabellaHtml = '<p class="workout-empty">Nessun esercizio per questa sessione.</p>';
  }

  return `
    <article class="workout-giorno-card" aria-label="Sessione ${nomeGiorno}">
      <header class="workout-giorno-card__header">
        <h3 class="workout-giorno-card__giorno">${nomeGiorno}</h3>
        <span class="workout-giorno-card__tipo">${tipo}</span>
      </header>
      ${noteSessione ? `<p class="workout-giorno-card__note">${noteSessione}</p>` : ''}
      ${tabellaHtml}
    </article>
  `;
}

// ── Render principale ─────────────────────────────────────

/**
 * Funzione principale di rendering della pagina allenamento.
 * Popola header scheda, selettore settimane e area dettaglio.
 * Viene chiamata al DOMContentLoaded dopo la fetch.
 * @param {Object} data — dati da workout.json
 */
function renderWorkout(data) {
  // Banner TOS (aggiorna titolo con nome scheda dal JSON)
  renderTOSBanner(data);

  // Header scheda (titolo + obiettivo)
  renderWorkoutHeader(data);

  // Determina la settimana corrente da mostrare di default (1 se non determinabile)
  const settimane = data?.settimane ?? [];
  const durata = data?.meta?.durata_settimane ?? settimane.length ?? 4;
  settimanaAttiva = settimane.length > 0 ? settimane[0].numero : 1;

  // Inizializza selettore settimane
  renderWeekSelector(settimanaAttiva);

  // Mostra il dettaglio della settimana di default
  renderWorkoutDetail(data, settimanaAttiva);

  // Collega i bottoni settimana
  for (let i = 1; i <= durata; i++) {
    const btn = document.getElementById(`week-btn-${i}`);
    if (!btn) continue;
    btn.addEventListener('click', () => {
      settimanaAttiva = i;
      renderWeekSelector(settimanaAttiva);
      renderWorkoutDetail(data, settimanaAttiva);
    });
  }
}

// ── Entry point ───────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const res = await fetch(DATA_PATH_WORKOUT);

    if (!res.ok) {
      throw new Error(`HTTP ${res.status} — ${res.statusText}`);
    }

    workoutData = await res.json();
    renderWorkout(workoutData);

  } catch (e) {
    showWorkoutError('Impossibile caricare i dati della scheda di allenamento.', e);

    // Fallback: mostra struttura vuota senza bloccare la UI
    const detail = document.getElementById('workout-detail');
    if (detail) {
      detail.innerHTML = '<p class="workout-empty">Dati non disponibili. Riprova più tardi.</p>';
    }
  }
});
