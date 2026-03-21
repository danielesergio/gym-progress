/* ============================================================
   plan.js — Logica pagina Piano e Obiettivi
   Daniele Fitness | fetch plan.json + renderPlan()
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  renderPlan();
});

/**
 * Fetch plan.json e popola le tre sezioni della pagina.
 * In questo task layout vengono già resi i placeholder skeleton
 * con le card delle fasi (evidenziando la fase corrente).
 * I component figli (strength-targets-table, ecc.) completeranno
 * il rendering dei container #plan-targets-container e
 * #plan-nutrition-container.
 */
async function renderPlan() {
  try {
    const res = await fetch('data/plan.json');
    if (!res.ok) throw new Error(`HTTP ${res.status} — impossibile caricare plan.json`);
    const planData = await res.json();

    console.log('[plan.js] plan.json caricato correttamente:', planData);

    renderTimeline(planData);
    renderStrengthTargets(planData);
    // I task figli completeranno: renderNutritionStrategy(planData)

  } catch (err) {
    console.error('[plan.js] Errore nel caricamento di plan.json:', err);
    renderError('plan-phase-cards', 'Impossibile caricare il piano. Verifica il file data/plan.json.');
    renderError('plan-targets-container', 'Dati non disponibili.');
    renderError('plan-nutrition-container', 'Dati non disponibili.');
  }
}

/**
 * Renderizza la timeline delle 10 fasi nel container #plan-phase-cards.
 * Ogni fase riceve la classe .plan-phase-card--current se stato === 'corrente'.
 * Le fasi con numero < numero fase corrente vengono marcate come completate.
 * @param {Object} planData — dati completi da plan.json
 */
function renderTimeline(planData) {
  const container = document.getElementById('plan-phase-cards');
  if (!container) return;

  const fasi = planData?.fasi;
  if (!Array.isArray(fasi) || fasi.length === 0) {
    container.innerHTML = '<p class="plan-placeholder">Nessuna fase disponibile.</p>';
    return;
  }

  const currentPhase = fasi.find(f => f.stato === 'corrente');
  const currentPhaseNumber = currentPhase?.numero ?? null;

  // Aggiorna meta header con nome fase corrente
  const headerPhaseEl = document.getElementById('header-current-phase');
  if (headerPhaseEl && currentPhase) {
    headerPhaseEl.textContent = `Fase ${currentPhase.numero} — ${currentPhase.nome}`;
  }

  // Aggiorna meta timeline con fase corrente e periodo totale del programma
  const timelineMetaEl = document.getElementById('plan-timeline-meta');
  if (timelineMetaEl) {
    if (currentPhase) {
      timelineMetaEl.textContent = `52 settimane · mar 2026 — mar 2027 · fase corrente: ${currentPhase.nome}`;
    } else {
      timelineMetaEl.textContent = '52 settimane · mar 2026 — mar 2027';
    }
  }

  // Genera card per ogni fase, passando il numero della fase corrente
  const cards = fasi.map(fase => buildPhaseCard(fase, currentPhaseNumber)).join('');
  container.innerHTML = cards;
}

/**
 * Costruisce l'HTML di una singola card fase.
 * Gestisce tre stati: 'corrente', 'completata' (derivata), 'futura'.
 * Una fase è completata se il suo numero è inferiore al numero della fase corrente.
 * @param {Object} fase — oggetto fase da plan.json
 * @param {number|null} currentPhaseNumber — numero della fase con stato 'corrente'
 * @returns {string} HTML della card
 */
