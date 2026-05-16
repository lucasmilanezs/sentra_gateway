```js
import {
  tenantsApi,
  routesApi,
  healthApi
} from './api.js';

import {
  requireAuth,
  logout,
  currentTenant
} from './auth.js';

requireAuth();

const sections = document.querySelectorAll('.page-section');
const navItems = document.querySelectorAll('.nav-item');

const tenantName = document.getElementById('tenant-name');
const logoutBtn = document.getElementById('logout-btn');

const tenant = currentTenant();

if (tenant && tenant.name) {
  tenantName.innerText = tenant.name;
}

logoutBtn.addEventListener('click', logout);

navItems.forEach((item) => {
  item.addEventListener('click', () => {
    const page = item.dataset.page;

    sections.forEach((section) => {
      section.classList.remove('active');
    });

    document.getElementById(page).classList.add('active');

    loadPage(page);
  });
});

async function loadPage(page) {
  switch (page) {
    case 'overview':
      await loadOverview();
      break;

    case 'routes':
      await loadRoutes();
      break;

    case 'tenants':
      await loadTenants();
      break;
  }
}

async function loadOverview() {
  const health = await healthApi.check();

  document.getElementById('health-status').innerText = health.status;
  document.getElementById('postgres-status').innerText = health.postgres;
  document.getElementById('redis-status').innerText = health.redis;
}

async function loadTenants() {
  const list = document.getElementById('tenant-list');

  const tenants = await tenantsApi.list();

  list.innerHTML = tenants
    .map(
      (tenant) => `
      <tr>
        <td>${tenant.name}</td>
        <td>${tenant.slug}</td>
        <td>${tenant.domain || '-'}</td>
      </tr>
    `
    )
    .join('');
}

async function loadRoutes() {
  const list = document.getElementById('routes-list');

  const routes = await routesApi.list(tenant.id);

  list.innerHTML = routes
    .map(
      (route) => `
      <tr>
        <td>${route.method}</td>
        <td>${route.path_pattern}</td>
        <td>${route.backend_url}</td>
      </tr>
    `
    )
    .join('');
}

loadOverview();