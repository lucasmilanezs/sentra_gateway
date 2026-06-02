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

// ── Audit polling / filtros ─────────────────────────────────────────────
// O polling só roda quando não há filtros ativos, para não sobrescrever uma consulta refinada.
const AUDIT_POLL_MS = 8000;
let _auditPollTimer  = null;
let _auditNewestTs   = null;
let _auditView = 'gateway';
let _lastGatewayAuditRows = [];
let _lastGovernanceAuditRows = [];
let _lastRawLogRows = [];

function _tenantLabel() {
  return tenant ? `Tenant: ${tenant.name || tenant.alias || 'atual'}` : 'Todos os tenants';
}

function _dateTimeStart(value) {
  return value ? `${value}T00:00:00` : '';
}

function _dateTimeEnd(value) {
  return value ? `${value}T23:59:59` : '';
}

function _gatewayAuditFilters() {
  return {
    tenantId: tenant?.id || null,
    pathContains: document.getElementById('audit-filter-path')?.value || '',
    method: document.getElementById('audit-filter-method')?.value || '',
    outcome: document.getElementById('audit-filter-outcome')?.value || '',
    dateFrom: _dateTimeStart(document.getElementById('audit-filter-from')?.value || ''),
    dateTo: _dateTimeEnd(document.getElementById('audit-filter-to')?.value || ''),
    limit: 100,
  };
}

function _governanceAuditFilters() {
  return {
    tenantId: tenant?.id || null,
    search: document.getElementById('governance-filter-search')?.value || '',
    resourceType: document.getElementById('governance-filter-resource')?.value || '',
    action: document.getElementById('governance-filter-action')?.value || '',
    actorRole: document.getElementById('governance-filter-role')?.value || '',
    dateFrom: _dateTimeStart(document.getElementById('governance-filter-from')?.value || ''),
    dateTo: _dateTimeEnd(document.getElementById('governance-filter-to')?.value || ''),
    limit: 100,
  };
}

function _hasActiveGatewayFilters() {
  const f = _gatewayAuditFilters();
  return Boolean(f.pathContains || f.method || f.outcome || f.dateFrom || f.dateTo);
}

async function _auditPollTick() {
  if (_auditView !== 'gateway' || _hasActiveGatewayFilters()) return;
  const tbody = document.getElementById('tbody-audit');
  if (!tbody) return;
  try {
    const data = await auditApi.requests({ tenantId: tenant?.id || null, limit: 100 });
    const rows = data.items || [];
    if (!rows.length) {
      document.getElementById('audit-empty').style.display = 'block';
      tbody.innerHTML = '';
      return;
    }

    const newRows = _auditNewestTs ? rows.filter(r => r.created_at > _auditNewestTs) : rows;
    if (!newRows.length) return;
    _auditNewestTs = rows[0].created_at;
    _lastGatewayAuditRows = rows;
    _renderGatewayAuditRows(rows);
  } catch { /* keep previous audit state */ }
}

function _auditRow(r) {
  const tr   = document.createElement('tr');
  const when = new Date(r.created_at).toLocaleString('pt-BR');
  const cls  = ['GET','POST','PUT','PATCH','DELETE'].includes(r.method) ? `m-${r.method}` : 'm-OTHER';
  tr.innerHTML = `
    <td style="font-size:.8rem;color:var(--text-secondary)">${when}</td>
    <td><span class="badge ${cls}">${r.method}</span></td>
    <td style="font-family:monospace;font-size:.8rem">${escHtml(r.path)}</td>
    <td style="font-family:monospace;font-size:.78rem;color:var(--text-secondary)">${escHtml(r.route_label || 'rota não resolvida')}</td>
    <td style="font-family:monospace">${r.status_code}</td>
    <td style="font-family:monospace;font-size:.78rem;color:var(--text-secondary)">${escHtml(r.outcome || 'SUCCESS')}</td>
    <td style="color:var(--text-secondary)">${Math.round(r.latency_ms)} ms</td>
    <td style="font-family:monospace;font-size:.78rem;color:var(--text-secondary)">${escHtml(r.client_ip)}</td>`;
  return tr;
}

