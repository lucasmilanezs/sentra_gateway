import { authApi } from './api.js';

export function requireAuth() {
  const token = sessionStorage.getItem('sentra_token');

  if (!token) {
    window.location.href = '/index.html';
  }
}

export function logout() {
  sessionStorage.clear();
  window.location.href = '/index.html';
}

export async function currentUser() {
  return await authApi.me();
}

export function currentTenant() {
  const tenant = sessionStorage.getItem('sentra_tenant');

  return tenant ? JSON.parse(tenant) : null;
}