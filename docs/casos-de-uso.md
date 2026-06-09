# Casos de uso — SENTRA (atualização 27/05)

| ID | Caso de uso | Status | Evidência |
|----|-------------|--------|-----------|
| UC01 | Cadastrar tenant com alias único | Implementado | `POST /api/v1/tenants`, UI tenant-select |
| UC02 | Cadastrar domain por tenant (Host header) | Implementado | `POST /api/v1/tenants/{id}/domains` |
| UC03 | Sugerir domains do grupo empresarial | Implementado | `GET /api/v1/tenants/{id}/domain-suggestions` |
| UC04 | Cadastrar rota REST com validação de path | Implementado | `POST /api/v1/routes`, validação front/back |
| UC05 | Configurar política por rota (JWT, rate limit, roles) | Implementado | `PUT /api/v1/routes/{id}/policy` |
| UC06 | Configurar política global por domain | Implementado | `PUT .../domains/{id}/policy` |
| UC07 | Validar JWT estrutural (exp, iss, aud) | Implementado | Gateway `PolicyEvaluator` |
| UC08 | Rate limiting sliding window (Redis) | Implementado | 429 após limite; chave por tenant+rota+IP |
| UC09 | Proxy transparente preservando status upstream | Implementado | Testes integração httpbin |
| UC10 | Isolamento multi-tenant por Host | Implementado | Resolução `admin_tenant_domains` |
| UC11 | Auditoria — últimas 100 requisições | Implementado | `GET /api/v1/audit`, painel Auditoria |
| UC12 | Dashboard de métricas (24h) | Implementado | `GET /api/v1/metrics/summary` |
| UC13 | Integração API externa (ex.: SMTP) | Parcial | `ConsoleEmailSender` / SMTP configurável |
| UC14 | RBAC em rotas protegidas | Parcial | `allowed_roles` no JWT; documentar limites |
| UC15 | Deploy local Docker para demonstração | Implementado | `deploy/docker/docker-compose.yml` |

## Cenários de teste recomendados

1. Política 5 req/min → 6ª requisição retorna **429**.
2. Rota com `requires_auth` → sem Bearer retorna **401**.
3. Dois tenants → auditoria de A não aparece para usuário de B.
4. `docker compose up` + checklist do [README.md](../README.md).
