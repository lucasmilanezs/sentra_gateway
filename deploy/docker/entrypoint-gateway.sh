#!/bin/sh
set -e

echo "[entrypoint] Aguardando Postgres..."
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

echo "[entrypoint] Aguardando Redis..."
python -c "
import time, socket, sys, os
host = os.environ.get('REDIS_HOST', 'redis')
port = int(os.environ.get('REDIS_PORT', '6379'))
for i in range(30):
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        print(f'[entrypoint] Redis acessível em {host}:{port}')
        sys.exit(0)
    except OSError:
        print(f'[entrypoint] Tentativa {i+1}/30 - aguardando {host}:{port}...')
        time.sleep(1)
print('[entrypoint] ERRO: Redis não respondeu em 30s')
sys.exit(1)
"


echo "[entrypoint] Iniciando Gateway na porta 8000..."
exec uvicorn src.gateway.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info