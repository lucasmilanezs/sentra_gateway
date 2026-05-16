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
    policy_router,
)
from src.admin.interface.http.wiring import AdminWiring # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = AdminSettings()
    wiring = AdminWiring(settings)
    app.state.admin = wiring

    mode = "Postgres" if settings.use_postgres else "JSON Local"
    logger.info(f"Admin iniciado. Persistência: {mode}")
    if settings.use_postgres:
        logger.info(f"  DB host: {settings.postgres_host}:{settings.postgres_port}")
    if settings.use_postgres:
        await _bootstrap_superuser(wiring, settings)

    yield

    await wiring.dispose()

async def _bootstrap_superuser(wiring, settings: AdminSettings) -> None:
    """Garante que o superuser de plataforma existe no banco. Idempotente."""
    from src.admin.domain.entities.user import User
    import uuid
    from datetime import datetime, timezone

    async with wiring._session_factory() as session:
        async with session.begin():
            w = wiring.build_use_cases_postgres(session)
            existing = await w.user_repository.get_by_email(settings.superuser_email)
            if existing:
                return
            now = datetime.now(timezone.utc)
            superuser = User(
                id=str(uuid.uuid4()),
                email=settings.superuser_email,
                password_hash=wiring.hasher.hash(settings.superuser_password),
                tenant_id=None,
                created_at=now,
                updated_at=now,
                role="superuser",
            )
            await w.user_repository.save(superuser)
            logger.info("Superuser criado: %s", settings.superuser_email)

app = FastAPI(title="Sentra Admin", lifespan=lifespan)

register_domain_exception_handlers(app)

app.include_router(health_router.router, tags=["Health"])
app.include_router(auth_router.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(tenant_router.router, prefix="/api/v1/tenants", tags=["Tenants"])
app.include_router(admin_route_router.router, prefix="/api/v1/routes", tags=["Routes"])
app.include_router(policy_router.router, prefix="/api/v1/routes", tags=["Policies"])
# StaticFiles por último
app.mount("/", StaticFiles(directory="src/admin/interface/web/static", html=True), name="frontend")
