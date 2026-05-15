import time
import httpx

URL = "http://localhost:8000/test/postman/get"
LIMIT = 5  # igual ao configurado na política

print("=== Fase 1: disparando 5 requests (deve passar tudo) ===")
for i in range(LIMIT):
    r = httpx.get(URL)
    print(f"  req {i+1}: {r.status_code}")

print(f"\nAguardando 55 segundos (quase uma janela completa)...")
time.sleep(55)

print("\n=== Fase 2: disparando 5 requests logo após (sliding window bloqueia, fixed não) ===")
for i in range(LIMIT):
    r = httpx.get(URL)
    print(f"  req {i+1}: {r.status_code}")