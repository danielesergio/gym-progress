/* ============================================================
   nav.js — Navigazione attiva condivisa
   Daniele Fitness | Imposta .active + aria-current="page"
   sul tab corrispondente alla pagina corrente.
   Incluso con <script src="js/nav.js" defer> in ogni HTML.
   ============================================================ */

/**
 * setActiveNav()
 * Legge window.location.pathname, confronta con l'href di ogni
 * <a class="nav-tab"> nel nav e applica .active + aria-current="page"
 * al tab corrispondente. Rimuove eventuali stati attivi hardcoded.
 */
function setActiveNav() {
  const navTabs = document.querySelectorAll('.nav-tab');
  if (!navTabs.length) return;

  // Pathname corrente (es. "/docs/dashboard.html" o solo "dashboard.html")
  const currentPath = window.location.pathname;

  // Estrae il nome del file dalla pathname (es. "dashboard.html")
  const currentFile = currentPath.split('/').pop() || 'dashboard.html';

  navTabs.forEach(function(tab) {
    // Rimuove stato attivo precedente (hardcoded nell'HTML)
    tab.classList.remove('active');
    tab.removeAttribute('aria-current');

    // Estrae il nome del file dall'href del tab (es. "dashboard.html")
    const tabHref = tab.getAttribute('href') || '';
    const tabFile = tabHref.split('/').pop();

    // Gestione pagina root (index.html o path vuoto → dashboard)
    const isRoot = (currentFile === '' || currentFile === 'index.html');
    const isTabDashboard = (tabFile === 'dashboard.html');

    if (tabFile === currentFile || (isRoot && isTabDashboard)) {
      tab.classList.add('active');
      tab.setAttribute('aria-current', 'page');
    }
  });
}

// Esegui al DOMContentLoaded
document.addEventListener('DOMContentLoaded', setActiveNav);
