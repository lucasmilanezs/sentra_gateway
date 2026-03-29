# Estrutura da Aplicação

Este diretório contém o código principal da aplicação Sentra.

O sistema é dividido em dois planos principais de operação:

- **Gateway (Data Plane)** – responsável por receber requisições externas, aplicar políticas de segurança e encaminhar requisições válidas para os serviços backend dos clientes.

- **Admin (Control Plane)** – responsável pela gestão e configuração da plataforma, incluindo cadastro de tenants, definição de rotas protegidas, configuração de políticas e visualização de logs.

Além desses dois módulos principais, existe também:

- **Shared** – módulo contendo utilidades e componentes compartilhados entre gateway e admin.

---

# Abordagem Arquitetural

O projeto segue princípios inspirados em:

- **Hexagonal Architecture**
- **Clean Architecture**
- **DDD (Domain Driven Design) leve**

Essa abordagem busca separar claramente:

- lógica de domínio
- orquestração da aplicação
- comunicação externa
- infraestrutura

O objetivo dessa separação é melhorar:

- manutenibilidade
- testabilidade
- organização do código
- independência entre camadas

---

# Estrutura Geral

```
src/
├─ admin/
│  ├─ application/        # Casos de uso e serviços de aplicação do módulo administrativo
│  ├─ domain/             # Entidades e regras de negócio do domínio administrativo
│  ├─ infrastructure/     # Integrações externas, persistência e adaptações técnicas
│  └─ interface/          # Controladores HTTP e pontos de entrada do módulo admin
│
├─ gateway/
│  ├─ application/        # Orquestração das requisições e execução das políticas do gateway
│  ├─ domain/             # Modelos de domínio e definições de políticas do gateway
│  ├─ infrastructure/     # Componentes técnicos de rede, roteamento e integrações externas
│  └─ interface/          # Interface de entrada para requisições processadas pelo gateway
│
├─ shared/                # Códigos e funções generalistas para reutilização ( duplicado no deploy )
│  ├─ config/
│  ├─ db/
│  ├─ errors/
│  ├─ http/
│  ├─ logging/           
│  ├─ observability/       
│  └─ security/
│
└─ readme.md
```

---

# Filosofia de Desenvolvimento

A arquitetura prioriza:

- separação clara de responsabilidades
- baixo acoplamento entre componentes
- dependências sempre apontando para dentro (em direção ao domínio)

Camadas internas não devem depender diretamente de detalhes de infraestrutura ou frameworks.