import { authApi } from './api.js';

const form = document.getElementById('reset-form');
const message = document.getElementById('message');

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const email = document.getElementById('email').value;
  const code = document.getElementById('code').value;
  const password = document.getElementById('password').value;

  try {
    await authApi.resetPassword(email, code, password);

    message.innerText = 'Senha redefinida com sucesso';
    message.className = 'message success';

    setTimeout(() => {
      window.location.href = '/index.html';
    }, 1500);
  } catch (error) {
    message.innerText = error.detail;
    message.className = 'message error';
  }
});