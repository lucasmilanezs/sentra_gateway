from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The unit suite is intentionally isolated from concrete infrastructure.
# Optional production dependencies are stubbed only when they are not installed.
if "jose" not in sys.modules:
    jose = types.ModuleType("jose")
    class JWTError(Exception):
        pass
    class _Jwt:
        @staticmethod
        def get_unverified_header(token):
            if token == "bad":
                raise JWTError("invalid header")
            return {"alg":"HS256"}
        @staticmethod
        def get_unverified_claims(token):
            if token == "bad":
                raise JWTError("invalid token")
            return {"exp": 9999999999, "iss": "issuer", "aud": "audience"}
        @staticmethod
        def decode(token, key, algorithms=None, audience=None, issuer=None, options=None):
            if token == "bad":
                raise JWTError("invalid signature")
            return {"sub": "user"}
    jose.JWTError = JWTError
    jose.jwt = _Jwt
    sys.modules["jose"] = jose

if "sqlalchemy" not in sys.modules:
    sqlalchemy = types.ModuleType("sqlalchemy")
    sqlalchemy.text = lambda sql: sql
    class _Stmt:
        def __init__(self, *a, **k): pass
        def where(self, *a, **k): return self
        def order_by(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def offset(self, *a, **k): return self
        def values(self, *a, **k): return self
    sqlalchemy.select = lambda *a, **k: _Stmt()
    sqlalchemy.delete = lambda *a, **k: _Stmt()
    sqlalchemy.update = lambda *a, **k: _Stmt()
    ext = types.ModuleType("sqlalchemy.ext")
    asyncio_mod = types.ModuleType("sqlalchemy.ext.asyncio")
    class AsyncSession: pass
    class _Engine:
        async def dispose(self): pass
    def create_async_engine(*a, **k): return _Engine()
    def async_sessionmaker(*a, **k):
        class _Maker:
            def __call__(self): return None
        return _Maker()
    asyncio_mod.AsyncSession = AsyncSession
    asyncio_mod.create_async_engine = create_async_engine
    asyncio_mod.async_sessionmaker = async_sessionmaker
    sys.modules["sqlalchemy"] = sqlalchemy
    sys.modules["sqlalchemy.ext"] = ext
    sys.modules["sqlalchemy.ext.asyncio"] = asyncio_mod


class AsyncRepo:
    def __init__(self, **items):
        self.items = dict(items)
        self.saved = []
        self.deleted = []
        self.recorded = []
    async def get_by_id(self, id): return self.items.get(id)
    async def get_by_email(self, email):
        return next((v for v in self.items.values() if getattr(v, "email", None) == email), None)
    async def get_by_alias(self, alias):
        return next((v for v in self.items.values() if getattr(v, "alias", None) == alias), None)
    async def save(self, obj):
        self.items[getattr(obj, "id", len(self.items))] = obj
        self.saved.append(obj)
    async def delete(self, id):
        self.deleted.append(id)
        return self.items.pop(id, None) is not None
    async def list_all(self, tenant_id=None):
        rows=list(self.items.values())
        if tenant_id is not None:
            rows=[r for r in rows if getattr(r, "tenant_id", None)==tenant_id or getattr(r, "id", None)==tenant_id]
        return rows
    async def list_members_by_tenant(self, tenant_id):
        return [u for u in self.items.values() if getattr(u, "role", None)=="member" and getattr(u, "tenant_id", None)==tenant_id]
    async def record(self, event): self.recorded.append(event)
    async def anonymize_user_references(self, user_id: str):
        self.anonymized = getattr(self, "anonymized", [])
        self.anonymized.append(user_id)

class Hasher:
    def hash(self, password: str) -> str: return "hash:" + password
    def verify(self, password: str, hashed: str) -> bool: return hashed == "hash:" + password

class Tokens:
    def create_access_token(self, sub, email, tenant_id, role, permissions=None):
        return f"token:{sub}:{role}:{tenant_id}:{','.join(permissions or [])}"
    def decode_and_validate(self, token):
        from src.admin.domain.exceptions import AuthError
        from src.admin.domain.value_objects.jwt_claims import JwtClaims
        if token == "bad":
            raise AuthError("token inválido")
        return JwtClaims(sub="u1", email="a@b.com", tenant_id="t1", role="admin")

def now():
    return datetime(2026, 1, 1, tzinfo=timezone.utc)

if "redis" not in sys.modules:
    redis = types.ModuleType("redis")
    redis_asyncio = types.ModuleType("redis.asyncio")
    class _RedisClient:
        async def ping(self): return True
        async def publish(self, *a, **k): return 1
        async def aclose(self): pass
    redis_asyncio.from_url = lambda *a, **k: _RedisClient()
    redis.asyncio = redis_asyncio
    sys.modules["redis"] = redis
    sys.modules["redis.asyncio"] = redis_asyncio
