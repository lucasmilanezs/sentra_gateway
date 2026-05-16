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

export function isSuperUser() {
  return currentTenant() === null;
}
