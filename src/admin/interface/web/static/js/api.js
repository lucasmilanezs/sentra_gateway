const API_BASE = '/api';

function getToken() {
  return sessionStorage.getItem('sentra_token');
}

function headers(extra = {}) {
  const token = getToken();

  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...extra
  };
}

async function request(method, path, body = null) {
  const options = {
    method,
    headers: headers()
  };

  if (body) {
    options.body = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE}${path}`, options);

  if (response.status === 401) {
    sessionStorage.clear();
    window.location.href = '/index.html';
    return;
  }

  if (response.status === 204) {
    return null;
  }

  const data = await response.json();

  if (!response.ok) {
    throw {
      status: response.status,
      detail: data.detail || 'Erro inesperado'
    };
  }

  return data;
}

export const authApi = {
  login: (email, password) =>
    request('POST', '/auth/login', { email, password }),

  register: (email, password, tenant_id = null) =>
    request('POST', '/auth/register', {
      email,
      password,
      tenant_id
    }),

  me: () => request('GET', '/auth/me'),

  forgotPassword: (email) =>
    request('POST', '/auth/forgot-password', { email }),

  resetPassword: (email, code, new_password) =>
    request('POST', '/auth/reset-password', {
      email,
      code,
      new_password
    }),

  changePassword: (current_password, new_password) =>
    request('POST', '/auth/change-password', {
      current_password,
      new_password
    })
};

export const tenantsApi = {
  list: () => request('GET', '/tenants'),

  create: (payload) => request('POST', '/tenants', payload),

  update: (id, payload) =>
    request('PATCH', `/tenants/${id}`, payload),

  delete: (id) => request('DELETE', `/tenants/${id}`)
};

export const routesApi = {
  list: (tenantId) =>
    request('GET', `/routes?tenant_id=${tenantId}`),

  create: (payload) =>
    request('POST', '/routes', payload),

  update: (id, payload) =>
    request('PATCH', `/routes/${id}`, payload),

  delete: (id) =>
    request('DELETE', `/routes/${id}`)
};

export const policiesApi = {
  get: (routeId) =>
    request('GET', `/routes/${routeId}/policy`),

  update: (routeId, payload) =>
    request('PUT', `/routes/${routeId}/policy`, payload),

  delete: (routeId) =>
    request('DELETE', `/routes/${routeId}/policy`)
};

export const healthApi = {
  check: () => request('GET', '/health')
};