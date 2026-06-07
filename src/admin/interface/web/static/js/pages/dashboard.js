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

  if (pageId === 'overview') { _startOverviewPoll(); return; }
  _stopOverviewPoll();
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

    const profileDeleteCard = document.getElementById('profile-delete-card');
    if (profileDeleteCard) {
      profileDeleteCard.style.display = me.role === 'member' ? '' : 'none';
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
const OVERVIEW_POLL_MS = 1000;
let _overviewPollTimer = null;

function _statusIcon(status) {
  if (status === 'ok') return '✓';
  if (status === 'degraded') return '!';
  if (status === 'error') return '✗';
  if (status === 'inactive') return '⏸';
  return '?';
}

function _statusText(status) {
  if (status === 'ok') return 'saudável';
  if (status === 'degraded') return 'degradado';
  if (status === 'error') return 'erro';
  if (status === 'inactive') return 'inativo';
  if (status === 'not_loaded') return 'não carregado';
  return status || 'desconhecido';
}

function _statusClass(status) {
  if (status === 'ok') return 'health-ok';
  if (status === 'error') return 'health-error';
  if (status === 'degraded') return 'health-degraded';
  if (status === 'inactive') return 'health-inactive';
  return 'health-unknown';
}

function _applyHealthClass(el, status) {
  if (!el) return;
  el.classList.remove('health-ok', 'health-error', 'health-degraded', 'health-inactive', 'health-unknown');
  el.classList.add(_statusClass(status));
}

function _setOverviewCard(id, status, sub = '') {
  const value = document.getElementById(id);
  const subEl = document.getElementById(`${id}-sub`);
  if (value) {
    value.textContent = _statusIcon(status);
    value.title = _statusText(status);
    _applyHealthClass(value, status);
  }
  if (subEl) {
    subEl.textContent = sub || _statusText(status);
    _applyHealthClass(subEl, status);
  }
}

function _isCriticalPostgresStatus(status) {
  return ['error', 'inactive', 'not_loaded'].includes(String(status || '').toLowerCase());
}

function _renderPostgresCriticalWarning(adminPostgres, gatewayPostgres) {
  const warning = document.getElementById('ov-postgres-critical-warning');
  if (!warning) return;

  const adminStatus = adminPostgres?.status || 'unknown';
  const gatewayStatus = gatewayPostgres?.status || 'unknown';
  const shouldShow = _isCriticalPostgresStatus(adminStatus) || _isCriticalPostgresStatus(gatewayStatus);

  warning.style.display = shouldShow ? 'block' : 'none';
  if (!shouldShow) return;

  const affected = [];
  if (_isCriticalPostgresStatus(adminStatus)) affected.push('Admin');
  if (_isCriticalPostgresStatus(gatewayStatus)) affected.push('Gateway');

  const text = warning.querySelector('.overview-critical-text');
  if (text) {
    text.textContent = `PostgreSQL indisponível no ${affected.join(' e ')}: o Admin perde a fonte de verdade para configurar políticas e a auditoria pode falhar. O Gateway segue com a última snapshot, mas a configuração está comprometida. Reinicie ou investigue o banco.`;
  }
}

function _translateHealthDetail(text) {
  if (!text) return '';
  const raw = String(text);
  const direct = {
    'Redis ping succeeded': 'Redis respondeu ao PING.',
    'snapshot loaded': 'Snapshot carregada com sucesso.',
    'snapshot reloaded': 'Snapshot recarregada com sucesso.',
    'writer configured; no write observed yet': 'Escritor configurado; aguardando o primeiro evento para confirmar escrita.',
    'disabled by configuration': 'Desativado por configuração.',
    'processo HTTP do admin está vivo': 'Processo HTTP do Admin está vivo.',
    'processo HTTP do gateway está vivo': 'Processo HTTP do Gateway está vivo.',
  };
  return direct[raw] || raw;
}

function _componentDetail(label, component) {
  const status = component?.status || 'unknown';
  const detail = component?.human_detail || component?.detail || component?.human_reason || component?.last_error || component?.last_error_type;
  if (detail) return _translateHealthDetail(detail);
  if (status === 'ok') return `${label} está saudável.`;
  if (status === 'degraded') return `${label} está operando em modo degradado.`;
  if (status === 'inactive') return `${label} foi marcado como inativo após falhas repetidas.`;
  if (status === 'error') return `${label} encontrou uma falha operacional.`;
  return `${label} ainda não reportou estado suficiente.`;
}

function _isRetrying(component) {
  const phase = String(component?.phase || '').toLowerCase();
  const reason = String(component?.reason_code || '').toLowerCase();
  return Boolean(
    component?.next_retry_at ||
    phase.includes('retry') ||
    phase.includes('connect') ||
    phase.includes('starting') ||
    phase.includes('restarting') ||
    reason.includes('connecting') ||
    reason.includes('restart_requested')
  ) && component?.status !== 'inactive' && component?.status !== 'ok';
}

function _healthDetail(label, component) {
  const status = component?.status || 'unknown';
  const detail = _componentDetail(label, component);
  const reason = component?.reason_code ? `Código: ${component.reason_code}` : '';
  const phase = component?.phase ? `Fase: ${component.phase}` : '';
  const lastOk = component?.last_ok_at ? `Último OK: ${new Date(component.last_ok_at).toLocaleString('pt-BR')}` : '';
  const lastFailure = component?.last_failure_at ? `Última falha: ${new Date(component.last_failure_at).toLocaleString('pt-BR')}` : '';
  const disabled = component?.disabled_at ? `Inativo desde: ${new Date(component.disabled_at).toLocaleString('pt-BR')}` : '';
  const retryAt = component?.next_retry_at ? `Nova tentativa: ${new Date(component.next_retry_at).toLocaleString('pt-BR')}` : '';
  const meta = [reason, phase, lastOk, lastFailure, disabled, retryAt].filter(Boolean).join(' · ');
  const cls = _statusClass(status);
  const retrying = _isRetrying(component);
  return `<div class="${cls}${retrying ? ' health-retrying' : ''}">
    <span>${escHtml(label)}</span>
    <strong class="${cls}" title="${escHtml(detail)}">${_statusIcon(status)} ${escHtml(_statusText(status))}</strong>
    <small title="${escHtml(detail)}">${escHtml(detail)}</small>
    ${meta ? `<em>${escHtml(meta)}</em>` : ''}
    ${retrying ? '<div class="health-retry-wave" aria-label="tentando reconectar"><i>.</i><i>.</i><i>.</i></div>' : ''}
  </div>`;
}

function _worstStatus(statuses, { redisIsDegraded = false } = {}) {
  const clean = statuses.filter(Boolean);
  if (clean.includes('error')) return redisIsDegraded ? 'degraded' : 'error';
  if (clean.some(s => ['degraded', 'inactive', 'unknown', 'not_loaded', 'not_configured'].includes(s))) return 'degraded';
  return clean.length ? 'ok' : 'unknown';
}

function _normalizeComponents(adminHealth, gatewayHealth) {
  const adminChecks = adminHealth?.checks || {};
  const gatewayChecks = gatewayHealth?.checks || {};
  return {
    admin_api: adminHealth || { status: 'error', detail: 'Admin não respondeu ao healthcheck.' },
    gateway_api: gatewayHealth || { status: 'error', detail: 'Gateway não respondeu ao healthcheck.' },
    admin_postgres: adminChecks.postgres || { status: 'unknown', detail: 'Admin não retornou estado do PostgreSQL.' },
    admin_redis: adminChecks.redis || { status: 'unknown', detail: 'Admin não retornou estado do Redis.' },
    gateway_snapshot: gatewayChecks.snapshot || { status: 'unknown', detail: 'Gateway não retornou estado da snapshot.' },
    gateway_postgres: gatewayChecks.postgres || { status: 'unknown', detail: 'Gateway não retornou estado do PostgreSQL.' },
    gateway_redis_ping: gatewayChecks.redis_ping || { status: 'unknown', detail: 'Gateway não retornou estado do Redis.' },
    gateway_pubsub: gatewayChecks.redis_pubsub || { status: 'unknown', detail: 'Detalhes disponíveis apenas para super-user.' },
    gateway_rate_limit: gatewayChecks.redis_rate_limit || { status: 'unknown', detail: 'Detalhes disponíveis apenas para super-user.' },
    gateway_raw_logs: gatewayChecks.redis_raw_logs || { status: 'unknown', detail: 'Detalhes disponíveis apenas para super-user.' },
    gateway_postgres_audit: gatewayChecks.postgres_audit || { status: 'unknown', detail: 'Detalhes disponíveis apenas para super-user.' },
    gateway_snapshot_reload: gatewayChecks.snapshot_reload || { status: 'unknown', detail: 'Nenhuma falha de recarga reportada.' },
  };
}

function _renderOverview(adminHealth, gatewayHealth) {
  const c = _normalizeComponents(adminHealth, gatewayHealth);
  const superuser = isSuperUser();

  const adminStatus = c.admin_api.status || 'unknown';
  const gatewayStatus = c.gateway_api.status || 'unknown';
  const postgresStatus = _worstStatus([c.admin_postgres.status, c.gateway_postgres.status]);
  const redisStatus = _worstStatus([c.admin_redis.status, c.gateway_redis_ping.status], { redisIsDegraded: false });
  const snapshotStatus = c.gateway_snapshot.status || 'unknown';
  const systemStatus = _worstStatus([adminStatus, gatewayStatus, postgresStatus, snapshotStatus, redisStatus], { redisIsDegraded: true });

  const snapshotAge = c.gateway_snapshot.age_seconds ?? '—';
  const snapshotDetail = snapshotStatus === 'ok'
    ? `última carga há ${snapshotAge}s`
    : (c.gateway_snapshot.detail || _statusText(snapshotStatus));

  _setOverviewCard('ov-status', systemStatus, systemStatus === 'ok'
    ? 'sistema operacional'
    : (superuser ? 'verifique os componentes abaixo' : 'contate o super-user para mais detalhes'));
  _setOverviewCard('ov-admin', adminStatus, _componentDetail('Admin', c.admin_api));
  _setOverviewCard('ov-gateway', gatewayStatus, _componentDetail('Gateway', c.gateway_api));
  _setOverviewCard('ov-postgres', postgresStatus, postgresStatus === 'ok' ? 'PostgreSQL conectado nos dois planos' : 'falha de PostgreSQL em um dos planos');
  _setOverviewCard('ov-redis', redisStatus, redisStatus === 'ok' ? 'Redis conectado nos dois planos' : 'Redis indisponível ou degradado');
  _setOverviewCard('ov-snapshot', snapshotStatus, snapshotDetail);

  _renderPostgresCriticalWarning(c.admin_postgres, c.gateway_postgres);

  const healthSummary = document.getElementById('ov-health-summary');
  if (healthSummary) {
    const loadedAt = c.gateway_snapshot.loaded_at
      ? new Date(c.gateway_snapshot.loaded_at).toLocaleString('pt-BR')
      : null;
    healthSummary.innerHTML = superuser
      ? `Admin: <strong>${escHtml(_statusText(adminStatus))}</strong>. Gateway: <strong>${escHtml(_statusText(gatewayStatus))}</strong>. ` +
        `Snapshot: <strong>${escHtml(_statusText(snapshotStatus))}</strong>${loadedAt ? ` desde <code>${escHtml(loadedAt)}</code>` : ''}.`
      : (systemStatus === 'ok'
          ? 'Resumo operacional disponível. Detalhes internos são restritos ao super-user.'
          : 'Estado degradado detectado. Contate o super-user para mais detalhes.');
  }

  const grid = document.getElementById('ov-health-grid');
  if (!grid) return;

  if (!superuser) {
    grid.innerHTML = `<div class="health-unknown overview-restricted">
      <span>Detalhes restritos</span>
      <strong>contate o super-user</strong>
      <small>Componentes internos podem expor timestamps e estado operacional de outros tenants.</small>
    </div>`;
    return;
  }

  grid.innerHTML = `
    <div class="health-plane-block">
      <h3>Plano Admin</h3>
      <div class="semantic-grid overview-health-subgrid">
        ${_healthDetail('API do Admin', c.admin_api)}
        ${_healthDetail('PostgreSQL do Admin', c.admin_postgres)}
        ${_healthDetail('Redis do Admin', c.admin_redis)}
      </div>
    </div>
    <div class="health-plane-block">
      <h3>Plano Gateway</h3>
      <div class="semantic-grid overview-health-subgrid">
        ${_healthDetail('API do Gateway', c.gateway_api)}
        ${_healthDetail('Snapshot do Gateway', c.gateway_snapshot)}
        ${_healthDetail('PostgreSQL do Gateway', c.gateway_postgres)}
        ${_healthDetail('Redis do Gateway', c.gateway_redis_ping)}
        ${_healthDetail('Mensageria Redis Pub/Sub', c.gateway_pubsub)}
        ${_healthDetail('Limitação de requisições', c.gateway_rate_limit)}
        ${_healthDetail('Logs operacionais', c.gateway_raw_logs)}
        ${_healthDetail('Auditoria PostgreSQL', c.gateway_postgres_audit)}
        ${_healthDetail('Recarga da snapshot', c.gateway_snapshot_reload)}
      </div>
    </div>`;
}

async function loadOverview() {
  try {
    const [adminHealth, gatewayHealth] = await Promise.all([
      healthApi.check(),
      healthApi.gateway(),
    ]);
    _renderOverview(adminHealth, gatewayHealth);
  } catch (err) {
    _setOverviewCard('ov-status', 'error', err.detail || 'erro ao carregar healthchecks');
    const summary = document.getElementById('ov-health-summary');
    if (summary) summary.textContent = err.detail || 'Erro ao carregar healthchecks.';
  }
}

function _startOverviewPoll() {
  _stopOverviewPoll();
  loadOverview();
  _overviewPollTimer = setInterval(() => {
    if (document.getElementById('page-overview')?.classList.contains('active')) {
      loadOverview();
    }
  }, OVERVIEW_POLL_MS);
}

function _stopOverviewPoll() {
  if (_overviewPollTimer) {
    clearInterval(_overviewPollTimer);
    _overviewPollTimer = null;
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
      const color = _normalizeColor(r.display_color);
      const tr = document.createElement('tr');
      tr.className = 'route-colored-row';
      tr.style.setProperty('--route-display-color', color);
      tr.innerHTML = `
        <td>${methodBadges}</td>
        <td style="font-family:monospace;font-size:.85rem"><span class="route-color-dot" style="background:${color}"></span>${r.path_pattern}</td>
        <td style="font-size:.8rem;color:var(--text-secondary);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${r.backend_url}">${r.backend_url}</td>
        <td>${policyHtml}</td>
        <td>
          <button class="btn-icon" onclick="_openPolicyModal('${r.id}','${esc(r.path_pattern)}')">Política</button>
          <button class="btn-icon" onclick="_editRoute('${r.id}','${methodsJson}','${esc(r.path_pattern)}','${esc(r.backend_url)}','${color}')">Editar</button>
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

function _openRouteModal(id='', methods=[], path='', backend='', displayColor='#2dd4bf') {
  document.getElementById('modal-route-title').textContent = id ? 'Editar rota' : 'Nova rota';
  document.getElementById('r-edit-id').value = id;
  _setMethodCheckboxes(Array.isArray(methods) ? methods : []);
  document.getElementById('r-path').value    = path;
  document.getElementById('r-backend').value = backend;
  _setRouteColor(displayColor);
  document.getElementById('r-error').style.display = 'none';
  document.getElementById('r-wildcard').classList.toggle('visible', path.includes('/*'));
  document.getElementById('modal-route').style.display = 'flex';
  document.getElementById('r-path').focus();
}

document.getElementById('r-path').addEventListener('input', e => {
  document.getElementById('r-wildcard').classList.toggle('visible', e.target.value.includes('/*'));
});

function _normalizeColor(value) {
  const raw = String(value || '#2dd4bf').trim();
  return /^#[0-9a-fA-F]{6}$/.test(raw) ? raw.toLowerCase() : '#2dd4bf';
}
function _setRouteColor(value) {
  const color = _normalizeColor(value);
  const picker = document.getElementById('r-display-color');
  const text = document.getElementById('r-display-color-text');
  if (picker) picker.value = color;
  if (text) text.value = color;
}
document.getElementById('r-display-color')?.addEventListener('input', e => _setRouteColor(e.target.value));
document.getElementById('r-display-color-text')?.addEventListener('input', e => _setRouteColor(e.target.value));

window._editRoute = (id, methodsJson, path, backend, displayColor='#2dd4bf') => {
  let methods = [];
  try { methods = JSON.parse(methodsJson); } catch {}
  _openRouteModal(id, methods, path, backend, displayColor);
};

document.getElementById('btn-new-route').addEventListener('click', () => _openRouteModal());
document.getElementById('r-cancel').addEventListener('click', () => { document.getElementById('modal-route').style.display = 'none'; });
document.getElementById('modal-route').addEventListener('click', e => { if (e.target.id === 'modal-route') document.getElementById('modal-route').style.display = 'none'; });

document.getElementById('r-save').addEventListener('click', async () => {
  const id      = document.getElementById('r-edit-id').value;
  const methods = [...document.querySelectorAll('input[name="r-methods"]:checked')].map(el => el.value);
  const path    = document.getElementById('r-path').value.trim();
  const backend = document.getElementById('r-backend').value.trim();
  const displayColor = _normalizeColor(document.getElementById('r-display-color-text')?.value);
  const errEl   = document.getElementById('r-error');
  errEl.style.display = 'none';

  if (!methods.length) { errEl.textContent = 'Selecione ao menos um método HTTP.'; errEl.style.display = 'block'; return; }
  if (!path || !backend) { errEl.textContent = 'Path e backend URL são obrigatórios.'; errEl.style.display = 'block'; return; }
  if (!path.startsWith('/')) { errEl.textContent = 'Path deve começar com /.'; errEl.style.display = 'block'; return; }

  try {
    if (id) {
      await routesApi.update(id, { methods, path_pattern: path, backend_url: backend, display_color: displayColor });
    } else {
      await routesApi.create({ tenant_id: tenant?.id, methods, path_pattern: path, backend_url: backend, display_color: displayColor });
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
const METRICS_SUMMARY_SECONDS = 7 * 24 * 60 * 60;
const CHART_UNIT_SECONDS = {
  second: 1,
  minute: 60,
  hour: 60 * 60,
  day: 24 * 60 * 60,
  week: 7 * 24 * 60 * 60,
  month: 30 * 24 * 60 * 60,
  year: 365 * 24 * 60 * 60,
};
const CHART_UNIT_LABELS = {
  second: 'segundos',
  minute: 'minutos',
  hour: 'horas',
  day: 'dia',
  week: 'semana',
  month: 'mês',
  year: 'ano',
};
const CHART_CONFIGURABLE_UNITS = new Set(['second', 'minute', 'hour']);
const CHART_FIXED_UNIT_HINT = 'janela configurável apenas disponível para segundo, minuto e hora';
const MONTH_LABELS_PT = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
let _metricsChartUnit = 'minute';
let _metricsChartAmount = 10;
let _metricsWindowSeconds = _metricsChartAmount * CHART_UNIT_SECONDS[_metricsChartUnit];
let _metricsBucketSeconds = _bucketForWindow(_metricsWindowSeconds);
let _metricsChartMode = 'all';
let _metricsSelectedRouteId = null;
let _metricsChartHitLines = [];
let _metricsChartHoveredRouteId = null;
let _lastChartMetrics = null;
let _lastRouteSummaryMetrics = null;
let _lastChartConfig = null;

function _metricsWindowLabel(seconds) {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}min`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  if (seconds < 604800) return `${Math.round(seconds / 86400)}d`;
  if (seconds < 2592000) return `${Math.round(seconds / 604800)}sem`;
  if (seconds < 31536000) return `${Math.round(seconds / 2592000)}m`;
  return `${Math.round(seconds / 31536000)}a`;
}

function _bucketForWindow(seconds) {
  const targetPoints = 80;
  const raw = Math.max(1, Math.ceil(seconds / targetPoints));
  const candidates = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 21600, 43200, 86400, 604800, 2592000];
  return candidates.find(v => v >= raw) || candidates[candidates.length - 1];
}

function _iso(dt) {
  return dt.toISOString();
}

function _setChartAmountControl(unit) {
  const amountInput = document.getElementById('mt-chart-amount');
  if (!amountInput) return;
  const configurable = CHART_CONFIGURABLE_UNITS.has(unit);
  amountInput.disabled = !configurable;
  amountInput.classList.toggle('disabled', !configurable);
  amountInput.title = configurable ? '' : CHART_FIXED_UNIT_HINT;
  amountInput.closest('label')?.classList.toggle('disabled', !configurable);
  if (unit === 'hour') {
    amountInput.max = '48';
    if (Number(amountInput.value || 1) > 48) amountInput.value = '48';
  } else {
    amountInput.removeAttribute('max');
  }
}

function _graphWindowConfig() {
  const unit = document.getElementById('mt-chart-unit')?.value || _metricsChartUnit;
  const amountInput = document.getElementById('mt-chart-amount');
  const now = new Date();
  let amount = Math.max(1, Number(amountInput?.value || _metricsChartAmount) || 1);
  _setChartAmountControl(unit);

  let start;
  let end;
  let bucketSeconds;
  let caption;

  if (unit === 'day') {
    end = now;
    start = new Date(end.getTime() - CHART_UNIT_SECONDS.day * 1000);
    amount = 1;
    bucketSeconds = 3600;
    caption = 'gráfico: últimas 24 horas · bucket 1h';
  } else if (unit === 'week') {
    end = now;
    start = new Date(end.getTime() - CHART_UNIT_SECONDS.week * 1000);
    amount = 1;
    bucketSeconds = 86400;
    caption = 'gráfico: últimos 7 dias · bucket 1d';
  } else if (unit === 'month') {
    start = new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0, 0);
    end = new Date(now.getFullYear(), now.getMonth() + 1, 1, 0, 0, 0, 0);
    amount = 1;
    bucketSeconds = 86400;
    caption = `gráfico: mês atual (${MONTH_LABELS_PT[now.getMonth()]}) · bucket 1d`;
  } else if (unit === 'year') {
    start = new Date(now.getFullYear(), 0, 1, 0, 0, 0, 0);
    end = new Date(now.getFullYear() + 1, 0, 1, 0, 0, 0, 0);
    amount = 1;
    bucketSeconds = 2592000;
    caption = `gráfico: ano atual (${now.getFullYear()}) · bucket mensal`;
  } else {
    if (unit === 'hour') amount = Math.min(48, amount);
    const seconds = amount * (CHART_UNIT_SECONDS[unit] || 60);
    end = now;
    start = new Date(end.getTime() - seconds * 1000);
    bucketSeconds = _bucketForWindow(seconds);
    caption = `gráfico: últimos ${amount} ${CHART_UNIT_LABELS[unit] || 'minutos'} · bucket ${_metricsWindowLabel(bucketSeconds)}`;
  }

  const windowSeconds = Math.max(10, Math.ceil((end.getTime() - start.getTime()) / 1000));
  _metricsChartUnit = unit;
  _metricsChartAmount = amount;
  _metricsWindowSeconds = windowSeconds;
  _metricsBucketSeconds = bucketSeconds;
  _lastChartConfig = { unit, amount, start, end, windowSeconds, bucketSeconds, caption };
  return _lastChartConfig;
}

