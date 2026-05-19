import { authApi } from './api.js';
import { saveCurrentUser } from './auth.js';

const form    = document.getElementById('register-form');
const message = document.getElementById('message');

function showMessage(text, type = 'error') {
  message.innerText = text;
  message.className = `message ${type}`;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const email          = document.getElementById('email').value.trim();
  const password       = document.getElementById('password').value;
  const confirm        = document.getElementById('confirm-password').value;
  const company_name   = document.getElementById('company-name').value.trim();
  const company_alias  = document.getElementById('company-alias').value.trim().toLowerCase();

  // Validações locais — backend revalida tudo de qualquer forma
  if (password !== confirm) {
    showMessage('As senhas não coincidem.');
    return;
  }
  if (password.length < 8) {
    showMessage('Senha deve ter pelo menos 8 caracteres.');
    return;
  }

  try {
    const data = await authApi.register({
      email,
      password,
      company_name,
      company_alias,
    });

    // Backend já retornou tenant + user — não precisa chamar me() de novo.
    sessionStorage.setItem('sentra_token', data.access_token);
    saveCurrentUser(data.user);
    sessionStorage.setItem(
      'sentra_tenant',
      JSON.stringify({
        id: data.tenant.id,
        name: data.tenant.name,
        alias: data.tenant.alias,
      }),
    );

    window.location.href = '/dashboard.html';
  } catch (error) {
    showMessage(error.detail || 'Erro ao criar conta');
  }
});