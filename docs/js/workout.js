/* ============================================================
   workout.js — Logica pagina Allenamento
   Pattern: (1) costanti, (2) funzioni render, (3) DOMContentLoaded
   ============================================================ */

// ── Costanti ──────────────────────────────────────────────
const DATA_PATH_WORKOUT = 'data/workout.json';

// ── Stato interno ─────────────────────────────────────────
let workoutData   = null;    // oggetto singolo scheda attiva (compatibilità render esistente)
let schedeData    = [];      // array normalizzato di tutte le schede
let settimanaAttiva    = 1;
let schemaAttivoIndex  = 0;
let giornoAttivoIndex  = 0;  // indice (0-based) del giorno attivo nella settimana corrente

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

// ── Utility: normalizzazione dati ─────────────────────────

/**
 * Normalizza il dato letto da workout.json in un array di schede.
 * Se il JSON radice è un oggetto singolo (struttura attuale), lo wrappa in [data].
 * Se è già un array, lo usa direttamente.
 * Questo garantisce compatibilità futura quando Python genererà un array.
 * @param {Object|Array} rawData — dato grezzo da fetch()
 * @returns {Array} array di schede (almeno [])
 */
function normalizzaSchede(rawData) {
  if (!rawData) return [];
  if (Array.isArray(rawData)) return rawData;
  return [rawData];
}

// ── Utility: rilevamento scheda attiva ────────────────────

/**
 * Trova l'indice della scheda da pre-selezionare nell'array delle schede.
 * Algoritmo:
 *   1. Parsa meta.periodo di ogni scheda (formato 'YYYY-MM / YYYY-MM')
 *   2. Se la data odierna è compresa nel periodo (mese incluso), quella scheda è attiva
 *   3. Se nessuna include la data corrente, seleziona quella con end date più recente
 *   4. Fallback sicuro: indice 0
 * @param {Array} schede — array di oggetti scheda
 * @returns {number} indice della scheda attiva
 */
function detectSchedaAttiva(schede) {
  if (!schede || schede.length === 0) return 0;
  if (schede.length === 1) return 0;

  const oggi = new Date();
  const oggiAnno = oggi.getFullYear();
  const oggiMese = oggi.getMonth() + 1; // 1-12

  let indicePiuRecente = 0;
  let maxEndYYYYMM = 0;

  for (let i = 0; i < schede.length; i++) {
    const periodo = schede[i]?.meta?.periodo ?? '';
    const parti = periodo.split('/').map(s => s.trim()); // ['YYYY-MM', 'YYYY-MM']

    if (parti.length < 2) continue;

    // Parsa start: 'YYYY-MM'
    const inizioParts = parti[0].split('-');
    const fineParts   = parti[1].split('-');

    if (inizioParts.length < 2 || fineParts.length < 2) continue;

    const inizioAnno = parseInt(inizioParts[0], 10);
    const inizioMese = parseInt(inizioParts[1], 10);
    const fineAnno   = parseInt(fineParts[0], 10);
    const fineMese   = parseInt(fineParts[1], 10);

    if (isNaN(inizioAnno) || isNaN(inizioMese) || isNaN(fineAnno) || isNaN(fineMese)) continue;

    // Controlla se la data odierna è compresa nel periodo (confronto anno-mese)
    const oggiYYYYMM  = oggiAnno * 100 + oggiMese;
    const inizioYYYYMM = inizioAnno * 100 + inizioMese;
    const fineYYYYMM   = fineAnno * 100 + fineMese;

    if (oggiYYYYMM >= inizioYYYYMM && oggiYYYYMM <= fineYYYYMM) {
      return i; // Scheda con periodo che include oggi → attiva
    }

    // Tieni traccia della scheda con end date più recente
    if (fineYYYYMM > maxEndYYYYMM) {
      maxEndYYYYMM = fineYYYYMM;
      indicePiuRecente = i;
    }
  }

  // Nessuna scheda include oggi: usa quella con periodo più recente
  return indicePiuRecente;
}

// ── Render selettore schede ────────────────────────────────

/**
 * Popola #schema-selector con un bottone per ogni scheda disponibile.
 * Il bottone della scheda attiva riceve classe 'active' e aria-pressed="true".
 * Con una sola scheda, il bottone è presente ma non invita all'interazione.
 * @param {Array}  schede       — array normalizzato di schede
 * @param {number} indiceAttivo — indice scheda pre-selezionata
 */