function buildPhaseCard(fase, currentPhaseNumber) {
  const isCurrent = fase.stato === 'corrente';
  const isCompleted = !isCurrent
    && currentPhaseNumber !== null
    && typeof fase.numero === 'number'
    && fase.numero < currentPhaseNumber;

  let cardClass = 'plan-phase-card';
  if (isCurrent) {
    cardClass += ' plan-phase-card--current';
  } else if (isCompleted) {
    cardClass += ' plan-phase-card--completed';
  }

  let badge = '';
  if (isCurrent) {
    badge = '<span class="plan-phase-badge plan-phase-badge--current">Corrente</span>';
  } else if (isCompleted) {
    badge = '<span class="plan-phase-badge plan-phase-badge--completed">Completata</span>';
  }

  const numero = fase.numero ?? '—';
  const nome = fase.nome ?? '—';
  const periodo = fase.periodo_indicativo ?? '—';
  const durata = fase.durata_settimane != null
    ? `${fase.durata_settimane} settimane`
    : '—';

  return `
    <article class="${cardClass}" role="listitem" aria-label="Fase ${numero}: ${nome}">
      <span class="plan-phase-number">Fase ${numero}</span>
      <span class="plan-phase-name">${nome}</span>
      <span class="plan-phase-period">${periodo}</span>
      <span class="plan-phase-duration">${durata}</span>
      ${badge}
    </article>
  `.trim();
}

/**
 * Renderizza la tabella dei target di forza progressivi nel container #plan-targets-container.
 * Mostra i valori attuali (riga "Oggi") e i 4 orizzonti temporali da plan.json.target.
 * La riga "Lungo termine" è visivamente evidenziata.
 * @param {Object} planData — dati completi da plan.json
 */
function renderStrengthTargets(planData) {
  const container = document.getElementById('plan-targets-container');
  if (!container) return;

  const massimali = planData?.massimali_attuali;
  const target = planData?.target;

  if (!Array.isArray(target) || target.length === 0) {
    renderError('plan-targets-container', 'Dati target di forza non disponibili.');
    return;
  }

  const sqActual = massimali?.squat != null ? massimali.squat.toFixed(1) : '—';
  const paActual = massimali?.panca != null ? massimali.panca.toFixed(1) : '—';
  const stActual = massimali?.stacco != null ? massimali.stacco.toFixed(1) : '—';

  const righeTarget = target.map(t => buildStrengthTargetRow(t)).join('');

  const html = `
    <table class="plan-targets-table" role="table" aria-label="Target di forza progressivi — Squat, Panca, Stacco">
      <thead>
        <tr>
          <th scope="col">Orizzonte</th>
          <th scope="col">Squat (kg)</th>
          <th scope="col">Panca (kg)</th>
          <th scope="col">Stacco (kg)</th>
          <th scope="col" class="plan-targets-col-note">Note</th>
        </tr>
      </thead>
      <tbody>
        <tr class="plan-targets-current-row">
          <th scope="row">
            <span class="plan-targets-badge-oggi">Oggi</span>
            Valori attuali
          </th>
          <td>${sqActual}</td>
          <td>${paActual}</td>
          <td>${stActual}</td>
          <td class="plan-targets-note">Stimati (tipo S)</td>
        </tr>
        ${righeTarget}
      </tbody>
    </table>
  `.trim();

  container.innerHTML = html;
}

/**
 * Costruisce una riga HTML per un orizzonte temporale nella tabella target forza.
 * Evidenzia la riga "Lungo termine" con la classe .plan-targets-row-longterm.
 * @param {Object} t — oggetto target da plan.json.target
 * @returns {string} HTML della riga <tr>
 */
function buildStrengthTargetRow(t) {
  const orizzonte = t?.orizzonte ?? '—';
  const data = t?.data ?? '';
  const squat = t?.squat != null ? t.squat : '—';
  const panca = t?.panca != null ? t.panca : '—';
  const stacco = t?.stacco != null ? t.stacco : '—';
  const note = t?.note ?? '—';

  const isLongterm = orizzonte.toLowerCase().includes('lungo termine');
  const rowClass = isLongterm ? ' class="plan-targets-row-longterm"' : '';

  const dataLabel = data ? ` <span class="plan-targets-data">(${data})</span>` : '';

  return `
    <tr${rowClass}>
      <th scope="row">${orizzonte}${dataLabel}</th>
      <td>${squat}</td>
      <td>${panca}</td>
      <td>${stacco}</td>
      <td class="plan-targets-note">${note}</td>
    </tr>
  `.trim();
}

/**
 * Mostra un messaggio di errore in un container.
 * @param {string} containerId — id del container target
 * @param {string} message — testo da mostrare
 */
function renderError(containerId, message) {
  const el = document.getElementById(containerId);
  if (el) {
    el.innerHTML = `<p class="plan-placeholder">${message}</p>`;
  }
}
