from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict:
    admin = getattr(request.app.state, "admin", None)
    return {
        "status": "ok",
        "postgres_connected": getattr(admin, "postgres_connected", False) if admin else False,
    }