function renderSchemaSelector(schede, indiceAttivo) {
  const container = document.getElementById('schema-selector');
  if (!container) return;

  if (!schede || schede.length === 0) {
    container.hidden = true;
    return;
  }

  // Con una sola scheda il selettore è visibile ma con classe che lo rende non invasivo
  const solaSingola = schede.length === 1;
  container.classList.toggle('workout-schema-selector--singola', solaSingola);
  container.hidden = false;

  const bttns = schede.map((scheda, i) => {
    const titolo  = scheda?.meta?.titolo  ?? '—';
    const periodo = scheda?.meta?.periodo ?? '—';
    const isActive = i === indiceAttivo;

    return `
      <button
        type="button"
        class="workout-schema-btn${isActive ? ' active' : ''}"
        data-schema-index="${i}"
        aria-pressed="${isActive ? 'true' : 'false'}"
        aria-label="Scheda: ${titolo}, periodo ${periodo}"
        ${solaSingola ? 'aria-disabled="true"' : ''}>
        <span class="workout-schema-btn__nome">${titolo}</span>
        <span class="workout-schema-btn__periodo">${periodo}</span>
      </button>
    `;
  });

  container.innerHTML = bttns.join('');

  // Collega i click solo se ci sono più schede
  if (!solaSingola) {
    container.querySelectorAll('.workout-schema-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.schemaIndex, 10);
        if (!isNaN(idx) && idx !== schemaAttivoIndex) {
          selectSchema(schede, idx);
        }
      });
    });
  }
}

/**
 * Seleziona una scheda per indice e aggiorna tutta la UI:
 * header della pagina, selettore bottoni scheda, selettore settimane, dettaglio.
 * @param {Array}  schede — array normalizzato di schede
 * @param {number} indice — indice della scheda da attivare
 */
