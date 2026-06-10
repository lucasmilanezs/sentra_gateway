from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.admin.application.use_cases.authenticate_user import (
    AuthenticateUser,
    ChangePassword,
    RequestPasswordReset,
    ResetPasswordWithCode,
)
from src.admin.domain.exceptions import AuthError
from src.admin.domain.value_objects.jwt_claims import JwtClaims
from src.admin.interface.http.dependencies import (
    get_authenticate_user,
    get_change_password,
    get_current_claims,
    get_request_password_reset,
    get_reset_password,
    get_request_wiring,
)
from src.admin.interface.http.wiring import AdminWiring
from src.admin.interface.schema.auth_schema import (
    ChangePasswordBody,
    ForgotPasswordBody,
    LoginBody,
    RegisterBody,
    RegisterResponse,
    ResetPasswordBody,
    TenantPublic,
    TokenResponse,
    UserPublic,
)

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterBody,
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
):
    """
    Onboarding atômico: cria tenant + admin numa única transação.
    O use case é acessado diretamente do wiring para garantir que
    tenant e admin compartilhem exatamente a mesma sessão de banco.
    """
    if not body.accepted_terms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="É necessário aceitar os termos de uso para criar a conta.",
        )

    user, tenant = await w.register_admin_with_tenant.execute(
        email=body.email,
        password=body.password,
        company_name=body.company_name,
        company_alias=body.company_alias,
    )
    access = w.token_service.create_access_token(
        user.id, user.email, user.tenant_id, user.role,
        permissions=user.permissions or None,
    )
    return RegisterResponse(
        user=UserPublic(
            id=user.id, email=user.email, tenant_id=user.tenant_id,
            role=user.role, permissions=user.permissions,
            tenant=TenantPublic(id=tenant.id, name=tenant.name, alias=tenant.alias),
        ),
        tenant=TenantPublic(id=tenant.id, name=tenant.name, alias=tenant.alias),
        access_token=access,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginBody,
    auth: Annotated[AuthenticateUser, Depends(get_authenticate_user)],
):
    access, _user = await auth.login(body.email, body.password)
    return TokenResponse(access_token=access)


@router.get("/me", response_model=UserPublic)
async def me(
    claims: Annotated[JwtClaims, Depends(get_current_claims)],
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
):
    user = await w.user_repository.get_by_id(claims.sub)
    if not user:
        raise AuthError("usuário não encontrado")

    tenant = None
    if user.tenant_id:
        tenant_entity = await w.tenant_repository.get_by_id(user.tenant_id)
        if tenant_entity:
            tenant = TenantPublic(
                id=tenant_entity.id,
                name=tenant_entity.name,
                alias=tenant_entity.alias,
            )

    return UserPublic(
        id=user.id, email=user.email, tenant_id=user.tenant_id,
        role=user.role, permissions=user.permissions,
        tenant=tenant,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordBody,
    claims: Annotated[JwtClaims, Depends(get_current_claims)],
    uc: Annotated[ChangePassword, Depends(get_change_password)],
):
    await uc.execute(claims.sub, body.current_password, body.new_password)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    body: ForgotPasswordBody,
    uc: Annotated[RequestPasswordReset, Depends(get_request_password_reset)],
):
    await uc.execute(body.email)
    return {"detail": "se o e-mail existir, você receberá um código em breve"}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    body: ResetPasswordBody,
    uc: Annotated[ResetPasswordWithCode, Depends(get_reset_password)],
):
    await uc.execute(body.email, body.code, body.new_password)