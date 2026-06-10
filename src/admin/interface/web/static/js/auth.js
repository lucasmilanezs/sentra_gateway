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

/** Persiste dados do usuário retornados por /auth/me.
 *
 * O backend pode retornar o tenant hidratado em `me.tenant`. Isso evita
 * que admin/member dependam de endpoints restritos a admin-like para exibir
 * nome/alias do próprio tenant.
 */
export function saveCurrentUser(me) {
  const user = {
    id:          me.id,
    email:       me.email,
    role:        me.role        || 'admin',
    tenant_id:   me.tenant_id  || null,
    tenant:      me.tenant     || null,
    permissions: me.permissions || [],
  };

  sessionStorage.setItem('sentra_user', JSON.stringify(user));

  if (user.tenant?.id) {
    sessionStorage.setItem('sentra_tenant', JSON.stringify({
      id: user.tenant.id,
      name: user.tenant.name,
      alias: user.tenant.alias,
    }));
  }
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