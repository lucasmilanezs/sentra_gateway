from src.admin.domain.value_objects.jwt_claims import JwtClaims

def test_admin_like_claims_have_all_permissions_and_scope_rules():
    admin = JwtClaims(sub="u", email="a@b.com", tenant_id="t", role="admin")
    assert admin.has_permission("anything")
    assert admin.resolve_tenant_scope("other") == "t"
    su = JwtClaims(sub="s", email="s@b.com", role="superuser")
    assert su.is_superuser() and su.resolve_tenant_scope("other") == "other"

def test_member_permission_check_is_granular():
    member = JwtClaims(sub="m", email="m@b.com", tenant_id="t", role="member", permissions=("routes",))
    assert member.has_permission("routes")
    assert not member.has_permission("audit")
