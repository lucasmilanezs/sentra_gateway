from datetime import datetime, timezone
import redis.asyncio as aioredis
from fastapi import APIRouter, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

router = APIRouter(tags=["health"])

@router.get("/health")
async def health(request: Request) -> dict:
    checks = {}
    snapshot = getattr(request.app.state, "snapshot", None)
    if snapshot:
        age = round((datetime.now(timezone.utc) - snapshot.loaded_at).total_seconds(), 1) if snapshot.loaded_at else None
        checks["snapshot"] = {"status": "ok", "routes_loaded": snapshot.route_count(), "tenants_loaded": snapshot.tenant_count(), "policies_loaded": snapshot.policy_count(), "loaded_at": snapshot.loaded_at.isoformat() if snapshot.loaded_at else None, "age_seconds": age}
    else:
        checks["snapshot"] = {"status": "not_loaded"}
    settings = getattr(request.app.state, "settings", None)
    if settings:
        try:
            r = aioredis.from_url(settings.redis_url)
            await r.ping()
            await r.aclose()
            checks["redis"] = {"status": "ok"}
        except Exception as e:
            checks["redis"] = {"status": "error", "detail": str(e)}
        try:
            engine = create_async_engine(settings.database_url, echo=False)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            checks["postgres"] = {"status": "ok"}
        except Exception as e:
            checks["postgres"] = {"status": "error", "detail": str(e)}
    overall = "ok" if all(v.get("status") == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
