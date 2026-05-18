import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.gateway.domain.models.log_event import LogEvent
from src.gateway.domain.ports.log_port import LogPort


class PostgresAuditWriter(LogPort):
    """Persists gateway request events to admin_audit_requests for operator audit."""

    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def write(self, event: LogEvent) -> None:
        async with self._session_factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO admin_audit_requests (
                        id, tenant_id, route_id, method, path,
                        upstream_url, status_code, latency_ms, client_ip, created_at
                    ) VALUES (
                        :id, :tenant_id, :route_id, :method, :path,
                        :upstream_url, :status_code, :latency_ms, :client_ip, :created_at
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "tenant_id": event.tenant_id,
                    "route_id": event.route_id,
                    "method": event.method,
                    "path": event.path,
                    "upstream_url": event.upstream_url,
                    "status_code": event.status_code,
                    "latency_ms": event.latency_ms,
                    "client_ip": event.client_ip or "unknown",
                    "created_at": event.timestamp or datetime.now(timezone.utc),
                },
            )
            await session.commit()

    async def dispose(self) -> None:
        await self._engine.dispose()
