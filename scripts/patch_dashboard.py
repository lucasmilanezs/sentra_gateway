import re
from pathlib import Path

p = Path("src/admin/interface/web/static/dashboard.html")
text = p.read_text(encoding="utf-8")

metrics_section = """<section class="page" id="page-metrics">
      <div class="page-header"><h1 class="page-title">Métricas</h1></div>
      <div class="metrics-grid">
        <motion class="metric-card">
          <div class="metric-label">Requisições (24h)</div>
          <div class="metric-value" id="mt-total">—</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">2xx / 4xx / 5xx</div>
          <div class="metric-value" id="mt-status">—</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Latência média</div>
          <div class="metric-value" id="mt-avg-lat">—</div>
          <div class="metric-sub" id="mt-p95-lat"></div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Top rotas</div>
          <div class="metric-value" id="mt-top-routes" style="font-size:.85rem">—</div>
        </div>
      </div>
    </section>""".replace("<motion ", "<div ")

text = re.sub(
    r'<section class="page" id="page-metrics">.*?</section>',
    metrics_section,
    text,
    count=1,
    flags=re.DOTALL,
)

jwt_block = """
    <div class="modal-field">
      <label class="modal-check">
        <input type="checkbox" id="p-jwt-validate-exp" checked />
        Validar expiração do JWT (exp)
      </label>
    </div>
    <div class="modal-field">
      <label>Issuer (iss) <span style="opacity:.5">— opcional</span></label>
      <input type="text" id="p-jwt-issuer" placeholder="https://auth.empresa.com" />
    </div>
    <div class="modal-field">
      <label>Audience (aud) <span style="opacity:.5">— opcional</span></label>
      <input type="text" id="p-jwt-audience" placeholder="api-interna" />
    </div>"""

if 'id="p-jwt-validate-exp"' not in text:
    text = text.replace(
        '<input type="text" id="p-roles" placeholder="admin, user" />\n    </motion>\n    <p class="modal-error" id="p-error"',
        '<input type="text" id="p-roles" placeholder="admin, user" />\n    </div>\n' + jwt_block + '\n    <p class="modal-error" id="p-error"',
        1,
    )
    text = text.replace(
        '<input type="text" id="dp-roles" placeholder="admin, user" />\n    </div>\n    <p class="modal-error" id="dp-error"',
        '<input type="text" id="dp-roles" placeholder="admin, user" />\n    </div>\n' + jwt_block.replace('p-', 'dp-') + '\n    <p class="modal-error" id="dp-error"',
        1,
    )

text = text.replace(
    "import { authApi, tenantsApi, domainsApi, routesApi, policiesApi, healthApi } from './js/api.js';",
    "import { authApi, tenantsApi, domainsApi, routesApi, policiesApi, healthApi, auditApi } from './js/api.js';",
)
text = text.replace("  audit:    () => {},", "  audit:    loadAudit,")

if "async function loadAudit" not in text:
    load_audit_fn = """
async function loadAudit() {
  const tbody = document.getElementById('tbody-audit');
  const empty = document.getElementById('audit-empty');
  const badge = document.getElementById('audit-tenant-badge');
  badge.textContent = tenant ? `Tenant: ${tenant.name || tenant.alias || tenant.id}` : 'Todos os tenants';
  tbody.innerHTML = '<tr><td colspan="6" style="font-style:italic;color:var(--text-sub)">Carregando…</td></tr>';
  empty.style.display = 'none';
  try {
    const rows = await auditApi.list(tenant?.id || null, 100);
    tbody.innerHTML = '';
    if (!rows.length) { empty.style.display = 'block'; return; }
    rows.forEach(r => {
      const tr = document.createElement('tr');
      const when = new Date(r.created_at).toLocaleString('pt-BR');
      tr.innerHTML = `<td style="font-size:.8rem">${when}</td><td><span class="badge">${r.method}</span></td><td style="font-family:monospace;font-size:.8rem">${r.path}</td><td>${r.status_code}</td><td>${Math.round(r.latency_ms)} ms</td><td>${r.client_ip}</td>`;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="color:#a03030">${err.detail||'Erro'}</td></tr>`;
  }
}
"""
    text = text.replace("// ── MÉTRICAS ─", load_audit_fn + "\n// ── MÉTRICAS ─")

metrics_fn = """async function loadMetrics() {
  try {
    const m = await auditApi.metrics(tenant?.id || null, 24);
    document.getElementById('mt-total').textContent = m.total_requests;
    document.getElementById('mt-status').textContent = `${m.status_2xx} / ${m.status_4xx} / ${m.status_5xx}`;
    document.getElementById('mt-avg-lat').textContent = `${m.avg_latency_ms} ms`;
    document.getElementById('mt-p95-lat').textContent = m.p95_latency_ms ? `p95: ${m.p95_latency_ms} ms` : '';
    const top = (m.top_routes || []).map(t => `${(t.route_id||'?').slice(0,8)}… (${t.count})`).join(', ');
    document.getElementById('mt-top-routes').textContent = top || '—';
  } catch {
    document.getElementById('mt-total').textContent = '—';
  }
}"""
text = re.sub(r"async function loadMetrics\(\) \{.*?\n\}", metrics_fn, text, count=1, flags=re.DOTALL)

if "validateRoutePath" not in text:
    text = text.replace(
        "document.getElementById('r-save').addEventListener",
        """function validateRoutePath(path) {
  if (!path.startsWith('/')) return 'Path deve começar com /';
  if (path.includes('//')) return 'Path não pode conter //';
  if (/[A-Z]/.test(path)) return 'Use apenas letras minúsculas no path (REST)';
  if (!/^\\/[a-z0-9][a-z0-9/_\\-{}]*$/.test(path)) return 'Path com caracteres inválidos';
  return null;
}
document.getElementById('r-save').addEventListener""",
    )
    text = text.replace(
        "  if (!methods.length) { errEl.textContent = 'Selecione ao menos um método HTTP.'; errEl.style.display = 'block'; return; }\n  if (!path || !backend)",
        "  if (!methods.length) { errEl.textContent = 'Selecione ao menos um método HTTP.'; errEl.style.display = 'block'; return; }\n  const pathErr = validateRoutePath(path);\n  if (pathErr) { errEl.textContent = pathErr; errEl.style.display = 'block'; return; }\n  if (!path || !backend)",
    )

text = text.replace(
    "await policiesApi.upsert(routeId, { requires_auth: requiresAuth, rate_limit_per_minute, allowed_roles });",
    """await policiesApi.upsert(routeId, {
      requires_auth: requiresAuth, rate_limit_per_minute, allowed_roles,
      jwt_validate_exp: document.getElementById('p-jwt-validate-exp').checked,
      jwt_issuer: document.getElementById('p-jwt-issuer').value.trim() || null,
      jwt_audience: document.getElementById('p-jwt-audience').value.trim() || null,
    });""",
)
text = text.replace(
    "await domainsApi.upsertPolicy(tenant.id, domainId, { requires_auth: requiresAuth, rate_limit_per_minute, allowed_roles });",
    """await domainsApi.upsertPolicy(tenant.id, domainId, {
      requires_auth: requiresAuth, rate_limit_per_minute, allowed_roles,
      jwt_validate_exp: document.getElementById('dp-jwt-validate-exp').checked,
      jwt_issuer: document.getElementById('dp-jwt-issuer').value.trim() || null,
      jwt_audience: document.getElementById('dp-jwt-audience').value.trim() || null,
    });""",
)

p.write_text(text, encoding="utf-8")
print("ok")
