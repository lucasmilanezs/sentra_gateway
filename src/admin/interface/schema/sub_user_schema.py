from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from src.admin.domain.value_objects.permission import Permission

_VALID_PERMISSIONS = [p.value for p in Permission]


class SubUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    permissions: list[str] = Field(
        ...,
        description=f"Permissões do sub-usuário. Valores válidos: {_VALID_PERMISSIONS}",
    )
    # Opcional — só usado por superuser para especificar o tenant alvo
    tenant_id: str | None = None


class SubUserUpdatePermissions(BaseModel):
    permissions: list[str] = Field(
        ...,
        description=f"Nova lista de permissões. Valores válidos: {_VALID_PERMISSIONS}",
    )


class SubUserResponse(BaseModel):
    id: str
    email: str
    tenant_id: str | None
    role: str
    permissions: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}