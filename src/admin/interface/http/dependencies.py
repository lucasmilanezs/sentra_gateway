from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.application.use_cases.manage_sub_user import ManageSubUser
from src.admin.application.use_cases.query_audit import QueryAudit
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
    wiring: AdminWiring = get_wiring(request)

    if not wiring.use_postgres:
        yield wiring
        return

    async with wiring._session_factory() as session:
        async with session.begin():
            yield wiring.build_use_cases_postgres(session)


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


def require_permission(permission: str):
    """
    Dependency factory — guard RBAC centralizado.

    Uso nos endpoints:
        _: Annotated[JwtClaims, Depends(require_permission("routes"))]

    Comportamento:
      - superuser e admin: sempre passam (acesso total implícito)
      - member: passa só se 'permission' estiver em claims.permissions
      - qualquer outro role ou token inválido: 403

    Retorna as claims validadas para que o endpoint possa usá-las
    se necessário (ex: para filtrar por tenant_id).
    """
    async def _guard(
        claims: Annotated[JwtClaims, Depends(get_current_claims)],
    ) -> JwtClaims:
        if not claims.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"permissão '{permission}' necessária",
            )
        return claims

    return _guard


def require_admin():
    """
    Guard para endpoints que exigem role admin ou superuser.
    Members não têm acesso, independente de permissões.
    """
    async def _guard(
        claims: Annotated[JwtClaims, Depends(get_current_claims)],
    ) -> JwtClaims:
        if claims.role not in ("superuser", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="acesso restrito a administradores",
            )
        return claims

    return _guard


def require_superuser():
    """Guard para endpoints exclusivos do superuser (ex: gestão de tenants)."""
    async def _guard(
        claims: Annotated[JwtClaims, Depends(get_current_claims)],
    ) -> JwtClaims:
        if claims.role != "superuser":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="acesso restrito ao superuser",
            )
        return claims

    return _guard


# ── Getters de use cases (sem alteração de lógica) ───────────────────────

def get_manage_tenant(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> object:
    return w.manage_tenant


def get_manage_tenant_domain(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> object:
    return w.manage_tenant_domain


def get_manage_route(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> object:
    return w.manage_route


def get_manage_policy(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> object:
    return w.manage_policy


def get_authenticate_user(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> object:
    return w.authenticate_user


def get_register_admin_with_tenant(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> object:
    return w.register_admin_with_tenant



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


def get_query_audit(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> QueryAudit:
    if w.query_audit is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="auditoria requer modo Postgres",
        )
    return w.query_audit


def get_manage_sub_user(
    w: Annotated[AdminWiring, Depends(get_request_wiring)],
) -> ManageSubUser:
    return w.manage_sub_user