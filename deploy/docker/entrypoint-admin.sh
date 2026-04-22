#!/bin/sh
set -e

echo "[entrypoint] Aguardando Postgres..."
# Loop simples — pg_isready não precisa de client instalado,
# mas o psycopg2 no Python sim. Usamos Python direto.
python -c "
import time, socket, sys, os
host = os.environ.get('POSTGRES_HOST', 'postgres')
port = int(os.environ.get('POSTGRES_PORT', '5432'))
for i in range(30):
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        print(f'[entrypoint] Postgres acessível em {host}:{port}')
        sys.exit(0)
    except OSError:
        print(f'[entrypoint] Tentativa {i+1}/30 - aguardando {host}:{port}...')
        time.sleep(1)
print('[entrypoint] ERRO: Postgres não respondeu em 30s')
sys.exit(1)
"

echo "[entrypoint] Rodando migrations..."
alembic upgrade head

echo "[entrypoint] Iniciando Admin na porta 8001..."
exec uvicorn src.admin.main:app \
    --host 0.0.0.0 \
    --port 8001 \
    --log-level info