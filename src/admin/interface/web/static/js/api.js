const API_BASE = '/api/v1';

function getToken() {
  return sessionStorage.getItem('sentra_token');
}

function buildHeaders() {
  const token = getToken();
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  };
}

async function request(method, path, body = null) {
  const options = { method, headers: buildHeaders() };
  if (body !== null) options.body = JSON.stringify(body);

  const response = await fetch(`${API_BASE}${path}`, options);

  if (response.status === 401) {
    sessionStorage.clear();
    window.location.href = '/index.html';
    return;
  }

  if (response.status === 204) return null;

  const data = await response.json();

  if (!response.ok) {
    throw { status: response.status, detail: data.detail || 'Erro inesperado' };
  }

  return data;
}

export const authApi = {
  login:          (email, password)                 => request('POST', '/auth/login', { email, password }),
  register:       (payload)                         => request('POST', '/auth/register', payload),
  me:             ()                                => request('GET',  '/auth/me'),
  forgotPassword: (email)                           => request('POST', '/auth/forgot-password', { email }),
  resetPassword:  (email, code, new_password)       => request('POST', '/auth/reset-password', { email, code, new_password }),
  changePassword: (current_password, new_password)  => request('POST', '/auth/change-password', { current_password, new_password }),
};

export const tenantsApi = {
  list:   ()            => request('GET',    '/tenants'),
  create: (payload)     => request('POST',   '/tenants', payload),
  get:    (id)          => request('GET',    `/tenants/${id}`),
  update: (id, payload) => request('PATCH',  `/tenants/${id}`, payload),
  delete: (id)          => request('DELETE', `/tenants/${id}`),
  domainSuggestions: (id) => request('GET', `/tenants/${id}/domain-suggestions`),
};

// Domains são sub-recurso de tenant — resolvem o Host header no gateway
export const domainsApi = {
  list:   (tenantId)                        => request('GET',    `/tenants/${tenantId}/domains`),
  create: (tenantId, payload)               => request('POST',   `/tenants/${tenantId}/domains`, payload),
  delete: (tenantId, domainId)              => request('DELETE', `/tenants/${tenantId}/domains/${domainId}`),

  // Política global por domain — fallback para rotas sem policy individual
  getPolicy:    (tenantId, domainId)           => request('GET',    `/tenants/${tenantId}/domains/${domainId}/policy`),
  upsertPolicy: (tenantId, domainId, payload)  => request('PUT',    `/tenants/${tenantId}/domains/${domainId}/policy`, payload),
  deletePolicy: (tenantId, domainId)           => request('DELETE', `/tenants/${tenantId}/domains/${domainId}/policy`),
};

export const routesApi = {
  list:   (tenantId)    => request('GET',    tenantId ? `/routes?tenant_id=${tenantId}` : '/routes'),
  create: (payload)     => request('POST',   '/routes', payload),
  get:    (id)          => request('GET',    `/routes/${id}`),
  update: (id, payload) => request('PATCH',  `/routes/${id}`, payload),
  delete: (id)          => request('DELETE', `/routes/${id}`),
};

export const policiesApi = {
  get:    (routeId)          => request('GET',    `/routes/${routeId}/policy`),
  upsert: (routeId, payload) => request('PUT',    `/routes/${routeId}/policy`, payload),
  delete: (routeId)          => request('DELETE', `/routes/${routeId}/policy`),
};

function gatewayBaseUrl() {
  const host = window.location.hostname || 'localhost';
  const protocol = window.location.protocol || 'http:';
  return `${protocol}//${host}:8000`;
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { 'Accept': 'application/json' } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw { status: response.status, detail: data.detail || `Erro HTTP ${response.status}` };
  }
  return data;
}

export const healthApi = {
  admin:      () => request('GET', '/health'),
  adminLive:  () => request('GET', '/health/live'),
  adminReady: () => request('GET', '/health/ready'),
  gateway:    () => fetchJson(`${gatewayBaseUrl()}/health`),
  gatewayLive:() => fetchJson(`${gatewayBaseUrl()}/health/live`),
  gatewayUrl: gatewayBaseUrl,
};

function appendQuery(q, values = {}) {
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== '') {
      q.set(key, String(value).trim());
    }
  });
  return q;
}

export const auditApi = {
  list: (tenantId = null, limit = 100) => {
    const q = appendQuery(new URLSearchParams({ limit: String(limit) }), { tenant_id: tenantId });
    return request('GET', `/audit?${q}`);
  },
  requests: (filters = {}) => {
    const q = appendQuery(new URLSearchParams({ limit: String(filters.limit || 100), offset: String(filters.offset || 0) }), {
      tenant_id: filters.tenantId,
      method: filters.method,
      outcome: filters.outcome,
      path_contains: filters.pathContains,
      date_from: filters.dateFrom,
      date_to: filters.dateTo,
    });
    return request('GET', `/audit/requests?${q}`);
  },
  changes: (tenantId = null, limit = 100) => {
    const q = appendQuery(new URLSearchParams({ limit: String(limit) }), { tenant_id: tenantId });
    return request('GET', `/audit/changes?${q}`);
  },
  changeEvents: (filters = {}) => {
    const q = appendQuery(new URLSearchParams({ limit: String(filters.limit || 100), offset: String(filters.offset || 0) }), {
      tenant_id: filters.tenantId,
      resource_type: filters.resourceType,
      action: filters.action,
      actor_role: filters.actorRole,
      search: filters.search,
      date_from: filters.dateFrom,
      date_to: filters.dateTo,
    });
    return request('GET', `/audit/changes?${q}`);
  },
  metrics: (tenantId = null, hours = 24) => {
    const q = appendQuery(new URLSearchParams({ hours: String(hours) }), { tenant_id: tenantId });
    return request('GET', `/metrics/summary?${q}`);
  },
};

export const rawLogsApi = {
  list: (tenantId = null, limit = 100) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (tenantId) q.set('tenant_id', tenantId);
    return request('GET', `/logs?${q}`);
  },
};

export const subUsersApi = {
  // Member creation is tenant-scoped. Keep the tenant in the URL so the
  // backend does not need to infer scope from an optional payload field.
  create:            (tenantId, payload)   => request('POST',   `/sub-users/${tenantId}`, payload),
  createLegacy:      (payload)             => request('POST',   '/sub-users', payload),
  listByTenant:      (tenantId)            => request('GET',    `/sub-users/${tenantId}`),
  updatePermissions: (userId, permissions) => request('PATCH',  `/sub-users/${userId}/permissions`, { permissions }),
  delete:            (userId)              => request('DELETE', `/sub-users/${userId}`),
};