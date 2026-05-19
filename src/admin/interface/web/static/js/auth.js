export function requireAuth() {
  if (!sessionStorage.getItem('sentra_token')) {
    window.location.href = '/index.html';
    return false;
  }
  return true;
}

export function logout() {
  sessionStorage.clear();
  window.location.href = '/index.html';
}

export function currentTenant() {
  const raw = sessionStorage.getItem('sentra_tenant');
  return raw ? JSON.parse(raw) : null;
}

export function currentUser() {
  const raw = sessionStorage.getItem('sentra_user');
  return raw ? JSON.parse(raw) : null;
}

/** Persiste dados do usuário retornados por /auth/me */
export function saveCurrentUser(me) {
  sessionStorage.setItem('sentra_user', JSON.stringify({
    id:          me.id,
    email:       me.email,
    role:        me.role        || 'admin',
    tenant_id:   me.tenant_id  || null,
    permissions: me.permissions || [],
  }));
}

export function isSuperUser() {
  const u = currentUser();
  if (u) return u.role === 'superuser';
  // fallback pre-saveCurrentUser: infere pela ausência de tenant
  return currentTenant() === null;
}

export function isAdmin() {
  const u = currentUser();
  if (!u) return false;
  return u.role === 'admin' || u.role === 'superuser';
}

/**
 * Verifica se o usuário tem acesso funcional à seção solicitada.
 * superuser e admin têm acesso total implícito.
 * member precisa ter a permissão explicitamente listada.
 */
export function hasPermission(permission) {
  const u = currentUser();
  if (!u) return false;
  if (u.role === 'superuser' || u.role === 'admin') return true;
  return (u.permissions || []).includes(permission);
}