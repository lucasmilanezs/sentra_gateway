// Lógica extraída do index.html — lógica preservada integralmente

    import { authApi } from '../api.js';

    // ── Redireciona se já autenticado ──────────────────────────────────
    if (sessionStorage.getItem('sentra_token')) {
      const tenant = sessionStorage.getItem('sentra_tenant');
      window.location.href = tenant ? '/dashboard.html' : '/tenant-select.html';
    }

    // ── Helpers ────────────────────────────────────────────────────────
    function msg(id, text, type) {
      const el = document.getElementById(id);
      el.textContent = text;
      el.className = 'auth-msg' + (type ? ' ' + type : '');
    }

    function setLoading(btnId, loading, label) {
      const btn = document.getElementById(btnId);
      btn.disabled = loading;
      btn.textContent = loading ? 'Aguarde…' : label;
    }

    // ── Tabs ───────────────────────────────────────────────────────────
    window.showTab = function(tab) {
      document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.auth-panel').forEach(p => p.classList.remove('active'));
      document.getElementById('tab-' + tab).classList.add('active');
      document.getElementById('panel-' + tab).classList.add('active');
    };

    window.showForgotStep = function(step) {
      document.getElementById('forgot-step1').style.display = step === 1 ? 'block' : 'none';
      document.getElementById('forgot-step2').style.display = step === 2 ? 'block' : 'none';
    };

    // ── Termos de uso no cadastro ─────────────────────────────────────
    const termsModal = document.getElementById('terms-modal');
    const termsCheckbox = document.getElementById('reg-terms-accepted');
    const registerButton = document.getElementById('reg-btn');

    function updateRegisterButtonState() {
      if (!registerButton || !termsCheckbox) return;
      registerButton.disabled = !termsCheckbox.checked;
    }

    function openTermsModal() {
      if (!termsModal) return;
      termsModal.classList.add('active');
      termsModal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('terms-modal-open');
    }

    function closeTermsModal() {
      if (!termsModal) return;
      termsModal.classList.remove('active');
      termsModal.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('terms-modal-open');
    }

    document.getElementById('open-terms-modal')?.addEventListener('click', openTermsModal);
    document.getElementById('close-terms-modal')?.addEventListener('click', closeTermsModal);
    document.getElementById('decline-terms-modal')?.addEventListener('click', closeTermsModal);
    document.getElementById('accept-terms-modal')?.addEventListener('click', () => {
      if (termsCheckbox) termsCheckbox.checked = true;
      updateRegisterButtonState();
      closeTermsModal();
      msg('reg-msg', '', '');
    });
    termsCheckbox?.addEventListener('change', updateRegisterButtonState);
    termsModal?.addEventListener('click', (event) => {
      if (event.target === termsModal) closeTermsModal();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && termsModal?.classList.contains('active')) {
        closeTermsModal();
      }
    });
    updateRegisterButtonState();

    // ── Login ──────────────────────────────────────────────────────────
    window.handleLogin = async function() {
      const email = document.getElementById('login-email').value.trim();
      const pass  = document.getElementById('login-pass').value;
      msg('login-msg', '', '');

      if (!email || !pass) { msg('login-msg', 'Preencha e-mail e senha.', 'error'); return; }

      setLoading('login-btn', true, 'Entrar');
      try {
        const { access_token } = await authApi.login(email, pass);
        sessionStorage.setItem('sentra_token', access_token);

        const me = await authApi.me();
        sessionStorage.setItem('sentra_user', JSON.stringify({
          id:          me.id,
          email:       me.email,
          role:        me.role,
          tenant_id:   me.tenant_id,
          permissions: me.permissions || [],
        }));
        if (me.role === 'superuser') {
          window.location.href = '/tenant-select.html';
          return;
        }

        if (!me.tenant_id) {
          throw { detail: 'Usuário admin/member sem tenant vinculado.' };
        }

sessionStorage.setItem('sentra_tenant', JSON.stringify({ id: me.tenant_id }));
window.location.href = '/dashboard.html';
      } catch (err) {
        msg('login-msg', err.detail || 'Credenciais inválidas.', 'error');
        setLoading('login-btn', false, 'Entrar');
      }
    };

    document.getElementById('login-pass').addEventListener('keydown', e => {
      if (e.key === 'Enter') handleLogin();
    });

    // ── Auto-alias no cadastro ──────────────────────────────────────────
    document.getElementById('reg-company').addEventListener('input', e => {
      const aliasEl = document.getElementById('reg-alias');
      // só preenche automaticamente se ainda não foi editado manualmente
      if (!aliasEl.dataset.edited) {
        aliasEl.value = e.target.value
          .toLowerCase()
          .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
          .replace(/[^a-z0-9]+/g, '-')
          .replace(/^-|-$/g, '');
      }
    });

    document.getElementById('reg-alias').addEventListener('input', e => {
      e.target.dataset.edited = '1';
      // sanitiza em tempo real
      e.target.value = e.target.value
        .toLowerCase()
        .replace(/[^a-z0-9-]/g, '-');
    });

    // ── Cadastro ───────────────────────────────────────────────────────
    // Onboarding atômico: o backend cria tenant + admin numa única
    // transação. Não há mais chamada separada a /tenants depois.
    window.handleRegister = async function() {
      const email   = document.getElementById('reg-email').value.trim();
      const pass    = document.getElementById('reg-pass').value;
      const confirm = document.getElementById('reg-confirm').value;
      const company = document.getElementById('reg-company').value.trim();
      const alias   = document.getElementById('reg-alias').value.trim();
      msg('reg-msg', '', '');

      if (!email || !pass || !company || !alias) {
        msg('reg-msg', 'Preencha todos os campos.', 'error'); return;
      }
      if (pass !== confirm) {
        msg('reg-msg', 'As senhas não coincidem.', 'error'); return;
      }
      if (pass.length < 8) {
        msg('reg-msg', 'Senha deve ter ao menos 8 caracteres.', 'error'); return;
      }
      if (!document.getElementById('reg-terms-accepted')?.checked) {
        msg('reg-msg', 'É necessário aceitar os termos de uso para criar a conta.', 'error'); return;
      }

      setLoading('reg-btn', true, 'Criando conta…');
      try {
        const data = await authApi.register({
          email,
          password: pass,
          company_name: company,
          company_alias: alias,
          accepted_terms: true,
        });

        // Backend já retornou user + tenant + token na mesma resposta.
        sessionStorage.setItem('sentra_token', data.access_token);
        sessionStorage.setItem('sentra_user', JSON.stringify({
          id:          data.user.id,
          email:       data.user.email,
          role:        data.user.role,
          tenant_id:   data.user.tenant_id,
          permissions: data.user.permissions || [],
        }));
        sessionStorage.setItem('sentra_tenant', JSON.stringify({
          id:    data.tenant.id,
          name:  data.tenant.name,
          alias: data.tenant.alias,
        }));

        msg('reg-msg', 'Conta criada! Redirecionando…', 'success');
        setTimeout(() => window.location.href = '/dashboard.html', 700);
      } catch (err) {
        msg('reg-msg', err.detail || 'Erro ao criar conta.', 'error');
        setLoading('reg-btn', false, 'Criar conta');
      }
    };

    // ── Esqueci a senha ────────────────────────────────────────────────
    let _forgotEmail = '';

    window.handleForgot = async function() {
      const email = document.getElementById('forgot-email').value.trim();
      msg('forgot-msg', '', '');
      if (!email) { msg('forgot-msg', 'Informe o e-mail cadastrado.', 'error'); return; }

      setLoading('forgot-btn', true, 'Enviando…');
      try {
        await authApi.forgotPassword(email);
        _forgotEmail = email;
        msg('forgot-msg', 'Código enviado. Verifique seu e-mail.', 'success');
        setTimeout(() => showForgotStep(2), 1200);
      } catch (err) {
        msg('forgot-msg', err.detail || 'Erro ao enviar código.', 'error');
        setLoading('forgot-btn', false, 'Enviar código');
      }
    };

    window.handleReset = async function() {
      const code    = document.getElementById('reset-code').value.trim();
      const pass    = document.getElementById('reset-pass').value;
      const confirm = document.getElementById('reset-confirm').value;
      msg('reset-msg', '', '');

      if (!code || !pass) { msg('reset-msg', 'Preencha o código e a nova senha.', 'error'); return; }
      if (pass !== confirm) { msg('reset-msg', 'As senhas não coincidem.', 'error'); return; }

      setLoading('reset-btn', true, 'Redefinindo…');
      try {
        await authApi.resetPassword(_forgotEmail, code, pass);
        msg('reset-msg', 'Senha redefinida. Redirecionando…', 'success');
        setTimeout(() => { showTab('login'); showForgotStep(1); }, 1500);
      } catch (err) {
        msg('reset-msg', err.detail || 'Código inválido ou expirado.', 'error');
        setLoading('reset-btn', false, 'Redefinir senha');
      }
    };
  