function _governanceAuditRow(r) {
  const tr = document.createElement('tr');
  const when = new Date(r.timestamp).toLocaleString('pt-BR');
  const actor = r.actor_label || r.actor_role || 'ator desconhecido';
  const resource = r.resource_label || r.resource_summary || r.resource_type || 'recurso';
  tr.innerHTML = `
    <td style="font-size:.8rem;color:var(--text-secondary)">${when}</td>
    <td style="font-family:monospace;font-size:.75rem">${escHtml(actor)}<br><span style="color:var(--text-secondary)">${escHtml(r.actor_role || '—')}</span></td>
    <td><span class="policy-on" style="font-size:.72rem;padding:2px 7px">${escHtml(r.action || '—')}</span></td>
    <td style="font-family:monospace;font-size:.78rem">${escHtml(r.resource_type || '—')}<br><span style="color:var(--text-secondary)">${escHtml(resource)}</span></td>
    <td style="font-size:.8rem">${escHtml(r.resource_summary || '—')}</td>
    <td style="font-size:.78rem;color:var(--text-secondary)">${escHtml(r.detail || '—')}</td>`;
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

function _groupLabel(row, groupBy, kind) {
  const dateValue = kind === 'governance' ? row.timestamp : row.created_at;
  if (groupBy === 'day') return new Date(dateValue).toLocaleDateString('pt-BR');
  if (groupBy === 'year') return String(new Date(dateValue).getFullYear());
  if (groupBy === 'method') return row.method || 'Sem método';
  if (groupBy === 'outcome') return row.outcome || 'Sem outcome';
  if (groupBy === 'resource_type') return row.resource_type || 'Sem recurso';
  if (groupBy === 'action') return row.action || 'Sem ação';
  return '';
}

function _appendGroupedRows(tbody, rows, rowBuilder, groupBy, kind, colspan) {
  let currentGroup = null;
  rows.forEach(row => {
    const label = _groupLabel(row, groupBy, kind);
    if (groupBy !== 'none' && label !== currentGroup) {
      currentGroup = label;
      const groupRow = document.createElement('tr');
      groupRow.innerHTML = `<td colspan="${colspan}" class="group-row">${escHtml(label)}</td>`;
      tbody.appendChild(groupRow);
    }
    tbody.appendChild(rowBuilder(row));
  });
}

function _renderGatewayAuditRows(rows) {
  const tbody = document.getElementById('tbody-audit');
  const empty = document.getElementById('audit-empty');
  tbody.innerHTML = '';
  if (!rows.length) { empty.style.display = 'block'; return; }
  empty.style.display = 'none';
  const groupBy = document.getElementById('audit-group-by')?.value || 'none';
  _appendGroupedRows(tbody, rows, _auditRow, groupBy, 'gateway', 8);
}

function _renderGovernanceAuditRows(rows) {
  const tbody = document.getElementById('tbody-governance-audit');
  const empty = document.getElementById('governance-audit-empty');
  tbody.innerHTML = '';
  if (!rows.length) { empty.style.display = 'block'; return; }
  empty.style.display = 'none';
  const groupBy = document.getElementById('governance-group-by')?.value || 'none';
  _appendGroupedRows(tbody, rows, _governanceAuditRow, groupBy, 'governance', 6);
}

async function _loadGatewayAudit() {
  const tbody = document.getElementById('tbody-audit');
  const empty = document.getElementById('audit-empty');
  tbody.innerHTML = '<tr><td colspan="8" style="font-style:italic;color:var(--text-secondary)">Carregando…</td></tr>';
  empty.style.display = 'none';
  try {
    const data = await auditApi.requests(_gatewayAuditFilters());
    _lastGatewayAuditRows = data.items || [];
    _renderGatewayAuditRows(_lastGatewayAuditRows);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="color:#a03030;font-style:italic">${escHtml(err.detail || 'Erro')}</td></tr>`;
  }
}

async function _loadGovernanceAudit() {
  const tbody = document.getElementById('tbody-governance-audit');
  const empty = document.getElementById('governance-audit-empty');
  tbody.innerHTML = '<tr><td colspan="6" style="font-style:italic;color:var(--text-secondary)">Carregando…</td></tr>';
  empty.style.display = 'none';
  try {
    const data = await auditApi.changeEvents(_governanceAuditFilters());
    _lastGovernanceAuditRows = data.items || [];
    _renderGovernanceAuditRows(_lastGovernanceAuditRows);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="color:#a03030;font-style:italic">${escHtml(err.detail || 'Erro')}</td></tr>`;
  }
}

function setAuditView(view) {
  const badge = document.getElementById('audit-tenant-badge');
  if (badge) badge.textContent = _tenantLabel();
  _auditView = view;
  document.querySelectorAll('.audit-tab').forEach(btn => btn.classList.toggle('active', btn.dataset.auditView === view));
  document.getElementById('audit-gateway-panel').style.display = view === 'gateway' ? '' : 'none';
  document.getElementById('audit-governance-panel').style.display = view === 'governance' ? '' : 'none';
  if (view === 'gateway') {
    if (_hasActiveGatewayFilters()) { _stopAuditPoll(); _loadGatewayAudit(); }
    else { _startAuditPoll(); }
  } else {
    _stopAuditPoll();
    _loadGovernanceAudit();
  }
}

document.querySelectorAll('.audit-tab').forEach(btn => {
  btn.addEventListener('click', () => setAuditView(btn.dataset.auditView));
});

document.getElementById('audit-apply-filters')?.addEventListener('click', () => { _stopAuditPoll(); _loadGatewayAudit(); });
document.getElementById('audit-clear-filters')?.addEventListener('click', () => {
  ['audit-filter-path','audit-filter-method','audit-filter-outcome','audit-filter-from','audit-filter-to'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  _startAuditPoll();
});
document.getElementById('audit-group-by')?.addEventListener('change', () => _renderGatewayAuditRows(_lastGatewayAuditRows));
document.getElementById('governance-apply-filters')?.addEventListener('click', _loadGovernanceAudit);
document.getElementById('governance-clear-filters')?.addEventListener('click', () => {
  ['governance-filter-search','governance-filter-resource','governance-filter-action','governance-filter-role','governance-filter-from','governance-filter-to'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  _loadGovernanceAudit();
});
document.getElementById('governance-group-by')?.addEventListener('change', () => _renderGovernanceAuditRows(_lastGovernanceAuditRows));

function navigate(pageId) {
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const btn  = document.querySelector(`.nav-item[data-page="${pageId}"]`);
  const page = document.getElementById('page-' + pageId);
  if (btn)  btn.classList.add('active');
  if (page) page.classList.add('active');

  if (pageId === 'audit') { setAuditView(_auditView || 'gateway'); }
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

      if (!tenant?.id) {
        sessionStorage.removeItem('sentra_tenant');
        window.location.href = '/tenant-select.html';
        return;
      }

      // Hydrate the selected tenant again. This prevents stale/incomplete
      // sessionStorage data from becoming the implicit scope for member CRUD.
      try {
        const full = await tenantsApi.get(tenant.id);
        tenant = { id: full.id, name: full.name, alias: full.alias };
        sessionStorage.setItem('sentra_tenant', JSON.stringify(tenant));
      } catch {
        sessionStorage.removeItem('sentra_tenant');
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
      tenant ? (tenant.name || tenant.alias || 'Tenant atual') : 'Superuser — sem tenant fixo';

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
  tbody.innerHTML = '<tr><td colspan="5" style="font-style:italic;color:var(--text-secondary)">Carregando…</td></tr>';
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
        <td style="font-style:italic;color:var(--text-secondary)">${t.alias}</td>
        <td>${domHtml}</td>
        <td style="font-size:.78rem;color:var(--text-secondary)">${t.created_at ? new Date(t.created_at).toLocaleDateString('pt-BR') : '—'}</td>
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

  badge.textContent = tenant ? `Tenant: ${tenant.name || tenant.alias || 'atual'}` : '';

  if (!tenantId) {
    tbody.innerHTML = '<tr><td colspan="4" style="font-style:italic;color:var(--text-secondary)">Selecione um tenant para ver os domains.</td></tr>';
    return;
  }

  tbody.innerHTML = '<tr><td colspan="4" style="font-style:italic;color:var(--text-secondary)">Carregando…</td></tr>';
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
        ? `${_policySummary(p)}
           <button class="btn-icon" onclick="_openDomainPolicyModal('${d.id}','${esc(d.domain)}')">Editar</button>`
        : `<span class="policy-off">sem política</span>
           <button class="btn-icon" onclick="_openDomainPolicyModal('${d.id}','${esc(d.domain)}')">Configurar</button>`;

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-family:monospace;font-size:.88rem">${d.domain}</td>
        <td>${pHtml}</td>
        <td style="font-size:.78rem;color:var(--text-secondary)">${d.created_at ? new Date(d.created_at).toLocaleDateString('pt-BR') : '—'}</td>
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
  _setPolicyForm('dp', null);
  document.getElementById('dp-error').style.display = 'none';
  _wirePolicyMode('dp');
  document.getElementById('modal-domain-policy').style.display = 'flex';
  try {
    const p = await domainsApi.getPolicy(tenant.id, domainId);
    if (p) _setPolicyForm('dp', p);
  } catch {}
};

document.getElementById('dp-cancel').addEventListener('click', () => { document.getElementById('modal-domain-policy').style.display = 'none'; });
document.getElementById('modal-domain-policy').addEventListener('click', e => { if (e.target.id === 'modal-domain-policy') document.getElementById('modal-domain-policy').style.display = 'none'; });

document.getElementById('dp-save').addEventListener('click', async () => {
  const domainId = document.getElementById('dp-domain-id').value;
  const errEl = document.getElementById('dp-error');
  errEl.style.display = 'none';
  try {
    await domainsApi.upsertPolicy(tenant.id, domainId, _policyPayload('dp'));
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
  badge.textContent = tenant ? `Tenant: ${tenant.name || tenant.alias || 'atual'}` : '';
  tbody.innerHTML = '<tr><td colspan="5" style="font-style:italic;color:var(--text-secondary)">Carregando…</td></tr>';
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
        ? `${_policySummary(p)}`
        : `<span class="policy-off">sem política</span>`;

      const methodsJson = esc(JSON.stringify(methods));
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${methodBadges}</td>
        <td style="font-family:monospace;font-size:.85rem">${r.path_pattern}</td>
        <td style="font-size:.8rem;color:var(--text-secondary);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${r.backend_url}">${r.backend_url}</td>
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
  _setPolicyForm('p', null);
  _wirePolicyMode('p');
  document.getElementById('modal-policy').style.display = 'flex';
  try {
    const p = await policiesApi.get(routeId);
    if (p) _setPolicyForm('p', p);
  } catch {}
};

document.getElementById('p-cancel').addEventListener('click', () => { document.getElementById('modal-policy').style.display = 'none'; });
document.getElementById('modal-policy').addEventListener('click', e => { if (e.target.id === 'modal-policy') document.getElementById('modal-policy').style.display = 'none'; });

document.getElementById('p-save').addEventListener('click', async () => {
  const routeId = document.getElementById('p-route-id').value;
  const errEl = document.getElementById('p-error');
  errEl.style.display = 'none';
  try {
    await policiesApi.upsert(routeId, _policyPayload('p'));
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
      '<tr><td colspan="4" style="font-style:italic;color:var(--text-secondary)">Selecione um tenant para ver os membros.</td></tr>';
    return;
  }

  const tbody = document.getElementById('tbody-members');
  const empty = document.getElementById('members-empty');
  const badge = document.getElementById('members-tenant-badge');

  badge.textContent = `Tenant: ${tenant.name || tenant.alias || 'atual'}`;
  tbody.innerHTML = '<tr><td colspan="4" style="font-style:italic;color:var(--text-secondary)">Carregando…</td></tr>';
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
        <td>${perms || '<span style="color:var(--text-secondary);font-size:.8rem;font-style:italic">nenhuma</span>'}</td>
        <td style="color:var(--text-secondary);font-size:.85rem">${when}</td>
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
      if (!tenant?.id) { errEl.textContent = 'Selecione um tenant antes de criar membros.'; errEl.style.display = 'block'; return; }
      await subUsersApi.create(tenant.id, { email, password: pass, permissions: perms });
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
  const badge = document.getElementById('audit-tenant-badge');
  if (badge) badge.textContent = _tenantLabel();
  setAuditView(_auditView || 'gateway');
}

// ── LOGS ──────────────────────────────────────────────────────────────────
async function loadRawLogs() {
  const tbody = document.getElementById('tbody-raw-logs');
  const empty = document.getElementById('raw-logs-empty');
  const badge = document.getElementById('raw-logs-tenant-badge');
  if (badge) badge.textContent = _tenantLabel();
  tbody.innerHTML = '<tr><td colspan="5" style="font-style:italic;color:var(--text-secondary)">Carregando…</td></tr>';
  empty.style.display = 'none';

  try {
    const data = await rawLogsApi.list(tenant?.id || null, 100);
    _lastRawLogRows = data.items || [];
    _renderRawLogs();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:#a03030;font-style:italic">${err.detail||'Erro'}</td></tr>`;
  }
}

function _sortedRawLogs() {
  const sortBy = document.getElementById('logs-sort-by')?.value || 'created_desc';
  const rows = [..._lastRawLogRows];
  const ts = r => r.timestamp ? new Date(r.timestamp).getTime() : 0;
  const latency = r => r.latency_ms ?? -1;
  if (sortBy === 'created_asc') rows.sort((a, b) => ts(a) - ts(b));
  else if (sortBy === 'latency_desc') rows.sort((a, b) => latency(b) - latency(a));
  else if (sortBy === 'latency_asc') rows.sort((a, b) => latency(a) - latency(b));
  else if (sortBy === 'method') rows.sort((a, b) => String(a.method || '').localeCompare(String(b.method || '')) || ts(b) - ts(a));
  else rows.sort((a, b) => ts(b) - ts(a));
  return rows;
}

function _rawLogGroupLabel(row, groupBy) {
  if (groupBy === 'day') return row.timestamp ? new Date(row.timestamp).toLocaleDateString('pt-BR') : 'Sem data';
  if (groupBy === 'year') return row.timestamp ? String(new Date(row.timestamp).getFullYear()) : 'Sem data';
  if (groupBy === 'method') return row.method || 'Sem método';
  if (groupBy === 'outcome') return row.outcome || 'Sem outcome';
  if (groupBy === 'route') return row.route_label || row.path || 'Rota não resolvida';
  return '';
}

function _rawLogRow(r) {
  const tr = document.createElement('tr');
  tr.className = 'raw-log-row';
  const when = r.timestamp ? new Date(r.timestamp).toLocaleString('pt-BR') : '—';
  const routeLabel = r.route_label || r.path || 'rota não resolvida';
  tr.innerHTML = `
    <td style="font-size:.78rem;color:var(--text-secondary)">${when}</td>
    <td style="font-family:monospace;font-size:.78rem">${escHtml(r.summary || `${r.method || '?'} ${r.path || '?'}`)}</td>
    <td><span class="policy-on" style="font-size:.72rem;padding:2px 7px">${escHtml(r.outcome || 'UNKNOWN')}</span></td>
    <td style="color:var(--text-secondary)">${r.latency_ms != null ? Math.round(r.latency_ms) + ' ms' : '—'}</td>
    <td style="font-family:monospace;font-size:.75rem;color:var(--text-secondary)">${escHtml(routeLabel)}</td>`;
  tr.addEventListener('click', () => _openRawLogModal(r));
  return tr;
}

function _renderRawLogs() {
  const tbody = document.getElementById('tbody-raw-logs');
  const empty = document.getElementById('raw-logs-empty');
  tbody.innerHTML = '';
  const rows = _sortedRawLogs();
  if (!rows.length) { empty.style.display = 'block'; return; }
  empty.style.display = 'none';
  const groupBy = document.getElementById('logs-group-by')?.value || 'none';
  let currentGroup = null;
  rows.forEach(row => {
    const label = _rawLogGroupLabel(row, groupBy);
    if (groupBy !== 'none' && label !== currentGroup) {
      currentGroup = label;
      const groupRow = document.createElement('tr');
      groupRow.innerHTML = `<td colspan="5" class="group-row">${escHtml(label)}</td>`;
      tbody.appendChild(groupRow);
    }
    tbody.appendChild(_rawLogRow(row));
  });
}

function _checkListHtml(title, checks) {
  if (!checks?.length) return '';
  const items = checks.map(c => `<li><span class="${c.passed ? 'check-ok' : 'check-fail'}">${c.passed ? '✓' : '✗'}</span> <code>${escHtml(c.check || 'check')}</code> — ${escHtml(c.detail || '')}</li>`).join('');
  return `<div class="semantic-block"><strong>${title}</strong><ul>${items}</ul></div>`;
}

function _openRawLogModal(record) {
  const semantic = document.getElementById('raw-log-semantic');
  const routeLabel = record.route_label || record.path || 'rota não resolvida';
  const layerErrors = record.layer_errors || {};
  const layerHtml = Object.keys(layerErrors).length
    ? `<div class="semantic-block"><strong>Erros por camada</strong><ul>${Object.entries(layerErrors).map(([k,v]) => `<li><code>${escHtml(k)}</code> — ${escHtml(v)}</li>`).join('')}</ul></div>`
    : '';
  semantic.innerHTML = `
    <div class="semantic-grid">
      <div><span>Método</span><strong>${escHtml(record.method || '—')}</strong></div>
      <div><span>Path</span><strong>${escHtml(record.path || '—')}</strong></div>
      <div><span>Rota</span><strong>${escHtml(routeLabel)}</strong></div>
      <div><span>Status</span><strong>${escHtml(record.status_code ?? '—')}</strong></div>
      <div><span>Outcome</span><strong>${escHtml(record.outcome || 'UNKNOWN')}</strong></div>
      <div><span>Latência</span><strong>${record.latency_ms != null ? Math.round(record.latency_ms) + ' ms' : '—'}</strong></div>
    </div>
    <div class="semantic-block"><strong>Resumo de política</strong><p>${escHtml(record.policy_summary || 'Sem checks de política registrados')}</p></div>
    ${_checkListHtml('Headers e matches', record.header_checks)}
    ${_checkListHtml('Params e matches', record.param_checks)}
    ${layerHtml}`;
  document.getElementById('raw-log-detail').textContent = JSON.stringify(record.payload || record, null, 2);
  document.getElementById('modal-raw-log').style.display = 'flex';
}

document.getElementById('logs-group-by')?.addEventListener('change', _renderRawLogs);
document.getElementById('logs-sort-by')?.addEventListener('change', _renderRawLogs);
document.getElementById('logs-refresh')?.addEventListener('click', loadRawLogs);
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
    const top = (m.top_routes || []).map(t => `${t.route_label || 'rota não resolvida'} (${t.count})`).join(', ');
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

const AUTH_MODE_LABELS = {
  none: 'Sem token',
  bearer: 'Bearer obrigatório',
  jwt_structural: 'JWT estrutural',
  jwt_claims: 'Exp/issuer/audience',
  jwt_signed: 'Assinatura local',
};

const AUTH_MODE_HELP = {
  none: 'O Gateway não exige token. O backend continua responsável por sua própria segurança.',
  bearer: 'Exige Authorization: Bearer <token>. Não interpreta JWT nem valida sessão.',
  jwt_structural: 'Exige Bearer e valida se o token tem estrutura JWT legível. Não valida assinatura.',
  jwt_claims: 'Pré-valida exp/issuer/audience declarados. Sem assinatura, isso é apenas filtro estrutural, não autenticação forte.',
  jwt_signed: 'Valida assinatura com secret HMAC ou chave pública fornecida pelo contratante. Não gerencia sessão, revogação ou autorização fina.',
};

const AUTH_MODE_ORDER = ['none', 'bearer', 'jwt_structural', 'jwt_claims', 'jwt_signed'];

function _authModeLabel(mode) {
  return AUTH_MODE_LABELS[mode || 'none'] || mode || 'Sem token';
}

function _authModeLevel(mode) {
  const idx = AUTH_MODE_ORDER.indexOf(mode || 'none');
  return idx >= 0 ? idx : 0;
}

function _policySummary(p) {
  if (!p) return '<span class="policy-off">sem política</span>';
  const parts = [_authModeLabel(p.auth_mode || (p.requires_auth ? 'jwt_claims' : 'none'))];
  if (p.auth_mode === 'jwt_signed' || p.jwt_signing_key_configured) {
    parts.push(p.jwt_signing_key_configured ? `assinatura ${p.jwt_signing_algorithm || ''}`.trim() : 'assinatura sem chave');
  }
  if (p.rate_limit_per_minute) parts.push(`${p.rate_limit_per_minute}/min`);
  const constraints = _policyConstraintSummary(p);
  return `<span class="policy-on">${parts.map(escHtml).join(' · ')}${constraints}</span>`;
}

function _setPolicyForm(prefix, p = null) {
  const mode = p?.auth_mode || (p?.requires_auth ? 'jwt_claims' : 'none');
  document.getElementById(`${prefix}-auth-mode`).value = mode;
  document.getElementById(`${prefix}-rate-limit`).value = p?.rate_limit_per_minute || '';
  document.getElementById(`${prefix}-jwt-validate-exp`).checked = p?.jwt_validate_exp ?? true;
  document.getElementById(`${prefix}-jwt-clock-skew`).value = p?.jwt_clock_skew_seconds ?? 30;
  document.getElementById(`${prefix}-jwt-issuer`).value = p?.jwt_issuer || '';
  document.getElementById(`${prefix}-jwt-audience`).value = p?.jwt_audience || '';
  document.getElementById(`${prefix}-jwt-signing-algorithm`).value = p?.jwt_signing_algorithm || 'HS256';
  document.getElementById(`${prefix}-jwt-signing-key`).value = '';
  const status = document.getElementById(`${prefix}-jwt-signing-key-status`);
  if (status) {
    status.textContent = p?.jwt_signing_key_configured
      ? `Material de assinatura já configurado${p.jwt_signing_key_hint ? ` (final ${p.jwt_signing_key_hint})` : ''}. Preencha apenas para substituir.`
      : 'Nenhum material de assinatura configurado.';
  }
  _setCsvInput(`${prefix}-required-headers`, p?.required_headers || []);
  _setCsvInput(`${prefix}-forbidden-headers`, p?.forbidden_headers || []);
  _setCsvInput(`${prefix}-required-params`, p?.required_params || []);
  _setCsvInput(`${prefix}-forbidden-params`, p?.forbidden_params || []);
  _refreshPolicyAuthUI(prefix);
}

function _refreshPolicyAuthUI(prefix) {
  const mode = document.getElementById(`${prefix}-auth-mode`)?.value || 'none';
  const level = _authModeLevel(mode);
  const help = document.getElementById(`${prefix}-auth-help`);
  if (help) help.textContent = AUTH_MODE_HELP[mode] || '';
  document.querySelectorAll(`[data-policy-prefix="${prefix}"] .policy-auth-section`).forEach(section => {
    const minMode = section.dataset.minMode || 'none';
    section.style.display = level >= _authModeLevel(minMode) ? 'block' : 'none';
  });
}

function _policyPayload(prefix) {
  const auth_mode = document.getElementById(`${prefix}-auth-mode`).value;
  const rateRaw = document.getElementById(`${prefix}-rate-limit`).value.trim();
  const signingKey = document.getElementById(`${prefix}-jwt-signing-key`).value;
  const payload = {
    auth_mode,
    requires_auth: auth_mode !== 'none',
    rate_limit_per_minute: rateRaw ? parseInt(rateRaw, 10) : null,
    allowed_roles: [],
    jwt_validate_exp: document.getElementById(`${prefix}-jwt-validate-exp`).checked,
    jwt_clock_skew_seconds: parseInt(document.getElementById(`${prefix}-jwt-clock-skew`).value || '30', 10),
    jwt_issuer: document.getElementById(`${prefix}-jwt-issuer`).value.trim() || null,
    jwt_audience: document.getElementById(`${prefix}-jwt-audience`).value.trim() || null,
    jwt_signing_algorithm: document.getElementById(`${prefix}-jwt-signing-algorithm`).value || null,
    required_headers: _csvInput(`${prefix}-required-headers`),
    forbidden_headers: _csvInput(`${prefix}-forbidden-headers`),
    required_params: _csvInput(`${prefix}-required-params`),
    forbidden_params: _csvInput(`${prefix}-forbidden-params`),
  };
  if (signingKey.trim()) payload.jwt_signing_key = signingKey;
  return payload;
}

function _wirePolicyMode(prefix) {
  const el = document.getElementById(`${prefix}-auth-mode`);
  if (el && !el.dataset.wired) {
    el.addEventListener('change', () => _refreshPolicyAuthUI(prefix));
    el.dataset.wired = 'true';
  }
}


function _policyConstraintSummary(p) {
  const parts = [];
  if (p.required_headers?.length) parts.push(`reqH:${p.required_headers.length}`);
  if (p.forbidden_headers?.length) parts.push(`forbH:${p.forbidden_headers.length}`);
  if (p.required_params?.length) parts.push(`reqP:${p.required_params.length}`);
  if (p.forbidden_params?.length) parts.push(`forbP:${p.forbidden_params.length}`);
  return parts.length ? ` · ${parts.join(' · ')}` : '';
}
