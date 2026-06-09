# Source Code

O código-fonte principal fica em `src/` e é dividido em três módulos:

```text
src/
├─ admin/
├─ gateway/
└─ shared/
```

---

# Admin Plane

O `admin/` representa o plano de controle.

Ele é responsável por:

- autenticação administrativa;
- gerenciamento de tenants;
- gerenciamento de domínios;
- gerenciamento de rotas;
- configuração de policies;
- gerenciamento de members;
- auditoria de governança;
- visualização de logs, auditoria e métricas.

---

# Gateway Plane

O `gateway/` representa o plano de dados.

Ele é responsável por:

- receber requisições;
- resolver tenant, domínio e rota;
- aplicar policies;
- executar rate limiting;
- registrar auditoria de requisição;
- registrar logs operacionais;
- encaminhar para o upstream configurado.

---

# Shared

O `shared/` contém utilitários reutilizados pelos dois planos.

Exemplos:

- configuração compartilhada;
- helpers HTTP;
- criptografia de secrets;
- diagnóstico de dependências;
- utilitários de runtime.

---

# Camadas

Cada plano segue a mesma separação arquitetural:

```text
interface/
application/
domain/
infrastructure/
```

## Interface

Camada de exposição.

Exemplos:

- routers HTTP;
- schemas Pydantic;
- assets web;
- tradução final para HTTP.

## Application

Camada de orquestração.

Contém casos de uso e coordena domínio, portas e infraestrutura.

Não deve conter regra de negócio central.

## Domain

Centro do sistema.

Contém entidades, invariantes, regras de negócio e serviços de domínio.

Não conhece banco, Redis, HTTP, FastAPI ou frameworks externos.

## Infrastructure

Integrações concretas.

Exemplos:

- PostgreSQL;
- Redis;
- pub/sub;
- proxy upstream;
- health checks;
- envio de e-mail.

---

# Regra de dependência

As dependências devem apontar para dentro.

Camadas externas podem conhecer camadas internas. O domínio não deve depender de camadas externas.
