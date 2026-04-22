/* ============================================================
   SENTRA – forgot-password.js
   Responsável pela lógica da tela de redefinição de senha
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
 * Valida e envia o formulário de redefinição de senha.
 */
async function handleForgotPassword() {
  const newPassword     = document.getElementById('forgot-new').value;
  const confirmPassword = document.getElementById('forgot-confirm').value;

  // Validação de campos obrigatórios
  if (!newPassword || !confirmPassword) {
    setMessage('forgot-msg', 'Preencha todos os campos.', 'error');
    return;
  }

  // Validação de tamanho mínimo
  if (newPassword.length < 8) {
    setMessage('forgot-msg', 'A senha deve ter no mínimo 8 caracteres.', 'error');
    return;
  }

  // Validação de confirmação
  if (newPassword !== confirmPassword) {
    setMessage('forgot-msg', 'As senhas não coincidem.', 'error');
    return;
  }

  setMessage('forgot-msg', 'Salvando…', '');

  try {
    /* ---------------------------------------------------------
       TODO: substituir pela URL real do backend FastAPI
       O token de redefinição normalmente vem via query param da URL,
       ex: /forgot-password.html?token=abc123

       const params  = new URLSearchParams(window.location.search);
       const token   = params.get('token');

       const response = await fetch('/api/auth/reset-password', {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({ token, new_password: newPassword }),
       });

       if (!response.ok) {
         const err = await response.json();
         setMessage('forgot-msg', err.detail || 'Erro ao redefinir senha.', 'error');
         return;
       }

       setMessage('forgot-msg', 'Senha atualizada com sucesso!', 'success');
       setTimeout(() => window.location.href = '/index.html', 1500);
    --------------------------------------------------------- */

    // Simulação temporária
    await new Promise(resolve => setTimeout(resolve, 900));
    setMessage('forgot-msg', 'Senha atualizada com sucesso!', 'success');
    setTimeout(() => window.location.href = 'index.html', 1500);

  } catch (error) {
    setMessage('forgot-msg', 'Erro ao conectar com o servidor.', 'error');
    console.error('[forgot-password] Erro na requisição:', error);
  }
}

// Permite enviar o formulário com a tecla Enter
document.addEventListener('DOMContentLoaded', () => {
  const inputs = document.querySelectorAll('#forgot-new, #forgot-confirm');
  inputs.forEach(input => {
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleForgotPassword();
    });
  });
});
