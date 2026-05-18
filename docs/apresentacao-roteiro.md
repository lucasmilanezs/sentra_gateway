# Roteiro de apresentação — SENTRA (storytelling)

**Duração alvo:** 12–15 minutos (+ perguntas)

## Personagens

- **CTO** — apresenta o problema do grupo empresarial
- **Dev Tenant Acme** — configura APIs da empresa A
- **Dev Tenant Beta** — configura APIs da empresa B

## Narrativa

1. **Problema (2 min)** — Grupo com filiais usa APIs diferentes; controles de segurança fragmentados; sem visibilidade central.
2. **Solução (1 min)** — SENTRA: gateway para **rede interna corporativa**; plano de gerenciamento + plano de dados.
3. **Arquitetura (2 min)** — Diagramas L0/L1 em `docs/architecture/models/`; Postgres, Redis, Docker local.
4. **Demo ao vivo (6 min)** — Seguir checklist do README:
   - Subir Docker
   - Login superuser → criar Acme e Beta
   - Domains sugeridos (`api.acme.local`)
   - Rotas `/v1/...` com validação REST
   - Política rate limit 5/min → mostrar 429
   - JWT obrigatório → 401 sem token
   - Tráfego pelo gateway → **Auditoria** (100 eventos) + **Métricas**
5. **Isolamento (1 min)** — Tenant Acme não vê auditoria/config de Beta.
6. **Limitações e evolução (1 min)** — Rede pública, WAF, deploy cloud como trabalho futuro.

## Slides sugeridos (mínimo)

1. Capa + equipe
2. Problema / Justificativa
3. Objetivos do PFC
4. Arquitetura (Admin + Gateway)
5. Rate limiting (sliding window + Redis)
6. JWT e políticas
7. Auditoria e métricas
8. Demo (screenshot ou ao vivo)
9. Conclusão

## Ensaio

- Rodar demo completa 2x em máquina de apresentação
- Confirmar Docker Desktop ativo antes da banca
- Credenciais superuser no `.env` anotadas em papel de backup
