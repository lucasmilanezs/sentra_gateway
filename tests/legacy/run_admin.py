"""
Script de conveniência para rodar o Admin FORA do Docker.

Em produção, o admin roda via Docker (entrypoint-admin.sh).
Este script existe para dev local em modo JSON (sem Postgres).

Se precisar testar com Postgres no Windows, use:
    cd deploy/docker && docker compose up --build
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.admin.main:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
    )