function _formatMilestone(ts, unit) {
  const d = new Date(ts);
  if (unit === 'second') return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  if (unit === 'minute') return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  if (unit === 'hour' || unit === 'day') return `${String(d.getHours()).padStart(2, '0')}:00`;
  if (unit === 'week' || unit === 'month') return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
  if (unit === 'year') return MONTH_LABELS_PT[d.getMonth()];
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}

function _chartMilestones(minX, maxX, unit) {
  const result = [];
  const push = (t) => {
    if (t >= minX - 1 && t <= maxX + 1) result.push(t);
  };
  if (unit === 'week') {
    const start = new Date(minX);
    start.setHours(0, 0, 0, 0);
    for (let t = start.getTime(); t <= maxX; t += 2 * 86400000) push(t);
    if (!result.length || result[result.length - 1] < maxX - 86400000) push(maxX);
    return result;
  }
  if (unit === 'month') {
    const start = new Date(minX);
    start.setHours(0, 0, 0, 0);
    const end = new Date(maxX);
    const lastDay = new Date(end.getFullYear(), end.getMonth(), 0).getDate();
    const days = [1, 7, 14, 21, lastDay];
    days.forEach(day => push(new Date(start.getFullYear(), start.getMonth(), day, 0, 0, 0, 0).getTime()));
    return Array.from(new Set(result)).sort((a, b) => a - b);
  }
  if (unit === 'year') {
    const year = new Date(minX).getFullYear();
    for (let month = 0; month < 12; month++) push(new Date(year, month, 1, 0, 0, 0, 0).getTime());
    return result;
  }
  const milestones = 5;
  for (let i = 0; i <= milestones; i++) result.push(minX + ((maxX - minX) / milestones) * i);
  return result;
}

