/* ============================================================
   SENTRA – login.js
   Responsável pela lógica da tela de login
   ============================================================ */

/**
 * Exibe uma mensagem de feedback para o usuário.
 * @param {string} elementId - ID do elemento de mensagem
 * @param {string} text      - Texto a exibir
 * @param {'error'|'success'|''} type - Tipo da mensagem
 */
function setMessage(elementId, text, type = '') {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.textContent = text;
  el.className = `msg ${type}`;
}

/**
 * Valida e envia o formulário de login.
 * Substitua o bloco fetch() pela chamada real ao backend quando disponível.
 */
async function handleLogin() {
  const username = document.getElementById('login-user').value.trim();
  const password = document.getElementById('login-pass').value;

  // Validação básica de campos
  if (!username || !password) {
    setMessage('login-msg', 'Preencha todos os campos.', 'error');
    return;
  }

  setMessage('login-msg', 'Autenticando…', '');

  try {
    /* ---------------------------------------------------------
       TODO: substituir pela URL real do backend FastAPI
       const response = await fetch('/api/auth/login', {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({ username, password }),
       });

       if (!response.ok) {
         const err = await response.json();
         setMessage('login-msg', err.detail || 'Credenciais inválidas.', 'error');
         return;
       }

       const data = await response.json();
       localStorage.setItem('access_token', data.access_token);
       window.location.href = '/dashboard.html';
    --------------------------------------------------------- */

    // Simulação temporária enquanto o backend não está pronto
    await new Promise(resolve => setTimeout(resolve, 900));
    setMessage('login-msg', 'Login realizado com sucesso!', 'success');

  } catch (error) {
    setMessage('login-msg', 'Erro ao conectar com o servidor.', 'error');
    console.error('[login] Erro na requisição:', error);
  }
}

// Permite enviar o formulário com a tecla Enter
document.addEventListener('DOMContentLoaded', () => {
  const inputs = document.querySelectorAll('#login-user, #login-pass');
  inputs.forEach(input => {
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleLogin();
    });
  });
});
