import pytest
from src.admin.application.use_cases.query_audit import QueryAudit

class AuditRepo:
    def __init__(self): self.calls=[]
    async def list_recent(self, **kw): self.calls.append(("recent", kw)); return []
    async def list_filtered(self, **kw): self.calls.append(("filtered", kw)); return []
    async def metrics_summary(self, **kw): self.calls.append(("metrics", kw)); return {"ok": True}

@pytest.mark.asyncio
async def test_query_audit_caps_limits_and_delegates_filters():
    repo=AuditRepo(); uc=QueryAudit(repo)
    await uc.list_recent(tenant_id="t", limit=999)
    await uc.list_filtered(tenant_id="t", route_id="r", outcome="SUCCESS", limit=999, offset=10)
    assert repo.calls[0][1]["limit"] == 100
    assert repo.calls[1][1]["limit"] == 200
    assert repo.calls[1][1]["offset"] == 10

@pytest.mark.asyncio
async def test_metrics_summary_delegates_hours_and_tenant():
    repo=AuditRepo(); out=await QueryAudit(repo).metrics_summary(tenant_id="t", hours=168)
    assert out == {"ok": True}
    assert repo.calls[-1] == ("metrics", {"tenant_id":"t", "hours":168})
