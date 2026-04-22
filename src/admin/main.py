import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from fastapi.staticfiles import StaticFiles


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_env() -> None:
    """Carrega .env da raiz do projeto se existir — útil em dev local sem Docker."""
    try:
        from dotenv import load_dotenv

        env_path = Path(__file__).resolve().parents[2] / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)
    except ImportError:
        pass


_load_env()

# Imports após carregar .env para que os settings leiam as variáveis corretas
from src.admin.infrastructure.config.settings import AdminSettings  # noqa: E402
from src.admin.interface.http.exception_handlers import register_domain_exception_handlers  # noqa: E402
from src.admin.interface.http.routers import (  # noqa: E402
    admin_route_router,
    auth_router,
    health_router,
    tenant_router,
)
from src.admin.interface.http.wiring import AdminWiring  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = AdminSettings()
    wiring = AdminWiring(settings)
    app.state.admin = wiring

    mode = "Postgres" if settings.use_postgres else "JSON Local"
    logger.info(f"Admin iniciado. Persistência: {mode}")
    if settings.use_postgres:
        logger.info(f"  DB host: {settings.postgres_host}:{settings.postgres_port}")

    yield

    await wiring.dispose()


app = FastAPI(title="Sentra Admin", lifespan=lifespan)

register_domain_exception_handlers(app)

app.include_router(health_router.router, tags=["Health"])
app.include_router(auth_router.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(tenant_router.router, prefix="/api/v1/tenants", tags=["Tenants"])
app.include_router(admin_route_router.router, prefix="/api/v1/routes", tags=["Routes"])
app.mount("/ui", StaticFiles(directory="src/admin/interface/web/static", html=True), name="ui")