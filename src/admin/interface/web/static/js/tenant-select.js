import { tenantsApi } from './api.js';
import { requireAuth } from './auth.js';

requireAuth();

const container = document.getElementById('tenant-grid');

async function loadTenants() {
  try {
    const tenants = await tenantsApi.list();

    container.innerHTML = '';

    tenants.forEach((tenant) => {
      const card = document.createElement('div');

      card.className = 'tenant-card';

      card.innerHTML = `
        <h3>${tenant.name}</h3>
        <p>${tenant.slug}</p>
      `;

      card.addEventListener('click', () => {
        sessionStorage.setItem(
          'sentra_tenant',
          JSON.stringify({
            id: tenant.id,
            name: tenant.name,
            slug: tenant.slug
          })
        );

        window.location.href = '/dashboard.html';
      });

      container.appendChild(card);
    });
  } catch (error) {
    container.innerHTML = '<p>Erro ao carregar tenants</p>';
  }
}

loadTenants();