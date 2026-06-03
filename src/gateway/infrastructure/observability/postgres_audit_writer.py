from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.gateway.domain.models.audit_event import AuditEvent
from src.gateway.domain.ports.audit_port import AuditPort
from src.shared.runtime.dependency_status import DependencyStatusRegistry


class PostgresAuditWriter(AuditPort):
    def __init__(
        self,
        database_url: str,
        *,
        status_registry: DependencyStatusRegistry | None = None,
        status_name: str = "postgres_audit",
    ) -> None:
        self._engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self._status_registry = status_registry
        self._status_name = status_name

    async def write(self, event: AuditEvent) -> None:
        try:
            async with self._session_factory() as session:
                await session.execute(text("""
                    INSERT INTO admin_audit_requests (id, tenant_id, route_id, method, path, upstream_url, status_code, latency_ms, client_ip, outcome, denial_reason, denial_check, created_at)
                    VALUES (:id, :tenant_id, :route_id, :method, :path, :upstream_url, :status_code, :latency_ms, :client_ip, :outcome, :denial_reason, :denial_check, :created_at)
                """), {
                    "id": event.id,
                    "tenant_id": event.tenant_id,
                    "route_id": event.route_id,
                    "method": event.method,
                    "path": event.path,
                    "upstream_url": event.upstream_url or "",
                    "status_code": event.upstream_status_code or 0,
                    "latency_ms": event.latency_ms or 0.0,
                    "client_ip": event.client_ip or "unknown",
                    "outcome": event.outcome,
                    "denial_reason": event.denial_reason,
                    "denial_check": event.denial_check,
                    "created_at": event.timestamp or datetime.now(timezone.utc),
                })
                await session.commit()
            if self._status_registry:
                self._status_registry.mark_ok(
                    self._status_name,
                    "Auditoria persistente saudável: último evento semântico gravado no PostgreSQL com sucesso.",
                    reason_code="audit_write_ok",
                    phase="operational",
                    last_event_outcome=event.outcome,
                    last_event_status_code=event.upstream_status_code,
                )
        except Exception as exc:
            if self._status_registry:
                self._status_registry.mark_error(
                    self._status_name,
                    exc,
                    detail=(
                        "Falha ao gravar evento de auditoria persistente no PostgreSQL. "
                        "O encaminhamento da requisição não foi interrompido, mas a evidência de auditoria pode estar incompleta."
                    ),
                    reason_code="audit_write_failed",
                    phase="postgres_write_failed",
                )
            raise

    async def dispose(self) -> None:
        await self._engine.dispose()
