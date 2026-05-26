// Lógica extraída do dashboard.html
// Fix aplicado: hidratação do tenant (name/alias) para admin/member

import { authApi, tenantsApi, domainsApi, routesApi, policiesApi, healthApi, auditApi, rawLogsApi, subUsersApi } from '../api.js';
import { requireAuth, logout, currentTenant, currentUser, saveCurrentUser, isSuperUser, isAdmin, hasPermission } from '../auth.js';

if (!requireAuth()) throw new Error('not authenticated');
let tenant = null;
// ── Topbar base (não depende de identidade) ───────────────────────────────
document.getElementById('btn-logout').addEventListener('click', logout);
document.getElementById('btn-switch').addEventListener('click', () => {
  sessionStorage.removeItem('sentra_tenant');
  window.location.href = '/tenant-select.html';
});

// ── Navegação ─────────────────────────────────────────────────────────────
const PAGE_LOADERS = {
  overview: loadOverview,
  tenants:  loadTenants,
  domains:  loadDomains,
  routes:   loadRoutes,
  members:  loadMembers,
  metrics:  loadMetrics,
  conta:    loadConta,
  audit:    loadAudit,
  'raw-logs': loadRawLogs,
};

document.querySelectorAll('.nav-item[data-page]').forEach(btn => {
  btn.addEventListener('click', () => navigate(btn.dataset.page));
});

// ── Audit polling ─────────────────────────────────────────────────────────
// Roda apenas enquanto a aba de auditoria está visível.
// Polling diferencial: só insere linhas novas no topo — sem reescrever a
// tabela inteira a cada tick.
const AUDIT_POLL_MS = 8000;
let _auditPollTimer  = null;
let _auditNewestTs   = null;   // ISO string do registro mais recente exibido

async function _auditPollTick() {
  const tbody = document.getElementById('tbody-audit');
  if (!tbody) return;
  try {
    const rows = await auditApi.list(tenant?.id || null, 100);
    if (!rows.length) return;

    // Quantos registros são mais novos que o último exibido
    const newRows = _auditNewestTs
      ? rows.filter(r => r.created_at > _auditNewestTs)
      : rows;

    if (!newRows.length) return;

    _auditNewestTs = rows[0].created_at;

    // Na primeira carga (placeholder ainda presente) substitui tudo
    if (tbody.querySelector('td[colspan]')) {
      tbody.innerHTML = '';
      rows.forEach(r => tbody.appendChild(_auditRow(r)));
      document.getElementById('audit-empty').style.display = rows.length ? 'none' : 'block';
      return;
    }

    // Insere novas linhas no topo com highlight transitório
    newRows.slice().reverse().forEach(r => {
      const tr = _auditRow(r);
      tr.style.transition = 'background 1.2s ease';
      tr.style.background = 'rgba(82,196,138,.15)';
      tbody.prepend(tr);
      requestAnimationFrame(() => { tr.style.background = ''; });
    });

    // Mantém no máximo 100 linhas
    while (tbody.rows.length > 100) tbody.deleteRow(tbody.rows.length - 1);

  } catch { /* falha silenciosa — estado anterior permanece */ }
}

function _auditRow(r) {
  const tr   = document.createElement('tr');
  const when = new Date(r.created_at).toLocaleString('pt-BR');
  const cls  = ['GET','POST','PUT','PATCH','DELETE'].includes(r.method) ? `m-${r.method}` : 'm-OTHER';
  tr.innerHTML = `
    <td style="font-size:.8rem;color:var(--text-sub)">${when}</td>
    <td><span class="badge ${cls}">${r.method}</span></td>
    <td style="font-family:monospace;font-size:.8rem">${r.path}</td>
    <td style="font-family:monospace">${r.status_code}</td>
    <td style="color:var(--text-sub)">${Math.round(r.latency_ms)} ms</td>
    <td style="font-family:monospace;font-size:.78rem;color:var(--text-sub)">${r.client_ip}</td>`;
  return tr;
}

function _startAuditPoll() {
  if (_auditPollTimer) return;
  _auditNewestTs  = null;
  _auditPollTimer = setInterval(_auditPollTick, AUDIT_POLL_MS);
  _auditPollTick();
}

function _stopAuditPoll() {
  if (!_auditPollTimer) return;
  clearInterval(_auditPollTimer);
  _auditPollTimer = null;
}

function navigate(pageId) {
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const btn  = document.querySelector(`.nav-item[data-page="${pageId}"]`);
  const page = document.getElementById('page-' + pageId);
  if (btn)  btn.classList.add('active');
  if (page) page.classList.add('active');

  if (pageId === 'audit') { _startAuditPoll(); }
  else                    { _stopAuditPoll();  }

  if (pageId !== 'audit') PAGE_LOADERS[pageId]?.();
}

