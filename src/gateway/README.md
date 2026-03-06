# Gateway (Data Plane)

O módulo **gateway** representa o plano de dados da plataforma Sentra.

Ele é responsável por receber requisições externas, aplicar políticas de segurança e encaminhar requisições válidas para os serviços backend dos clientes.

Esse componente opera diretamente no caminho das requisições, portanto prioriza:

- desempenho
- previsibilidade
- confiabilidade
- baixo acoplamento com infraestrutura

---

# Responsabilidades

O gateway é responsável por:

- identificar o tenant da requisição
- validar autenticação
- aplicar autorização
- aplicar rate limiting
- validar requisições
- encaminhar requisições válidas para serviços upstream
- registrar logs e eventos de auditoria

O gateway **não persiste o conteúdo do payload das requisições**. Os dados são tratados apenas durante o runtime.

---

# Estrutura Interna

O gateway segue uma estrutura inspirada em **Hexagonal Architecture** e **DDD** leve onde é conveniente:

```
gateway/
├─ application/
│  ├─ dtos/               # Objetos de transferência de dados entre camadas ( se aplicável )
│  └─ use_cases/          # Casos de uso responsáveis pelo fluxo de aplicação do gateway
│
├─ domain/
│  ├─ models/             # Modelos centrais e entidades de negócio do domínio do gateway
│  ├─ ports/              # Contratos e abstrações para comunicação com camadas externas
│  └─ services/           # Serviços de domínio com regras de negócio e validações centrais
│
├─ infrastructure/
│  ├─ cache/              # Componentes de cache e armazenamento temporário de dados
│  ├─ observability/      # Instrumentação de métricas, tracing e monitoramento
│  ├─ persistence/        # Implementações de persistência e acesso a dados
│  ├─ proxy/              # Componentes responsáveis pelo encaminhamento das requisições
│  └─ pubsub/             # Mecanismos de mensageria e comunicação assíncrona
│
├─ interface/
│  ├─ http/               # Camada de entrada HTTP do gateway
│  │  └─ routers/         # Definição e organização das rotas expostas
│  └─ schema/             # Esquemas de validação e serialização de dados do Pydantic
│
└─ README.md              # Documentação específica da estrutura do módulo gateway
```

---

# Camadas da Aplicação

## Interface

Responsável pela comunicação com o mundo externo.

Exemplos:

- rotas HTTP
- parsing de requisições
- formatação de respostas
- integração com frameworks (FastAPI)

Essa camada não deve conter lógica de negócio.

---

## Application

Contém os **casos de uso** da aplicação.

Responsável por:

- orquestrar fluxo de execução
- coordenar serviços de domínio
- integrar componentes do sistema

---

## Domain

Contém as **regras centrais do sistema**.

Exemplos:

- avaliação de políticas
- controle de rate limiting
- resolução de rotas
- identificação de tenants

Essa camada deve permanecer independente de frameworks e infraestrutura.

---

## Infrastructure

Implementações concretas de integração externa.

Exemplos:

- acesso a banco de dados
- integração com Redis
- mecanismos de cache
- encaminhamento HTTP para serviços upstream

Infraestrutura depende do domínio, mas o domínio não depende da infraestrutura.