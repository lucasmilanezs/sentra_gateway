"""
Testes unitários — ForwardRequest (caminho crítico do gateway)

Cobre:
  - Happy path: rota → domínio → policy → proxy → log → response
  - RouteNotFoundError  (path sem rota registrada)
  - DomainNotFoundError (rota aponta para domínio inexistente)
  - PolicyDeniedError   (policy bloqueia a requisição)
  - Falha do upstream   (proxy lança exceção)
  - Falha do log        (não afeta a resposta — best-effort)

O proxy é sempre mockado — nenhum teste abre conexão de rede.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.gateway.application.dtos.gateway_response import GatewayResponse
from src.gateway.application.use_cases.forward_request import (
    ForwardRequest,
    RouteNotFoundError,
    DomainNotFoundError,
    PolicyDeniedError,
)
from src.gateway.domain.models.domain import Domain
from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.policy_result import PolicyResult
from src.gateway.domain.models.request import Request
from src.gateway.domain.models.route import Route
from src.gateway.domain.ports.upstream_proxy_port import UpstreamResponse
from src.gateway.domain.services.log_event_builder import LogEventBuilder
from src.gateway.domain.services.policy_evaluator import PolicyEvaluator
from src.gateway.domain.value_objects.backend_url import BackendUrl
from src.gateway.domain.value_objects.http_method import HttpMethod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_request(path: str = "/httpbin/get", method: str = "GET") -> Request:
    return Request(
        method=HttpMethod(method),
        path=path,
        headers={"host": "localhost"},
        query_params={},
    )


def _make_route(path_prefix: str = "/httpbin", domain_id: str = "domain-httpbin") -> Route:
    return Route(
        id="route-1",
        path_prefix=path_prefix,
        domain_id=domain_id,
        methods=(HttpMethod.GET, HttpMethod.POST),
    )


def _make_domain(backend: str = "https://httpbin.org") -> Domain:
    return Domain(
        id="domain-httpbin",
        name="httpbin",
        backend_url=BackendUrl(backend),
    )


def _make_upstream_response(status: int = 200, body: bytes = b'{"ok": true}') -> UpstreamResponse:
    return UpstreamResponse(
        status_code=status,
        headers={"content-type": "application/json"},
        body=body,
    )


def _make_use_case(
    route=None,
    domain=None,
    policy=None,
    proxy_response=None,
    proxy_raises=None,
    log_raises=None,
    policy_result: PolicyResult = None,
):
    """
    Monta um ForwardRequest com todos os colaboradores mockados.
    Aceita None em qualquer posição para simular ausência (not found).
    """
    route_repo = AsyncMock()
    route_repo.get_by_path.return_value = route

    domain_repo = AsyncMock()
    domain_repo.get_by_id.return_value = domain

    policy_repo = AsyncMock()
    policy_repo.get_by_route_id.return_value = policy

    proxy = AsyncMock()
    if proxy_raises:
        proxy.forward.side_effect = proxy_raises
    else:
        proxy.forward.return_value = proxy_response or _make_upstream_response()

    log_port = AsyncMock()
    if log_raises:
        log_port.write.side_effect = log_raises

    evaluator = MagicMock(spec=PolicyEvaluator)
    if policy_result is not None:
        evaluator.evaluate.return_value = policy_result
    else:
        evaluator.evaluate.return_value = PolicyResult(allowed=True)

    return ForwardRequest(
        route_repository=route_repo,
        domain_repository=domain_repo,
        policy_repository=policy_repo,
        proxy=proxy,
        log_port=log_port,
        policy_evaluator=evaluator,
        log_event_builder=LogEventBuilder(),
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_happy_path_returns_upstream_response():
    """
    Caminho completo sem erros:
    rota encontrada → domínio encontrado → policy permite → proxy responde → log gravado.
    O GatewayResponse deve refletir exatamente o que o upstream devolveu.
    """
    route = _make_route()
    domain = _make_domain()
    upstream = _make_upstream_response(status=200, body=b'{"slideshow": {}}')

    use_case = _make_use_case(route=route, domain=domain, proxy_response=upstream)

    response = await use_case.handle(_make_request(), raw_body=b"")

    assert isinstance(response, GatewayResponse)
    assert response.status_code == 200
    assert response.body == b'{"slideshow": {}}'


@pytest.mark.asyncio
async def test_happy_path_strips_prefix_before_forwarding():
    """
    O upstream recebe o path SEM o prefixo da rota.
    /httpbin/get com prefixo /httpbin → upstream recebe /get.
    """
    route = _make_route(path_prefix="/httpbin")
    domain = _make_domain(backend="https://httpbin.org")

    proxy = AsyncMock()
    proxy.forward.return_value = _make_upstream_response()

    use_case = ForwardRequest(
        route_repository=AsyncMock(get_by_path=AsyncMock(return_value=route)),
        domain_repository=AsyncMock(get_by_id=AsyncMock(return_value=domain)),
        policy_repository=AsyncMock(get_by_route_id=AsyncMock(return_value=None)),
        proxy=proxy,
        log_port=AsyncMock(),
        policy_evaluator=PolicyEvaluator(),
        log_event_builder=LogEventBuilder(),
    )

    await use_case.handle(_make_request(path="/httpbin/get"), raw_body=b"")

    call_kwargs = proxy.forward.call_args.kwargs
    assert call_kwargs["url"] == "https://httpbin.org/get"


@pytest.mark.asyncio
async def test_happy_path_log_is_called():
    """O log deve ser chamado exatamente uma vez em um request bem-sucedido."""
    route = _make_route()
    domain = _make_domain()

    log_port = AsyncMock()

    use_case = ForwardRequest(
        route_repository=AsyncMock(get_by_path=AsyncMock(return_value=route)),
        domain_repository=AsyncMock(get_by_id=AsyncMock(return_value=domain)),
        policy_repository=AsyncMock(get_by_route_id=AsyncMock(return_value=None)),
        proxy=AsyncMock(forward=AsyncMock(return_value=_make_upstream_response())),
        log_port=log_port,
        policy_evaluator=PolicyEvaluator(),
        log_event_builder=LogEventBuilder(),
    )

    await use_case.handle(_make_request(), raw_body=b"")

    log_port.write.assert_awaited_once()


# ---------------------------------------------------------------------------
# Erros de rota e domínio
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_not_found_raises():
    """Nenhuma rota bate com o path → RouteNotFoundError."""
    use_case = _make_use_case(route=None)

    with pytest.raises(RouteNotFoundError):
        await use_case.handle(_make_request(path="/nao/existe"), raw_body=b"")


@pytest.mark.asyncio
async def test_domain_not_found_raises():
    """Rota existe mas referencia um domínio não registrado → DomainNotFoundError."""
    route = _make_route(domain_id="dominio-fantasma")
    use_case = _make_use_case(route=route, domain=None)

    with pytest.raises(DomainNotFoundError):
        await use_case.handle(_make_request(), raw_body=b"")


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_policy_denied_raises():
    """PolicyEvaluator nega a requisição → PolicyDeniedError com o motivo correto."""
    route = _make_route()
    domain = _make_domain()
    denied = PolicyResult(allowed=False, status_code=403, reason="Token ausente.")

    use_case = _make_use_case(route=route, domain=domain, policy_result=denied)

    with pytest.raises(PolicyDeniedError) as exc_info:
        await use_case.handle(_make_request(), raw_body=b"")

    assert exc_info.value.status_code == 403
    assert "Token ausente" in exc_info.value.reason


@pytest.mark.asyncio
async def test_no_policy_allows_request():
    """Sem policy associada à rota, o request deve passar sem restrições."""
    route = _make_route()
    domain = _make_domain()

    use_case = _make_use_case(route=route, domain=domain, policy=None)
    response = await use_case.handle(_make_request(), raw_body=b"")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_policy_requires_auth_missing_bearer_denies():
    """
    Policy com requires_auth=True e request sem Authorization →
    PolicyDeniedError com status 401.
    """
    route = _make_route()
    domain = _make_domain()
    policy = Policy(id="p1", route_id="route-1", requires_auth=True)

    use_case = ForwardRequest(
        route_repository=AsyncMock(get_by_path=AsyncMock(return_value=route)),
        domain_repository=AsyncMock(get_by_id=AsyncMock(return_value=domain)),
        policy_repository=AsyncMock(get_by_route_id=AsyncMock(return_value=policy)),
        proxy=AsyncMock(),
        log_port=AsyncMock(),
        policy_evaluator=PolicyEvaluator(),
        log_event_builder=LogEventBuilder(),
    )

    with pytest.raises(PolicyDeniedError) as exc_info:
        await use_case.handle(_make_request(), raw_body=b"")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_policy_requires_auth_with_bearer_allows():
    """Request com Bearer token válido (presença) deve passar pela policy de auth."""
    route = _make_route()
    domain = _make_domain()
    policy = Policy(id="p1", route_id="route-1", requires_auth=True)

    request = Request(
        method=HttpMethod.GET,
        path="/httpbin/get",
        headers={"authorization": "Bearer eyJtoken"},
        query_params={},
    )

    use_case = ForwardRequest(
        route_repository=AsyncMock(get_by_path=AsyncMock(return_value=route)),
        domain_repository=AsyncMock(get_by_id=AsyncMock(return_value=domain)),
        policy_repository=AsyncMock(get_by_route_id=AsyncMock(return_value=policy)),
        proxy=AsyncMock(forward=AsyncMock(return_value=_make_upstream_response())),
        log_port=AsyncMock(),
        policy_evaluator=PolicyEvaluator(),
        log_event_builder=LogEventBuilder(),
    )

    response = await use_case.handle(request, raw_body=b"")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Falha do upstream
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proxy_failure_propagates():
    """
    Falha de rede no proxy (ex: upstream inacessível) deve propagar a exceção.
    O gateway_router traduz isso para 502 — aqui só verificamos que a exceção sobe.
    """
    route = _make_route()
    domain = _make_domain()

    use_case = _make_use_case(
        route=route,
        domain=domain,
        proxy_raises=Exception("Connection refused"),
    )

    with pytest.raises(Exception, match="Connection refused"):
        await use_case.handle(_make_request(), raw_body=b"")


# ---------------------------------------------------------------------------
# Falha do log (best-effort)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_failure_does_not_affect_response():
    """
    Falha no log NÃO deve impedir a resposta ao cliente.
    O use case absorve silenciosamente qualquer exceção do log_port.
    """
    route = _make_route()
    domain = _make_domain()

    use_case = _make_use_case(
        route=route,
        domain=domain,
        log_raises=IOError("Disco cheio"),
    )

    response = await use_case.handle(_make_request(), raw_body=b"")

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Propagação do body
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_raw_body_forwarded_unchanged():
    """O body recebido da interface deve chegar ao proxy sem modificação."""
    route = _make_route()
    domain = _make_domain()
    original_body = b'{"user": "lucas", "action": "test"}'

    proxy = AsyncMock()
    proxy.forward.return_value = _make_upstream_response()

    use_case = ForwardRequest(
        route_repository=AsyncMock(get_by_path=AsyncMock(return_value=route)),
        domain_repository=AsyncMock(get_by_id=AsyncMock(return_value=domain)),
        policy_repository=AsyncMock(get_by_route_id=AsyncMock(return_value=None)),
        proxy=proxy,
        log_port=AsyncMock(),
        policy_evaluator=PolicyEvaluator(),
        log_event_builder=LogEventBuilder(),
    )

    await use_case.handle(_make_request(), raw_body=original_body)

    call_kwargs = proxy.forward.call_args.kwargs
    assert call_kwargs["body"] == original_body