// ── Inicialização — tudo depende de me() ─────────────────────────────────
// Uma única chamada ao servidor confirma a identidade antes de qualquer
// decisão de UI. Nenhuma inferência por sessionStorage antes disso.
(async function init() {
  try {
    const me = await authApi.me();
    saveCurrentUser(me);

    if (me.role === 'superuser') {
      tenant = currentTenant();

      if (!tenant) {
        window.location.href = '/tenant-select.html';
        return;
      }
    } else {
      if (!me.tenant_id) {
        logout();
        return;
      }

  tenant = { id: me.tenant_id };
  sessionStorage.setItem('sentra_tenant', JSON.stringify(tenant));
  // Fix: hidratar name/alias para exibir na topbar e no perfil.
  // Se o endpoint não aceitar a leitura por admin/member, o catch
  // silencioso preserva o comportamento anterior (sem UUID visível —
  // o profile-tenant usa o id como último fallback, que é o original).
  try {
    const full = await tenantsApi.get(me.tenant_id);
    if (full?.name || full?.alias) {
      tenant = { id: full.id, name: full.name, alias: full.alias };
      sessionStorage.setItem('sentra_tenant', JSON.stringify(tenant));
    }
  } catch {}
}

    // Topbar
    document.getElementById('topbar-tenant').textContent = tenant?.name || tenant?.alias || '';
    document.getElementById('topbar-user').textContent   = me.email;

    // Perfil
    document.getElementById('profile-email').textContent = me.email;
    document.getElementById('profile-role').textContent  = me.role || '—';
    document.getElementById('profile-tenant').textContent =
      tenant ? (tenant.name || tenant.alias || tenant.id) : 'Superuser — sem tenant fixo';

    if (me.role === 'member' && me.permissions?.length) {
      document.getElementById('profile-perms-row').style.display = '';
      document.getElementById('profile-perms').textContent = me.permissions.join(', ');
    }

    // btn-switch e nav-tenants: apenas superuser real (role confirmado pelo servidor)
    if (me.role === 'superuser') {
      document.getElementById('btn-switch').style.display  = 'inline-block';
      document.getElementById('nav-tenants').style.display = 'flex';
    }

    // Visibilidade das abas funcionais
    const permMap = {
      'nav-domains':  'domains',
      'nav-routes':   'routes',
      'nav-audit':    'audit',
      'nav-raw-logs': 'audit',
      'nav-metrics':  'metrics',
    };
    for (const [id, perm] of Object.entries(permMap)) {
      if (hasPermission(perm)) {
        document.getElementById(id).style.display = 'flex';
      }
    }
    if (isAdmin()) {
      document.getElementById('nav-members').style.display = 'flex';
    }

    navigate('overview');
  } catch {
    // token inválido ou expirado — api.js já redireciona para index no 401
  }
})();

// ── OVERVIEW ─────────────────────────────────────────────────────────────
async function loadOverview() {
  try {
    const h = await healthApi.check();
    document.getElementById('ov-status').textContent    = h.status === 'ok' ? '✓' : '✗';
    document.getElementById('ov-postgres').textContent  = h.postgres_connected ? '✓' : '✗';
    document.getElementById('ov-postgres-sub').textContent = h.postgres_connected ? 'conectado' : 'offline';
  } catch { document.getElementById('ov-status').textContent = 'erro'; }

  if (tenant) {
    try {
      const [routes, domains] = await Promise.all([
        routesApi.list(tenant.id),
        domainsApi.list(tenant.id),
      ]);
      document.getElementById('ov-routes').textContent  = routes.length;
      document.getElementById('ov-domains').textContent = domains.length;
    } catch {}
  }
}

