/* ============================================================
   plan.js — Logica pagina Piano e Obiettivi
   Daniele Fitness | fetch plan.json + renderPlan()
   ============================================================ */

// ── Stato dettaglio mesociclo aperto ──────────────────────────
let currentOpenMesoNumber = null;

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
    renderNutritionStrategy(planData);

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

  // Costruisce mappa mesocicli da macrocicli e attacca listener click delegato
  const mesoMap = buildMesoMap(planData);
  attachTimelineClickListener(container, mesoMap);
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
    <article class="${cardClass} plan-phase-card--clickable"
             role="button"
             tabindex="0"
             aria-expanded="false"
             aria-controls="plan-meso-detail-panel"
             data-meso-id="${numero}"
             aria-label="Fase ${numero}: ${nome} — clicca per dettagli">
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

// ══════════════════════════════════════════
// DETTAGLIO MESOCICLO — funzioni espansione
// ══════════════════════════════════════════

/**
 * Costruisce una mappa numerica dei mesocicli da planData.macrocicli[n].mesocicli[m].
 * La chiave è il numero (int) del mesociclo per lookup rapido nel click handler.
 * @param {Object} planData — dati completi da plan.json
 * @returns {Map<number, Object>} mappa numero → oggetto mesociclo
 */
function buildMesoMap(planData) {
  const mesoMap = new Map();
  const macrocicli = planData?.macrocicli;
  if (!Array.isArray(macrocicli)) return mesoMap;

  for (const macro of macrocicli) {
    const mesocicli = macro?.mesocicli;
    if (!Array.isArray(mesocicli)) continue;
    for (const meso of mesocicli) {
      if (meso?.numero != null) {
        mesoMap.set(meso.numero, meso);
      }
    }
  }
  return mesoMap;
}

/**
 * Costruisce l'HTML del pannello dettaglio per un mesociclo.
 * Mostra: nome, tipo, fase nutrizionale, durata, obiettivo, metodologia,
 * note, criteri di avanzamento (lista), incrocio stimolo/ambiente (opzionale).
 * @param {Object} meso — oggetto mesociclo da planData.macrocicli[n].mesocicli[m]
 * @returns {string} HTML del pannello dettaglio
 */
function renderMesocicloDetail(meso) {
  const numero = meso?.numero ?? '—';
  const nome = meso?.nome ?? '—';
  const tipo = meso?.tipo ?? '—';
  const faseNutrizionale = meso?.fase_nutrizionale ?? '—';
  const durata = meso?.durata_settimane != null ? `${meso.durata_settimane} settimane` : '—';
  const obiettivo = meso?.obiettivo ?? '—';
  const metodologia = meso?.metodologia ?? '—';
  const note = meso?.note ?? '—';
  const criteriRaw = meso?.criteri_avanzamento ?? '';
  const incrocioPossibile = meso?.incrocio_stimolo_ambiente ?? null;

  // Split criteri su '. ' e filtra stringhe vuote
  const criteriaList = criteriRaw
    ? criteriRaw.split('. ').filter(s => s.trim().length > 0).map(s => {
        const trimmed = s.trim();
        // Aggiunge punto finale se mancante
        return trimmed.endsWith('.') ? trimmed : trimmed + '.';
      })
    : [];

  const criteriHTML = criteriaList.length > 0
    ? `<ul class="plan-meso-criteria-list">${criteriaList.map(c => `<li>${c}</li>`).join('')}</ul>`
    : '<p class="plan-meso-detail-text">—</p>';

  const incrociHTML = incrocioPossibile
    ? `<div class="plan-meso-detail-field">
        <span class="plan-meso-detail-label">Nutrizione contestuale</span>
        <p class="plan-meso-detail-text plan-meso-detail-text--note">${incrocioPossibile}</p>
      </div>`
    : '';

  return `
    <div class="plan-meso-detail-header">
      <div class="plan-meso-detail-title-row">
        <span class="plan-meso-badge plan-meso-badge--tipo" data-tipo="${tipo.toLowerCase()}">${tipo}</span>
        <span class="plan-meso-badge plan-meso-nutri-badge" data-fase="${faseNutrizionale}">${faseNutrizionale}</span>
        <h3 class="plan-meso-detail-title">Fase ${numero} — ${nome}</h3>
        <button class="plan-meso-detail-close" aria-label="Chiudi dettaglio mesociclo" type="button">×</button>
      </div>
      <p class="plan-meso-detail-duration">${durata}</p>
    </div>
    <div class="plan-meso-detail-body">
      <div class="plan-meso-detail-field">
        <span class="plan-meso-detail-label">Obiettivo</span>
        <p class="plan-meso-detail-text">${obiettivo}</p>
      </div>
      <div class="plan-meso-detail-field">
        <span class="plan-meso-detail-label">Metodologia</span>
        <p class="plan-meso-detail-text">${metodologia}</p>
      </div>
      <div class="plan-meso-detail-field">
        <span class="plan-meso-detail-label">Note</span>
        <p class="plan-meso-detail-text">${note}</p>
      </div>
      <div class="plan-meso-detail-field">
        <span class="plan-meso-detail-label">Criteri di avanzamento</span>
        ${criteriHTML}
      </div>
      ${incrociHTML}
    </div>
  `.trim();
}

/**
 * Toggling del pannello dettaglio: apre/chiude/aggiorna in base alla card cliccata.
 * Gestisce lo stato: un solo pannello aperto per volta.
 * Aggiorna aria-expanded su tutte le card.
 * @param {number} mesoNumber — numero del mesociclo cliccato
 * @param {Map<number, Object>} mesoMap — mappa numero → mesociclo
 * @param {HTMLElement} cardsContainer — container #plan-phase-cards
 */
