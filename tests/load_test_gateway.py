"""
Teste de carga simples contra o gateway (requer stack Docker rodando).

Uso:
  python tests/load_test_gateway.py --url http://localhost:8000/v1/ping --host api.acme.local --n 100
"""
from __future__ import annotations

import argparse
import asyncio
import time

import httpx


async def run(url: str, host: str, n: int, concurrency: int) -> None:
    sem = asyncio.Semaphore(concurrency)
    results: list[int] = []

    async def one(client: httpx.AsyncClient) -> None:
        async with sem:
            try:
                r = await client.get(url, headers={"Host": host})
                results.append(r.status_code)
            except Exception:
                results.append(0)

    async with httpx.AsyncClient(timeout=10.0) as client:
        start = time.perf_counter()
        await asyncio.gather(*[one(client) for _ in range(n)])
        elapsed = time.perf_counter() - start

    from collections import Counter

    c = Counter(results)
    print(f"Requests: {n} | Concurrency: {concurrency} | Time: {elapsed:.2f}s")
    print(f"RPS: {n/elapsed:.1f}")
    print("Status codes:", dict(sorted(c.items())))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000/v1/ping")
    p.add_argument("--host", default="api.acme.local")
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--concurrency", type=int, default=10)
    args = p.parse_args()
    asyncio.run(run(args.url, args.host, args.n, args.concurrency))


if __name__ == "__main__":
    main()