function _rgba(hex, alpha) {
  const color = _normalizeColor(hex).replace('#', '');
  const r = parseInt(color.slice(0, 2), 16);
  const g = parseInt(color.slice(2, 4), 16);
  const b = parseInt(color.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function _routeMetricCard(route) {
  const color = _normalizeColor(route.display_color);
  const lastSeen = route.last_seen_at ? new Date(route.last_seen_at).toLocaleString('pt-BR') : 'sem eventos na última semana';
  const methods = (route.methods || []).map(m => `<span class="badge m-${m}">${escHtml(m)}</span>`).join('');
  return `<article class="route-metric-item" id="metric-route-${escHtml(route.route_id)}" style="--route-display-color:${color}">
    <button class="route-metric-summary" data-route-id="${escHtml(route.route_id)}">
      <span class="route-metric-main">
        <strong>${escHtml(route.route_label)}</strong>
        <small>${methods || 'métodos não informados'}</small>
      </span>
      <span class="route-metric-kpi"><b>${route.total_requests}</b><small>requisições</small></span>
      <span class="route-metric-kpi"><b>${Math.round(route.avg_latency_ms || 0)} ms</b><small>lat. média</small></span>
      <span class="route-metric-kpi"><b>${route.status_5xx || 0}</b><small>5xx</small></span>
      <span class="route-metric-chevron">▾</span>
    </button>
    <div class="route-metric-details">
      <div><span>Sucesso</span><strong>${route.success_count}</strong></div>
      <div><span>Negadas por política</span><strong>${route.denied_count}</strong></div>
      <div><span>Erros</span><strong>${route.error_count}</strong></div>
      <div><span>2xx / 4xx / 5xx</span><strong>${route.status_2xx} / ${route.status_4xx} / ${route.status_5xx}</strong></div>
      <div><span>p95</span><strong>${Math.round(route.p95_latency_ms || 0)} ms</strong></div>
      <div><span>Último evento</span><strong>${escHtml(lastSeen)}</strong></div>
    </div>
  </article>`;
}

function _renderRouteMetrics(data) {
  const list = document.getElementById('mt-route-list');
  const empty = document.getElementById('mt-route-empty');
  if (!list || !empty) return;
  const routes = data.routes || [];
  list.innerHTML = routes.map(_routeMetricCard).join('');
  empty.style.display = routes.length ? 'none' : 'block';

  list.querySelectorAll('.route-metric-summary').forEach(btn => {
    btn.addEventListener('click', () => btn.closest('.route-metric-item')?.classList.toggle('expanded'));
  });

  const selector = document.getElementById('mt-route-selector');
  if (selector) {
    const previous = _metricsSelectedRouteId;
    selector.innerHTML = routes.map(r => `<option value="${escHtml(r.route_id)}">${escHtml(r.route_label)}</option>`).join('');
    _metricsSelectedRouteId = routes.some(r => r.route_id === previous) ? previous : (routes[0]?.route_id || null);
    if (_metricsSelectedRouteId) selector.value = _metricsSelectedRouteId;
  }
}

function _routeMetadataMap(summaryData, chartData) {
  const map = new Map();
  (summaryData?.routes || []).forEach(r => map.set(r.route_id, r));
  (chartData?.routes || []).forEach(r => {
    if (!map.has(r.route_id)) map.set(r.route_id, r);
  });
  return map;
}

function _buildChartSeries(chartData) {
  const routeMap = _routeMetadataMap(_lastRouteSummaryMetrics, chartData);
  const allRoutes = Array.from(routeMap.values());
  const visibleRoutes = _metricsChartMode === 'single' && _metricsSelectedRouteId
    ? allRoutes.filter(r => r.route_id === _metricsSelectedRouteId)
    : allRoutes;
  const bucketMs = (chartData.bucket_seconds || _metricsBucketSeconds || 60) * 1000;
  const end = chartData.window_end ? new Date(chartData.window_end).getTime() : new Date(chartData.generated_at || Date.now()).getTime();
  const start = chartData.window_start ? new Date(chartData.window_start).getTime() : end - (chartData.window_seconds || _metricsWindowSeconds) * 1000;
  const buckets = [];
  for (let t = Math.floor(start / bucketMs) * bucketMs; t <= end; t += bucketMs) buckets.push(t);
  const values = new Map();
  (chartData.series || []).forEach(p => {
    const t = new Date(p.bucket_start).getTime();
    values.set(`${p.route_id}:${t}`, p.count);
  });
  return visibleRoutes.map(route => ({
    route,
    points: buckets.map(t => ({ x: t, y: values.get(`${route.route_id}:${t}`) || 0 })),
    color: _normalizeColor(route.display_color),
    label: route.route_label,
  }));
}

function _drawMetricsChart(chartData) {
  const canvas = document.getElementById('mt-line-chart');
  if (!canvas) return;
  _lastChartMetrics = chartData;
  const ctx = canvas.getContext('2d');
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 1000;
  const height = canvas.clientHeight || 320;
  canvas.width = Math.floor(width * ratio);
  canvas.height = Math.floor(height * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  _metricsChartHitLines = [];

  const series = _buildChartSeries(chartData);
  const unit = _metricsChartUnit;
  const pad = { left: 44, right: 18, top: 18, bottom: 42 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const maxY = Math.max(1, ...series.flatMap(s => s.points.map(p => p.y)));
  const cfgStart = chartData.window_start ? new Date(chartData.window_start).getTime() : null;
  const cfgEnd = chartData.window_end ? new Date(chartData.window_end).getTime() : null;
  const minX = cfgStart || Math.min(...series.flatMap(s => s.points.map(p => p.x)), Date.now() - 1000);
  const maxX = cfgEnd || Math.max(...series.flatMap(s => s.points.map(p => p.x)), Date.now());
  const xOf = x => pad.left + ((x - minX) / Math.max(1, maxX - minX)) * plotW;
  const yOf = y => pad.top + plotH - (y / maxY) * plotH;

  const bg = ctx.createLinearGradient(0, 0, 0, height);
  bg.addColorStop(0, '#050810');
  bg.addColorStop(1, '#090d16');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = 'rgba(148, 163, 184, 0.08)';
  ctx.lineWidth = 1;
  ctx.font = '11px DM Mono, monospace';
  ctx.fillStyle = 'rgba(180,200,240,0.52)';
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + (plotH / 4) * i;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(width - pad.right, y); ctx.stroke();
    ctx.fillText(String(Math.round(maxY - (maxY / 4) * i)), 10, y + 4);
  }

  const milestones = _chartMilestones(minX, maxX, unit);
  ctx.strokeStyle = 'rgba(148, 163, 184, 0.055)';
  milestones.forEach((t, idx) => {
    const x = xOf(t);
    ctx.beginPath(); ctx.moveTo(x, pad.top); ctx.lineTo(x, pad.top + plotH); ctx.stroke();
    ctx.fillStyle = 'rgba(180,200,240,0.50)';
    ctx.textAlign = idx === 0 ? 'left' : idx === milestones.length - 1 ? 'right' : 'center';
    ctx.fillText(String(_formatMilestone(t, unit)), x, height - 14);
  });
  ctx.textAlign = 'left';

  series.forEach(s => {
    if (!s.points.length) return;
    const isHovered = _metricsChartHoveredRouteId === s.route.route_id;
    const opacity = _metricsChartHoveredRouteId ? (isHovered ? 1 : 0.18) : 0.42;
    ctx.strokeStyle = _rgba(s.color, opacity);
    ctx.lineWidth = isHovered ? 2.8 : 1.8;
    ctx.beginPath();
    const linePoints = [];
    s.points.forEach((p, idx) => {
      const x = xOf(p.x), y = yOf(p.y);
      linePoints.push({x, y});
      idx ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    ctx.stroke();
    if (isHovered) {
      ctx.shadowColor = _rgba(s.color, 0.45);
      ctx.shadowBlur = 8;
      ctx.stroke();
      ctx.shadowBlur = 0;
    }
    _metricsChartHitLines.push({ route: s.route, color: s.color, label: s.label, points: linePoints });
  });
}

function _nearestChartLine(x, y) {
  let best = null;
  for (const line of _metricsChartHitLines) {
    for (let i = 1; i < line.points.length; i++) {
      const a = line.points[i - 1], b = line.points[i];
      const dx = b.x - a.x, dy = b.y - a.y;
      const len2 = dx * dx + dy * dy || 1;
      const t = Math.max(0, Math.min(1, ((x - a.x) * dx + (y - a.y) * dy) / len2));
      const px = a.x + t * dx, py = a.y + t * dy;
      const dist = Math.hypot(x - px, y - py);
      if (!best || dist < best.dist) best = { ...line, dist };
    }
  }
  return best && best.dist <= 14 ? best : null;
}

function _focusRouteMetric(routeId) {
  const el = document.getElementById(`metric-route-${routeId}`);
  if (!el) return;
  el.classList.add('expanded', 'metric-focus-glow');
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  setTimeout(() => el.classList.remove('metric-focus-glow'), 2600);
}

function _wireMetricsChartInteractions() {
  const canvas = document.getElementById('mt-line-chart');
  const tooltip = document.getElementById('mt-chart-tooltip');
  if (!canvas || canvas.dataset.wired === '1') return;
  canvas.dataset.wired = '1';
  canvas.addEventListener('mousemove', e => {
    const rect = canvas.getBoundingClientRect();
    const hit = _nearestChartLine(e.clientX - rect.left, e.clientY - rect.top);
    const nextHovered = hit?.route?.route_id || null;
    if (_metricsChartHoveredRouteId !== nextHovered) {
      _metricsChartHoveredRouteId = nextHovered;
      if (_lastChartMetrics) _drawMetricsChart(_lastChartMetrics);
    }
    if (!hit || !tooltip) { if (tooltip) tooltip.style.display = 'none'; canvas.style.cursor = 'default'; return; }
    tooltip.textContent = hit.label;
    tooltip.style.display = 'block';
    tooltip.style.left = `${e.clientX - rect.left + 14}px`;
    tooltip.style.top = `${e.clientY - rect.top + 10}px`;
    tooltip.style.borderColor = hit.color;
    canvas.style.cursor = 'pointer';
  });
  canvas.addEventListener('mouseleave', () => {
    _metricsChartHoveredRouteId = null;
    if (_lastChartMetrics) _drawMetricsChart(_lastChartMetrics);
    if (tooltip) tooltip.style.display = 'none';
    canvas.style.cursor = 'default';
  });
  canvas.addEventListener('click', e => {
    const rect = canvas.getBoundingClientRect();
    const hit = _nearestChartLine(e.clientX - rect.left, e.clientY - rect.top);
    if (hit) _focusRouteMetric(hit.route.route_id);
  });
}

function _renderMetricsSummary(data) {
  _lastRouteSummaryMetrics = data;
  const total = (data.routes || []).reduce((sum, r) => sum + Number(r.total_requests || 0), 0);
  const s2xx = (data.routes || []).reduce((sum, r) => sum + Number(r.status_2xx || 0), 0);
  const s4xx = (data.routes || []).reduce((sum, r) => sum + Number(r.status_4xx || 0), 0);
  const s5xx = (data.routes || []).reduce((sum, r) => sum + Number(r.status_5xx || 0), 0);
  const avg = total ? Math.round((data.routes || []).reduce((sum, r) => sum + (Number(r.avg_latency_ms || 0) * Number(r.total_requests || 0)), 0) / total) : 0;
  const p95 = Math.max(0, ...(data.routes || []).map(r => Number(r.p95_latency_ms || 0)));
  document.getElementById('mt-total').textContent = total;
  document.getElementById('mt-status').textContent = `${s2xx} / ${s4xx} / ${s5xx}`;
  document.getElementById('mt-avg-lat').textContent = `${avg} ms`;
  document.getElementById('mt-p95-lat').textContent = p95 ? `maior p95: ${Math.round(p95)} ms` : '';
  document.getElementById('mt-window-label').textContent = 'últimos 7 dias';
  _renderRouteMetrics(data);
}

function _renderMetricsChartOnly(data) {
  const caption = document.getElementById('mt-chart-caption');
  if (caption) caption.textContent = _lastChartConfig?.caption || `gráfico: últimos ${_metricsWindowLabel(data.window_seconds || _metricsWindowSeconds)} · bucket ${_metricsWindowLabel(data.bucket_seconds || _metricsBucketSeconds)}`;
  _drawMetricsChart(data);
  _wireMetricsChartInteractions();
}

async function loadMetrics() {
  try {
    const chartConfig = _graphWindowConfig();
    const tenantId = tenant?.id || null;
    const [summaryData, chartData] = await Promise.all([
      auditApi.routeMetrics(tenantId, METRICS_SUMMARY_SECONDS, 86400),
      auditApi.routeMetrics(tenantId, chartConfig.windowSeconds, chartConfig.bucketSeconds, { dateFrom: _iso(chartConfig.start), dateTo: _iso(chartConfig.end) }),
    ]);
    _renderMetricsSummary(summaryData);
    _renderMetricsChartOnly(chartData);
  } catch (err) {
    document.getElementById('mt-total').textContent = '—';
    document.getElementById('mt-route-list').innerHTML = `<div class="metric-error">${escHtml(err.detail || 'Erro ao carregar métricas.')}</div>`;
  }
}

function _reloadMetricsChartOnly() {
  const chartConfig = _graphWindowConfig();
  auditApi.routeMetrics(tenant?.id || null, chartConfig.windowSeconds, chartConfig.bucketSeconds, { dateFrom: _iso(chartConfig.start), dateTo: _iso(chartConfig.end) })
    .then(_renderMetricsChartOnly)
    .catch(err => {
      const caption = document.getElementById('mt-chart-caption');
      if (caption) caption.textContent = err.detail || 'Erro ao atualizar gráfico.';
    });
}

document.getElementById('mt-chart-apply')?.addEventListener('click', _reloadMetricsChartOnly);
document.getElementById('mt-chart-unit')?.addEventListener('change', _reloadMetricsChartOnly);
document.getElementById('mt-chart-amount')?.addEventListener('change', _reloadMetricsChartOnly);
document.getElementById('mt-chart-all')?.addEventListener('click', () => {
  _metricsChartMode = 'all';
  document.getElementById('mt-chart-all').classList.add('active');
  document.getElementById('mt-chart-single').classList.remove('active');
  document.getElementById('mt-route-selector-shell').classList.remove('visible');
  if (_lastChartMetrics) _drawMetricsChart(_lastChartMetrics);
});
document.getElementById('mt-chart-single')?.addEventListener('click', () => {
  _metricsChartMode = 'single';
  document.getElementById('mt-chart-single').classList.add('active');
  document.getElementById('mt-chart-all').classList.remove('active');
  document.getElementById('mt-route-selector-shell').classList.add('visible');
  if (_lastChartMetrics) _drawMetricsChart(_lastChartMetrics);
});
document.getElementById('mt-route-selector')?.addEventListener('change', e => {
  _metricsSelectedRouteId = e.target.value;
  if (_lastChartMetrics) _drawMetricsChart(_lastChartMetrics);
});

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


document.getElementById('btn-delete-profile-member')?.addEventListener('click', async () => {
  const msg = document.getElementById('profile-delete-msg');
  if (msg) { msg.textContent = ''; msg.className = 'inline-msg'; }
  if (!confirm('Excluir sua conta de membro? Esta ação encerra sua sessão e anonimiza suas referências em auditoria.')) return;
  try {
    await subUsersApi.deleteMe();
    sessionStorage.clear();
    window.location.href = '/index.html';
  } catch (err) {
    if (msg) {
      msg.textContent = err.detail || 'Erro ao excluir conta.';
      msg.className = 'inline-msg error';
    }
  }
});
