import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.admin.application.use_cases.authenticate_user import (
    AuthenticateUser,
    ChangePassword,
    RegisterUser,
    RequestPasswordReset,
    ResetPasswordWithCode,
)
from src.admin.application.use_cases.manage_admin_route import ManageAdminRoute
from src.admin.application.use_cases.manage_tenant import ManageTenant
from src.admin.infrastructure.config.settings import AdminSettings
from src.admin.infrastructure.email.console_email_sender import ConsoleEmailSender
from src.admin.infrastructure.email.smtp_email_sender import SmtpEmailSender
from src.admin.infrastructure.persistence.json.json_admin_route_repository import JsonAdminRouteRepository
from src.admin.infrastructure.persistence.json.json_document_store import JsonDocumentStore
from src.admin.infrastructure.persistence.json.json_password_reset_repository import JsonPasswordResetRepository
from src.admin.infrastructure.persistence.json.json_tenant_repository import JsonTenantRepository
from src.admin.infrastructure.persistence.json.json_user_repository import JsonUserRepository
from src.admin.infrastructure.persistence.postgres.database import (
    check_connection,
    create_postgres_engine,
    create_session_factory,
)
from src.admin.infrastructure.security.bcrypt_password_hasher import BcryptPasswordHasher
from src.admin.infrastructure.security.jwt_token_service import JwtTokenService
from src.admin.interface.http.exception_handlers import register_domain_exception_handlers
from src.admin.interface.http.routers.admin_route_router import router as routes_router
from src.admin.interface.http.routers.auth_router import router as auth_router
from src.admin.interface.http.routers.health_router import router as health_router
from src.admin.interface.http.routers.tenant_router import router as tenant_router
from src.admin.interface.http.wiring import AdminWiring

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = AdminSettings()
    store = JsonDocumentStore(settings.json_data_path)
    tenant_repo = JsonTenantRepository(store)
    route_repo = JsonAdminRouteRepository(store)
    user_repo = JsonUserRepository(store)
    reset_repo = JsonPasswordResetRepository(store)

    hasher = BcryptPasswordHasher()
    token_service = JwtTokenService(
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.jwt_expire_minutes,
    )

    if settings.email_use_console or not settings.smtp_host:
        email_sender = ConsoleEmailSender()
    else:
        email_sender = SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            user=settings.smtp_user,
            password=settings.smtp_password,
            mail_from=settings.smtp_from or settings.smtp_user or "noreply@sentra.local",
        )

    engine = create_postgres_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    postgres_ok = check_connection(engine)
    if postgres_ok:
        logger.info("Postgres acessível; ORM pronto para migrações futuras.")
    else:
        logger.info("Postgres não acessível; usando apenas armazenamento JSON local.")

    manage_tenant = ManageTenant(tenant_repo, route_repo)
    manage_route = ManageAdminRoute(route_repo, tenant_repo)
    authenticate_user = AuthenticateUser(user_repo, hasher, token_service)
    register_user = RegisterUser(user_repo, hasher, tenant_repo)
    change_password = ChangePassword(user_repo, hasher)
    request_password_reset = RequestPasswordReset(user_repo, reset_repo, email_sender)
    reset_password = ResetPasswordWithCode(user_repo, reset_repo, hasher)

    app.state.admin = AdminWiring(
        settings=settings,
        postgres_connected=postgres_ok,
        user_repository=user_repo,
        manage_tenant=manage_tenant,
        manage_route=manage_route,
        authenticate_user=authenticate_user,
        register_user=register_user,
        change_password=change_password,
        request_password_reset=request_password_reset,
        reset_password_with_code=reset_password,
        token_service=token_service,
    )
    app.state.postgres_engine = engine
    app.state.postgres_session_factory = session_factory

    yield

    engine.dispose()


app = FastAPI(title="Sentra Admin", lifespan=lifespan)
register_domain_exception_handlers(app)

app.include_router(health_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(tenant_router, prefix="/api/v1")
app.include_router(routes_router, prefix="/api/v1")
