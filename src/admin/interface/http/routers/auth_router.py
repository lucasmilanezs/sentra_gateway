from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.admin.application.use_cases.authenticate_user import (
    AuthenticateUser,
    ChangePassword,
    RegisterUser,
    RequestPasswordReset,
    ResetPasswordWithCode,
)
from src.admin.domain.exceptions import AuthError
from src.admin.domain.value_objects.jwt_claims import JwtClaims
from src.admin.interface.http.dependencies import (
    get_authenticate_user,
    get_change_password,
    get_current_claims,
    get_register_user,
    get_request_password_reset,
    get_reset_password,
    get_wiring,
)
from src.admin.interface.http.wiring import AdminWiring
from src.admin.interface.schema.auth_schema import (
    ChangePasswordBody,
    ForgotPasswordBody,
    LoginBody,
    RegisterBody,
    RegisterResponse,
    ResetPasswordBody,
    TokenResponse,
    UserPublic,
)

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterBody,
    reg: Annotated[RegisterUser, Depends(get_register_user)],
    wiring: Annotated[AdminWiring, Depends(get_wiring)],
):
    user = await reg.execute(body.email, body.password, body.tenant_id)
    access = wiring.token_service.create_access_token(user.id, user.email, user.tenant_id)
    return RegisterResponse(
        user=UserPublic(id=user.id, email=user.email, tenant_id=user.tenant_id),
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
    wiring: Annotated[AdminWiring, Depends(get_wiring)],
):
    user = await wiring.user_repository.get_by_id(claims.sub)
    if not user:
        raise AuthError("usuário não encontrado")
    return UserPublic(id=user.id, email=user.email, tenant_id=user.tenant_id)


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
