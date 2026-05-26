from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.admin.domain.entities.audit_request import AuditRequest
from src.admin.domain.ports.audit_repository import AuditRepositoryPort
from src.admin.infrastructure.persistence.postgres.models import AuditRequestORM

def _to_entity(row):
    return AuditRequest(
        id=row.id, tenant_id=row.tenant_id, route_id=row.route_id,
        method=row.method, path=row.path, upstream_url=row.upstream_url,
        status_code=row.status_code, latency_ms=row.latency_ms,
        client_ip=row.client_ip, created_at=row.created_at,
        outcome=row.outcome, denial_reason=row.denial_reason, denial_check=row.denial_check,
    )

class AuditRepository(AuditRepositoryPort):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_recent(self, *, tenant_id=None, limit=100):
        q = select(AuditRequestORM).order_by(AuditRequestORM.created_at.desc()).limit(limit)
        if tenant_id:
            q = q.where(AuditRequestORM.tenant_id == tenant_id)
        result = await self._session.execute(q)
        return [_to_entity(r) for r in result.scalars().all()]

    async def list_filtered(self, *, tenant_id=None, route_id=None, outcome=None, method=None, date_from=None, date_to=None, limit=100, offset=0):
        q = select(AuditRequestORM)
        cq = select(func.count(AuditRequestORM.id))
        for fq in (q, cq):
            pass
        filters = []
        if tenant_id: filters.append(AuditRequestORM.tenant_id == tenant_id)
        if route_id: filters.append(AuditRequestORM.route_id == route_id)
        if outcome: filters.append(AuditRequestORM.outcome == outcome)
        if method: filters.append(AuditRequestORM.method == method.upper())
        if date_from: filters.append(AuditRequestORM.created_at >= date_from)
        if date_to: filters.append(AuditRequestORM.created_at <= date_to)
        for f in filters:
            q = q.where(f)
            cq = cq.where(f)
        total = (await self._session.execute(cq)).scalar() or 0
        q = q.order_by(AuditRequestORM.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(q)
        return [_to_entity(r) for r in result.scalars().all()], total

    async def metrics_summary(self, *, tenant_id=None, hours=24):
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        tf = "AND tenant_id = :tenant_id" if tenant_id else ""
        params = {"since": since}
        if tenant_id: params["tenant_id"] = tenant_id
        row = (await self._session.execute(text(f"""
            SELECT COUNT(*) AS total, AVG(latency_ms) AS avg_latency,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency,
                SUM(CASE WHEN outcome='SUCCESS' THEN 1 ELSE 0 END) AS success_count,
                SUM(CASE WHEN outcome='POLICY_DENIED' THEN 1 ELSE 0 END) AS denied_count,
                SUM(CASE WHEN outcome LIKE 'UPSTREAM%%' THEN 1 ELSE 0 END) AS upstream_errors,
                SUM(CASE WHEN outcome IN ('TENANT_NOT_FOUND','ROUTE_NOT_FOUND','DOMAIN_NOT_FOUND') THEN 1 ELSE 0 END) AS resolution_errors,
                SUM(CASE WHEN status_code BETWEEN 200 AND 299 THEN 1 ELSE 0 END) AS s2xx,
                SUM(CASE WHEN status_code BETWEEN 400 AND 499 THEN 1 ELSE 0 END) AS s4xx,
                SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) AS s5xx
            FROM admin_audit_requests WHERE created_at >= :since {tf}"""), params)).one()
        top_routes = (await self._session.execute(text(f"""
            SELECT route_id, COUNT(*) AS cnt FROM admin_audit_requests
            WHERE created_at >= :since {tf} AND route_id IS NOT NULL
            GROUP BY route_id ORDER BY cnt DESC LIMIT 5"""), params)).all()
        return {
            "total_requests": int(row.total or 0), "avg_latency_ms": round(float(row.avg_latency or 0), 2),
            "p95_latency_ms": round(float(row.p95_latency or 0), 2),
            "success_count": int(row.success_count or 0), "denied_count": int(row.denied_count or 0),
            "upstream_errors": int(row.upstream_errors or 0), "resolution_errors": int(row.resolution_errors or 0),
            "status_2xx": int(row.s2xx or 0), "status_4xx": int(row.s4xx or 0), "status_5xx": int(row.s5xx or 0),
            "top_routes": [{"route_id": r.route_id, "count": int(r.cnt)} for r in top_routes],
            "window_hours": hours,
        }
