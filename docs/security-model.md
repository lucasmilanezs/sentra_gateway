# Security Model

O Sentra aplica políticas de segurança progressivas e configuráveis.

O objetivo do Gateway é reduzir superfície de ataque, padronizar pré-controles e gerar rastreabilidade, sem assumir o papel de provedor de identidade ou sistema de sessão do contratante.

---

# Validação de token

As policies podem definir o nível de validação aplicado ao token recebido.

Quanto maior o nível, mais informação o contratante precisa fornecer ao Sentra.

---

## Nível 0 — Nenhuma validação

O Gateway não exige token.

Uso típico:

- rotas internas públicas;
- health checks;
- endpoints sem proteção no gateway.

---

## Nível 1 — Bearer obrigatório

O Gateway exige:

```http
Authorization: Bearer <token>
```

Valida:

- presença do header `Authorization`;
- schema `Bearer`;
- token não vazio.

Não valida:

- JWT;
- assinatura;
- expiração;
- issuer;
- audience;
- roles;
- scopes.

---

## Nível 2 — JWT estrutural

O Gateway valida que o token parece um JWT bem formado.

Valida:

- três segmentos no formato `header.payload.signature`;
- header decodificável;
- payload decodificável;
- bloqueio de algoritmo `none`.

Não valida assinatura criptográfica.

As claims lidas nesse nível são apenas declaradas, não confiáveis.

---

## Nível 3 — Claims declaradas

O Gateway pré-valida claims estáticas declaradas no payload.

Pode validar:

- `exp`;
- `iss`;
- `aud`.

Sem assinatura criptográfica, essa validação funciona como pré-filtro estrutural. Ela não prova que o token foi emitido por uma autoridade confiável.

---

## Nível 4 — Assinatura JWT local

O Gateway valida criptograficamente o token usando material fornecido pelo contratante.

Pode validar:

- assinatura;
- algoritmo configurado;
- `exp`;
- `iss`;
- `aud`.

Esse nível exige material de validação cadastrado na policy.

Tipos comuns:

- HMAC secret compartilhada para `HS256`;
- chave pública PEM para `RS256`.

Material sensível é armazenado criptografado no banco e nunca retornado em texto claro pela API.

---

# O que o Gateway não valida

O Gateway não gerencia:

- sessão do usuário final;
- refresh token;
- revogação de token;
- autorização fina por roles/scopes;
- regras internas do backend protegido.

Essas responsabilidades permanecem com o sistema contratante.

---

# Headers

Policies podem configurar:

- headers obrigatórios;
- headers proibidos.

Essas validações atuam sobre a presença ou ausência das chaves de header, sem interpretar regras complexas de valor.

---

# Query parameters

Policies podem configurar:

- parâmetros obrigatórios;
- parâmetros proibidos.

Assim como headers, a validação atual é estrutural e orientada à presença/ausência.

---

# Rate limiting

Policies podem definir limite de requisições por janela temporal.

O estado operacional do rate limit é mantido no Redis.

Quando Redis está indisponível, o comportamento pode ser configurado conforme a policy.

---

# Auditoria e logs

O Sentra separa dois conceitos:

## Auditoria

Registro semântico e persistente.

Usado para:

- rastreabilidade;
- governança;
- investigação;
- histórico de decisões.

Persistência principal: PostgreSQL.

## Logs operacionais

Registro técnico e denso do processamento do Gateway.

Usado para:

- diagnóstico;
- depuração;
- análise operacional recente.

Persistência operacional: Redis, com retenção curta.

---

# Diretriz central

O Gateway deve ser sincero sobre o que valida.

Validações sem assinatura são pré-filtros. Validações com assinatura são criptograficamente confiáveis, desde que o material cadastrado seja correto e protegido.
