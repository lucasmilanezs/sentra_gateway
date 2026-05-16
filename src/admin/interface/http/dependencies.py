from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import HTTPException, status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.domain.exceptions import AuthError
from src.admin.domain.value_objects.jwt_claims import JwtClaims
from src.admin.interface.http.wiring import AdminWiring

_bearer = HTTPBearer(auto_error=False)


def get_wiring(request: Request) -> AdminWiring:
    w = getattr(request.app.state, "admin", None)
    if not w:
        raise HTTPException(status_code=500, detail="admin não inicializado")
    return w


async def get_request_wiring(
    request: Request,
) -> AsyncGenerator[AdminWiring, None]:
    """
    Dependency principal que resolve o wiring correto por request.

    - Modo JSON: retorna o wiring global diretamente (sem sessão).
    - Modo Postgres: abre uma AsyncSession, constrói wiring com repositórios
      transacionais, faz commit/rollback ao fim do request e fecha a sessão.
    """
    wiring: AdminWiring = get_wiring(request)

    if not wiring.use_postgres:
        yield wiring
        return

    async with wiring._session_factory() as session:
        async with session.begin():
            yield wiring.build_use_cases_postgres(session)


def get_manage_tenant(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> object:
    return w.manage_tenant


def get_manage_route(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> object:
    return w.manage_route


def get_authenticate_user(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> object:
    return w.authenticate_user


def get_register_user(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> object:
    return w.register_user


def get_change_password(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> object:
    return w.change_password


def get_request_password_reset(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> object:
    return w.request_password_reset


def get_reset_password(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> object:
    return w.reset_password_with_code

def get_manage_policy(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> object:
    return w.manage_policy

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
    try:
        return wiring.token_service.decode_and_validate(cred.credentials)
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

def require_superuser(
    claims: Annotated[JwtClaims, Depends(get_current_claims)],
) -> JwtClaims:
    if claims.role != "superuser":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="acesso restrito ao superuser",
        )
    return claims


def require_own_tenant(claims: JwtClaims, tenant_id: str) -> None:
    """Superuser passa sempre. Admin só acessa o próprio tenant."""
    if claims.role == "superuser":
        return
    if claims.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="acesso negado a recurso de outro tenant",
        )


def get_manage_global_policy(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> object:
    return w.manage_global_policy