/* ============================================================
   progress.js — Scheletro pagina Progressi
   Daniele Fitness | fetch measurements.json + workout_history.json
   I task figli (weight-bf-chart, strength-chart,
   circumferences-chart, measurements-table) estenderanno
   renderProgress() con le singole render function.
   ============================================================ */

/* ── Costanti ── */
const DATA_PATH_MEASUREMENTS    = 'data/measurements.json';
const DATA_PATH_WORKOUT_HISTORY = 'data/workout_history.json';

/* ── Riferimenti DOM ── */
const progressErrorContainer = document.getElementById('progress-error');

/* ── Registri grafici Chart.js (usati dai task figli per destroy) ── */
const progressCharts = {};

/* ============================================================
   showError(container, error)
   Mostra un messaggio di errore in un container DOM.
   Usato quando fetch fallisce o i dati sono malformati.
   ============================================================ */
function showError(container, error) {
  if (!container) return;
  container.textContent = 'Dati non disponibili. Riprova più tardi.';
  container.removeAttribute('hidden');
  console.error('[progress.js] Errore caricamento dati:', error);
}

/* ============================================================
   formatDateIT(isoString)
   Converte una data ISO 8601 (YYYY-MM-DD) in formato italiano
   leggibile (es. '20 mar 2026').
   ============================================================ */
function formatDateIT(isoString) {
  if (!isoString) return '—';
  const [year, month, day] = isoString.split('-').map(Number);
  if (!year || !month || !day) return isoString;
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString('it-IT', {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  });
}

/* ============================================================
   renderWeightBfChart(data)
   Grafico a linee doppio asse Y: peso (kg) asse sinistro,
   BF% asse destro, massa magra (kg) linea opzionale.
   Asse X lineare con timestamp per gestire intervalli irregolari.
   ============================================================ */
