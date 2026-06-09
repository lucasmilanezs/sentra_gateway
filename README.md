# Sentra Gateway

O **Sentra** é uma plataforma de gateway interno para segurança, governança e auditoria de APIs.

O projeto centraliza controles que normalmente ficariam espalhados entre diferentes serviços backend, como políticas de autenticação, validação de requisições, rate limiting, auditoria e observabilidade operacional.

A solução é organizada em dois planos principais:

- **Admin Plane (Control Plane)**: responsável pela configuração, governança e interface administrativa.
- **Gateway Plane (Data Plane)**: responsável pelo processamento das requisições e aplicação das políticas configuradas.

---

# Principais funcionalidades

- Gerenciamento multi-tenant.
- Cadastro de domínios internos.
- Cadastro de rotas protegidas.
- Configuração de políticas por domínio e por rota.
- Validação progressiva de token Bearer/JWT.
- Validação de headers e query parameters.
- Rate limiting com Redis.
- Encaminhamento controlado para serviços upstream.
- Auditoria de requisições do gateway.
- Auditoria de alterações administrativas.
- Logs operacionais densos do gateway.
- Métricas e health checks.

---

# Visão arquitetural

O projeto segue princípios de **Arquitetura Hexagonal** e **Clean Architecture**, com separação explícita entre exposição, orquestração, domínio e integrações concretas.

```text
Interface
↓
Application
↓
Domain
↓
Infrastructure
```

A regra geral é que o domínio não conhece frameworks, banco de dados, Redis, HTTP ou qualquer tecnologia concreta. Essas integrações ficam nas camadas externas.

---

# Estrutura do projeto

```text
sentra_gateway/
├─ deploy/          # Docker, Compose e instruções de operação
├─ docs/            # Documentação complementar do projeto
├─ migrations/      # Evolução do schema via Alembic
├─ src/             # Código-fonte principal
│  ├─ admin/        # Plano administrativo
│  ├─ gateway/      # Plano de dados
│  └─ shared/       # Utilitários compartilhados
└─ tests/           # Testes automatizados e coleções auxiliares
```

---

# Execução local

A forma recomendada de subir o ambiente completo é via Docker Compose.

```bash
docker compose up --build
```

Para detalhes de variáveis, secrets, Fernet key e integração com plataformas de deploy, consulte:

```text
deploy/README.md
```

---

# Testes

A suíte automatizada principal fica em:

```text
tests/unit/
```

Execução:

```bash
pytest -q
```

---

# Observação de escopo

O Sentra não é um provedor de identidade, Authorization Server ou sistema de sessão do contratante.

O gateway atua como camada de pré-validação, enforcement configurável, auditoria e encaminhamento. A autenticação final, autorização fina, claims específicas, escopos, sessão e revogação continuam sendo responsabilidade do backend protegido.
