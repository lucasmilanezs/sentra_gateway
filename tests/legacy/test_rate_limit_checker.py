import pytest
from unittest.mock import AsyncMock

from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.request import Request
from src.gateway.domain.services.rate_limit_checker import RateLimitChecker
from src.gateway.domain.value_objects.http_method import HttpMethod


class FakeRateLimitPort:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int]] = []

    async def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        self.calls.append((key, limit, window_seconds))
        return len([c for c in self.calls if c[0] == key]) <= limit


@pytest.mark.asyncio
async def test_rate_limit_key_includes_tenant_and_route():
    policy = Policy(id="p1", route_id="route-abc", rate_limit_per_minute=5)
    request = Request(
        method=HttpMethod.GET,
        path="/v1/test",
        headers={"x-forwarded-for": "203.0.113.1"},
        query_params={},
    )
    port = FakeRateLimitPort()
    checker = RateLimitChecker(port=port)

    for _ in range(5):
        result = await checker.check(
            policy, request, tenant_id="tenant-1", route_id="route-abc"
        )
        assert result.allowed

    result = await checker.check(
        policy, request, tenant_id="tenant-1", route_id="route-abc"
    )
    assert not result.allowed
    assert result.status_code == 429
    assert port.calls[0][0] == "rate:tenant-1:route-abc:203.0.113.1"
    assert port.calls[0][1] == 5
