# Migrations

O schema do banco de dados é versionado com **Alembic**.

As migrations representam a fonte oficial de evolução estrutural do PostgreSQL usado pelo Admin Plane e pelo Gateway Plane.

---

# Responsabilidades

As migrations controlam:

- tabelas administrativas;
- usuários e tenants;
- domínios e rotas;
- policies;
- auditoria;
- campos de validação JWT;
- material criptografado de policies;
- atributos visuais como `display_color`.

---

# Aplicar migrations

```bash
alembic upgrade head
```

---

# Criar nova migration

```bash
alembic revision --autogenerate -m "description"
```

Revise sempre o arquivo gerado antes de aplicar.

---

# Reverter última migration

```bash
alembic downgrade -1
```

Use apenas em ambiente controlado.

---

# Regras do projeto

- Não editar migrations já aplicadas em ambientes compartilhados.
- Toda alteração estrutural deve gerar uma nova migration.
- O banco deve ser reproduzível a partir da sequência completa de migrations.
- O `revision` e o `down_revision` devem usar os IDs internos do Alembic, não o nome semântico do arquivo.

---

# Fonte de verdade

O PostgreSQL é a fonte de verdade para configuração e auditoria formal.

O Gateway consome essas configurações através de snapshot operacional, mas a persistência primária permanece no banco relacional.