function renderWeightBfChart(data) {
  const canvas = document.getElementById('chart-peso-bf');
  if (!canvas) return;

  /* Filtra record con dati validi */
  const records = Array.isArray(data)
    ? data.filter(function (d) { return d && d.data; })
    : [];

  if (records.length === 0) {
    canvas.closest('.progress-chart-container')
      ?.insertAdjacentHTML('beforeend',
        '<p class="progress-placeholder">Nessun dato disponibile.</p>');
    return;
  }

  /* Converti date in timestamp per asse X lineare */
  const timestamps = records.map(function (d) {
    return new Date(d.data).getTime();
  });

  /* Dataset peso */
  const pesoDataset = records.map(function (d, i) {
    return { x: timestamps[i], y: d.peso_kg ?? null };
  });

  /* Dataset BF% */
  const bfDataset = records.map(function (d, i) {
    return { x: timestamps[i], y: d.body_fat_pct ?? null };
  });

  /* Dataset massa magra */
  const massaMagraDataset = records.map(function (d, i) {
    return { x: timestamps[i], y: d.massa_magra_kg ?? null };
  });

  /* Range asse Y sinistro (kg): combina peso_kg + massa_magra_kg (entrambi su yAxisID:'y') */
  const pesoValues       = pesoDataset.map(function (p) { return p.y; }).filter(function (v) { return v !== null; });
  const massaMagraValues = massaMagraDataset.map(function (p) { return p.y; }).filter(function (v) { return v !== null; });
  const yLeftValues = pesoValues.concat(massaMagraValues);
  const minPeso = yLeftValues.length ? Math.min.apply(null, yLeftValues) : 65;
  const maxPeso = yLeftValues.length ? Math.max.apply(null, yLeftValues) : 95;

  /* Range asse BF% con padding */
  const bfValues = bfDataset.map(function (p) { return p.y; }).filter(function (v) { return v !== null; });
  const minBf = bfValues.length ? Math.min.apply(null, bfValues) : 10;
  const maxBf = bfValues.length ? Math.max.apply(null, bfValues) : 20;

  /* Colori dal design system */
  const COLOR_PESO     = '#ff6b35';            /* --color-accent */
  const COLOR_BF       = '#ffc107';            /* --color-warning */
  const COLOR_MM       = '#4caf50';            /* --color-success */
  const COLOR_GRID     = 'rgba(58,58,58,0.6)'; /* --color-border */
  const COLOR_TEXT     = '#a0a0a0';            /* --color-text-muted */

  /* Distruggi istanza precedente */
  progressCharts['pesoBf']?.destroy();

  progressCharts['pesoBf'] = new Chart(canvas, {
    type: 'line',
    data: {
      datasets: [
        {
          label: 'Peso (kg)',
          data: pesoDataset,
          borderColor: COLOR_PESO,
          backgroundColor: 'rgba(255,107,53,0.12)',
          pointBackgroundColor: COLOR_PESO,
          pointRadius: 5,
          pointHoverRadius: 7,
          borderWidth: 2,
          fill: false,
          tension: 0.3,
          spanGaps: true,
          yAxisID: 'y'
        },
        {
          label: 'BF%',
          data: bfDataset,
          borderColor: COLOR_BF,
          backgroundColor: 'rgba(255,193,7,0.1)',
          pointBackgroundColor: COLOR_BF,
          pointRadius: 5,
          pointHoverRadius: 7,
          borderWidth: 2,
          fill: false,
          tension: 0.3,
          spanGaps: true,
          yAxisID: 'y1'
        },
        {
          label: 'Massa magra (kg)',
          data: massaMagraDataset,
          borderColor: COLOR_MM,
          backgroundColor: 'rgba(76,175,80,0.08)',
          pointBackgroundColor: COLOR_MM,
          pointRadius: 4,
          pointHoverRadius: 6,
          borderWidth: 1.5,
          borderDash: [5, 4],
          fill: false,
          tension: 0.3,
          spanGaps: true,
          yAxisID: 'y'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          display: true,
          position: 'bottom',
          labels: {
            color: COLOR_TEXT,
            font: { size: 12 },
            usePointStyle: true,
            pointStyleWidth: 12,
            padding: 16
          }
        },
        tooltip: {
          backgroundColor: '#2d2d2d',
          borderColor: '#3a3a3a',
          borderWidth: 1,
          titleColor: '#f0f0f0',
          bodyColor: '#a0a0a0',
          callbacks: {
            title: function (items) {
              if (!items.length) return '';
              const ts = items[0].parsed.x;
              const iso = new Date(ts).toISOString().slice(0, 10);
              return formatDateIT(iso);
            },
            label: function (item) {
              const unit = item.datasetIndex === 1 ? '%' : ' kg';
              return ' ' + item.dataset.label + ': ' + item.parsed.y.toFixed(1) + unit;
            }
          }
        }
      },
      scales: {
        x: {
          type: 'linear',
          position: 'bottom',
          ticks: {
            color: COLOR_TEXT,
            font: { size: 11 },
            maxTicksLimit: 6,
            callback: function (value) {
              const iso = new Date(value).toISOString().slice(0, 10);
              return formatDateIT(iso);
            }
          },
          grid: {
            color: COLOR_GRID
          }
        },
        y: {
          type: 'linear',
          position: 'left',
          min: Math.floor(minPeso - 2),
          max: Math.ceil(maxPeso + 2),
          ticks: {
            color: COLOR_PESO,
            font: { size: 11 },
            callback: function (value) { return value + ' kg'; }
          },
          grid: {
            color: COLOR_GRID
          },
          title: {
            display: true,
            text: 'Peso (kg)',
            color: COLOR_PESO,
            font: { size: 11 }
          }
        },
        y1: {
          type: 'linear',
          position: 'right',
          min: Math.floor(minBf - 1),
          max: Math.ceil(maxBf + 1),
          ticks: {
            color: COLOR_BF,
            font: { size: 11 },
            callback: function (value) { return value + '%'; }
          },
          grid: {
            drawOnChartArea: false
          },
          title: {
            display: true,
            text: 'BF%',
            color: COLOR_BF,
            font: { size: 11 }
          }
        }
      }
    }
  });
}

/* ============================================================
   renderStrengthChart(data)
   Grafico a linee: evoluzione storica Squat, Panca e Stacco 1RM.
   Asse X lineare con timestamp. 3 colori distinti per esercizio.
   Il punto stimato (squat_1rm_tipo/panca_1rm_tipo/stacco_1rm_tipo='S')
   è differenziato visivamente per esercizio con pointStyle 'rect'
   (quadrato) vs 'circle' per i punti reali. Ogni esercizio ha il proprio
   indice stimato indipendente per supportare tipi misti.
   ============================================================ */
