# Deploy e operação

Esta pasta contém os artefatos de execução da plataforma Sentra, incluindo Dockerfiles, entrypoints e Docker Compose.

O ambiente padrão sobe quatro componentes principais:

- Admin Plane
- Gateway Plane
- PostgreSQL
- Redis

---

# Dependências locais

Para execução local, instale:

- Docker
- Docker Compose

Para tarefas de desenvolvimento fora dos containers, recomenda-se também:

- Python 3.11+
- Ambiente virtual (`venv`)

---

# Variáveis de ambiente essenciais

O projeto depende de variáveis de ambiente para inicialização do banco, autenticação administrativa, superuser inicial e criptografia de material sensível de políticas.

Exemplo mínimo local:

```env
POSTGRES_USER=sentra
POSTGRES_PASSWORD=sentra_secret
POSTGRES_DB=sentra_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

ADMIN_JWT_SECRET=change-me-in-production
ADMIN_JWT_ALGORITHM=HS256
ADMIN_USE_POSTGRES=true

SENTRA_SUPERUSER_EMAIL=superuser@sentra.dev
SENTRA_SUPERUSER_PASSWORD=change-me-in-production

GATEWAY_AUDIT_TO_POSTGRES=true
GATEWAY_RAW_LOG_RETENTION_DAYS=7
GATEWAY_RAW_LOG_MAX_ENTRIES_PER_TENANT_PER_DAY=1000
GATEWAY_RAW_LOG_REDACT_HEADERS=authorization,cookie,set-cookie,x-api-key
```

---

# Fernet key para policies assinadas

Quando políticas usam validação local de assinatura JWT, o sistema precisa armazenar material de validação de forma criptografada.

Para isso, configure a variável local:

```env
SENTRA_POLICY_SECRET_KEY=<fernet-key>
```

Essa variável deve existir nos containers do **Admin** e do **Gateway**.

Ela não deve ser versionada e não precisa aparecer com valor real em exemplos públicos.

Gerar uma chave:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

A chave é usada para criptografar e descriptografar secrets/chaves configuradas nas policies. O valor sensível é persistido criptografado no banco e materializado em memória apenas durante a operação necessária.

---

# Variáveis fornecidas pela plataforma de deploy

Em plataformas como Railway, Render, Coolify, Kubernetes, Docker Swarm ou ECS, normalmente as variáveis são configuradas pelo próprio ambiente.

Nesse caso, o arquivo `.env` pode atuar apenas como mapeamento:

```env
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=${POSTGRES_DB}
POSTGRES_HOST=${POSTGRES_HOST}
POSTGRES_PORT=${POSTGRES_PORT}

ADMIN_JWT_SECRET=${ADMIN_JWT_SECRET}
ADMIN_JWT_ALGORITHM=${ADMIN_JWT_ALGORITHM}
ADMIN_USE_POSTGRES=${ADMIN_USE_POSTGRES}

SENTRA_SUPERUSER_EMAIL=${SENTRA_SUPERUSER_EMAIL}
SENTRA_SUPERUSER_PASSWORD=${SENTRA_SUPERUSER_PASSWORD}

GATEWAY_AUDIT_TO_POSTGRES=${GATEWAY_AUDIT_TO_POSTGRES}
GATEWAY_RAW_LOG_RETENTION_DAYS=${GATEWAY_RAW_LOG_RETENTION_DAYS}
GATEWAY_RAW_LOG_MAX_ENTRIES_PER_TENANT_PER_DAY=${GATEWAY_RAW_LOG_MAX_ENTRIES_PER_TENANT_PER_DAY}
GATEWAY_RAW_LOG_REDACT_HEADERS=${GATEWAY_RAW_LOG_REDACT_HEADERS}

SENTRA_POLICY_SECRET_KEY=${SENTRA_POLICY_SECRET_KEY}
```

O importante é garantir que os containers recebam as mesmas variáveis obrigatórias no runtime.

---

# Inicialização

Na raiz do projeto:

```bash
docker compose up --build
```

Ou, caso esteja usando o Compose dentro desta pasta, adapte o caminho conforme a organização local.

---

# Migrações

O container do Admin executa as migrations antes de iniciar a aplicação.

Caso precise rodar manualmente:

```bash
alembic upgrade head
```

Consulte também:

```text
migrations/README.md
```

---

# Observações operacionais

- PostgreSQL é a fonte de verdade para configuração, usuários e auditoria formal.
- Redis é usado para rate limiting, pub/sub e logs operacionais de retenção curta.
- O Gateway usa snapshot em memória para evitar consultas síncronas ao banco no caminho crítico.
- Secrets de políticas nunca devem ser logadas, auditadas em texto claro ou retornadas pela API.
