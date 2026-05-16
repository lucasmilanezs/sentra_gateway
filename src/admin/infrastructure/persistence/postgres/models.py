from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.db import Base


class TenantORM(Base):
    __tablename__ = "admin_tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    routes: Mapped[list["AdminRouteORM"]] = relationship(back_populates="tenant")


class AdminRouteORM(Base):
    __tablename__ = "admin_routes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("admin_tenants.id"), nullable=False)
    path_pattern: Mapped[str] = mapped_column(String(512), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    backend_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped[TenantORM] = relationship(back_populates="routes")
    policy: Mapped["PolicyORM | None"] = relationship(
        back_populates="route", uselist=False, cascade="all, delete-orphan"
    )


class UserORM(Base):
    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("admin_tenants.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="admin")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

class PolicyORM(Base):
    __tablename__ = "admin_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    route_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_routes.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    requires_auth: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allowed_roles: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    route: Mapped[AdminRouteORM] = relationship(back_populates="policy")

# ADICIONAR ao final do arquivo
class GlobalPolicyORM(Base):
    __tablename__ = "admin_global_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_tenants.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    requires_auth: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allowed_roles: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped[TenantORM] = relationship()