function renderStrengthChart(data) {
  const canvas = document.getElementById('chart-massimali');
  if (!canvas) return;

  /* Filtra record con data presente */
  const records = Array.isArray(data)
    ? data.filter(function (d) { return d && d.data; })
    : [];

  if (records.length === 0) {
    canvas.closest('.progress-chart-container')
      ?.insertAdjacentHTML('beforeend',
        '<p class="progress-placeholder">Nessun dato disponibile.</p>');
    return;
  }

  /* Converti date in timestamp per asse X lineare */
  const timestamps = records.map(function (d) {
    return new Date(d.data).getTime();
  });

  /* Indice dell'ultimo record — usato come fallback se nessun record stimato trovato */
  const lastIdx = records.length - 1;

  /* Colori dal design system */
  const COLOR_SQUAT  = '#ff6b35';            /* --color-accent, arancio */
  const COLOR_PANCA  = '#4fc3f7';            /* celeste */
  const COLOR_STACCO = '#ce93d8';            /* viola chiaro */
  const COLOR_GRID   = 'rgba(58,58,58,0.6)'; /* --color-border */
  const COLOR_TEXT   = '#a0a0a0';            /* --color-text-muted */

  /* Colori punto stimato (più chiari / semi-trasparenti per distinguerli) */
  const COLOR_SQUAT_STIMATO  = 'rgba(255,107,53,0.4)';
  const COLOR_PANCA_STIMATO  = 'rgba(79,195,247,0.4)';
  const COLOR_STACCO_STIMATO = 'rgba(206,147,216,0.4)';

  /* Helper: costruisce array di pointStyle (circle per reali, rect per stimato) */
  function buildPointStyles(len, stimatoIdx) {
    return records.map(function (d, i) {
      return i === stimatoIdx ? 'rect' : 'circle';
    });
  }

  /* Helper: costruisce array di pointBackgroundColor */
  function buildPointColors(baseColor, stimatoColor, len, stimatoIdx) {
    return records.map(function (d, i) {
      return i === stimatoIdx ? stimatoColor : baseColor;
    });
  }

  /* Helper: costruisce array di pointRadius (leggermente più grande il punto stimato) */
  function buildPointRadius(len, stimatoIdx, normalR, stimatoR) {
    return records.map(function (d, i) {
      return i === stimatoIdx ? stimatoR : normalR;
    });
  }

  /* Determina l'indice stimato per-esercizio: legge il campo specifico xxx_1rm_tipo.
     Fallback su massimali_tipo (legacy) se tutti e tre i campi per-esercizio sono assenti.
     Se findIndex ritorna -1 (nessun record stimato) si usa lastIdx come fallback. */
  const hasPerEsercizioTipo = records.some(function (d) {
    return d.squat_1rm_tipo || d.panca_1rm_tipo || d.stacco_1rm_tipo;
  });

  let squatStimatoIdx, pancaStimatoIdx, staccoStimatoIdx;

  if (hasPerEsercizioTipo) {
    squatStimatoIdx  = records.findIndex(function (d) { return d.squat_1rm_tipo  === 'S'; });
    pancaStimatoIdx  = records.findIndex(function (d) { return d.panca_1rm_tipo  === 'S'; });
    staccoStimatoIdx = records.findIndex(function (d) { return d.stacco_1rm_tipo === 'S'; });
    /* -1 = nessun record stimato → fallback lastIdx */
    if (squatStimatoIdx  === -1) squatStimatoIdx  = lastIdx;
    if (pancaStimatoIdx  === -1) pancaStimatoIdx  = lastIdx;
    if (staccoStimatoIdx === -1) staccoStimatoIdx = lastIdx;
  } else {
    /* Record legacy senza campi per-esercizio: usa massimali_tipo globale */
    const legacyIdx = records.findIndex(function (d) { return d.massimali_tipo === 'S'; });
    const effectiveLegacy = legacyIdx !== -1 ? legacyIdx : lastIdx;
    squatStimatoIdx  = effectiveLegacy;
    pancaStimatoIdx  = effectiveLegacy;
    staccoStimatoIdx = effectiveLegacy;
  }

  /* Dataset Squat */
  const squatDataset = records.map(function (d, i) {
    return { x: timestamps[i], y: d.squat_1rm ?? null };
  });

  /* Dataset Panca */
  const pancaDataset = records.map(function (d, i) {
    return { x: timestamps[i], y: d.panca_1rm ?? null };
  });

  /* Dataset Stacco */
  const staccoDataset = records.map(function (d, i) {
    return { x: timestamps[i], y: d.stacco_1rm ?? null };
  });

  /* Distruggi istanza precedente */
  progressCharts['massimali']?.destroy();

  progressCharts['massimali'] = new Chart(canvas, {
    type: 'line',
    data: {
      datasets: [
        {
          label: 'Squat 1RM (kg)',
          data: squatDataset,
          borderColor: COLOR_SQUAT,
          backgroundColor: 'rgba(255,107,53,0.10)',
          pointBackgroundColor: buildPointColors(COLOR_SQUAT, COLOR_SQUAT_STIMATO, records.length, squatStimatoIdx),
          pointBorderColor: buildPointColors(COLOR_SQUAT, COLOR_SQUAT, records.length, squatStimatoIdx),
          pointBorderWidth: buildPointRadius(records.length, squatStimatoIdx, 1, 2),
          pointStyle: buildPointStyles(records.length, squatStimatoIdx),
          pointRadius: buildPointRadius(records.length, squatStimatoIdx, 5, 8),
          pointHoverRadius: buildPointRadius(records.length, squatStimatoIdx, 7, 10),
          borderWidth: 2,
          fill: false,
          tension: 0.3,
          spanGaps: true
        },
        {
          label: 'Panca 1RM (kg)',
          data: pancaDataset,
          borderColor: COLOR_PANCA,
          backgroundColor: 'rgba(79,195,247,0.10)',
          pointBackgroundColor: buildPointColors(COLOR_PANCA, COLOR_PANCA_STIMATO, records.length, pancaStimatoIdx),
          pointBorderColor: buildPointColors(COLOR_PANCA, COLOR_PANCA, records.length, pancaStimatoIdx),
          pointBorderWidth: buildPointRadius(records.length, pancaStimatoIdx, 1, 2),
          pointStyle: buildPointStyles(records.length, pancaStimatoIdx),
          pointRadius: buildPointRadius(records.length, pancaStimatoIdx, 5, 8),
          pointHoverRadius: buildPointRadius(records.length, pancaStimatoIdx, 7, 10),
          borderWidth: 2,
          fill: false,
          tension: 0.3,
          spanGaps: true
        },
        {
          label: 'Stacco 1RM (kg)',
          data: staccoDataset,
          borderColor: COLOR_STACCO,
          backgroundColor: 'rgba(206,147,216,0.10)',
          pointBackgroundColor: buildPointColors(COLOR_STACCO, COLOR_STACCO_STIMATO, records.length, staccoStimatoIdx),
          pointBorderColor: buildPointColors(COLOR_STACCO, COLOR_STACCO, records.length, staccoStimatoIdx),
          pointBorderWidth: buildPointRadius(records.length, staccoStimatoIdx, 1, 2),
          pointStyle: buildPointStyles(records.length, staccoStimatoIdx),
          pointRadius: buildPointRadius(records.length, staccoStimatoIdx, 5, 8),
          pointHoverRadius: buildPointRadius(records.length, staccoStimatoIdx, 7, 10),
          borderWidth: 2,
          fill: false,
          tension: 0.3,
          spanGaps: true
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          display: true,
          position: 'bottom',
          labels: {
            color: COLOR_TEXT,
            font: { size: 12 },
            usePointStyle: true,
            pointStyleWidth: 12,
            padding: 16
          }
        },
        tooltip: {
          backgroundColor: '#2d2d2d',
          borderColor: '#3a3a3a',
          borderWidth: 1,
          titleColor: '#f0f0f0',
          bodyColor: '#a0a0a0',
          callbacks: {
            title: function (items) {
              if (!items.length) return '';
              const ts = items[0].parsed.x;
              const iso = new Date(ts).toISOString().slice(0, 10);
              return formatDateIT(iso);
            },
            label: function (item) {
              if (item.parsed.y === null || item.parsed.y === undefined) return null;
              /* Trova il record corrispondente tramite timestamp */
              const recIdx = records.findIndex(function (d) {
                return new Date(d.data).getTime() === item.parsed.x;
              });
              /* Determina il campo tipo corretto per questo esercizio (per-esercizio) */
              const labelLow = item.dataset.label.toLowerCase();
              const tipoField = labelLow.includes('squat')
                ? 'squat_1rm_tipo'
                : labelLow.includes('panca')
                  ? 'panca_1rm_tipo'
                  : 'stacco_1rm_tipo';
              /* Lettura campo per-esercizio con fallback su massimali_tipo (legacy) */
              const tipo = (recIdx !== -1 && records[recIdx]?.[tipoField])
                ? records[recIdx][tipoField]
                : (records[recIdx]?.massimali_tipo ?? 'R');
              return ' ' + item.dataset.label + ': ' + item.parsed.y.toFixed(1) + ' kg (' + tipo + ')';
            }
          }
        }
      },
      scales: {
        x: {
          type: 'linear',
          position: 'bottom',
          ticks: {
            color: COLOR_TEXT,
            font: { size: 11 },
            maxTicksLimit: 6,
            callback: function (value) {
              const iso = new Date(value).toISOString().slice(0, 10);
              return formatDateIT(iso);
            }
          },
          grid: {
            color: COLOR_GRID
          }
        },
        y: {
          type: 'linear',
          position: 'left',
          ticks: {
            color: COLOR_TEXT,
            font: { size: 11 },
            callback: function (value) { return value + ' kg'; }
          },
          grid: {
            color: COLOR_GRID
          },
          title: {
            display: true,
            text: '1RM (kg)',
            color: COLOR_TEXT,
            font: { size: 11 }
          }
        }
      }
    }
  });
}

