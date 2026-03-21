/* ============================================================
   volume.js — Pagina Volume di Allenamento
   Daniele Fitness | fetch volume.json → KPI card + bar chart + tabella
   ============================================================ */

// ── Costanti DATA_PATH ────────────────────────────────────────
const DATA_PATH_VOLUME = 'data/volume.json';

// ── Riferimenti DOM top-level ─────────────────────────────────
const volumeErrorContainer   = document.getElementById('volume-error');
const volumeMetaCard         = document.getElementById('volume-meta-card');
const volumeDetailContainer  = document.getElementById('volume-detail-container');
const headerTotalVolume      = document.getElementById('header-total-volume');

// ── Registro istanza Chart.js ─────────────────────────────────
let volumeChartInstance = null;

// ── Mappa colori per ruolo ────────────────────────────────────
const RUOLO_LABEL = {
  principale: 'P',
  secondario: 'S',
  terziario:  'T'
};

/* ============================================================
   showError(container, error)
   Mostra un messaggio di errore nel container DOM.
   @param {HTMLElement} container
   @param {Error|string} error
   ============================================================ */
function showError(container, error) {
  if (!container) return;
  container.textContent = 'Dati non disponibili. Riprova più tardi.';
  container.removeAttribute('hidden');
  console.error('[volume.js] Errore caricamento dati:', error);
}

/* ============================================================
   formatBalance(rating)
   Trasforma il balance_rating snake_case in etichetta leggibile.
   @param {string} rating
   @returns {string}
   ============================================================ */
function formatBalance(rating) {
  if (!rating) return '—';
  return rating.replace(/_/g, ' ');
}

/* ============================================================
   getBalanceClass(rating)
   Restituisce la classe CSS del badge in base al rating.
   @param {string} rating
   @returns {string}
   ============================================================ */
function getBalanceClass(rating) {
  if (!rating) return 'volume-balance-badge--neutral';
  if (rating.includes('eccessivo_pull')) return 'volume-balance-badge--warning';
  if (rating.includes('eccessivo_push')) return 'volume-balance-badge--warning';
  if (rating.includes('ottimale'))       return 'volume-balance-badge--ok';
  return 'volume-balance-badge--neutral';
}

// ── SEZIONE: renderVolumeMetaCard ─────────────────────────────

/* ============================================================
   renderVolumeMetaCard(meta)
   Renderizza la card KPI con i metadati globali di volume:
   totale serie pesate, pull/push/ratio, balance_rating.
   @param {Object} meta  — oggetto meta da volume.json
   ============================================================ */
function renderVolumeMetaCard(meta) {
  if (!volumeMetaCard) return;

  if (!meta) {
    volumeMetaCard.innerHTML = '<p class="volume-placeholder">Metadati non disponibili.</p>';
    return;
  }

  const totalSerie    = meta.total_serie_pesate != null ? meta.total_serie_pesate.toFixed(1) : '—';
  const pullSerie     = meta.pull_serie         != null ? meta.pull_serie.toFixed(1)         : '—';
  const pushSerie     = meta.push_serie         != null ? meta.push_serie.toFixed(1)         : '—';
  const ratio         = meta.pull_push_ratio    != null ? meta.pull_push_ratio.toFixed(2)    : '—';
  const rating        = meta.balance_rating     ?? '—';
  const ratingLabel   = formatBalance(rating);
  const ratingClass   = getBalanceClass(rating);

  // Aggiorna header meta
  if (headerTotalVolume) {
    headerTotalVolume.textContent = `${totalSerie} serie`;
  }

  volumeMetaCard.innerHTML = `
    <div class="volume-meta-grid">
      <div class="volume-meta-item">
        <span class="volume-meta-label">Serie pesate totali</span>
        <span class="volume-meta-value">${totalSerie}</span>
      </div>
      <div class="volume-meta-item">
        <span class="volume-meta-label">Serie Pull</span>
        <span class="volume-meta-value volume-meta-value--pull">${pullSerie}</span>
      </div>
      <div class="volume-meta-item">
        <span class="volume-meta-label">Serie Push</span>
        <span class="volume-meta-value volume-meta-value--push">${pushSerie}</span>
      </div>
      <div class="volume-meta-item">
        <span class="volume-meta-label">Ratio Pull/Push</span>
        <span class="volume-meta-value">${ratio}</span>
      </div>
      <div class="volume-meta-item volume-meta-item--balance">
        <span class="volume-meta-label">Balance Pull/Push</span>
        <span class="volume-balance-badge ${ratingClass}">${ratingLabel}</span>
      </div>
    </div>
  `;
}

// ── SEZIONE: renderVolumeChart ────────────────────────────────

/* ============================================================
   renderVolumeChart(volumi)
   Renderizza il grafico a barre orizzontali (Chart.js) con i
   gruppi muscolari ordinati per serie_pesate decrescente.
   Distrugge l'istanza precedente se esiste.
   @param {Array} volumi  — array da volume.json["volumi"]
   ============================================================ */
