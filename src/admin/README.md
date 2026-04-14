# Admin Plane (Control Plane)

O módulo **admin** representa o plano de controle da plataforma Sentra.

Ele fornece as funcionalidades administrativas responsáveis pela configuração e operação do gateway.

---

# Responsabilidades

Entre as principais responsabilidades estão:

- gerenciamento de tenants
- cadastro de serviços backend
- definição de rotas protegidas
- configuração de políticas de autenticação
- configuração de rate limiting
- visualização de logs e eventos de auditoria

Essas configurações são utilizadas posteriormente pelo gateway durante o processamento das requisições.

---

# Estrutura Interna

O admin segue os mesmos princípios arquiteturais adotados no gateway, com a diferença que a API administrativa se aproxima mais do padrão REST.

```
admin/
├─ application/
│  ├─ dtos/               # Objetos de transferência de dados entre camadas ( se aplicável )
│  └─ use_cases/          # Casos de uso responsáveis pela orquestração das camadas inferiores
│
├─ domain/
│  ├─ models/             # Modelos centrais e entidades de negócio do domínio do gateway
│  └─ services/           # Serviços de domínio com regras de negócio e validações centrais
│
├─ infrastructure/
│  ├─ observability/      # Instrumentação de métricas, tracing e monitoramento
│  ├─ persistence/        # Implementações de persistência e acesso a dados
│  ├─ proxy/              # Componentes responsáveis pelo encaminhamento das requisições
│  └─ pubsub/             # Mecanismos de mensageria e comunicação assíncrona
│
├─ interface/
│  ├─ http/               # Camada de entrada HTTP do admin plane
│  │  └─ routers/         # Definição e organização das rotas expostas
│  └─ schema/             # Esquemas de validação e serialização de dados do Pydantic
│
└─ README.md              # Documentação específica da estrutura do módulo admin
```

---

# Camadas

## Interface

Responsável por expor APIs administrativas e, quando aplicável, servir a interface web do painel administrativo.

Exemplos:

- rotas HTTP
- schemas de requisição
- assets estáticos da interface

---

## Application

Contém os casos de uso administrativos, como:

- criar tenants
- registrar rotas
- atualizar políticas

Essa camada coordena operações entre domínio e infraestrutura.

---

## Domain

Contém as regras centrais relacionadas à configuração da plataforma.

Exemplos:

- entidades de tenant
- definição de políticas
- regras de configuração

---

## Infrastructure

Implementa as integrações concretas com sistemas externos.

Exemplos:

- persistência em banco de dados
- integração com cache
- serviços auxiliares de logging