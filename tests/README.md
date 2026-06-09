# Testes

A suíte oficial de testes automatizados fica em:

```text
tests/unit/
```

---

# Objetivos

Os testes cobrem:

- regras de domínio;
- casos de uso;
- validações de policy;
- processamento do gateway;
- controle de acesso administrativo;
- parsing e roteamento HTTP;
- builders de auditoria e logs.

---

# Execução

Na raiz do projeto:

```bash
pytest -q
```

Também é recomendado validar sintaxe antes de entrega:

```bash
python -m compileall -q src
```

---

# Postman

A pasta `tests/postman/` contém coleções auxiliares para validações manuais e demonstrações de integração.

Essas coleções não substituem a suíte unitária, mas ajudam a validar fluxos reais do Admin e Gateway durante a apresentação.

---

# Observação

Testes legados, artefatos de execução e arquivos temporários não devem ser mantidos como parte da suíte oficial.