function renderVolumeChart(volumi) {
  const canvas = document.getElementById('chart-volume-muscoli');
  if (!canvas) return;

  if (!Array.isArray(volumi) || volumi.length === 0) {
    canvas.closest('.volume-chart-container')
      ?.insertAdjacentHTML('beforeend',
        '<p class="volume-placeholder">Nessun dato disponibile.</p>');
    return;
  }

  // Ordina per serie_pesate decrescente
  const sorted = [...volumi].sort((a, b) => (b.serie_pesate ?? 0) - (a.serie_pesate ?? 0));

  const labels = sorted.map(v => v.muscolo ?? '—');
  const values = sorted.map(v => v.serie_pesate ?? 0);

  // Genera colori basati sull'intensità (accent → muted)
  const backgroundColors = values.map((val, i) => {
    const alpha = Math.max(0.35, 1 - i * 0.065);
    return `rgba(255, 107, 53, ${alpha})`;
  });

  // Distruggi istanza precedente per evitare memory leak
  if (volumeChartInstance) {
    volumeChartInstance.destroy();
    volumeChartInstance = null;
  }

  volumeChartInstance = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Serie pesate',
        data: values,
        backgroundColor: backgroundColors,
        borderColor: backgroundColors.map(c => c.replace(/[\d.]+\)$/, '1)')),
        borderWidth: 1,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          callbacks: {
            label(context) {
              const val = context.parsed.x;
              return ` ${val != null ? val.toFixed(1) : '—'} serie pesate`;
            }
          }
        }
      },
      scales: {
        x: {
          beginAtZero: true,
          grid: {
            color: 'rgba(255,255,255,0.06)'
          },
          ticks: {
            color: 'rgba(240,240,240,0.6)',
            font: { size: 12 }
          },
          title: {
            display: true,
            text: 'Serie pesate',
            color: 'rgba(240,240,240,0.5)',
            font: { size: 11 }
          }
        },
        y: {
          grid: {
            display: false
          },
          ticks: {
            color: 'rgba(240,240,240,0.85)',
            font: { size: 12 }
          }
        }
      }
    }
  });
}

// ── SEZIONE: renderVolumeTable ────────────────────────────────

/* ============================================================
   renderVolumeTable(volumi)
   Renderizza la tabella dettaglio esercizi per ogni gruppo
   muscolare. Un blocco per muscolo con tabella interna.
   Colonne: esercizio, giorno, serie, ruolo, contributo.
   @param {Array} volumi  — array da volume.json["volumi"]
   ============================================================ */
function renderVolumeTable(volumi) {
  if (!volumeDetailContainer) return;

  if (!Array.isArray(volumi) || volumi.length === 0) {
    volumeDetailContainer.innerHTML =
      '<p class="volume-placeholder">Nessun dato disponibile.</p>';
    return;
  }

  // Ordina per serie_pesate decrescente (coerente col grafico)
  const sorted = [...volumi].sort((a, b) => (b.serie_pesate ?? 0) - (a.serie_pesate ?? 0));

  const html = sorted.map(muscoloObj => {
    const muscolo    = muscoloObj.muscolo     ?? '—';
    const serieTot   = muscoloObj.serie_pesate != null
      ? muscoloObj.serie_pesate.toFixed(1)
      : '—';
    const dettaglio  = Array.isArray(muscoloObj.dettaglio) ? muscoloObj.dettaglio : [];

    const rows = dettaglio.map(ex => {
      const esercizio  = ex.esercizio  ?? '—';
      const giorno     = ex.giorno     ?? '—';
      const serie      = ex.serie      != null ? Math.round(ex.serie) : '—';
      const ruolo      = ex.ruolo      ?? '—';
      const contributo = ex.contributo != null ? ex.contributo.toFixed(1) : '—';
      const ruoloLabel = RUOLO_LABEL[ruolo] ?? ruolo;
      const ruoloClass = `volume-ruolo-badge volume-ruolo-badge--${ruolo}`;

      return `
        <tr>
          <td>${esercizio}</td>
          <td>${giorno}</td>
          <td class="volume-detail-table__num">${serie}</td>
          <td><span class="${ruoloClass}" title="${ruolo}">${ruoloLabel}</span></td>
          <td class="volume-detail-table__num">${contributo}</td>
        </tr>`;
    }).join('');

    const emptyRow = dettaglio.length === 0
      ? '<tr><td colspan="5" class="volume-placeholder">Nessun esercizio.</td></tr>'
      : '';

    return `
      <div class="volume-muscle-block">
        <div class="volume-muscle-block-header">
          <span class="volume-muscle-name">${muscolo}</span>
          <span class="volume-muscle-total">${serieTot} serie pesate</span>
        </div>
        <div class="volume-detail-table-wrap">
          <table class="volume-detail-table">
            <thead>
              <tr>
                <th scope="col">Esercizio</th>
                <th scope="col">Giorno</th>
                <th scope="col" class="volume-detail-table__num">Serie</th>
                <th scope="col">Ruolo</th>
                <th scope="col" class="volume-detail-table__num">Contributo</th>
              </tr>
            </thead>
            <tbody>
              ${rows}${emptyRow}
            </tbody>
          </table>
        </div>
      </div>`;
  }).join('');

  volumeDetailContainer.innerHTML = html;
}

// ── SEZIONE: initVolume ───────────────────────────────────────

/* ============================================================
   initVolume()
   Entry point: fetch volume.json, poi chiama le tre render.
   ============================================================ */
async function initVolume() {
  try {
    const response = await fetch(DATA_PATH_VOLUME);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();

    // Accede al campo radice 'volumi' — non 'volumes' né 'data'
    const volumi = data?.volumi;
    const meta   = data?.meta;

    if (!Array.isArray(volumi)) {
      throw new Error('Campo "volumi" assente o non è un array.');
    }

    renderVolumeMetaCard(meta);
    renderVolumeChart(volumi);
    renderVolumeTable(volumi);

  } catch (error) {
    showError(volumeErrorContainer, error);
    // Mostra placeholder nei container figli
    if (volumeMetaCard) {
      volumeMetaCard.innerHTML = '<p class="volume-placeholder">Dati non disponibili.</p>';
    }
    if (volumeDetailContainer) {
      volumeDetailContainer.innerHTML = '<p class="volume-placeholder">Dati non disponibili.</p>';
    }
  }
}

document.addEventListener('DOMContentLoaded', initVolume);