// ── TENANTS (superuser) ───────────────────────────────────────────────────
async function loadTenants() {
  const tbody = document.getElementById('tbody-tenants');
  const empty = document.getElementById('tenants-empty');
  tbody.innerHTML = '<tr><td colspan="5" style="font-style:italic;color:var(--text-sub)">Carregando…</td></tr>';
  empty.style.display = 'none';

  try {
    const list = await tenantsApi.list();
    tbody.innerHTML = '';
    if (!list.length) { empty.style.display = 'block'; return; }

    const domainLists = await Promise.all(
      list.map(t => domainsApi.list(t.id).catch(() => []))
    );

    list.forEach((t, i) => {
      const doms = domainLists[i];
      const domHtml = doms.length
        ? doms.map(d => `<span class="domain-pill">${d.domain}</span>`).join('')
        : '<span style="opacity:.4;font-style:italic;font-size:.8rem">nenhum</span>';
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${t.name}</td>
        <td style="font-style:italic;color:var(--text-sub)">${t.alias}</td>
        <td>${domHtml}</td>
        <td style="font-size:.78rem;color:var(--text-sub)">${t.created_at ? new Date(t.created_at).toLocaleDateString('pt-BR') : '—'}</td>
        <td>
          <button class="btn-icon" onclick="_editTenant('${t.id}','${esc(t.name)}','${esc(t.alias)}')">Editar</button>
          <button class="btn-icon danger" onclick="_deleteTenant('${t.id}','${esc(t.name)}')">Excluir</button>
        </td>`;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:#a03030;font-style:italic">${err.detail||'Erro'}</td></tr>`;
  }
}

function _openTenantModal(id='', name='', alias='') {
  document.getElementById('modal-tenant-title').textContent = id ? 'Editar tenant' : 'Novo tenant';
  document.getElementById('tenant-edit-id').value = id;
  document.getElementById('t-name').value  = name;
  document.getElementById('t-alias').value = alias;
  document.getElementById('t-error').style.display = 'none';
  document.getElementById('modal-tenant').style.display = 'flex';
  document.getElementById('t-name').focus();
}
window._editTenant = _openTenantModal;

document.getElementById('btn-new-tenant').addEventListener('click', () => _openTenantModal());
document.getElementById('t-cancel').addEventListener('click', () => { document.getElementById('modal-tenant').style.display = 'none'; });
document.getElementById('modal-tenant').addEventListener('click', e => { if (e.target.id === 'modal-tenant') document.getElementById('modal-tenant').style.display = 'none'; });

document.getElementById('t-save').addEventListener('click', async () => {
  const id    = document.getElementById('tenant-edit-id').value;
  const name  = document.getElementById('t-name').value.trim();
  const alias = document.getElementById('t-alias').value.trim();
  const errEl = document.getElementById('t-error');
  errEl.style.display = 'none';
  if (!name || !alias) { errEl.textContent = 'Nome e alias são obrigatórios.'; errEl.style.display = 'block'; return; }
  try {
    id ? await tenantsApi.update(id, { name, alias }) : await tenantsApi.create({ name, alias });
    document.getElementById('modal-tenant').style.display = 'none';
    loadTenants();
  } catch (err) { errEl.textContent = err.detail || 'Erro ao salvar.'; errEl.style.display = 'block'; }
});

window._deleteTenant = async function(id, name) {
  if (!confirm(`Excluir tenant "${name}"?`)) return;
  try { await tenantsApi.delete(id); loadTenants(); }
  catch (err) { alert(err.detail || 'Erro ao excluir.'); }
};

// ── DOMAINS ───────────────────────────────────────────────────────────────
async function loadDomains() {
  const tenantId = tenant?.id;
  const badge  = document.getElementById('domains-tenant-badge');
  const tbody  = document.getElementById('tbody-domains');
  const empty  = document.getElementById('domains-empty');

  badge.textContent = tenant ? `Tenant: ${tenant.name || tenant.alias || tenant.id}` : '';

  if (!tenantId) {
    tbody.innerHTML = '<tr><td colspan="4" style="font-style:italic;color:var(--text-sub)">Selecione um tenant para ver os domains.</td></tr>';
    return;
  }

  tbody.innerHTML = '<tr><td colspan="4" style="font-style:italic;color:var(--text-sub)">Carregando…</td></tr>';
  empty.style.display = 'none';

  try {
    const list = await domainsApi.list(tenantId);
    tbody.innerHTML = '';
    if (!list.length) { empty.style.display = 'block'; return; }

    const policies = await Promise.all(
      list.map(d => domainsApi.getPolicy(tenantId, d.id).catch(() => null))
    );

    list.forEach((d, i) => {
      const p = policies[i];
      const pHtml = p
        ? `<span class="policy-on">JWT${p.rate_limit_per_minute ? ` · ${p.rate_limit_per_minute}/min` : ''}${p.allowed_roles?.length ? ` · ${p.allowed_roles.join(',')}` : ''}${_policyConstraintSummary(p)}</span>
           <button class="btn-icon" onclick="_openDomainPolicyModal('${d.id}','${esc(d.domain)}')">Editar</button>`
        : `<span class="policy-off">sem política</span>
           <button class="btn-icon" onclick="_openDomainPolicyModal('${d.id}','${esc(d.domain)}')">Configurar</button>`;

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-family:monospace;font-size:.88rem">${d.domain}</td>
        <td>${pHtml}</td>
        <td style="font-size:.78rem;color:var(--text-sub)">${d.created_at ? new Date(d.created_at).toLocaleDateString('pt-BR') : '—'}</td>
        <td>
          <button class="btn-icon danger" onclick="_deleteDomain('${d.id}','${esc(d.domain)}')">Remover</button>
        </td>`;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4" style="color:#a03030;font-style:italic">${err.detail||'Erro'}</td></tr>`;
  }
}

document.getElementById('btn-new-domain').addEventListener('click', () => {
  document.getElementById('d-domain').value = '';
  document.getElementById('d-error').style.display = 'none';
  document.getElementById('modal-domain').style.display = 'flex';
  document.getElementById('d-domain').focus();
});
document.getElementById('d-cancel').addEventListener('click', () => { document.getElementById('modal-domain').style.display = 'none'; });
document.getElementById('modal-domain').addEventListener('click', e => { if (e.target.id === 'modal-domain') document.getElementById('modal-domain').style.display = 'none'; });

document.getElementById('d-save').addEventListener('click', async () => {
  const domain = document.getElementById('d-domain').value.trim();
  const errEl  = document.getElementById('d-error');
  errEl.style.display = 'none';
  if (!domain) { errEl.textContent = 'Informe o domain.'; errEl.style.display = 'block'; return; }
  try {
    await domainsApi.create(tenant.id, { domain });
    document.getElementById('modal-domain').style.display = 'none';
    loadDomains();
  } catch (err) { errEl.textContent = err.detail || 'Erro ao criar domain.'; errEl.style.display = 'block'; }
});

window._deleteDomain = async function(domainId, domain) {
  if (!confirm(`Remover domain "${domain}"? O gateway deixará de aceitar requisições com este Host.`)) return;
  try { await domainsApi.delete(tenant.id, domainId); loadDomains(); }
  catch (err) { alert(err.detail || 'Erro ao remover.'); }
};

window._openDomainPolicyModal = async function(domainId, domainName) {
  document.getElementById('dp-domain-id').value = domainId;
  document.getElementById('dp-domain-name').textContent = domainName;
  document.getElementById('dp-requires-auth').checked = false;
  document.getElementById('dp-rate-limit').value = '';
  document.getElementById('dp-roles').value = '';
  document.getElementById('dp-jwt-validate-exp').checked = true;
  document.getElementById('dp-jwt-issuer').value = '';
  document.getElementById('dp-jwt-audience').value = '';
  _setCsvInput('dp-required-headers', []);
  _setCsvInput('dp-forbidden-headers', []);
  _setCsvInput('dp-required-params', []);
  _setCsvInput('dp-forbidden-params', []);
  document.getElementById('dp-error').style.display = 'none';
  document.getElementById('modal-domain-policy').style.display = 'flex';
  try {
    const p = await domainsApi.getPolicy(tenant.id, domainId);
    if (p) {
      document.getElementById('dp-requires-auth').checked = p.requires_auth;
      document.getElementById('dp-rate-limit').value = p.rate_limit_per_minute || '';
      document.getElementById('dp-roles').value = (p.allowed_roles || []).join(', ');
      document.getElementById('dp-jwt-validate-exp').checked = p.jwt_validate_exp ?? true;
      document.getElementById('dp-jwt-issuer').value = p.jwt_issuer || '';
      document.getElementById('dp-jwt-audience').value = p.jwt_audience || '';
      _setCsvInput('dp-required-headers', p.required_headers || []);
      _setCsvInput('dp-forbidden-headers', p.forbidden_headers || []);
      _setCsvInput('dp-required-params', p.required_params || []);
      _setCsvInput('dp-forbidden-params', p.forbidden_params || []);
    }
  } catch {}
};

document.getElementById('dp-cancel').addEventListener('click', () => { document.getElementById('modal-domain-policy').style.display = 'none'; });
document.getElementById('modal-domain-policy').addEventListener('click', e => { if (e.target.id === 'modal-domain-policy') document.getElementById('modal-domain-policy').style.display = 'none'; });

document.getElementById('dp-save').addEventListener('click', async () => {
  const domainId     = document.getElementById('dp-domain-id').value;
  const requiresAuth = document.getElementById('dp-requires-auth').checked;
  const rateRaw      = document.getElementById('dp-rate-limit').value.trim();
  const rolesRaw     = document.getElementById('dp-roles').value.trim();
  const errEl        = document.getElementById('dp-error');
  errEl.style.display = 'none';
  const rate_limit_per_minute = rateRaw ? parseInt(rateRaw, 10) : null;
  const allowed_roles = rolesRaw ? rolesRaw.split(',').map(s => s.trim()).filter(Boolean) : [];
  try {
    await domainsApi.upsertPolicy(tenant.id, domainId, {
      requires_auth: requiresAuth, rate_limit_per_minute, allowed_roles,
      jwt_validate_exp: document.getElementById('dp-jwt-validate-exp').checked,
      jwt_issuer:   document.getElementById('dp-jwt-issuer').value.trim()   || null,
      jwt_audience: document.getElementById('dp-jwt-audience').value.trim() || null,
      required_headers: _csvInput('dp-required-headers'),
      forbidden_headers: _csvInput('dp-forbidden-headers'),
      required_params: _csvInput('dp-required-params'),
      forbidden_params: _csvInput('dp-forbidden-params'),
    });
    document.getElementById('modal-domain-policy').style.display = 'none';
    loadDomains();
  } catch (err) { errEl.textContent = err.detail || 'Erro ao salvar política.'; errEl.style.display = 'block'; }
});

document.getElementById('dp-delete').addEventListener('click', async () => {
  const domainId = document.getElementById('dp-domain-id').value;
  try {
    await domainsApi.deletePolicy(tenant.id, domainId);
    document.getElementById('modal-domain-policy').style.display = 'none';
    loadDomains();
  } catch (err) { document.getElementById('dp-error').textContent = err.detail || 'Erro ao remover.'; document.getElementById('dp-error').style.display = 'block'; }
});

// ── ROTAS ─────────────────────────────────────────────────────────────────
async function loadRoutes() {
  const tbody = document.getElementById('tbody-routes');
  const empty = document.getElementById('routes-empty');
  const badge = document.getElementById('routes-tenant-badge');
  badge.textContent = tenant ? `Tenant: ${tenant.name || tenant.alias || tenant.id}` : '';
  tbody.innerHTML = '<tr><td colspan="5" style="font-style:italic;color:var(--text-sub)">Carregando…</td></tr>';
  empty.style.display = 'none';

  try {
    const list = await routesApi.list(tenant?.id);
    tbody.innerHTML = '';
    if (!list.length) { empty.style.display = 'block'; return; }

    const policies = await Promise.all(
      list.map(r => policiesApi.get(r.id).catch(() => null))
    );

    list.forEach((r, i) => {
      const p = policies[i];
      const methods = Array.isArray(r.methods) ? r.methods : (r.method ? [r.method] : []);
      const methodBadges = methods.map(m => {
        const cls = ['GET','POST','PUT','PATCH','DELETE','OPTIONS','HEAD'].includes(m) ? `m-${m}` : 'm-OTHER';
        return `<span class="badge ${cls}">${m}</span>`;
      }).join('');

      const policyHtml = p
        ? `<span class="policy-on">JWT${p.rate_limit_per_minute ? ` · ${p.rate_limit_per_minute}/min` : ''}${p.allowed_roles?.length ? ` · ${p.allowed_roles.join(',')}` : ''}${_policyConstraintSummary(p)}</span>`
        : `<span class="policy-off">sem política</span>`;

      const methodsJson = esc(JSON.stringify(methods));
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${methodBadges}</td>
        <td style="font-family:monospace;font-size:.85rem">${r.path_pattern}</td>
        <td style="font-size:.8rem;color:var(--text-sub);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${r.backend_url}">${r.backend_url}</td>
        <td>${policyHtml}</td>
        <td>
          <button class="btn-icon" onclick="_openPolicyModal('${r.id}','${esc(r.path_pattern)}')">Política</button>
          <button class="btn-icon" onclick="_editRoute('${r.id}','${methodsJson}','${esc(r.path_pattern)}','${esc(r.backend_url)}')">Editar</button>
          <button class="btn-icon danger" onclick="_deleteRoute('${r.id}','${esc(r.path_pattern)}')">Excluir</button>
        </td>`;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:#a03030;font-style:italic">${err.detail||'Erro'}</td></tr>`;
  }
}

function _setMethodCheckboxes(methods) {
  document.querySelectorAll('input[name="r-methods"]').forEach(cb => {
    cb.checked = methods.includes(cb.value);
    cb.closest('.method-check').classList.toggle('checked', cb.checked);
  });
}

document.querySelectorAll('input[name="r-methods"]').forEach(cb => {
  cb.addEventListener('change', () => {
    cb.closest('.method-check').classList.toggle('checked', cb.checked);
  });
});

function _openRouteModal(id='', methods=[], path='', backend='') {
  document.getElementById('modal-route-title').textContent = id ? 'Editar rota' : 'Nova rota';
  document.getElementById('r-edit-id').value = id;
  _setMethodCheckboxes(Array.isArray(methods) ? methods : []);
  document.getElementById('r-path').value    = path;
  document.getElementById('r-backend').value = backend;
  document.getElementById('r-error').style.display = 'none';
  document.getElementById('r-wildcard').classList.toggle('visible', path.includes('/*'));
  document.getElementById('modal-route').style.display = 'flex';
  document.getElementById('r-path').focus();
}

document.getElementById('r-path').addEventListener('input', e => {
  document.getElementById('r-wildcard').classList.toggle('visible', e.target.value.includes('/*'));
});

window._editRoute = (id, methodsJson, path, backend) => {
  let methods = [];
  try { methods = JSON.parse(methodsJson); } catch {}
  _openRouteModal(id, methods, path, backend);
};

document.getElementById('btn-new-route').addEventListener('click', () => _openRouteModal());
document.getElementById('r-cancel').addEventListener('click', () => { document.getElementById('modal-route').style.display = 'none'; });
document.getElementById('modal-route').addEventListener('click', e => { if (e.target.id === 'modal-route') document.getElementById('modal-route').style.display = 'none'; });

document.getElementById('r-save').addEventListener('click', async () => {
  const id      = document.getElementById('r-edit-id').value;
  const methods = [...document.querySelectorAll('input[name="r-methods"]:checked')].map(el => el.value);
  const path    = document.getElementById('r-path').value.trim();
  const backend = document.getElementById('r-backend').value.trim();
  const errEl   = document.getElementById('r-error');
  errEl.style.display = 'none';

  if (!methods.length) { errEl.textContent = 'Selecione ao menos um método HTTP.'; errEl.style.display = 'block'; return; }
  if (!path || !backend) { errEl.textContent = 'Path e backend URL são obrigatórios.'; errEl.style.display = 'block'; return; }
  if (!path.startsWith('/')) { errEl.textContent = 'Path deve começar com /.'; errEl.style.display = 'block'; return; }

  try {
    if (id) {
      await routesApi.update(id, { methods, path_pattern: path, backend_url: backend });
    } else {
      await routesApi.create({ tenant_id: tenant?.id, methods, path_pattern: path, backend_url: backend });
    }
    document.getElementById('modal-route').style.display = 'none';
    loadRoutes();
  } catch (err) { errEl.textContent = err.detail || 'Erro ao salvar rota.'; errEl.style.display = 'block'; }
});

window._deleteRoute = async function(id, path) {
  if (!confirm(`Excluir rota "${path}"?`)) return;
  try { await routesApi.delete(id); loadRoutes(); }
  catch (err) { alert(err.detail || 'Erro ao excluir.'); }
};

window._openPolicyModal = async function(routeId, routePath) {
  document.getElementById('p-route-id').value = routeId;
  document.getElementById('p-route-path').textContent = routePath;
  document.getElementById('p-error').style.display = 'none';
  document.getElementById('p-requires-auth').checked = false;
  document.getElementById('p-rate-limit').value = '';
  document.getElementById('p-roles').value = '';
  document.getElementById('p-jwt-validate-exp').checked = true;
  document.getElementById('p-jwt-issuer').value = '';
  document.getElementById('p-jwt-audience').value = '';
  _setCsvInput('p-required-headers', []);
  _setCsvInput('p-forbidden-headers', []);
  _setCsvInput('p-required-params', []);
  _setCsvInput('p-forbidden-params', []);
  document.getElementById('modal-policy').style.display = 'flex';
  try {
    const p = await policiesApi.get(routeId);
    if (p) {
      document.getElementById('p-requires-auth').checked = p.requires_auth;
      document.getElementById('p-rate-limit').value = p.rate_limit_per_minute || '';
      document.getElementById('p-roles').value = (p.allowed_roles || []).join(', ');
      document.getElementById('p-jwt-validate-exp').checked = p.jwt_validate_exp ?? true;
      document.getElementById('p-jwt-issuer').value = p.jwt_issuer || '';
      document.getElementById('p-jwt-audience').value = p.jwt_audience || '';
      _setCsvInput('p-required-headers', p.required_headers || []);
      _setCsvInput('p-forbidden-headers', p.forbidden_headers || []);
      _setCsvInput('p-required-params', p.required_params || []);
      _setCsvInput('p-forbidden-params', p.forbidden_params || []);
    }
  } catch {}
};

document.getElementById('p-cancel').addEventListener('click', () => { document.getElementById('modal-policy').style.display = 'none'; });
document.getElementById('modal-policy').addEventListener('click', e => { if (e.target.id === 'modal-policy') document.getElementById('modal-policy').style.display = 'none'; });

document.getElementById('p-save').addEventListener('click', async () => {
  const routeId      = document.getElementById('p-route-id').value;
  const requiresAuth = document.getElementById('p-requires-auth').checked;
  const rateRaw      = document.getElementById('p-rate-limit').value.trim();
  const rolesRaw     = document.getElementById('p-roles').value.trim();
  const errEl        = document.getElementById('p-error');
  errEl.style.display = 'none';
  const rate_limit_per_minute = rateRaw ? parseInt(rateRaw, 10) : null;
  const allowed_roles = rolesRaw ? rolesRaw.split(',').map(s => s.trim()).filter(Boolean) : [];
  try {
    await policiesApi.upsert(routeId, {
      requires_auth: requiresAuth, rate_limit_per_minute, allowed_roles,
      jwt_validate_exp: document.getElementById('p-jwt-validate-exp').checked,
      jwt_issuer:   document.getElementById('p-jwt-issuer').value.trim()   || null,
      jwt_audience: document.getElementById('p-jwt-audience').value.trim() || null,
      required_headers: _csvInput('p-required-headers'),
      forbidden_headers: _csvInput('p-forbidden-headers'),
      required_params: _csvInput('p-required-params'),
      forbidden_params: _csvInput('p-forbidden-params'),
    });
    document.getElementById('modal-policy').style.display = 'none';
    loadRoutes();
  } catch (err) { errEl.textContent = err.detail || 'Erro ao salvar.'; errEl.style.display = 'block'; }
});

document.getElementById('p-delete').addEventListener('click', async () => {
  const routeId = document.getElementById('p-route-id').value;
  try {
    await policiesApi.delete(routeId);
    document.getElementById('modal-policy').style.display = 'none';
    loadRoutes();
  } catch (err) { document.getElementById('p-error').textContent = err.detail || 'Erro ao remover.'; document.getElementById('p-error').style.display = 'block'; }
});

// ── MEMBROS ───────────────────────────────────────────────────────────────
async function loadMembers() {
  if (!tenant) {
    document.getElementById('tbody-members').innerHTML =
      '<tr><td colspan="4" style="font-style:italic;color:var(--text-sub)">Selecione um tenant para ver os membros.</td></tr>';
    return;
  }

  const tbody = document.getElementById('tbody-members');
  const empty = document.getElementById('members-empty');
  const badge = document.getElementById('members-tenant-badge');

  badge.textContent = `Tenant: ${tenant.name || tenant.alias || tenant.id}`;
  tbody.innerHTML = '<tr><td colspan="4" style="font-style:italic;color:var(--text-sub)">Carregando…</td></tr>';
  empty.style.display = 'none';

  try {
    const members = await subUsersApi.listByTenant(tenant.id);
    tbody.innerHTML = '';
    if (!members.length) { empty.style.display = 'block'; return; }

    members.forEach(m => {
      const tr = document.createElement('tr');
      const perms = (m.permissions || [])
        .map(p => `<span class="policy-on" style="font-size:.75rem;padding:2px 7px">${p}</span>`)
        .join(' ');
      const when = new Date(m.created_at).toLocaleDateString('pt-BR');
      tr.innerHTML = `
        <td>${m.email}</td>
        <td>${perms || '<span style="color:var(--text-sub);font-size:.8rem;font-style:italic">nenhuma</span>'}</td>
        <td style="color:var(--text-sub);font-size:.85rem">${when}</td>
        <td>
          <button class="btn-icon"
            data-member-id="${m.id}"
            data-member-email="${esc(m.email)}"
            data-member-perms='${JSON.stringify(m.permissions || [])}'>
            Editar
          </button>
        </td>`;
      tbody.appendChild(tr);
    });

    tbody.querySelectorAll('[data-member-id]').forEach(btn => {
      btn.addEventListener('click', () => _openEditMember(
        btn.dataset.memberId,
        btn.dataset.memberEmail,
        JSON.parse(btn.dataset.memberPerms),
      ));
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4" style="color:#a03030">${err.detail || 'Erro ao carregar membros'}</td></tr>`;
  }
}

function _openNewMember() {
  document.getElementById('modal-member-title').textContent = 'Novo membro';
  document.getElementById('member-edit-id').value = '';
  document.getElementById('m-email').value = '';
  document.getElementById('m-email').disabled = false;
  document.getElementById('m-password').value = '';
  document.getElementById('m-password-field').style.display = 'block';
  document.getElementById('m-delete').style.display = 'none';
  document.getElementById('m-error').style.display = 'none';
  ['domains','routes','audit','metrics'].forEach(p => {
    document.getElementById(`m-perm-${p}`).checked = false;
  });
  document.getElementById('modal-member').style.display = 'flex';
  document.getElementById('m-email').focus();
}

function _openEditMember(id, email, permissions) {
  document.getElementById('modal-member-title').textContent = 'Editar membro';
  document.getElementById('member-edit-id').value = id;
  document.getElementById('m-email').value = email;
  document.getElementById('m-email').disabled = true;
  document.getElementById('m-password-field').style.display = 'none';
  document.getElementById('m-delete').style.display = 'inline-flex';
  document.getElementById('m-error').style.display = 'none';
  ['domains','routes','audit','metrics'].forEach(p => {
    document.getElementById(`m-perm-${p}`).checked = permissions.includes(p);
  });
  document.getElementById('modal-member').style.display = 'flex';
}

function _closeMemberModal() {
  document.getElementById('modal-member').style.display = 'none';
  document.getElementById('m-email').disabled = false;
}

document.getElementById('btn-new-member').addEventListener('click', _openNewMember);
document.getElementById('m-cancel').addEventListener('click', _closeMemberModal);
document.getElementById('modal-member').addEventListener('click', e => { if (e.target.id === 'modal-member') _closeMemberModal(); });

document.getElementById('m-save').addEventListener('click', async () => {
  const id    = document.getElementById('member-edit-id').value;
  const email = document.getElementById('m-email').value.trim();
  const pass  = document.getElementById('m-password').value;
  const perms = ['domains','routes','audit','metrics'].filter(p => document.getElementById(`m-perm-${p}`).checked);
  const errEl = document.getElementById('m-error');
  errEl.style.display = 'none';

  try {
    if (id) {
      await subUsersApi.updatePermissions(id, perms);
    } else {
      if (!email) { errEl.textContent = 'E-mail obrigatório.'; errEl.style.display = 'block'; return; }
      if (!pass)  { errEl.textContent = 'Senha obrigatória.'; errEl.style.display = 'block'; return; }
      if (!perms.length) { errEl.textContent = 'Selecione ao menos uma permissão.'; errEl.style.display = 'block'; return; }
      await subUsersApi.create({ email, password: pass, permissions: perms, tenant_id: tenant?.id || null });
    }
    _closeMemberModal();
    loadMembers();
  } catch (err) {
    errEl.textContent = err.detail || 'Erro ao salvar.';
    errEl.style.display = 'block';
  }
});

document.getElementById('m-delete').addEventListener('click', async () => {
  const id = document.getElementById('member-edit-id').value;
  if (!id || !confirm('Remover este membro?')) return;
  try {
    await subUsersApi.delete(id);
    _closeMemberModal();
    loadMembers();
  } catch (err) {
    document.getElementById('m-error').textContent = err.detail || 'Erro ao remover.';
    document.getElementById('m-error').style.display = 'block';
  }
});

// ── AUDITORIA ─────────────────────────────────────────────────────────────
function loadAudit() {
  // A carga e atualização da auditoria é gerida pelo poll diferencial (_startAuditPoll).
  // navigate() chama _startAuditPoll() diretamente quando a aba é selecionada;
  // esta função existe apenas para compatibilidade com PAGE_LOADERS e não faz nada.
  const badge = document.getElementById('audit-tenant-badge');
  if (badge) badge.textContent = tenant ? `Tenant: ${tenant.name || tenant.alias || tenant.id}` : 'Todos os tenants';
}

// ── LOGS BRUTOS ───────────────────────────────────────────────────────────
async function loadRawLogs() {
  const tbody = document.getElementById('tbody-raw-logs');
  const empty = document.getElementById('raw-logs-empty');
  const badge = document.getElementById('raw-logs-tenant-badge');
  if (badge) badge.textContent = tenant ? `Tenant: ${tenant.name || tenant.alias || tenant.id}` : 'Todos os tenants';
  tbody.innerHTML = '<tr><td colspan="5" style="font-style:italic;color:var(--text-sub)">Carregando…</td></tr>';
  empty.style.display = 'none';

  try {
    const data = await rawLogsApi.list(tenant?.id || null, 100);
    const rows = data.items || [];
    tbody.innerHTML = '';
    if (!rows.length) { empty.style.display = 'block'; return; }

    rows.forEach((r, idx) => {
      const tr = document.createElement('tr');
      tr.className = 'raw-log-row';
      tr.dataset.rawLogIndex = String(idx);
      const when = r.timestamp ? new Date(r.timestamp).toLocaleString('pt-BR') : '—';
      tr.innerHTML = `
        <td style="font-size:.78rem;color:var(--text-sub)">${when}</td>
        <td style="font-family:monospace;font-size:.78rem">${escHtml(r.summary || `${r.method || '?'} ${r.path || '?'}`)}</td>
        <td><span class="policy-on" style="font-size:.72rem;padding:2px 7px">${escHtml(r.outcome || 'UNKNOWN')}</span></td>
        <td style="color:var(--text-sub)">${r.latency_ms != null ? Math.round(r.latency_ms) + ' ms' : '—'}</td>
        <td style="font-family:monospace;font-size:.75rem;color:var(--text-sub)">${escHtml((r.route_id || '—').slice(0, 12))}</td>`;
      tr.addEventListener('click', () => _openRawLogModal(r));
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:#a03030;font-style:italic">${err.detail||'Erro'}</td></tr>`;
  }
}

function _openRawLogModal(record) {
  document.getElementById('raw-log-detail').textContent = JSON.stringify(record, null, 2);
  document.getElementById('modal-raw-log').style.display = 'flex';
}

document.getElementById('raw-log-close')?.addEventListener('click', () => { document.getElementById('modal-raw-log').style.display = 'none'; });
document.getElementById('modal-raw-log')?.addEventListener('click', e => { if (e.target.id === 'modal-raw-log') document.getElementById('modal-raw-log').style.display = 'none'; });

// ── MÉTRICAS ──────────────────────────────────────────────────────────────
async function loadMetrics() {
  try {
    const m = await auditApi.metrics(tenant?.id || null, 24);
    document.getElementById('mt-total').textContent     = m.total_requests;
    document.getElementById('mt-status').textContent    = `${m.status_2xx} / ${m.status_4xx} / ${m.status_5xx}`;
    document.getElementById('mt-avg-lat').textContent   = `${m.avg_latency_ms} ms`;
    document.getElementById('mt-p95-lat').textContent   = m.p95_latency_ms ? `p95: ${m.p95_latency_ms} ms` : '';
    const top = (m.top_routes || []).map(t => `${(t.route_id||'?').slice(0,8)}… (${t.count})`).join(', ');
    document.getElementById('mt-top-routes').textContent = top || '—';
  } catch {
    document.getElementById('mt-total').textContent = '—';
  }
}

// ── CONTA ─────────────────────────────────────────────────────────────────
function loadConta() {
  document.getElementById('btn-change-pw').addEventListener('click', async () => {
    const current = document.getElementById('pw-current').value;
    const next    = document.getElementById('pw-new').value;
    const confirm = document.getElementById('pw-confirm').value;
    const msgEl   = document.getElementById('pw-msg');
    msgEl.className = 'inline-msg';
    msgEl.textContent = '';
    if (!current || !next) { msgEl.className += ' error'; msgEl.textContent = 'Preencha todos os campos.'; return; }
    if (next !== confirm)  { msgEl.className += ' error'; msgEl.textContent = 'As senhas não coincidem.'; return; }
    try {
      await authApi.changePassword(current, next);
      msgEl.className += ' success';
      msgEl.textContent = 'Senha alterada com sucesso.';
      document.getElementById('pw-current').value = '';
      document.getElementById('pw-new').value = '';
      document.getElementById('pw-confirm').value = '';
    } catch (err) { msgEl.className += ' error'; msgEl.textContent = err.detail || 'Erro ao alterar senha.'; }
  }, { once: true });
}

// ── Util ──────────────────────────────────────────────────────────────────
function esc(s) { return (s||'').replace(/'/g, "\'").replace(/"/g, '&quot;'); }
function escHtml(s) {
  return String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
function _csvInput(id) {
  return document.getElementById(id).value.split(',').map(s => s.trim()).filter(Boolean);
}
function _setCsvInput(id, values) {
  const el = document.getElementById(id);
  if (el) el.value = (values || []).join(', ');
}
function _policyConstraintSummary(p) {
  const parts = [];
  if (p.required_headers?.length) parts.push(`reqH:${p.required_headers.length}`);
  if (p.forbidden_headers?.length) parts.push(`forbH:${p.forbidden_headers.length}`);
  if (p.required_params?.length) parts.push(`reqP:${p.required_params.length}`);
  if (p.forbidden_params?.length) parts.push(`forbP:${p.forbidden_params.length}`);
  return parts.length ? ` · ${parts.join(' · ')}` : '';
}
