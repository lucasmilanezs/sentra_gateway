from pydantic import BaseModel, EmailStr, Field


class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    company_name: str = Field(min_length=1, max_length=255)
    company_alias: str = Field(min_length=1, max_length=128)
    accepted_terms: bool = False


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TenantPublic(BaseModel):
    id: str
    name: str
    alias: str


class UserPublic(BaseModel):
    id: str
    email: str
    tenant_id: str | None
    role: str | None = None
    permissions: list[str] = []
    tenant: TenantPublic | None = None


class RegisterResponse(BaseModel):
    user: UserPublic
    tenant: TenantPublic
    access_token: str
    token_type: str = "bearer"


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordBody(BaseModel):
    email: EmailStr


class ResetPasswordBody(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=32)
    new_password: str = Field(min_length=8, max_length=128)