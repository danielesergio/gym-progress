/* ============================================================
   dashboard.js — Logica pagina Dashboard
   Pattern: (1) costanti, (2) funzioni render, (3) DOMContentLoaded
   ============================================================ */

// ── Costanti ──────────────────────────────────────────────
const DATA_PATH_MEASUREMENTS = 'data/measurements.json';
const DATA_PATH_PLAN         = 'data/plan.json';
const DATA_PATH_WORKOUT      = 'data/workout.json';
const ATHLETE_NAME           = 'Daniele';

// ── Utility ───────────────────────────────────────────────

/**
 * Formatta una data ISO (YYYY-MM-DD) in italiano (es. "20 mar 2026").
 * Restituisce '—' se la stringa è nulla o non parsabile.
 */
function formatDateIt(isoString) {
  if (!isoString) return '—';
  const date = new Date(isoString + 'T00:00:00');
  if (isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('it-IT', {
    day:   '2-digit',
    month: 'short',
    year:  'numeric'
  });
}

/**
 * Mostra un messaggio di errore in un container.
 * Non usa alert() — scrive nel DOM e logga in console.
 * @param {HTMLElement} container
 * @param {Error} error
 */
function showError(container, error) {
  if (!container) return;
  container.innerHTML = '<p class="error-message">Dati non disponibili</p>';
  console.error('[dashboard.js]', error);
}

// ── Render header: data ultima misurazione ────────────────

/**
 * Aggiorna #header-last-date con la data dell'ultima misurazione.
 * @param {Array} measurements — array di oggetti misurazione
 */
function renderHeaderDate(measurements) {
  const el = document.getElementById('header-last-date');
  if (!el) return;
  const last = measurements?.[measurements.length - 1];
  el.textContent = last?.data ? formatDateIt(last.data) : '—';
}

// ── Render Card Stato Atleta ──────────────────────────────

/**
 * Popola #card-stato con i dati corporei dell'ultima misurazione
 * e la fase corrente del programma.
 * @param {Object|null|undefined} last  — ultima misurazione
 * @param {Object|null|undefined} plan  — dati piano (fasi)
 */
function renderAthleteStatusCard(last, plan) {
  const container = document.getElementById('card-stato');
  if (!container) return;

  // Fase corrente da plan.fasi: cerca stato === 'corrente',
  // con fallback alla prima fase non completata, poi alla prima fase
  const fasi = plan?.fasi ?? [];
  const currentPhaseObj =
    fasi.find(f => f.stato === 'corrente') ??
    fasi.find(f => f.stato !== 'completata') ??
    fasi[0] ??
    null;
  const currentPhase = currentPhaseObj?.nome ?? null;

  // Badge fase: mostrato solo se disponibile
  const phaseBadgeHtml = currentPhase
    ? `<span class="status-card__phase-badge">${currentPhase}</span>`
    : '';

  // Valori metriche con fallback '—'
  const peso      = last?.peso_kg       != null ? `${last.peso_kg.toFixed(1)}<span class="status-card__unit">kg</span>`     : '—';
  const bf        = last?.body_fat_pct  != null ? `${last.body_fat_pct.toFixed(1)}<span class="status-card__unit">%</span>`  : '—';
  const massaMagra = last?.massa_magra_kg != null ? `${last.massa_magra_kg.toFixed(1)}<span class="status-card__unit">kg</span>` : '—';
  const ffmi      = last?.ffmi_adj      != null ? last.ffmi_adj.toFixed(1)                                                   : '—';
  const tdee      = last?.tdee_kcal     != null ? `${Math.round(last.tdee_kcal)}<span class="status-card__unit">kcal</span>` : '—';

  container.innerHTML = `
    <h2 class="dashboard-card__title">Stato Atleta</h2>
    ${phaseBadgeHtml}
    <div class="status-card__grid">
      <div class="status-card__metric">
        <span class="status-card__label">Peso</span>
        <span class="status-card__value">${peso}</span>
      </div>
      <div class="status-card__metric">
        <span class="status-card__label">Body Fat</span>
        <span class="status-card__value">${bf}</span>
      </div>
      <div class="status-card__metric">
        <span class="status-card__label">Massa Magra</span>
        <span class="status-card__value">${massaMagra}</span>
      </div>
      <div class="status-card__metric">
        <span class="status-card__label">FFMI</span>
        <span class="status-card__value">${ffmi}</span>
      </div>
      <div class="status-card__metric">
        <span class="status-card__label">TDEE</span>
        <span class="status-card__value">${tdee}</span>
      </div>
    </div>
  `;
}

// ── Render Card Massimali Big 3 ───────────────────────────

/**
 * Popola #card-massimali con i massimali correnti (Squat, Panca, Stacco),
 * il target a 12 mesi per ciascuno e il badge tipo (Stimato / Reale).
 * @param {Object|null|undefined} last  — ultima misurazione
 * @param {Object|null|undefined} plan  — dati piano (target)
 */
function renderStrengthSummaryCard(last, plan) {
  const container = document.getElementById('card-massimali');
  if (!container) return;

  // Badge tipo: preferisce i campi per-esercizio (squat/panca/stacco_1rm_tipo).
  // Logica a cascata:
  //   1) se almeno uno tra i tre campi per-esercizio è 'S' → badge 'Stimato'
  //   2) se tutti e tre i campi per-esercizio sono 'R'     → badge 'Reale'
  //   3) se tutti e tre sono assenti → fallback su massimali_tipo (record legacy)
  //   4) se anche massimali_tipo è assente                 → nessun badge
  const hasPerEsercizioTipo = last?.squat_1rm_tipo || last?.panca_1rm_tipo || last?.stacco_1rm_tipo;
  let tipoRaw;
  if (hasPerEsercizioTipo) {
    const isStimato = last?.squat_1rm_tipo === 'S' || last?.panca_1rm_tipo === 'S' || last?.stacco_1rm_tipo === 'S';
    tipoRaw = isStimato ? 'S' : 'R';
  } else {
    tipoRaw = last?.massimali_tipo ?? null;
  }
  const tipoLabel = tipoRaw === 'S' ? 'Stimato' : tipoRaw === 'R' ? 'Reale' : null;
  const tipoClass = tipoRaw === 'S' ? 'strength-card__tipo-badge--stimato' : 'strength-card__tipo-badge--reale';
  const tipoBadgeHtml = tipoLabel
    ? `<span class="strength-card__tipo-badge ${tipoClass}">${tipoLabel}</span>`
    : '';

  // Target 12 mesi: cerca il primo oggetto con orizzonte '12 mesi'
  const target12 = (plan?.target ?? []).find(t => t.orizzonte === '12 mesi') ?? null;

  // Dati Big 3 — fallback '—' per valori null/undefined
  const exercises = [
    {
      nome:   'Squat',
      valore: last?.squat_1rm   != null ? last.squat_1rm   : null,
      target: target12?.squat   != null ? target12.squat   : null,
    },
    {
      nome:   'Panca',
      valore: last?.panca_1rm   != null ? last.panca_1rm   : null,
      target: target12?.panca   != null ? target12.panca   : null,
    },
    {
      nome:   'Stacco',
      valore: last?.stacco_1rm  != null ? last.stacco_1rm  : null,
      target: target12?.stacco  != null ? target12.stacco  : null,
    },
  ];

  const exercisesHtml = exercises.map(ex => {
    const valoreStr = ex.valore != null ? `${ex.valore.toFixed(1)}<span class="strength-card__unit">kg</span>` : '—';
    const targetStr = ex.target != null ? `→ ${ex.target.toFixed(1)} kg` : '—';
    return `
      <div class="strength-card__exercise">
        <span class="strength-card__name">${ex.nome}</span>
        <span class="strength-card__value">${valoreStr}</span>
        <span class="strength-card__target">${targetStr}</span>
      </div>`;
  }).join('');

  container.innerHTML = `
    <h2 class="dashboard-card__title">Massimali Big 3</h2>
    ${tipoBadgeHtml}
    <div class="strength-card__list">
      ${exercisesHtml}
    </div>
  `;
}

// ── Render Card Fase Corrente del Programma ───────────────

/**
 * Popola #card-fase con il nome, numero e periodo della fase attiva,
 * l'obiettivo sintetico e una barra di progressione settimanale CSS pura.
 * La settimana corrente X è calcolata dinamicamente da plan.meta.data_aggiornamento
 * e dalle fasi precedenti. Il totale Y è la somma delle durata_settimane di tutte le fasi.
 * @param {Object|null|undefined} plan — dati piano (fasi[])
 */
function renderProgramPhaseCard(plan) {
  const container = document.getElementById('card-fase');
  if (!container) return;

  // Fallback dati non disponibili
  const fasi = plan?.fasi ?? [];
  if (!plan || fasi.length === 0) {
    container.innerHTML = '<p class="error-message">Dati non disponibili</p>';
    return;
  }

  // Fase corrente: stato === 'corrente', poi prima non completata, poi fasi[0]
  const faseCorrente =
    fasi.find(f => f.stato === 'corrente') ??
    fasi.find(f => f.stato !== 'completata') ??
    fasi[0];

  // Campi con fallback '—'
  const numero  = faseCorrente?.numero  != null ? `Fase ${faseCorrente.numero}` : '—';
  const nome    = faseCorrente?.nome    ?? '—';
  const periodo = faseCorrente?.periodo_indicativo ?? '—';
  const obiettivo = faseCorrente?.obiettivo ?? '—';

  // Calcolo totale settimane: somma dinamica da tutte le fasi del piano
  const totaleSettimane = fasi.reduce((acc, f) => acc + (f.durata_settimane ?? 0), 0);

  // Indice della fase corrente nell'array (per calcolare le settimane precedenti)
  const indiceFaseCorrente = fasi.indexOf(faseCorrente);

  // Settimane già trascorse nelle fasi precedenti alla fase corrente
  const settimanePreFase = fasi
    .slice(0, indiceFaseCorrente < 0 ? 0 : indiceFaseCorrente)
    .reduce((acc, f) => acc + (f.durata_settimane ?? 0), 0);

  // Data di inizio programma da meta.data_aggiornamento — fallback a oggi se assente/non parsabile
  const oggi = new Date();
  let dataInizioProgramma = oggi;
  const dataAggiornamentoStr = plan?.meta?.data_aggiornamento;
  if (dataAggiornamentoStr) {
    const parsed = new Date(dataAggiornamentoStr + 'T00:00:00');
    if (!isNaN(parsed.getTime())) {
      dataInizioProgramma = parsed;
    }
  }

  // Data di inizio della fase corrente = inizio programma + settimane delle fasi precedenti
  const MS_PER_SETTIMANA = 7 * 24 * 3600 * 1000;
  const dataInizioFaseCorrente = new Date(dataInizioProgramma.getTime() + settimanePreFase * MS_PER_SETTIMANA);

  // Settimana corrente nella fase: giorni trascorsi / 7, arrotondato per eccesso, clampato [1, durata fase]
  const durataProgramma = faseCorrente?.durata_settimane ?? totaleSettimane;
  const settCorrenteFase = Math.max(1, Math.ceil((oggi - dataInizioFaseCorrente) / MS_PER_SETTIMANA));
  const settCorrente = Math.min(totaleSettimane, settimanePreFase + Math.min(settCorrenteFase, durataProgramma));

  const percentuale = Math.min(100, Math.round(settCorrente / (totaleSettimane || 1) * 100));

  container.innerHTML = `
    <h2 class="dashboard-card__title">Fase Corrente</h2>
    <div class="phase-card__header">
      <span class="phase-card__number">${numero}</span>
      <span class="phase-card__name">${nome}</span>
    </div>
    <p class="phase-card__period">${periodo}</p>
    <p class="phase-card__objective">${obiettivo}</p>
    <div class="phase-card__progress-bar" aria-label="Progressione settimana ${settCorrente} di ${totaleSettimane}">
      <div class="phase-card__progress-fill" style="width: ${percentuale}%"></div>
    </div>
    <p class="phase-card__progress-label">Settimana ${settCorrente} di ${totaleSettimane}</p>
  `;
}

// ── Render Card Target Progressivi di Forza ───────────────

/**
 * Popola #card-target con la tabella dei target futuri di forza:
 * 3 mesi, 6 mesi, 12 mesi e lungo termine (2-5 anni).
 * Il target lungo termine è evidenziato con stile visivo distinto.
 * @param {Object|null|undefined} plan — dati piano (target[])
 */
function renderTargetsCard(plan) {
  const container = document.getElementById('card-target');
  if (!container) return;

  // Fallback: dati non disponibili
  if (!plan || !plan.target || plan.target.length === 0) {
    container.innerHTML = '<p class="error-message">Dati non disponibili</p>';
    return;
  }

  const targets = plan.target;

  // Costruisce le celle di intestazione (orizzonti)
  const headCellsHtml = targets.map((t, idx) => {
    const isLongterm = idx === targets.length - 1;
    const colClass = isLongterm ? 'targets-card__th targets-card__th--longterm' : 'targets-card__th';
    const badgeHtml = isLongterm ? '<span class="targets-card__goal-badge">🎯 Obiettivo</span>' : '';
    const dataHtml = t.data ? `<span class="targets-card__horizon-date">${t.data}</span>` : '';
    return `<th class="${colClass}" scope="col">${t.orizzonte ?? '—'}${dataHtml}${badgeHtml}</th>`;
  }).join('');

  // Righe per i 3 esercizi
  const exercises = [
    { nome: 'Squat',  campo: 'squat'  },
    { nome: 'Panca',  campo: 'panca'  },
    { nome: 'Stacco', campo: 'stacco' },
  ];

  const bodyRowsHtml = exercises.map(ex => {
    const cellsHtml = targets.map((t, tidx) => {
      const isLongterm = tidx === targets.length - 1;
      const val = t[ex.campo];
      let valStr = '—';
      if (val != null) {
        valStr = isLongterm
          ? `${val}<span class="targets-card__unit">kg</span>`
          : `${val.toFixed(1)}<span class="targets-card__unit">kg</span>`;
      }
      const cellClass = isLongterm ? 'targets-card__td targets-card__td--longterm' : 'targets-card__td';
      return `<td class="${cellClass}">${valStr}</td>`;
    }).join('');

    return `
      <tr class="targets-card__row">
        <th class="targets-card__exercise-label" scope="row">${ex.nome}</th>
        ${cellsHtml}
      </tr>`;
  }).join('');

  container.innerHTML = `
    <h2 class="dashboard-card__title">Target di Forza</h2>
    <div class="targets-card__table-wrapper">
      <table class="targets-card__table">
        <thead>
          <tr>
            <th class="targets-card__th targets-card__th--label" scope="col"></th>
            ${headCellsHtml}
          </tr>
        </thead>
        <tbody>
          ${bodyRowsHtml}
        </tbody>
      </table>
    </div>
  `;
}

// ── Render Dashboard ──────────────────────────────────────

/**
 * Renderizza il contenuto principale della dashboard.
 * (Le card di dettaglio saranno implementate nei task successivi)
 * @param {Array}  measurements
 * @param {Object} plan
 * @param {Object} workout
 */
function renderDashboard(measurements, plan, workout) {
  renderHeaderDate(measurements);

  const container = document.querySelector('#page-content .container');
  if (!container) return;

  const last = measurements?.[measurements.length - 1];

  // Placeholder: il contenuto delle card sarà completato
  // dal task successivo (dashboard-cards). Il contenitore
  // viene predisposto con gli id attesi.
  container.innerHTML = `
    <div id="dashboard-grid">
      <div id="card-stato" class="dashboard-card" aria-label="Stato attuale atleta">
        <!-- card-stato: verrà popolata dal task dashboard-cards -->
      </div>
      <div id="card-massimali" class="dashboard-card" aria-label="Massimali Big 3">
        <!-- card-massimali: verrà popolata dal task dashboard-cards -->
      </div>
      <div id="card-fase" class="dashboard-card" aria-label="Fase corrente programma">
        <!-- card-fase: verrà popolata dal task dashboard-cards -->
      </div>
      <div id="card-target" class="dashboard-card" aria-label="Target progressivi">
        <!-- card-target: verrà popolata dal task dashboard-cards -->
      </div>
    </div>
  `;

  // Popola card-stato con dati corporei e fase corrente
  renderAthleteStatusCard(last, plan);

  // Popola card-massimali con i massimali Big 3 e target 12 mesi
  renderStrengthSummaryCard(last, plan);

  // Popola card-fase con la fase corrente del programma e la barra di progressione
  renderProgramPhaseCard(plan);

  // Popola card-target con i target progressivi di forza a 3/6/12 mesi e lungo termine
  renderTargetsCard(plan);
}

// ── Entry point ───────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  const pageContent = document.getElementById('page-content');

  // Fetch parallelo dei 3 JSON necessari alla dashboard
  try {
    const [resMeasurements, resPlan, resWorkout] = await Promise.all([
      fetch(DATA_PATH_MEASUREMENTS),
      fetch(DATA_PATH_PLAN),
      fetch(DATA_PATH_WORKOUT)
    ]);

    // measurements è il più critico: gestito separatamente
    let measurements = [];
    if (resMeasurements.ok) {
      measurements = await resMeasurements.json();
    } else {
      console.error('[dashboard.js] measurements.json non disponibile:', resMeasurements.status);
    }

    let plan = null;
    if (resPlan.ok) {
      plan = await resPlan.json();
    } else {
      console.error('[dashboard.js] plan.json non disponibile:', resPlan.status);
    }

    let workout = null;
    if (resWorkout.ok) {
      workout = await resWorkout.json();
    } else {
      console.error('[dashboard.js] workout.json non disponibile:', resWorkout.status);
    }

    renderDashboard(measurements, plan, workout);

  } catch (e) {
    // Almeno l'header mostra il fallback '—'
    const headerDate = document.getElementById('header-last-date');
    if (headerDate) headerDate.textContent = '—';
    showError(pageContent, e);
  }
});
