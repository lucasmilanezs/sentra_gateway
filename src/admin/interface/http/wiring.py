import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.admin.application.use_cases.authenticate_user import (
    AuthenticateUser, ChangePassword, RegisterUser,
    RequestPasswordReset, ResetPasswordWithCode,
)
from src.admin.application.use_cases.manage_admin_route import ManageAdminRoute
from src.admin.application.use_cases.manage_policy import ManagePolicy
from src.admin.application.use_cases.manage_tenant import ManageTenant
from src.admin.infrastructure.config.settings import AdminSettings
from src.admin.infrastructure.email.console_email_sender import ConsoleEmailSender
from src.admin.infrastructure.email.smtp_email_sender import SmtpEmailSender
from src.admin.infrastructure.pubsub.redis_publisher import RedisPublisher

# JSON adapters
from src.admin.infrastructure.persistence.json.store import DocumentStore
from src.admin.infrastructure.persistence.json.route import RouteRepository as JsonRouteRepository
from src.admin.infrastructure.persistence.json.tenant import TenantRepository as JsonTenantRepository
from src.admin.infrastructure.persistence.json.user import UserRepository as JsonUserRepository
from src.admin.infrastructure.persistence.json.password_reset import PasswordResetRepository as JsonPasswordResetRepository
from src.admin.infrastructure.persistence.json.policy import PolicyRepository as JsonPolicyRepository

# Postgres adapters
from src.admin.infrastructure.persistence.postgres.route import RouteRepository as PgRouteRepository
from src.admin.infrastructure.persistence.postgres.tenant import TenantRepository as PgTenantRepository
from src.admin.infrastructure.persistence.postgres.user import UserRepository as PgUserRepository
from src.admin.infrastructure.persistence.postgres.policy import PolicyRepository as PgPolicyRepository
from src.admin.infrastructure.persistence.postgres.global_policy import GlobalPolicyRepository as PgGlobalPolicyRepository
from src.admin.application.use_cases.manage_global_policy import ManageGlobalPolicy

from src.admin.infrastructure.security.bcrypt_password_hasher import BcryptPasswordHasher
from src.admin.infrastructure.security.jwt_token_service import JwtTokenService


class AdminWiring:
    def __init__(self, settings: AdminSettings) -> None:
        self.settings = settings
        self.use_postgres = settings.use_postgres

        # Segurança
        self.hasher = BcryptPasswordHasher()
        self.token_service = JwtTokenService(
            secret=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
            expire_minutes=settings.jwt_expire_minutes,
        )

        # Email
        if settings.email_use_console or not settings.smtp_host:
            self.email_sender = ConsoleEmailSender()
        else:
            self.email_sender = SmtpEmailSender(
                host=settings.smtp_host,
                port=settings.smtp_port,
                user=settings.smtp_user,
                password=settings.smtp_password,
                mail_from=settings.smtp_from or "noreply@sentra.local",
            )

        # Redis — compartilhado entre publisher e (futuramente) password reset
        self._redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        self.publisher = RedisPublisher(client=self._redis_client)

        # Persistência
        if settings.use_postgres:
            self._engine = create_async_engine(
                settings.database_url,
                echo=False,
                pool_pre_ping=True,
            )
            self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            self.user_repository = None
            self.tenant_repository = None
            self.route_repository = None
            self.policy_repository = None
            self.reset_repository = None
            self.manage_tenant = None
            self.manage_route = None
            self.manage_policy = None
            self.authenticate_user = None
            self.register_user = None
            self.change_password = None
            self.request_password_reset = None
            self.reset_password_with_code = None
        else:
            self._engine = None
            self._session_factory = None
            store = DocumentStore(settings.json_data_path)
            self.user_repository = JsonUserRepository(store)
            self.tenant_repository = JsonTenantRepository(store)
            self.route_repository = JsonRouteRepository(store)
            self.policy_repository = JsonPolicyRepository(store)
            self.reset_repository = JsonPasswordResetRepository(store)
            self._build_use_cases_json()

        self.postgres_connected = settings.use_postgres

    def _build_use_cases_json(self) -> None:
        self.manage_tenant = ManageTenant(self.tenant_repository, self.route_repository)
        self.manage_route = ManageAdminRoute(
            self.route_repository, self.tenant_repository, publisher=self.publisher
        )
        self.manage_policy = ManagePolicy(
            self.policy_repository, self.route_repository, publisher=self.publisher
        )
        self.authenticate_user = AuthenticateUser(self.user_repository, self.hasher, self.token_service)
        self.register_user = RegisterUser(self.user_repository, self.hasher, self.tenant_repository)
        self.change_password = ChangePassword(self.user_repository, self.hasher)
        self.request_password_reset = RequestPasswordReset(
            self.user_repository, self.reset_repository, self.email_sender
        )
        self.reset_password_with_code = ResetPasswordWithCode(
            self.user_repository, self.reset_repository, self.hasher
        )
        self.manage_global_policy = ManageGlobalPolicy(
            None, self.tenant_repository, publisher=self.publisher  # JSON: sem persistência real
        )

    def build_use_cases_postgres(self, session: AsyncSession) -> "AdminWiring":
        w = object.__new__(AdminWiring)
        w.settings = self.settings
        w.use_postgres = True
        w.hasher = self.hasher
        w.token_service = self.token_service
        w.email_sender = self.email_sender
        w._engine = self._engine
        w._session_factory = self._session_factory
        w._redis_client = self._redis_client
        w.publisher = self.publisher
        w.postgres_connected = True

        w.user_repository = PgUserRepository(session)
        w.tenant_repository = PgTenantRepository(session)
        w.route_repository = PgRouteRepository(session)
        w.policy_repository = PgPolicyRepository(session)
        w.reset_repository = JsonPasswordResetRepository(
            DocumentStore(self.settings.json_data_path)
        )

        w.manage_tenant = ManageTenant(w.tenant_repository, w.route_repository)
        w.manage_route = ManageAdminRoute(
            w.route_repository, w.tenant_repository, publisher=w.publisher
        )
        w.manage_policy = ManagePolicy(
            w.policy_repository, w.route_repository, publisher=w.publisher
        )
        w.authenticate_user = AuthenticateUser(w.user_repository, w.hasher, w.token_service)
        w.register_user = RegisterUser(w.user_repository, w.hasher, w.tenant_repository)
        w.change_password = ChangePassword(w.user_repository, w.hasher)
        w.request_password_reset = RequestPasswordReset(
            w.user_repository, w.reset_repository, w.email_sender
        )
        w.reset_password_with_code = ResetPasswordWithCode(
            w.user_repository, w.reset_repository, w.hasher
        )
        w.manage_global_policy = ManageGlobalPolicy(
            PgGlobalPolicyRepository(session), w.tenant_repository, publisher=w.publisher
        )
        return w

    async def dispose(self) -> None:
        if self._engine:
            await self._engine.dispose()
        await self._redis_client.aclose()