/* ============================================================
   renderMeasurementsTable(data)
   Genera la tabella storica delle misurazioni nel container
   #table-misurazioni. I dati arrivano come parametro da
   renderProgress() — nessun fetch aggiuntivo.
   Colonne sempre visibili: Data, Peso, BF%, Massa Magra,
   Squat 1RM, Panca 1RM, Stacco 1RM.
   Colonne nascoste su mobile (.col-mobile-hide):
   FFMI, Vita, Petto, Braccio, Coscia.
   Note non vuote: riga aggiuntiva .measurements-table__note-row.
   ============================================================ */
function renderMeasurementsTable(data) {
  const container = document.getElementById('table-misurazioni');
  if (!container) return;

  /* Filtra record validi */
  const records = Array.isArray(data)
    ? data.filter(function (d) { return d && d.data; })
    : [];

  if (records.length === 0) {
    container.innerHTML = '<p class="progress-placeholder">Nessun dato disponibile.</p>';
    return;
  }

  /* ── Helper: valore numerico formattato o '—' ── */
  function fmtNum(val, decimals) {
    if (val === null || val === undefined || val === '') return '—';
    const n = Number(val);
    if (isNaN(n)) return '—';
    return decimals !== undefined ? n.toFixed(decimals) : String(n);
  }

  /* ── Helper: badge tipo massimale ── */
  function badgeTipo(tipo) {
    if (!tipo) return '';
    const cls = tipo === 'S'
      ? 'td-badge td-badge--stimato'
      : 'td-badge td-badge--reale';
    return '<span class="' + cls + '">' + tipo + '</span>';
  }

  /* ── Helper: cella massimale con badge tipo ── */
  function cellaMassimale(val, tipo) {
    const numStr = fmtNum(val, 1);
    if (numStr === '—') return '—';
    return numStr + ' kg' + badgeTipo(tipo);
  }

  /* ── Costruzione HTML tabella ── */
  let html = '<table class="measurements-table" aria-label="Storico misurazioni">';

  /* Intestazione */
  html += '<thead><tr>';
  html += '<th scope="col">Data</th>';
  html += '<th scope="col">Peso (kg)</th>';
  html += '<th scope="col">BF%</th>';
  html += '<th scope="col">Massa Magra (kg)</th>';
  html += '<th scope="col" class="col-mobile-hide">FFMI</th>';
  html += '<th scope="col" class="col-mobile-hide">Vita (cm)</th>';
  html += '<th scope="col" class="col-mobile-hide">Petto (cm)</th>';
  html += '<th scope="col" class="col-mobile-hide">Braccio (cm)</th>';
  html += '<th scope="col" class="col-mobile-hide">Coscia (cm)</th>';
  html += '<th scope="col">Squat 1RM</th>';
  html += '<th scope="col">Panca 1RM</th>';
  html += '<th scope="col">Stacco 1RM</th>';
  html += '</tr></thead>';

  /* Righe dati */
  html += '<tbody>';

  records.forEach(function (d) {
    const nota = (d.note !== null && d.note !== undefined) ? String(d.note).trim() : '';
    const hasNota = nota.length > 0;

    /* ── Riga principale ── */
    html += '<tr>';

    /* Data */
    html += '<td class="td-date">' + formatDateIT(d.data) + '</td>';

    /* Peso */
    html += '<td>' + fmtNum(d.peso_kg, 1) + '</td>';

    /* BF% */
    html += '<td>' + fmtNum(d.body_fat_pct, 1) + '%</td>';

    /* Massa Magra */
    html += '<td>' + fmtNum(d.massa_magra_kg, 1) + '</td>';

    /* FFMI — col-mobile-hide */
    html += '<td class="td-muted col-mobile-hide">' + fmtNum(d.ffmi_adj, 1) + '</td>';

    /* Vita — col-mobile-hide */
    html += '<td class="td-muted col-mobile-hide">' + fmtNum(d.vita_cm) + '</td>';

    /* Petto — col-mobile-hide */
    html += '<td class="td-muted col-mobile-hide">' + fmtNum(d.petto_cm) + '</td>';

    /* Braccio — col-mobile-hide */
    html += '<td class="td-muted col-mobile-hide">' + fmtNum(d.braccio_dx_cm, 1) + '</td>';

    /* Coscia — col-mobile-hide */
    html += '<td class="td-muted col-mobile-hide">' + fmtNum(d.coscia_dx_cm, 1) + '</td>';

    /* Squat 1RM */
    html += '<td>' + cellaMassimale(d.squat_1rm, d.squat_1rm_tipo) + '</td>';

    /* Panca 1RM */
    html += '<td>' + cellaMassimale(d.panca_1rm, d.panca_1rm_tipo) + '</td>';

    /* Stacco 1RM */
    html += '<td>' + cellaMassimale(d.stacco_1rm, d.stacco_1rm_tipo) + '</td>';

    html += '</tr>';

    /* ── Riga aggiuntiva nota (solo se presente) ── */
    if (hasNota) {
      html += '<tr class="measurements-table__note-row">';
      /* Colspan totale colonne = 12 */
      html += '<td colspan="12">' + nota + '</td>';
      html += '</tr>';
    }
  });

  html += '</tbody></table>';

  container.innerHTML = html;
}

