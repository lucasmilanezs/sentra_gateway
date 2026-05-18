from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.db import Base


class TenantORM(Base):
    __tablename__ = "admin_tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    alias: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    routes: Mapped[list["AdminRouteORM"]] = relationship(back_populates="tenant")
    domains: Mapped[list["TenantDomainORM"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class TenantDomainORM(Base):
    __tablename__ = "admin_tenant_domains"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped[TenantORM] = relationship(back_populates="domains")
    policy: Mapped["DomainPolicyORM | None"] = relationship(
        back_populates="domain_obj", uselist=False, cascade="all, delete-orphan"
    )


class AuditRequestORM(Base):
    __tablename__ = "admin_audit_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("admin_tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    route_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    upstream_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    client_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class DomainPolicyORM(Base):
    __tablename__ = "admin_domain_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    domain_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("admin_tenant_domains.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    requires_auth: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allowed_roles: Mapped[str] = mapped_column(Text, nullable=False, default="")
    jwt_validate_exp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    jwt_issuer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    jwt_audience: Mapped[str | None] = mapped_column(String(255), nullable=True)
    jwt_clock_skew_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    domain_obj: Mapped[TenantDomainORM] = relationship(back_populates="policy")


class AdminRouteORM(Base):
    __tablename__ = "admin_routes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_tenants.id"), nullable=False
    )
    path_pattern: Mapped[str] = mapped_column(String(512), nullable=False)
    # Comma-separated list: "GET,POST" — replaces single "method" column
    methods: Mapped[str] = mapped_column(Text, nullable=False)
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
    jwt_validate_exp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    jwt_issuer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    jwt_audience: Mapped[str | None] = mapped_column(String(255), nullable=True)
    jwt_clock_skew_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    route: Mapped[AdminRouteORM] = relationship(back_populates="policy")
