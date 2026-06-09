# Admin Plane (Control Plane)

O módulo **admin** representa o plano de controle da plataforma Sentra.

Ele fornece as funcionalidades administrativas responsáveis pela configuração, governança e operação do gateway.

---

# Responsabilidades

Entre as principais responsabilidades estão:

- autenticação administrativa;
- bootstrap de superuser;
- gerenciamento de tenants;
- cadastro de domínios internos;
- cadastro de rotas protegidas;
- configuração de policies por domínio e rota;
- configuração de rate limiting;
- gerenciamento de members e permissões;
- auditoria de alterações administrativas;
- consulta de auditoria do gateway;
- consulta de logs operacionais;
- visualização de métricas e health checks.

Essas configurações são utilizadas posteriormente pelo Gateway Plane durante o processamento das requisições.

---

# Estrutura interna

O Admin segue os mesmos princípios arquiteturais adotados no Gateway, com uma API administrativa mais próxima do padrão REST e uma interface web acoplada ao plano de controle.

```text
admin/
├─ application/
│  ├─ services/           # Serviços de aplicação para orquestrações auxiliares
│  └─ use_cases/          # Casos de uso administrativos
│
├─ domain/
│  ├─ entities/           # Entidades centrais do domínio administrativo
│  ├─ ports/              # Contratos abstratos usados pela aplicação
│  ├─ services/           # Serviços de domínio com regras transversais
│  └─ value_objects/      # Tipos com semântica e validação próprias
│
├─ infrastructure/
│  ├─ config/             # Configuração do plano administrativo
│  ├─ email/              # Adaptadores de envio de e-mail
│  ├─ health/             # Diagnóstico de dependências
│  ├─ observability/      # Leitura de logs operacionais do gateway
│  ├─ persistence/        # Persistência JSON/PostgreSQL
│  ├─ pubsub/             # Notificações de alteração de configuração
│  └─ security/           # Hash de senha e emissão de JWT administrativo
│
├─ interface/
│  ├─ http/               # Rotas HTTP, dependências e handlers
│  ├─ schema/             # Schemas Pydantic
│  └─ web/                # Interface administrativa estática
│
└─ main.py                # Inicialização do Admin Plane
```

---

# Camadas

## Interface

Responsável por expor APIs administrativas e servir o painel web.

Exemplos:

- rotas HTTP;
- schemas de entrada e saída;
- autenticação de endpoints;
- tradução de erros para HTTP;
- arquivos estáticos da interface.

---

## Application

Contém os casos de uso administrativos.

Exemplos:

- criar tenants;
- registrar rotas;
- atualizar policies;
- gerenciar members;
- consultar auditoria;
- consultar logs do gateway.

Essa camada coordena operações entre domínio e infraestrutura, sem assumir regras centrais de negócio.

---

## Domain

Contém as regras centrais relacionadas à configuração da plataforma.

Exemplos:

- invariantes de tenant;
- invariantes de usuário;
- regras de acesso por tenant;
- permissões de members;
- definição de policy;
- factories de eventos auditáveis.

---

## Infrastructure

Implementa integrações concretas.

Exemplos:

- PostgreSQL;
- Redis;
- SMTP;
- bcrypt;
- JWT administrativo;
- leitura de logs operacionais;
- publicação de atualização de configuração.

---

# Auditoria e logs

O Admin trabalha com dois tipos distintos de informação:

- **Auditoria formal**: eventos persistidos no PostgreSQL, usados para rastreabilidade e governança.
- **Logs operacionais**: eventos densos do Gateway, mantidos no Redis com retenção curta para diagnóstico.

Esses dados são exibidos separadamente na interface para evitar confusão entre evidência auditável e observabilidade técnica.