/* ============================================================
   renderCircumferencesChart(data)
   Grafico a linee: evoluzione storica delle circonferenze corporee.
   3 linee: vita_cm (proxy grasso), braccio_dx_cm (proxy massa),
   coscia_dx_cm (terza linea opzionale).
   Asse X lineare con timestamp per intervalli irregolari.
   ============================================================ */
function renderCircumferencesChart(data) {
  const canvas = document.getElementById('chart-circonferenze');
  if (!canvas) return;

  /* Filtra record con data presente */
  const records = Array.isArray(data)
    ? data.filter(function (d) { return d && d.data; })
    : [];

  if (records.length === 0) {
    canvas.closest('.progress-chart-container')
      ?.insertAdjacentHTML('beforeend',
        '<p class="progress-placeholder">Nessun dato disponibile.</p>');
    return;
  }

  /* Converti date in timestamp per asse X lineare */
  const timestamps = records.map(function (d) {
    return new Date(d.data).getTime();
  });

  /* Colori dal design system */
  const COLOR_VITA    = '#ff6b35';            /* arancio — proxy grasso */
  const COLOR_BRACCIO = '#4fc3f7';            /* celeste — proxy massa muscolare */
  const COLOR_COSCIA  = '#ce93d8';            /* viola — terza linea opzionale */
  const COLOR_GRID    = 'rgba(58,58,58,0.6)'; /* --color-border */
  const COLOR_TEXT    = '#a0a0a0';            /* --color-text-muted */

  /* Dataset vita */
  const vitaDataset = records.map(function (d, i) {
    return { x: timestamps[i], y: d.vita_cm ?? null };
  });

  /* Dataset braccio destro */
  const braccioDataset = records.map(function (d, i) {
    return { x: timestamps[i], y: d.braccio_dx_cm ?? null };
  });

  /* Dataset coscia destra */
  const cosciaDataset = records.map(function (d, i) {
    return { x: timestamps[i], y: d.coscia_dx_cm ?? null };
  });

  /* Range asse Y con padding: include tutti e tre i dataset */
  const allValues = [...vitaDataset, ...braccioDataset, ...cosciaDataset]
    .map(function (p) { return p.y; })
    .filter(function (v) { return v !== null && v !== undefined; });
  const minVal = allValues.length ? Math.min.apply(null, allValues) : 25;
  const maxVal = allValues.length ? Math.max.apply(null, allValues) : 100;

  /* Distruggi istanza precedente */
  progressCharts['circonferenze']?.destroy();

  progressCharts['circonferenze'] = new Chart(canvas, {
    type: 'line',
    data: {
      datasets: [
        {
          label: 'Vita (cm)',
          data: vitaDataset,
          borderColor: COLOR_VITA,
          backgroundColor: 'rgba(255,107,53,0.10)',
          pointBackgroundColor: COLOR_VITA,
          pointRadius: 5,
          pointHoverRadius: 7,
          borderWidth: 2,
          fill: false,
          tension: 0.3,
          spanGaps: true
        },
        {
          label: 'Braccio dx (cm)',
          data: braccioDataset,
          borderColor: COLOR_BRACCIO,
          backgroundColor: 'rgba(79,195,247,0.10)',
          pointBackgroundColor: COLOR_BRACCIO,
          pointRadius: 5,
          pointHoverRadius: 7,
          borderWidth: 2,
          fill: false,
          tension: 0.3,
          spanGaps: true
        },
        {
          label: 'Coscia dx (cm)',
          data: cosciaDataset,
          borderColor: COLOR_COSCIA,
          backgroundColor: 'rgba(206,147,216,0.10)',
          pointBackgroundColor: COLOR_COSCIA,
          pointRadius: 5,
          pointHoverRadius: 7,
          borderWidth: 2,
          fill: false,
          tension: 0.3,
          spanGaps: true
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          display: true,
          position: 'bottom',
          labels: {
            color: COLOR_TEXT,
            font: { size: 12 },
            usePointStyle: true,
            pointStyleWidth: 12,
            padding: 16
          }
        },
        tooltip: {
          backgroundColor: '#2d2d2d',
          borderColor: '#3a3a3a',
          borderWidth: 1,
          titleColor: '#f0f0f0',
          bodyColor: '#a0a0a0',
          callbacks: {
            title: function (items) {
              if (!items.length) return '';
              const ts = items[0].parsed.x;
              const iso = new Date(ts).toISOString().slice(0, 10);
              return formatDateIT(iso);
            },
            label: function (item) {
              if (item.parsed.y === null || item.parsed.y === undefined) return null;
              return ' ' + item.dataset.label + ': ' + item.parsed.y.toFixed(1) + ' cm';
            }
          }
        }
      },
      scales: {
        x: {
          type: 'linear',
          position: 'bottom',
          ticks: {
            color: COLOR_TEXT,
            font: { size: 11 },
            maxTicksLimit: 6,
            callback: function (value) {
              const iso = new Date(value).toISOString().slice(0, 10);
              return formatDateIT(iso);
            }
          },
          grid: {
            color: COLOR_GRID
          }
        },
        y: {
          type: 'linear',
          position: 'left',
          min: Math.floor(minVal - 3),
          max: Math.ceil(maxVal + 3),
          ticks: {
            color: COLOR_TEXT,
            font: { size: 11 },
            callback: function (value) { return value + ' cm'; }
          },
          grid: {
            color: COLOR_GRID
          },
          title: {
            display: true,
            text: 'Circonferenza (cm)',
            color: COLOR_TEXT,
            font: { size: 11 }
          }
        }
      }
    }
  });
}

