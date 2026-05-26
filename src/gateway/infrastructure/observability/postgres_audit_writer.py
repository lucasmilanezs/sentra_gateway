from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.gateway.domain.models.audit_event import AuditEvent
from src.gateway.domain.ports.audit_port import AuditPort

class PostgresAuditWriter(AuditPort):
    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(bind=self._engine, class_=AsyncSession, expire_on_commit=False)

    async def write(self, event: AuditEvent) -> None:
        async with self._session_factory() as session:
            await session.execute(text("""
                INSERT INTO admin_audit_requests (id, tenant_id, route_id, method, path, upstream_url, status_code, latency_ms, client_ip, outcome, denial_reason, denial_check, created_at)
                VALUES (:id, :tenant_id, :route_id, :method, :path, :upstream_url, :status_code, :latency_ms, :client_ip, :outcome, :denial_reason, :denial_check, :created_at)
            """), {
                "id": event.id, "tenant_id": event.tenant_id, "route_id": event.route_id,
                "method": event.method, "path": event.path, "upstream_url": event.upstream_url or "",
                "status_code": event.upstream_status_code or 0, "latency_ms": event.latency_ms or 0.0,
                "client_ip": event.client_ip or "unknown", "outcome": event.outcome,
                "denial_reason": event.denial_reason, "denial_check": event.denial_check,
                "created_at": event.timestamp or datetime.now(timezone.utc),
            })
            await session.commit()

    async def dispose(self) -> None:
        await self._engine.dispose()
