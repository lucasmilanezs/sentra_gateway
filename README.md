# Sentra Gateway

O **Sentra Gateway** é uma plataforma de gateway de segurança para APIs web projetada para centralizar a aplicação de políticas de segurança, controle de acesso, limitação de requisições e auditoria de eventos.  
A solução busca reduzir a fragmentação de mecanismos de segurança em arquiteturas distribuídas, concentrando esses controles em um ponto único de entrada para serviços backend.

A arquitetura do projeto separa responsabilidades entre domínio de gateway, gerenciamento administrativo e componentes compartilhados, seguindo princípios de baixo acoplamento e organização modular.

---

## Estrutura do Projeto

```
/sentra
├─ academic/                    # Materiais acadêmicos relacionados ao projeto (TCC, relatórios, etc.)
│
├─ deploy/
│ └─ docker/                    # Arquivos e configurações para execução do sistema via Docker
│ └─ README.md
│
├─ docs/
│ └─ architecture/              # Documentação de arquitetura e decisões de design
│
├─ migrations/                  # Scripts de migração e versionamento de banco de dados
│
├─ src/
│ ├─ admin/                     # Módulo administrativo responsável pela gestão do sistema
│ ├─ gateway/                   # Núcleo do gateway responsável pelo processamento das requisições
│ ├─ shared/                    # Componentes reutilizáveis compartilhados entre os módulos
│ └─ README.md
│
└─ README.md 
```

---

## Objetivo do Projeto

O objetivo da plataforma é demonstrar a viabilidade técnica de um gateway de segurança para APIs que permita:

- centralização de políticas de segurança  
- aplicação uniforme de autenticação e autorização  
- limitação de requisições e mitigação de abuso de recursos  
- rastreabilidade e auditoria de eventos  

A solução foi projetada com foco em **clareza arquitetural, simplicidade operacional e aplicabilidade em ambientes de pequeno a médio porte**.

---