/* ============================================================
   buildPhaseMap(historyData)
   Costruisce una mappa id_misurazione_start → fase_teorica
   a partire dall'array workout_history.json.
   I record con fase_teorica null (es. il periodo aperto corrente)
   vengono ignorati. La mappa è usata dalle funzioni render per
   etichettare o colorare i punti del grafico in base alla fase.
   @param {Array} historyData — array da workout_history.json (o [])
   @returns {Object} mappa { [start_id]: fase_teorica_string }
   ============================================================ */
function buildPhaseMap(historyData) {
  const phaseMap = {};
  if (!Array.isArray(historyData)) return phaseMap;
  historyData.forEach(function (record) {
    if (record?.fase_teorica != null && record?.start) {
      phaseMap[record.start] = record.fase_teorica;
    }
  });
  return phaseMap;
}

/* ============================================================
   renderProgress(data, workoutHistoryData)
   Funzione principale di rendering della pagina Progressi.
   Riceve l'array di misurazioni da measurements.json e
   l'array degli intervalli da workout_history.json.
   workoutHistoryData può essere [] se il file non è disponibile:
   la pagina funziona correttamente anche senza di esso.
   I task figli aggiungono qui le chiamate alle loro render fn:
     - renderWeightBfChart(data)       → task weight-bf-chart
     - renderStrengthChart(data)       → task strength-chart
     - renderCircumferencesChart(data) → task circumferences-chart
     - renderMeasurementsTable(data)   → task measurements-table
   @param {Array} data               — array misurazioni measurements.json
   @param {Array} workoutHistoryData — array intervalli workout_history.json
   ============================================================ */
