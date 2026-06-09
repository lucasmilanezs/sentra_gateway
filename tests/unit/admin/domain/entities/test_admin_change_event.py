from src.admin.domain.services.audit_event_factory import GovernanceAuditEventFactory

def test_governance_event_factory_serializes_detail():
    ev = GovernanceAuditEventFactory.build(tenant_id="t", actor_id="u", actor_role="admin", action="CREATE", resource_type="route", resource_id="r", resource_summary="/x", detail={"k":"v"})
    assert ev.tenant_id == "t"
    assert ev.action == "CREATE"
    assert '"k": "v"' in ev.detail
