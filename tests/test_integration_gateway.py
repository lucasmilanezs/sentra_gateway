"""
Testes de integração — Gateway contra httpbin.org

Requer:
  pip install asgi-lifespan

Cada teste sobe e derruba o app completo (scope="function") para evitar
conflitos de event loop entre o LifespanManager e o pytest-asyncio no Windows.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager

from src.gateway.main import app


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Client fixture — scope="function" para evitar RuntimeError: Event loop is closed
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def client():
    """
    scope="function" (padrão) garante que cada teste tenha seu próprio
    LifespanManager e event loop — necessário no Windows com ProactorEventLoop.

    scope="module" causava RuntimeError: Event loop is closed no teardown
    porque o loop era encerrado antes do shutdown do LifespanManager terminar.
    """
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://testserver",
        ) as c:
            yield c


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_proxied_to_httpbin(client: AsyncClient):
    """GET /httpbin/get deve ser encaminhado para httpbin.org/get e retornar 200."""
    response = await client.get("/httpbin/get")

    assert response.status_code == 200
    body = response.json()
    assert "url" in body
    assert "httpbin.org/get" in body["url"]


@pytest.mark.asyncio
async def test_post_proxied_to_httpbin(client: AsyncClient):
    """POST com body JSON deve ser refletido de volta no campo 'json' do httpbin."""
    payload = {"sentra": "gateway", "test": True}
    response = await client.post("/httpbin/post", json=payload)

    assert response.status_code == 200
    assert response.json()["json"] == payload


@pytest.mark.asyncio
async def test_query_params_forwarded(client: AsyncClient):
    """Query params devem aparecer no campo 'args' da resposta do httpbin."""
    response = await client.get("/httpbin/get", params={"foo": "bar", "n": "42"})

    assert response.status_code == 200
    args = response.json()["args"]
    assert args.get("foo") == "bar"
    assert args.get("n") == "42"


@pytest.mark.asyncio
async def test_custom_header_forwarded(client: AsyncClient):
    """Headers customizados devem ser repassados e refletidos pelo httpbin."""
    response = await client.get(
        "/httpbin/get",
        headers={"x-sentra-test": "integration"},
    )

    assert response.status_code == 200
    assert response.json()["headers"].get("X-Sentra-Test") == "integration"


# ---------------------------------------------------------------------------
# Erros de rota
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_path_returns_404(client: AsyncClient):
    """Path sem rota registrada deve retornar 404 com code ROUTE_NOT_FOUND."""
    response = await client.get("/nao/existe/essa/rota")

    assert response.status_code == 404
    assert response.json()["code"] == "ROUTE_NOT_FOUND"


@pytest.mark.asyncio
async def test_wrong_method_returns_404(client: AsyncClient):
    """Método não permitido pela rota deve retornar 404."""
    response = await client.delete("/httpbin/delete")

    assert response.status_code == 404
    assert response.json()["code"] == "ROUTE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Status codes do upstream preservados
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upstream_status_code_preserved(client: AsyncClient):
    """O gateway deve repassar o status code do upstream sem alteração."""
    response = await client.get("/httpbin/status/201")

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_upstream_404_preserved(client: AsyncClient):
    """404 do upstream chega como 404 — sem o body de erro do gateway."""
    response = await client.get("/httpbin/status/404")

    assert response.status_code == 404
    assert "ROUTE_NOT_FOUND" not in response.text


# ---------------------------------------------------------------------------
# Prefix stripping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prefix_stripped_in_upstream_url(client: AsyncClient):
    """A URL refletida pelo httpbin não deve conter o prefixo /httpbin."""
    response = await client.get("/httpbin/get")

    assert response.status_code == 200
    url = response.json()["url"]
    assert "/httpbin/" not in url
    assert url.endswith("/get")