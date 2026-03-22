/* ============================================================
   theme.js — Gestione tema Dark / Pro
   Daniele Fitness | Anti-FOUC: caricato SENZA defer nel <head>
   ============================================================ */

/* ── 1. initTheme() — applica subito il tema da localStorage ──
   DEVE essere chiamata senza DOMContentLoaded per evitare FOUC */
function initTheme() {
  const saved = localStorage.getItem('fitness-theme');
  if (saved === 'pro') {
    document.documentElement.classList.add('theme-pro');
  }
}

/* ── 2. updateToggleBtn(isPro) — aggiorna contenuto e aria-label ── */
function updateToggleBtn(isPro) {
  const btn = document.getElementById('theme-toggle-btn');
  if (!btn) return;

  if (isPro) {
    btn.setAttribute('aria-label', 'Attiva tema originale');
    btn.innerHTML = '<span class="theme-toggle-icon" aria-hidden="true">☀</span><span class="theme-toggle-label">Pro</span>';
    btn.classList.add('theme-toggle-btn--active');
  } else {
    btn.setAttribute('aria-label', 'Attiva tema professionale');
    btn.innerHTML = '<span class="theme-toggle-icon" aria-hidden="true">☾</span><span class="theme-toggle-label">Dark</span>';
    btn.classList.remove('theme-toggle-btn--active');
  }
}

/* ── 3. toggleTheme() — inverte stato, salva, aggiorna UI ── */
function toggleTheme() {
  const isPro = document.documentElement.classList.toggle('theme-pro');
  localStorage.setItem('fitness-theme', isPro ? 'pro' : 'original');
  updateToggleBtn(isPro);
}

/* ── Esecuzione immediata anti-FOUC ── */
initTheme();

/* ── 4. DOMContentLoaded — aggancia listener e sincronizza pulsante ── */
document.addEventListener('DOMContentLoaded', function () {
  const btn = document.getElementById('theme-toggle-btn');
  if (btn) {
    btn.addEventListener('click', toggleTheme);
  }
  const isPro = document.documentElement.classList.contains('theme-pro');
  updateToggleBtn(isPro);
});
