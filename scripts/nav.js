// ============================================================
// NAV — showPage(n)
// Toggles .active class on pages and nav tabs.
// Pages are identified by id="page-N", tabs by .nav-tab order.
// ============================================================
function showPage(n) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('page-' + n).classList.add('active');
  document.querySelectorAll('.nav-tab')[n - 1].classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