function selectSchema(schede, indice) {
  if (!schede || indice < 0 || indice >= schede.length) return;

  schemaAttivoIndex = indice;
  workoutData = schede[indice];

  // Aggiorna stato bottoni selettore scheda
  const selector = document.getElementById('schema-selector');
  if (selector) {
    selector.querySelectorAll('.workout-schema-btn').forEach((btn, i) => {
      const isActive = i === indice;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
  }

  // Re-render banner TOS con nuova scheda
  renderTOSBanner(workoutData);

  // Re-render header scheda (aggiorna anche #header-workout-period)
  renderWorkoutHeader(workoutData);

  // Reset settimana al numero iniziale della nuova scheda
  const settimane = workoutData?.settimane ?? [];
  settimanaAttiva = settimane.length > 0 ? settimane[0].numero : 1;

  // Ri-collega i bottoni settimana alla nuova scheda
  aggiornaSelezioneSettimane(workoutData);
}

/**
 * Aggiorna il selettore settimane in base alla scheda corrente:
 * - Genera i bottoni dinamicamente via renderWeekSelector() leggendo settimane[]
 * - Collega event delegation sul container #week-selector (via cloneNode)
 * - Resetta giornoAttivoIndex = 0 e ri-renderizza selettore giorni + dettaglio giorno singolo
 * Non usa loop fissi 1..4: itera su settimane.length reale.
 * @param {Object} data — scheda workout attiva
 */
function aggiornaSelezioneSettimane(data) {
  const settimane = data?.settimane ?? [];

  // Reset giorno al primo della settimana
  giornoAttivoIndex = 0;

  // Genera i bottoni settimana dinamicamente (N bottoni = N settimane nel JSON)
  renderWeekSelector(settimane, settimanaAttiva);

  // Recupera i giorni della settimana attiva per il selettore giorni
  const settimanaCorrente = settimane.find(s => s.numero === settimanaAttiva) ?? null;
  const giorniCorrente = settimanaCorrente?.giorni ?? [];

  // Render selettore giorni + dettaglio giorno singolo
  renderDaySelector(giorniCorrente, data, settimanaAttiva);
  renderGiornoSingolo(data, settimanaAttiva, giornoAttivoIndex);

  // Collega event delegation su #week-selector
  // cloneNode rimuove eventuali listener precedenti
  const container = document.getElementById('week-selector');
  if (!container) return;

  const newContainer = container.cloneNode(true);
  container.parentNode.replaceChild(newContainer, container);

  newContainer.addEventListener('click', (e) => {
    const btn = e.target.closest('.week-btn');
    if (!btn) return;
    const numeroSettimana = parseInt(btn.dataset.week, 10);
    if (isNaN(numeroSettimana) || numeroSettimana === settimanaAttiva) return;

    settimanaAttiva = numeroSettimana;
    giornoAttivoIndex = 0;

    // Aggiorna stato visivo bottoni settimana
    newContainer.querySelectorAll('.week-btn').forEach(b => {
      const num = parseInt(b.dataset.week, 10);
      const isActive = num === settimanaAttiva;
      b.classList.toggle('active', isActive);
      b.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });

    // Recupera giorni della nuova settimana
    const settimanaTarget = (data?.settimane ?? []).find(s => s.numero === settimanaAttiva) ?? null;
    const giorniTarget = settimanaTarget?.giorni ?? [];

    renderDaySelector(giorniTarget, data, settimanaAttiva);
    renderGiornoSingolo(data, settimanaAttiva, giornoAttivoIndex);
  });
}

// ── Render banner TOS ─────────────────────────────────────

/**
 * Rileva se la scheda segnala un infortunio attivo e aggiorna il banner #tos-alert-banner:
 * — Se nessuna nota in note_generali[] inizia con "INFORTUNIO" (case-insensitive),
 *   il banner riceve l'attributo "hidden" e non viene mostrato.
 * — Se almeno una nota indica un infortunio attivo:
 *   · rimuove "hidden" dal banner;
 *   · popola .workout-tos-banner__title con il titolo del protocollo;
 *   · popola .workout-tos-banner__list con la lista degli esercizi esclusi (estratta dalla nota);
 *   · popola .workout-tos-banner__safety con il messaggio di stop (se presente).
 * Non lancia eccezioni: gestisce array assente, vuoto o privo di note rilevanti.
 * @param {Object} data — dati da workout.json (scheda attiva)
 */
function renderTOSBanner(data) {
  const banner   = document.getElementById('tos-alert-banner');
  if (!banner) return;

  const noteGenerali = data?.note_generali ?? [];

  // Cerca la nota di infortunio (inizia con "INFORTUNIO", case-insensitive)
  const notaInfortunio = noteGenerali.find(
    n => typeof n === 'string' && n.trim().toUpperCase().startsWith('INFORTUNIO')
  ) ?? null;

  // Nessun infortunio attivo → nascondi banner e svuota i campi
  if (!notaInfortunio) {
    banner.setAttribute('hidden', '');
    const titleEl  = banner.querySelector('.workout-tos-banner__title');
    const listEl   = banner.querySelector('.workout-tos-banner__list');
    const safetyEl = banner.querySelector('.workout-tos-banner__safety');
    if (titleEl)  titleEl.textContent  = '';
    if (listEl)   listEl.innerHTML     = '';
    if (safetyEl) safetyEl.innerHTML   = '';
    return;
  }

  // ── Infortunio attivo: estrai i dati dalla nota ──────────────

  // Titolo: testo prima del primo punto (tutto ciò che precede ":" nel segmento iniziale)
  // Esempio: "INFORTUNIO TOS ATTIVO: sono esclusi TUTTI gli esercizi..."
  const colonPos   = notaInfortunio.indexOf(':');
  const titoloRaw  = colonPos > -1
    ? notaInfortunio.substring(0, colonPos).trim()   // "INFORTUNIO TOS ATTIVO"
    : notaInfortunio.split('.')[0].trim();

  // Testo dopo i due punti (contiene la lista esercizi esclusi)
  const testoRestrizioni = colonPos > -1
    ? notaInfortunio.substring(colonPos + 1).trim()
    : '';

  // Estrai singoli esercizi: cerca tutto ciò che segue "esclusi" fino al punto finale.
  // La nota contiene una lista separata da virgole e "." finale.
  // Strategia: prendi il testo dopo eventuale "esclusi" (o tutto il testo restrizioni),
  // poi spezza per virgola + ". Non fare" (stop alla frase finale).
  let eserciziVietati = [];
  const matchEsclusi = testoRestrizioni.match(/(?:esclusi\s+(?:TUTTI\s+)?(?:gli\s+esercizi\s+che\s+)?)?(.+)/i);
  if (matchEsclusi) {
    const parte = matchEsclusi[1] ?? '';
    // Rimuovi la frase "Non fare eccezioni." e simili che seguono
    const partePulita = parte.split(/\.\s*(?:Non\s+fare|Stop|Ferma)/i)[0].trim();
    // Spezza per virgola e pulisci
    eserciziVietati = partePulita
      .split(',')
      .map(s => s.trim().replace(/^(TUTTI\s+gli\s+esercizi\s+che\s+coinvolgono\s+)?/i, '').trim())
      .filter(s => s.length > 0);
  }

  // Cerca la nota di stop immediato (inizia con "Segnale di stop")
  const notaStop = noteGenerali.find(
    n => typeof n === 'string' && /segnale\s+di\s+stop/i.test(n)
  ) ?? null;

  // ── Popola il DOM ────────────────────────────────────────────

  const titleEl  = banner.querySelector('.workout-tos-banner__title');
  const listEl   = banner.querySelector('.workout-tos-banner__list');
  const safetyEl = banner.querySelector('.workout-tos-banner__safety');

  if (titleEl) {
    titleEl.textContent = titoloRaw;
  }

  if (listEl) {
    if (eserciziVietati.length > 0) {
      listEl.innerHTML = eserciziVietati
        .map(e => `<li>${e}</li>`)
        .join('');
    } else {
      // Fallback: mostra il testo restrizioni come item singolo se il parsing non ha trovato lista
      listEl.innerHTML = testoRestrizioni
        ? `<li>${testoRestrizioni}</li>`
        : '';
    }
  }

  if (safetyEl) {
    if (notaStop) {
      // Evidenzia "Stop immediato" o "Segnale di stop" con <strong>
      const testoStop = notaStop.replace(
        /^(segnale\s+di\s+stop\s+immediato\s*:?\s*)/i,
        '<strong>Stop immediato</strong>: '
      );
      safetyEl.innerHTML = testoStop;
    } else {
      safetyEl.innerHTML = '';
    }
  }

  // Mostra il banner
  banner.removeAttribute('hidden');
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
 * Genera dinamicamente i bottoni settimana nel container #week-selector
 * leggendo l'array settimane[] fornito.
 * Il bottone della settimana attiva riceve classe 'active' e aria-pressed="true".
 * Usa innerHTML per generare tutti i bottoni in base al numero reale di settimane.
 * @param {Array}  settimane      — array di oggetti settimana (ciascuno con campo .numero)
 * @param {number} numeroSettimana — numero della settimana attiva (es. 1, 2, …N)
 */
function renderWeekSelector(settimane, numeroSettimana) {
  const container = document.getElementById('week-selector');
  if (!container) return;

  if (!settimane || settimane.length === 0) {
    container.innerHTML = '';
    return;
  }

  const bttns = settimane.map(settimana => {
    const num = settimana?.numero ?? 0;
    const isActive = num === numeroSettimana;
    return `<button
      type="button"
      class="week-btn${isActive ? ' active' : ''}"
      id="week-btn-${num}"
      data-week="${num}"
      aria-pressed="${isActive ? 'true' : 'false'}">S${num}</button>`;
  });

  container.innerHTML = bttns.join('');
}

// ── Render selettore giorni ───────────────────────────────

/**
 * Popola #day-selector con un bottone per ogni giorno della settimana attiva.
 * Nasconde il container se la settimana ha un solo giorno (o nessuno).
 * Usa event delegation: un unico listener sul container.
 * @param {Array}  giorni    — array di oggetti giorno dalla settimana attiva
 * @param {Object} data      — dati workout.json (scheda attiva)
 * @param {number} numeroSettimana — numero settimana attiva
 */
function renderDaySelector(giorni, data, numeroSettimana) {
  const container = document.getElementById('day-selector');
  if (!container) return;

  // Nasconde il selettore se c'è un solo giorno o nessuno
  if (!giorni || giorni.length <= 1) {
    container.hidden = true;
    container.innerHTML = '';
    return;
  }

  container.hidden = false;

  const bttns = giorni.map((giorno, i) => {
    const etichetta = giorno?.giorno ?? `Giorno ${i + 1}`;
    const isActive = i === giornoAttivoIndex;
    return `<button
      type="button"
      class="day-btn${isActive ? ' active' : ''}"
      data-day-index="${i}"
      aria-pressed="${isActive ? 'true' : 'false'}"
      aria-label="Giorno ${etichetta}">${etichetta}</button>`;
  });

  container.innerHTML = bttns.join('');

  // Event delegation: un solo listener sul container
  // Rimuove eventuali listener precedenti clonando il nodo
  const newContainer = container.cloneNode(true);
  container.parentNode.replaceChild(newContainer, container);

  newContainer.addEventListener('click', (e) => {
    const btn = e.target.closest('.day-btn');
    if (!btn) return;
    const idx = parseInt(btn.dataset.dayIndex, 10);
    if (isNaN(idx) || idx === giornoAttivoIndex) return;

    giornoAttivoIndex = idx;

    // Aggiorna stato visivo bottoni
    newContainer.querySelectorAll('.day-btn').forEach((b, i) => {
      const isActive = i === giornoAttivoIndex;
      b.classList.toggle('active', isActive);
      b.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });

    // Re-render dettaglio con il nuovo giorno
    renderGiornoSingolo(data, numeroSettimana, giornoAttivoIndex);
  });
}

/**
 * Popola #workout-detail con il riepilogo della settimana + la card
 * del singolo giorno all'indice giornoIndex nell'array giorni.
 * Sostituisce il vecchio renderWorkoutDetail() per la logica a giorno singolo.
 * @param {Object} data            — dati workout.json
 * @param {number} numeroSettimana — 1..N
 * @param {number} giornoIndex     — indice 0-based del giorno da mostrare
 */
function renderGiornoSingolo(data, numeroSettimana, giornoIndex) {
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

  if (giorni.length === 0) {
    container.innerHTML = `
      <div class="workout-week-summary">
        <p class="workout-week-summary__intensita">
          <span class="workout-week-summary__label">Intensità target:</span>
          <span class="workout-week-summary__value">${intensita}</span>
        </p>
        ${note ? `<p class="workout-week-summary__note">${note}</p>` : ''}
      </div>
      <p class="workout-empty">Nessuna sessione per questa settimana.</p>
    `;
    return;
  }

  // Clamp dell'indice per sicurezza
  const idx = Math.min(Math.max(giornoIndex, 0), giorni.length - 1);
  const giornoCard = renderGiornoCard(giorni[idx]);

  container.innerHTML = `
    <div class="workout-week-summary">
      <p class="workout-week-summary__intensita">
        <span class="workout-week-summary__label">Intensità target:</span>
        <span class="workout-week-summary__value">${intensita}</span>
      </p>
      ${note ? `<p class="workout-week-summary__note">${note}</p>` : ''}
    </div>
    <div class="workout-giorni">
      ${giornoCard}
    </div>
  `;
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
 * Normalizza i dati in array, rileva la scheda attiva, renderizza il selettore schede,
 * poi delega a selectSchema() per l'header, il selettore settimane e il dettaglio.
 * @param {Object|Array} rawData — dati grezzi da workout.json
 */
function renderWorkout(rawData) {
  // 1. Normalizza in array (wrap se oggetto singolo)
  schedeData = normalizzaSchede(rawData);

  if (schedeData.length === 0) {
    showWorkoutError('Nessuna scheda disponibile nei dati.');
    return;
  }

  // 2. Determina quale scheda pre-selezionare
  schemaAttivoIndex = detectSchedaAttiva(schedeData);

  // 3. Render selettore schede (#schema-selector)
  renderSchemaSelector(schedeData, schemaAttivoIndex);

  // 4. Render scheda attiva (header + settimane + dettaglio)
  selectSchema(schedeData, schemaAttivoIndex);
}

// ── Entry point ───────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const res = await fetch(DATA_PATH_WORKOUT);

    if (!res.ok) {
      throw new Error(`HTTP ${res.status} — ${res.statusText}`);
    }

    const rawData = await res.json();
    renderWorkout(rawData);

  } catch (e) {
    showWorkoutError('Impossibile caricare i dati della scheda di allenamento.', e);

    // Fallback: mostra struttura vuota senza bloccare la UI
    const detail = document.getElementById('workout-detail');
    if (detail) {
      detail.innerHTML = '<p class="workout-empty">Dati non disponibili. Riprova più tardi.</p>';
    }
  }
});
