import redis.asyncio as aioredis
from fastapi import APIRouter, Request
from sqlalchemy import text

router = APIRouter(tags=["health"])

@router.get("/health")
async def health(request: Request) -> dict:
    admin = getattr(request.app.state, "admin", None)
    checks = {}
    if admin and hasattr(admin, "_session_factory") and admin._session_factory:
        try:
            async with admin._session_factory() as s:
                await s.execute(text("SELECT 1"))
            checks["postgres"] = {"status": "ok"}
        except Exception as e:
            checks["postgres"] = {"status": "error", "detail": str(e)}
    else:
        checks["postgres"] = {"status": "not_configured"}
    if admin and hasattr(admin, "_redis_client"):
        try:
            await admin._redis_client.ping()
            checks["redis"] = {"status": "ok"}
        except Exception as e:
            checks["redis"] = {"status": "error", "detail": str(e)}
    else:
        checks["redis"] = {"status": "not_configured"}
    overall = "ok" if all(v.get("status") == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "postgres_connected": checks.get("postgres", {}).get("status") == "ok", "checks": checks}
