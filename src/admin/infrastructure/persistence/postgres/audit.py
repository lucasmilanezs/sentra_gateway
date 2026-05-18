from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.domain.entities.audit_request import AuditRequest
from src.admin.domain.ports.audit_repository import AuditRepositoryPort
from src.admin.infrastructure.persistence.postgres.models import AuditRequestORM


def _to_entity(row: AuditRequestORM) -> AuditRequest:
    return AuditRequest(
        id=row.id,
        tenant_id=row.tenant_id,
        route_id=row.route_id,
        method=row.method,
        path=row.path,
        upstream_url=row.upstream_url,
        status_code=row.status_code,
        latency_ms=row.latency_ms,
        client_ip=row.client_ip,
        created_at=row.created_at,
    )


class AuditRepository(AuditRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_recent(
        self,
        *,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditRequest]:
        q = select(AuditRequestORM).order_by(AuditRequestORM.created_at.desc()).limit(limit)
        if tenant_id:
            q = q.where(AuditRequestORM.tenant_id == tenant_id)
        result = await self._session.execute(q)
        return [_to_entity(r) for r in result.scalars().all()]

    async def metrics_summary(
        self,
        *,
        tenant_id: str | None = None,
        hours: int = 24,
    ) -> dict:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        tenant_filter = "AND tenant_id = :tenant_id" if tenant_id else ""
        params: dict = {"since": since}
        if tenant_id:
            params["tenant_id"] = tenant_id

        row = (
            await self._session.execute(
                text(
                    f"""
                    SELECT
                        COUNT(*) AS total,
                        AVG(latency_ms) AS avg_latency,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency,
                        SUM(CASE WHEN status_code BETWEEN 200 AND 299 THEN 1 ELSE 0 END) AS s2xx,
                        SUM(CASE WHEN status_code BETWEEN 400 AND 499 THEN 1 ELSE 0 END) AS s4xx,
                        SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) AS s5xx
                    FROM admin_audit_requests
                    WHERE created_at >= :since {tenant_filter}
                    """
                ),
                params,
            )
        ).one()

        top_routes = (
            await self._session.execute(
                text(
                    f"""
                    SELECT route_id, COUNT(*) AS cnt
                    FROM admin_audit_requests
                    WHERE created_at >= :since {tenant_filter}
                      AND route_id IS NOT NULL
                    GROUP BY route_id
                    ORDER BY cnt DESC
                    LIMIT 5
                    """
                ),
                params,
            )
        ).all()

        return {
            "total_requests": int(row.total or 0),
            "avg_latency_ms": round(float(row.avg_latency or 0), 2),
            "p95_latency_ms": round(float(row.p95_latency or 0), 2),
            "status_2xx": int(row.s2xx or 0),
            "status_4xx": int(row.s4xx or 0),
            "status_5xx": int(row.s5xx or 0),
            "top_routes": [{"route_id": r.route_id, "count": int(r.cnt)} for r in top_routes],
            "window_hours": hours,
        }
