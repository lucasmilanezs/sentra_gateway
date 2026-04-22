/* ============================================================
   SENTRA – dashboard.js
   Controla navegação da sidebar e troca de páginas
   ============================================================ */

/**
 * Abre ou fecha um grupo de submenu da sidebar.
 * @param {string} groupId - ID do grupo (ex: 'group-rotas')
 */
function toggleGroup(groupId) {
  const header = document.getElementById(`header-${groupId}`);
  const sub    = document.getElementById(`sub-${groupId}`);

  if (!header || !sub) return;

  const isOpen = sub.classList.contains('open');

  // Fecha todos os grupos abertos
  document.querySelectorAll('.nav-sub.open').forEach(el => el.classList.remove('open'));
  document.querySelectorAll('.nav-group-header.open').forEach(el => el.classList.remove('open'));

  // Abre o grupo clicado (se estava fechado)
  if (!isOpen) {
    sub.classList.add('open');
    header.classList.add('open');
  }
}

/**
 * Navega para uma página específica e marca o item de menu como ativo.
 * @param {string} pageId   - ID da <div class="page"> a exibir
 * @param {string} navId    - ID do item de nav a marcar como ativo
 * @param {string} groupId  - (opcional) ID do grupo pai para manter aberto
 */
function navigate(pageId, navId, groupId = null) {
  // ── Troca de página ──
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const target = document.getElementById(pageId);
  if (target) target.classList.add('active');

  // ── Marca item ativo ──
  document.querySelectorAll('.nav-item, .nav-sub-item').forEach(el => {
    el.classList.remove('active');
  });
  const navEl = document.getElementById(navId);
  if (navEl) navEl.classList.add('active');

  // ── Garante que o grupo pai está aberto ──
  if (groupId) {
    const sub    = document.getElementById(`sub-${groupId}`);
    const header = document.getElementById(`header-${groupId}`);
    if (sub)    sub.classList.add('open');
    if (header) header.classList.add('open');
  }
}

/**
 * Ativa a primeira página ao carregar o dashboard.
 */
document.addEventListener('DOMContentLoaded', () => {
  navigate('page-sobre', 'nav-sobre');
});
