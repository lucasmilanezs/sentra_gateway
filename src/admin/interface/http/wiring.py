from src.admin.infrastructure.config.settings import AdminSettings
from src.admin.infrastructure.security.bcrypt_password_hasher import BcryptPasswordHasher
from src.admin.infrastructure.security.jwt_token_service import JwtTokenService
from src.admin.infrastructure.email.console_email_sender import ConsoleEmailSender
from src.admin.infrastructure.email.smtp_email_sender import SmtpEmailSender
from src.admin.infrastructure.persistence.json.json_document_store import JsonDocumentStore
from src.admin.infrastructure.persistence.json.json_user_repository import JsonUserRepository
from src.admin.infrastructure.persistence.json.json_tenant_repository import JsonTenantRepository
from src.admin.infrastructure.persistence.json.json_admin_route_repository import JsonAdminRouteRepository
from src.admin.infrastructure.persistence.json.json_password_reset_repository import JsonPasswordResetRepository
from src.admin.application.use_cases.manage_tenant import ManageTenant
from src.admin.application.use_cases.manage_admin_route import ManageAdminRoute
from src.admin.application.use_cases.authenticate_user import (
    AuthenticateUser, RegisterUser, ChangePassword, RequestPasswordReset, ResetPasswordWithCode
)

class AdminWiring:
    def __init__(self, settings: AdminSettings):
        self.settings = settings
        
        # 1. Infraestrutura Base
        self.hasher = BcryptPasswordHasher()
        self.token_service = JwtTokenService(
            secret=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
            expire_minutes=settings.jwt_expire_minutes
        )

        # 2. Escolha do Persistence (Por enquanto só JSON conforme sua necessidade)
        # No futuro, aqui você coloca o 'if settings.use_postgres'
        self.store = JsonDocumentStore(settings.json_data_path)
        self.user_repository = JsonUserRepository(self.store)
        self.tenant_repository = JsonTenantRepository(self.store)
        self.route_repository = JsonAdminRouteRepository(self.store)
        self.reset_repository = JsonPasswordResetRepository(self.store)

        # 3. Email
        if settings.email_use_console or not settings.smtp_host:
            self.email_sender = ConsoleEmailSender()
        else:
            self.email_sender = SmtpEmailSender(
                host=settings.smtp_host, port=settings.smtp_port,
                user=settings.smtp_user, password=settings.smtp_password,
                mail_from=settings.smtp_from or "noreply@sentra.local"
            )

        # 4. Use Cases (Injeção de Dependência interna)
        self.manage_tenant = ManageTenant(self.tenant_repository, self.route_repository)
        self.manage_route = ManageAdminRoute(self.route_repository, self.tenant_repository)
        self.authenticate_user = AuthenticateUser(self.user_repository, self.hasher, self.token_service)
        self.register_user = RegisterUser(self.user_repository, self.hasher, self.tenant_repository)
        self.change_password = ChangePassword(self.user_repository, self.hasher)
        self.request_password_reset = RequestPasswordReset(self.user_repository, self.reset_repository, self.email_sender)
        self.reset_password_with_code = ResetPasswordWithCode(self.user_repository, self.reset_repository, self.hasher)

        # Flag para o seu Health Check não quebrar
        self.postgres_connected = False