function toggleMesocicloDetail(mesoNumber, mesoMap, cardsContainer) {
  const panel = document.getElementById('plan-meso-detail-panel');
  if (!panel) return;

  const meso = mesoMap.get(mesoNumber);
  if (!meso) return;

  // Reimposta aria-expanded su tutte le card
  const allCards = cardsContainer.querySelectorAll('[data-meso-id]');

  if (currentOpenMesoNumber === mesoNumber) {
    // Stessa card cliccata: chiudi il pannello
    panel.innerHTML = '';
    panel.classList.remove('plan-meso-detail--open');
    panel.hidden = true;
    currentOpenMesoNumber = null;

    allCards.forEach(card => card.setAttribute('aria-expanded', 'false'));
  } else {
    // Nuova card o nessuna aperta: aggiorna e apri
    panel.innerHTML = renderMesocicloDetail(meso);
    panel.classList.add('plan-meso-detail--open');
    panel.hidden = false;
    currentOpenMesoNumber = mesoNumber;

    allCards.forEach(card => {
      const cardNum = parseInt(card.getAttribute('data-meso-id'), 10);
      card.setAttribute('aria-expanded', cardNum === mesoNumber ? 'true' : 'false');
    });

    // Listener per il pulsante "Chiudi" ×
    const closeBtn = panel.querySelector('.plan-meso-detail-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        panel.innerHTML = '';
        panel.classList.remove('plan-meso-detail--open');
        panel.hidden = true;
        currentOpenMesoNumber = null;
        allCards.forEach(card => card.setAttribute('aria-expanded', 'false'));
      });
    }

    // Scroll del pannello in vista (soft)
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

/**
 * Attacca il listener click delegato al container delle card.
 * Gestisce click con mouse e tastiera (Enter/Space).
 * @param {HTMLElement} container — #plan-phase-cards
 * @param {Map<number, Object>} mesoMap — mappa numero → mesociclo
 */
function attachTimelineClickListener(container, mesoMap) {
  if (!container) return;

  const handleActivation = (target) => {
    const card = target.closest('[data-meso-id]');
    if (!card) return;
    const mesoNumber = parseInt(card.getAttribute('data-meso-id'), 10);
    if (isNaN(mesoNumber)) return;
    toggleMesocicloDetail(mesoNumber, mesoMap, container);
  };

  container.addEventListener('click', (e) => {
    handleActivation(e.target);
  });

  container.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleActivation(e.target);
    }
  });
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

// ── Strategia Nutrizionale ────────────────────────────────

/**
 * Raccoglie tutti i mesocicli da planData.macrocicli in un array piatto ordinato.
 * @param {Object} planData — dati completi da plan.json
 * @returns {Array} array di oggetti mesociclo
 */
function buildNutritionMesoList(planData) {
  const macrocicli = planData?.macrocicli;
  if (!Array.isArray(macrocicli) || macrocicli.length === 0) return [];
  const result = [];
  for (const macro of macrocicli) {
    const mesocicli = macro?.mesocicli;
    if (Array.isArray(mesocicli)) {
      for (const meso of mesocicli) {
        result.push(meso);
      }
    }
  }
  return result;
}

/**
 * Renderizza la strategia nutrizionale nel container #plan-nutrition-container.
 * Itera su planData.macrocicli[n].mesocicli[m] e mostra per ogni mesociclo:
 * numero, nome, badge fase_nutrizionale colorato e testo incrocio_stimolo_ambiente.
 * @param {Object} planData — dati completi da plan.json
 * @returns {void}
 */
function renderNutritionStrategy(planData) {
  const container = document.getElementById('plan-nutrition-container');
  if (!container) return;

  if (!Array.isArray(planData?.macrocicli) || planData.macrocicli.length === 0) {
    renderError('plan-nutrition-container', 'Strategia nutrizionale non disponibile.');
    return;
  }

  const mesoList = buildNutritionMesoList(planData);
  if (mesoList.length === 0) {
    renderError('plan-nutrition-container', 'Nessun mesociclo trovato nel piano.');
    return;
  }

  // ── Build lista mesocicli ──
  const itemsHtml = mesoList.map(meso => {
    const numero = meso?.numero ?? '—';
    const nome = meso?.nome ?? '—';
    const faseNutrizionale = meso?.fase_nutrizionale ?? 'mantenimento';
    const rationale = meso?.incrocio_stimolo_ambiente ?? '—';

    const itemEl = document.createElement('li');
    itemEl.className = 'plan-nutrition-meso-item';

    const headerEl = document.createElement('div');
    headerEl.className = 'plan-nutrition-meso-header';

    const numEl = document.createElement('span');
    numEl.className = 'plan-nutrition-meso-number';
    numEl.textContent = `Meso ${numero}`;

    const nomeEl = document.createElement('span');
    nomeEl.className = 'plan-nutrition-meso-name';
    nomeEl.textContent = nome;

    const badgeEl = document.createElement('span');
    badgeEl.className = 'plan-meso-badge plan-meso-nutri-badge';
    badgeEl.setAttribute('data-fase', faseNutrizionale);
    badgeEl.textContent = faseNutrizionale;

    headerEl.appendChild(numEl);
    headerEl.appendChild(nomeEl);
    headerEl.appendChild(badgeEl);

    const rationaleEl = document.createElement('p');
    rationaleEl.className = 'plan-nutrition-meso-rationale';
    rationaleEl.textContent = rationale;

    itemEl.appendChild(headerEl);
    itemEl.appendChild(rationaleEl);

    return itemEl.outerHTML;
  }).join('');

  const html = `<ul class="plan-nutrition-meso-list" aria-label="Strategia nutrizionale per mesociclo">${itemsHtml}</ul>`;
  container.innerHTML = html;
}
