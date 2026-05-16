import { authApi } from './api.js';

const form = document.getElementById('register-form');
const message = document.getElementById('message');

function showMessage(text, type = 'error') {
  message.innerText = text;
  message.className = `message ${type}`;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const email = document.getElementById('email').value;
  const password = document.getElementById('password').value;

  try {
    const data = await authApi.register(email, password);

    sessionStorage.setItem('sentra_token', data.access_token);

    window.location.href = '/dashboard.html';
  } catch (error) {
    showMessage(error.detail || 'Erro ao registrar');
  }
});