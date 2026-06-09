// Lógica extraída do tenant-select.html — preservada integralmente

  import { tenantsApi, authApi } from '../api.js';
  import { requireAuth, logout } from '../auth.js';

  if (!requireAuth()) throw new Error('not authenticated');
  const me = await authApi.me();

  if (me.role !== 'superuser') {
    window.location.href = '/dashboard.html';
  }

  document.getElementById('ts-logout').addEventListener('click', logout);

  // Carrega email do usuário
  authApi.me().then(me => {
    document.getElementById('ts-user-email').textContent = me.email;
  }).catch(() => {});

  // Carrega tenants
  async function loadTenants() {
    const grid = document.getElementById('tenant-grid');
    const errEl = document.getElementById('ts-error');
    grid.innerHTML = '<p class="ts-empty">Carregando…</p>';
    errEl.style.display = 'none';

    try {
      const list = await tenantsApi.list();
      if (!list.length) {
        grid.innerHTML = '<p class="ts-empty">Nenhum tenant cadastrado.</p>';
        return;
      }
      grid.innerHTML = '';
      list.forEach(t => {
        const card = document.createElement('div');
        card.className = 'tenant-card';
        card.innerHTML = `
          <div class="tc-name">${t.name}</div>
          <div class="tc-alias">${t.alias}</div>
          ${t.domain ? `<div class="tc-domain">${t.domain}</div>` : ''}
          <span class="tc-arrow">→</span>
        `;
        card.addEventListener('click', () => {
          sessionStorage.setItem('sentra_tenant', JSON.stringify({ id: t.id, name: t.name, alias: t.alias }));
          window.location.href = '/dashboard.html';
        });
        grid.appendChild(card);
      });
    } catch (err) {
      grid.innerHTML = '';
      errEl.textContent = err.detail || 'Erro ao carregar tenants.';
      errEl.style.display = 'block';
    }
  }

  loadTenants();

  // Modal novo tenant
  const modal = document.getElementById('modal-new');
  document.getElementById('btn-new-tenant').addEventListener('click', () => {
    modal.style.display = 'flex';
    document.getElementById('nt-name').focus();
  });
  document.getElementById('nt-cancel').addEventListener('click', () => {
    modal.style.display = 'none';
  });
  modal.addEventListener('click', e => { if (e.target === modal) modal.style.display = 'none'; });

  document.getElementById('nt-save').addEventListener('click', async () => {
    const name   = document.getElementById('nt-name').value.trim();
    const alias   = document.getElementById('nt-alias').value.trim();
    const domain = document.getElementById('nt-domain').value.trim() || undefined;
    const errEl  = document.getElementById('nt-error');
    errEl.style.display = 'none';

    if (!name || !alias) {
      errEl.textContent = 'Nome e alias são obrigatórios.';
      errEl.style.display = 'block';
      return;
    }

    try {
      await tenantsApi.create({ name, alias, domain });
      modal.style.display = 'none';
      document.getElementById('nt-name').value = '';
      document.getElementById('nt-alias').value = '';
      document.getElementById('nt-domain').value = '';
      await loadTenants();
    } catch (err) {
      errEl.textContent = err.detail || 'Erro ao criar tenant.';
      errEl.style.display = 'block';
    }
  });
