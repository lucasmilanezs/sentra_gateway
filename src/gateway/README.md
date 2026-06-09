# Gateway Plane (Data Plane)

O módulo **gateway** representa o plano de dados da plataforma Sentra.

Ele recebe requisições HTTP, resolve a configuração aplicável, executa policies e encaminha tráfego válido para o backend configurado.

---

# Responsabilidades

Entre as principais responsabilidades estão:

- receber requisições HTTP;
- decompor método, path, host, headers, query params e body;
- resolver tenant por domínio;
- resolver rota por tenant, path e método;
- aplicar policy por rota ou fallback do domínio;
- validar token em níveis progressivos;
- validar headers e query params;
- executar rate limiting;
- registrar auditoria de requisições;
- registrar logs operacionais densos;
- encaminhar requisições válidas ao upstream;
- preservar resposta do backend quando aplicável.

---

# Não responsabilidades

O Gateway não é responsável por:

- emitir tokens de sessão;
- renovar sessão de usuários externos;
- revogar tokens do contratante;
- interpretar regras de autorização fina do backend;
- substituir a autenticação final do serviço protegido;
- executar regras de negócio da aplicação protegida.

O Gateway reduz superfície de ataque e aplica pré-controles configuráveis, mas a autoridade final de sessão e autorização permanece no backend protegido.

---

# Estrutura interna

```text
gateway/
├─ application/
│  └─ use_cases/          # Orquestração do processamento de requisições
│
├─ domain/
│  ├─ models/             # Entidades e modelos centrais do Gateway
│  ├─ ports/              # Contratos abstratos de saída
│  └─ services/           # Avaliação de policies, auditoria, logs e rate limit
│
├─ infrastructure/
│  ├─ config/             # Configuração do plano de dados
│  ├─ observability/      # Escrita de auditoria/logs
│  ├─ persistence/        # Snapshot carregada do PostgreSQL
│  ├─ proxy/              # Encaminhamento upstream
│  ├─ pubsub/             # Assinatura de eventos de atualização
│  └─ redis/              # Rate limiting
│
├─ interface/
│  └─ http/               # Parser e routers HTTP
│
└─ main.py                # Inicialização do Gateway Plane
```

---

# Fluxo simplificado

```text
Request
↓
Parse HTTP
↓
Resolve tenant/domain
↓
Resolve route
↓
Select policy
↓
Evaluate policy
↓
Rate limit
↓
Audit + operational log
↓
Forward upstream
↓
Return response
```

---

# Snapshot operacional

O Gateway usa uma snapshot em memória com configurações vindas do PostgreSQL.

Essa snapshot não é persistência primária. Ela é uma cópia operacional temporária para reduzir latência no caminho crítico.

A fonte de verdade continua sendo o PostgreSQL gerenciado pelo Admin Plane.

---

# Validação de token

O Gateway trabalha com níveis configuráveis de validação.

Ele pode apenas exigir Bearer token, validar estrutura JWT, pré-validar claims declaradas ou validar assinatura criptográfica quando o contratante fornecer material apropriado.

A validação do Gateway não substitui o backend protegido como autoridade final de sessão, claims, roles, scopes ou revogação.

Consulte:

```text
docs/security-model.md
```
