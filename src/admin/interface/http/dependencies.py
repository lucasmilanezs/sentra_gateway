from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.admin.domain.exceptions import AuthError
from src.admin.domain.value_objects.jwt_claims import JwtClaims
from src.admin.interface.http.wiring import AdminWiring

_bearer = HTTPBearer(auto_error=False)


def get_wiring(request: Request) -> AdminWiring:
    w = getattr(request.app.state, "admin", None)
    if not w:
        raise HTTPException(status_code=500, detail="admin não inicializado")
    return w


def get_manage_tenant(request: Request) -> object:
    return get_wiring(request).manage_tenant


def get_manage_route(request: Request) -> object:
    return get_wiring(request).manage_route


def get_authenticate_user(request: Request) -> object:
    return get_wiring(request).authenticate_user


def get_register_user(request: Request) -> object:
    return get_wiring(request).register_user


def get_change_password(request: Request) -> object:
    return get_wiring(request).change_password


def get_request_password_reset(request: Request) -> object:
    return get_wiring(request).request_password_reset


def get_reset_password(request: Request) -> object:
    return get_wiring(request).reset_password_with_code


async def get_current_claims(
    request: Request,
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> JwtClaims:
    if not cred or cred.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="credenciais ausentes",
            headers={"WWW-Authenticate": "Bearer"},
        )
    wiring = get_wiring(request)
    token_svc = wiring.token_service
    try:
        return token_svc.decode_and_validate(cred.credentials)
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
