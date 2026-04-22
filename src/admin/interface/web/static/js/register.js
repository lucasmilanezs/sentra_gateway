/* ============================================================
   SENTRA – register.js
   Responsável pela lógica da tela de cadastro
   ============================================================ */

/**
 * Exibe uma mensagem de feedback para o usuário.
 */
function setMessage(elementId, text, type = '') {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.textContent = text;
  el.className = `msg ${type}`;
}

/**
 * Valida e envia o formulário de cadastro.
 */
async function handleRegister() {
  const username        = document.getElementById('reg-user').value.trim();
  const password        = document.getElementById('reg-pass').value;
  const confirmPassword = document.getElementById('reg-confirm').value;

  // Validação de campos obrigatórios
  if (!username || !password || !confirmPassword) {
    setMessage('reg-msg', 'Preencha todos os campos.', 'error');
    return;
  }

  // Validação de tamanho mínimo de senha
  if (password.length < 8) {
    setMessage('reg-msg', 'A senha deve ter no mínimo 8 caracteres.', 'error');
    return;
  }

  // Validação de confirmação de senha
  if (password !== confirmPassword) {
    setMessage('reg-msg', 'As senhas não coincidem.', 'error');
    return;
  }

  setMessage('reg-msg', 'Criando conta…', '');

  try {
    /* ---------------------------------------------------------
       TODO: substituir pela URL real do backend FastAPI
       const response = await fetch('/api/auth/register', {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({ username, password }),
       });

       if (!response.ok) {
         const err = await response.json();
         setMessage('reg-msg', err.detail || 'Erro ao criar conta.', 'error');
         return;
       }

       setMessage('reg-msg', 'Conta criada com sucesso!', 'success');
       setTimeout(() => window.location.href = '/index.html', 1500);
    --------------------------------------------------------- */

    // Simulação temporária
    await new Promise(resolve => setTimeout(resolve, 900));
    setMessage('reg-msg', 'Conta criada com sucesso!', 'success');
    setTimeout(() => window.location.href = 'index.html', 1500);

  } catch (error) {
    setMessage('reg-msg', 'Erro ao conectar com o servidor.', 'error');
    console.error('[register] Erro na requisição:', error);
  }
}

// Permite enviar o formulário com a tecla Enter
document.addEventListener('DOMContentLoaded', () => {
  const inputs = document.querySelectorAll('#reg-user, #reg-pass, #reg-confirm');
  inputs.forEach(input => {
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleRegister();
    });
  });
});