function renderProgress(data, workoutHistoryData) {
  if (!Array.isArray(data) || data.length === 0) {
    showError(progressErrorContainer, new Error('Array dati vuoto o non valido'));
    return;
  }

  /* Normalizza workoutHistoryData: se assente o non array usa [] */
  const historyData = Array.isArray(workoutHistoryData) ? workoutHistoryData : [];

  /* Costruisce la mappa fase per le funzioni render future */
  const phaseMap = buildPhaseMap(historyData);

  /* Aggiorna data ultima misurazione nell'header */
  const lastEntry = data[data.length - 1];
  const headerLastDate = document.getElementById('header-last-date');
  if (headerLastDate) {
    headerLastDate.textContent = formatDateIT(lastEntry?.data) ?? '—';
  }

  /* ── Grafici e tabella ── */
  renderWeightBfChart(data);
  renderStrengthChart(data);
  renderCircumferencesChart(data);
  renderMeasurementsTable(data);
}

/* ============================================================
   DOMContentLoaded — Promise.all fetch() + try/catch
   Carica measurements.json e workout_history.json in parallelo.
   Se workout_history.json non è disponibile (404 o errore rete)
   si usa un fallback [] e la pagina rimane funzionante.
   ============================================================ */
document.addEventListener('DOMContentLoaded', async function () {
  try {
    /* Fetch measurements (critico) + workout_history (opzionale) in parallelo */
    const [resM, resH] = await Promise.all([
      fetch(DATA_PATH_MEASUREMENTS),
      fetch(DATA_PATH_WORKOUT_HISTORY).catch(function (err) {
        console.error('[progress.js] workout_history.json non disponibile (rete):', err);
        return null;
      })
    ]);

    /* Verifica measurements (critico: se fallisce blocca tutto) */
    if (!resM.ok) throw new Error('HTTP ' + resM.status + ': ' + resM.statusText);
    const measurementsData = await resM.json();

    /* Verifica workout_history (opzionale: fallback []) */
    let workoutHistoryData = [];
    if (resH && resH.ok) {
      try {
        workoutHistoryData = await resH.json();
      } catch (parseErr) {
        console.error('[progress.js] Errore parsing workout_history.json:', parseErr);
      }
    } else if (resH && !resH.ok) {
      console.error('[progress.js] workout_history.json risposta HTTP ' + resH.status + ' — uso fallback []');
    }

    renderProgress(measurementsData, workoutHistoryData);
  } catch (e) {
    showError(progressErrorContainer, e);
  }
});
