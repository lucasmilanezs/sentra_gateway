from dataclasses import dataclass

from src.admin.application.use_cases.authenticate_user import (
    AuthenticateUser,
    ChangePassword,
    RegisterUser,
    RequestPasswordReset,
    ResetPasswordWithCode,
)
from src.admin.application.use_cases.manage_admin_route import ManageAdminRoute
from src.admin.application.use_cases.manage_tenant import ManageTenant
from src.admin.domain.ports.user_repository import UserRepositoryPort
from src.admin.domain.services.token_service import TokenServicePort
from src.admin.infrastructure.config.settings import AdminSettings


@dataclass
class AdminWiring:
    settings: AdminSettings
    postgres_connected: bool
    user_repository: UserRepositoryPort
    manage_tenant: ManageTenant
    manage_route: ManageAdminRoute
    authenticate_user: AuthenticateUser
    register_user: RegisterUser
    change_password: ChangePassword
    request_password_reset: RequestPasswordReset
    reset_password_with_code: ResetPasswordWithCode
    token_service: TokenServicePort
