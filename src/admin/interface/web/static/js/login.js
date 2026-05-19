import { authApi } from './api.js';
import { saveCurrentUser } from './auth.js';

const form    = document.getElementById('login-form');
const message = document.getElementById('message');

function showMessage(text, type = 'error') {
  message.innerText   = text;
  message.className   = `message ${type}`;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const email    = document.getElementById('email').value;
  const password = document.getElementById('password').value;

  try {
    const loginData = await authApi.login(email, password);
    sessionStorage.setItem('sentra_token', loginData.access_token);

    const me = await authApi.me();
    saveCurrentUser(me); // grava role + permissions antes de qualquer redirect

    if (me.tenant_id) {
      // admin ou member com tenant fixo — vai direto pro dashboard
      sessionStorage.setItem(
        'sentra_tenant',
        JSON.stringify({ id: me.tenant_id, name: me.tenant_id }),
      );
      window.location.href = '/dashboard.html';
      return;
    }

    // superuser ou admin de plataforma sem tenant fixo — seleciona tenant
    window.location.href = '/tenant-select.html';
  } catch (error) {
    showMessage(error.detail || 'Falha no login');
  }
});